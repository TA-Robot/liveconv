# MS-2 SSH preflight

`scripts/ms2-ssh-preflight.sh` checks the minimum MS-2 personal SSH transport
boundary in ADR-0003 before a tunnel is started. It checks only configuration
and metadata; it does not connect to the remote host, read a private key, send a
bearer credential, or create a Gateway session. A pass is not the actual Chrome
route evidence required for MS-2 closure.

The preflight combines three sources:

- `ssh -F <isolated-config> -G <host-alias>` for the actual client intent;
- a redacted server-policy JSON record derived from the forwarding account's
  `authorized_keys` options and `sshd -T -C` output; and
- a redacted Gateway JSON record from the operator's deployed settings.

The client supplies three expected values independently of the evidence records:
the dedicated `IdentityFile`, dedicated `UserKnownHostsFile`, and exact Chrome
Extension Origin. The script canonicalizes each path and fails unless the
effective SSH configuration resolves to those exact files. It only reads file
metadata for the identity; it never reads or derives private-key contents.

The checker writes one JSON record to standard output. It contains only pass
metadata and ports. It does not echo paths, host names, public-key material,
the extension Origin, bearer values, tickets, or either input record.

## Prepare non-secret evidence

On the remote host, collect the effective SSH daemon settings for the account.
Do not put an SSH public-key blob, private key, token, ticket, environment file,
or any other credential in the evidence file.

```bash
sudo sshd -T -C user=liveconv-tunnel,host=SERVER_HOST,addr=CLIENT_IP \
  | grep -E '^(authenticationmethods|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|disableforwarding|allowtcpforwarding|allowstreamlocalforwarding|permitopen|permittty|permittunnel|maxsessions|x11forwarding|allowagentforwarding|permituserrc) '
```

Create `server-evidence.json` with the values from that command and with the
three restrictions on the dedicated `authorized_keys` line represented as
booleans. `permitopen` must agree in both locations. The format is deliberately
closed: extra fields are rejected so the file remains non-secret evidence.

```json
{
  "schema_version": 1,
  "kind": "liveconv-ms2-ssh-server-evidence",
  "account": "liveconv-tunnel",
  "authorized_key": {
    "restrict": true,
    "port_forwarding": true,
    "permitopen": "127.0.0.1:8765"
  },
  "sshd": {
    "authenticationmethods": "publickey",
    "pubkeyauthentication": "yes",
    "passwordauthentication": "no",
    "kbdinteractiveauthentication": "no",
    "disableforwarding": "no",
    "allowtcpforwarding": "local",
    "allowstreamlocalforwarding": "no",
    "permitopen": "127.0.0.1:8765",
    "permittty": "no",
    "permittunnel": "no",
    "maxsessions": "0",
    "x11forwarding": "no",
    "allowagentforwarding": "no",
    "permituserrc": "no"
  }
}
```

Create `gateway-evidence.json` from the deployed Gateway configuration and
implementation state. `bearer_auth_required` states that the bearer is required;
it is not the bearer itself. The exact Origin is supplied again as an independent
command-line value and is never repeated in the preflight report. Both values
must be the same exact no-newline Chrome Extension Origin.
`ticket.ttl_seconds` must be positive and no greater than 30 seconds.

```json
{
  "schema_version": 1,
  "kind": "liveconv-ms2-gateway-evidence",
  "bind_host": "127.0.0.1",
  "bind_port": 8765,
  "bearer_auth_required": true,
  "allowed_origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
  "ticket": { "one_use": true, "ttl_seconds": 30 },
  "max_sessions": 1
}
```

## Run

The isolated configuration must be a canonical regular file owned by the user
running the command and not writable by group or others. Its dedicated identity
must be a canonical regular file owned by that user with no group or other
permissions. The dedicated known-hosts file must also be canonical, regular,
owned by that user, and not writable by group or others. Use ordinary paths with
no embedded whitespace or line breaks for `IdentityFile` and
`UserKnownHostsFile`.

The isolated configuration must not use `Include` or any `Match` directive; the
script rejects both before it invokes `ssh -G`. Use LF line endings: carriage
returns and control bytes other than tab/LF are also rejected before `ssh -G`.
The configuration must set the dedicated user and one dedicated non-`none`
identity, one dedicated `UserKnownHostsFile`,
`GlobalKnownHostsFile none`, `KnownHostsCommand none`, `StrictHostKeyChecking
yes`, `VerifyHostKeyDNS no`, `NoHostAuthenticationForLocalhost no`,
`ControlMaster no`, no `ControlPath` (or `ControlPath none`), `ControlPersist
no`, `UpdateHostKeys no`, `BatchMode yes`, and `ExitOnForwardFailure yes`. Do
not set `HostKeyAlias`: the host pin must apply to the effective host and SSH
port.

The checker requires exactly one `LocalForward` from client `127.0.0.1` to
remote `127.0.0.1`; dynamic and remote forwards are rejected. The remote target
port must equal both `PermitOpen` values and the Gateway bind port. The dedicated
known-hosts file must contain a syntactically valid non-revoked key for the
effective host and SSH port. A revoked-only match is not a pin, and a candidate
key duplicated in a matching `@revoked` record is rejected.

```bash
bash scripts/ms2-ssh-preflight.sh \
  --ssh-bin /usr/bin/ssh \
  --ssh-config "$HOME/.config/liveconv/ssh/config" \
  --host-alias liveconv-audio \
  --expected-identity-file "$HOME/.ssh/liveconv_client" \
  --expected-known-hosts "$HOME/.config/liveconv/ssh/known_hosts" \
  --expected-extension-origin 'chrome-extension://EXTENSION_ID' \
  --server-evidence /secure/operator-records/server-evidence.json \
  --gateway-evidence /secure/operator-records/gateway-evidence.json
```

Use the existing guarded client launcher only after this command passes. A
failure means correct the isolated client configuration or the deployed policy;
do not override it with SSH command-line options. The preflight invokes the SSH
binary with the canonical configuration as `-F <config> -G -- <host-alias>`.
Successful JSON contains only pass metadata and loopback ports, never paths,
host names, public-key material, Origin values, bearer values, tickets, or input
records.
