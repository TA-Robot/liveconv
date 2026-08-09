# Client setup over an SSH tunnel

Status: Accepted Linux personal-client path; macOS and Windows preview

This procedure satisfies the loopback development case of
[NFR-011](../product/requirements.md) and the trust boundary in
[ADR-0002](../architecture/adr/0002-remote-model-router.md). It lets one trusted
Chrome client use a Gateway on a remote Linux host without publishing the
Gateway port. It does not change the authenticated session and generation
contract in [remote protocol version 1](../architecture/remote-protocol.md).
The initial supported personal client is Linux. The macOS and Windows sections
are best-effort previews for MS-5 and do not satisfy the MS-4 client gate.

```text
Chrome Extension
  http://127.0.0.1:8765
  ws://127.0.0.1:8765/v1/ws
          |
          | client loopback
          v
OpenSSH local forward (-L)
          |
          | encrypted SSH connection
          v
remote 127.0.0.1:8765
          |
          v
liveconv Gateway -> isolated model worker
```

The Gateway bearer token, one-use WebSocket ticket, and exact Extension
`Origin` check remain mandatory. SSH supplies transport encryption and server
host authentication for the non-loopback hop; it does not replace Gateway
authentication.

## Scope

This is the personal-v1 SSH-only route. Public HTTPS/WSS, Caddy, DNS, ACME,
Internet ingress, and public clients are post-v1 and intentionally not covered
here. Do not expose the Gateway directly, publish port 8765, or change its bind
address to `0.0.0.0` for this workflow.

## Exact browser URL behavior

Configure only the Gateway origin in the popup. The Extension validates it and
derives the WebSocket URL from the server's same-origin `websocket_path`.

| Route | Popup Gateway origin | Derived WebSocket URL | Network protection |
|---|---|---|---|
| Default SSH tunnel | `http://127.0.0.1:8765` | `ws://127.0.0.1:8765/v1/ws` | Loopback plus encrypted SSH hop |
| Alternate local port | `http://127.0.0.1:18765` | `ws://127.0.0.1:18765/v1/ws` | Loopback plus encrypted SSH hop |

For the tunnel, local `ws://` is intentional. Adding local TLS would produce
`wss://`, but this procedure does not configure a client-loopback certificate.
The WebSocket ticket is still sent only in the first attachment message, never
in a URL. The ticket is single-use, normally expires after 30 seconds, and the
first attachment message normally has a 5-second timeout.

Use the literal IPv4 address `127.0.0.1`. `localhost` is accepted by the
Extension, but it can resolve to IPv6 `::1` while the forward below listens only
on IPv4. Do not enter a path, query, fragment, credentials, the remote hostname,
or `/v1/ws` in the popup Gateway field.

The popup requests the optional Chrome host permission
`http://127.0.0.1/*`. Chrome host permissions do not distinguish ports, but this
grant does not cover LAN addresses or the remote server. This browser permission
is different from the Gateway allowlist: `LIVECONV_ALLOWED_ORIGINS` contains the
caller's exact `chrome-extension://EXTENSION_ID` origin, not the loopback URL.

## Prerequisites

Remote server:

- a supported Linux host with OpenSSH server and administrator access through a
  console or a separate tested SSH account
- the repository and locked Python environment installed for the Gateway
  operator
- the Gateway able to listen on `127.0.0.1:8765`
- OpenSSL for the token-generation command below
- inbound SSH access on the chosen SSH port; port 8765 stays closed externally
- one forwarding-only SSH public key per client

Supported Linux client:

- Chrome 116 or newer and a checkout containing `apps/extension/`
- OpenSSH client tools: `ssh`, `ssh-keygen`, and `ssh-keyscan`
- Bash 4 or newer plus `awk` and `realpath` for the guarded launcher
- `curl`
- the Gateway token delivered through an approved private channel
- optional supervision through a systemd user service

The macOS and Windows commands remain preview material for MS-5 portability
work. They require platform validation before they can be used as milestone
evidence.

Node.js is required for the Extension test suite, but not to load the unpacked
Extension. Replace every uppercase placeholder in this guide. Never paste a
private key, bearer token, or one-use WebSocket ticket into a command line, SSH
configuration, chat, issue, or log.

## Create one client SSH key

Use a distinct key for every client so one machine can be revoked without
affecting another. On Linux or macOS, run:

```bash
install -d -m 0700 ~/.ssh
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/liveconv_client \
  -C liveconv-forward-only
```

On Windows PowerShell, run:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen.exe -t ed25519 -a 100 `
  -f "$env:USERPROFILE\.ssh\liveconv_client" `
  -C liveconv-forward-only
```

A passphrase-protected key is preferred. Load it into the platform SSH agent
before the first tunnel connection because the client configuration below uses
`BatchMode yes` and cannot prompt. If an unattended client cannot use an agent
or hardware-backed key, use a dedicated unpassphrased key only with the
server-side restrictions below and protect the client account and private-key
file. Never reuse an administrative SSH key.

Deliver only `liveconv_client.pub` to the server administrator through an
approved channel.

## Create a least-privilege forwarding account

The following server steps are for an administrator on a typical Linux OpenSSH
host. Keep the current administrative session open until `sshd -t`, a new tunnel
login, and the health checks have all succeeded.

Create an account that does not own the Gateway checkout, environment file,
model artifacts, Docker socket, or logs:

```bash
sudo useradd --create-home --shell /usr/sbin/nologin liveconv-tunnel
sudo install -d -m 0700 -o liveconv-tunnel -g liveconv-tunnel \
  /home/liveconv-tunnel/.ssh
sudo touch /home/liveconv-tunnel/.ssh/authorized_keys
sudo chown liveconv-tunnel:liveconv-tunnel \
  /home/liveconv-tunnel/.ssh/authorized_keys
sudo chmod 0600 /home/liveconv-tunnel/.ssh/authorized_keys
sudoedit /home/liveconv-tunnel/.ssh/authorized_keys
```

Add one physical line per client. Replace the public-key placeholder with the
complete contents of that client's `.pub` file:

```text
restrict,port-forwarding,permitopen="127.0.0.1:8765" ssh-ed25519 REDACTED_CLIENT_PUBLIC_KEY liveconv-forward-only
```

`restrict` disables shell-adjacent key capabilities; `port-forwarding` enables
only forwarding again; and `permitopen` constrains `-L` to the Gateway's exact
remote destination. The SSH daemon policy should independently enforce the same
boundary. Confirm that `/etc/ssh/sshd_config` includes
`/etc/ssh/sshd_config.d/*.conf`, then create this drop-in:

```bash
sudoedit /etc/ssh/sshd_config.d/liveconv-forward.conf
```

```sshconfig
Match User liveconv-tunnel
    AuthenticationMethods publickey
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding no
    PermitOpen 127.0.0.1:8765
    PermitTTY no
    PermitTunnel no
    MaxSessions 0
    X11Forwarding no
    AllowAgentForwarding no
    PermitUserRC no

Match all
```

If the installed daemon does not load that drop-in directory, place the same
`Match User` block and its closing `Match all` at the end of
`/etc/ssh/sshd_config`. The closing match prevents a later included file or
directive from accidentally inheriting the forwarding-user condition.

`MaxSessions 0` blocks shell, login, and subsystem sessions while still allowing
TCP forwarding. Validate before reloading:

```bash
sudo sshd -t
sudo sshd -T -C user=liveconv-tunnel,host=SERVER_HOST,addr=CLIENT_IP \
  | grep -E '^(authenticationmethods|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|allowtcpforwarding|allowstreamlocalforwarding|permitopen|permittty|permittunnel|maxsessions|x11forwarding|allowagentforwarding|permituserrc) '
```

The effective output must show public-key authentication, local-only TCP
forwarding, `127.0.0.1:8765` as the only permitted destination, zero sessions,
and the other capabilities disabled. Reload the actual unit name used by the
server distribution, for example `sshd` on Fedora/RHEL or `ssh` on
Debian/Ubuntu:

```bash
sudo systemctl reload sshd
```

or:

```bash
sudo systemctl reload ssh
```

Do not use `GatewayPorts`, remote forwarding (`-R`), dynamic forwarding (`-D`),
agent forwarding, or a general-purpose shell account for this route.

## Pin the SSH server host key

Host-key pinning must happen before the tunnel credential is used. On the server
console, have the administrator obtain the expected fingerprint:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Send that `SHA256:...` fingerprint to the client through an authenticated,
independent channel. On the supported Linux client, collect the advertised key
inside the isolated SSH directory and inspect it. The macOS preview uses the
same draft path:

```bash
install -d -m 0700 ~/.config/liveconv/ssh
umask 077
ssh-keyscan -p 22 -t ed25519 SERVER_HOST \
  > ~/.config/liveconv/ssh/known_hosts.pending
ssh-keygen -lf ~/.config/liveconv/ssh/known_hosts.pending
```

On Windows PowerShell:

```powershell
$pending = "$env:USERPROFILE\.ssh\liveconv_known_hosts.pending"
ssh-keyscan.exe -p 22 -t ed25519 SERVER_HOST | Set-Content -Encoding ascii $pending
ssh-keygen.exe -lf $pending
```

Substitute the real SSH port for 22. `ssh-keyscan` is not authentication: a key
is trusted only after every displayed fingerprint matches the value obtained
out of band. After a match, promote the file.

Linux, and the non-gating macOS preview:

```bash
mv ~/.config/liveconv/ssh/known_hosts.pending \
  ~/.config/liveconv/ssh/known_hosts
chmod 0600 ~/.config/liveconv/ssh/known_hosts
```

Windows PowerShell:

```powershell
Move-Item -Force `
  "$env:USERPROFILE\.ssh\liveconv_known_hosts.pending" `
  "$env:USERPROFILE\.ssh\liveconv_known_hosts"
```

If the server does not offer an Ed25519 host key, the administrator must choose
and provide the fingerprint of another approved host-key type; use that same
type in `ssh-keyscan`. Never work around a changed-key warning with
`StrictHostKeyChecking=no` or by blindly deleting the pinned file. Confirm an
authorized rotation out of band, build a new pending file, compare it, and only
then replace the pin.

## Configure an isolated SSH client

Do **not** add a `liveconv-audio` stanza to `~/.ssh/config` or to the Windows
user OpenSSH configuration. This route always passes `-F` with a purpose-built
file, so an ordinary `Host *` block cannot supply a different user, weaken host
key checking, or add a second forward. The configuration below has no `Include`
or `Host *` block. Its preflight also rejects any unexpected forwarding value
that a system-level SSH configuration contributes to the effective result.

On Linux, create `~/.config/liveconv/ssh/config`. The macOS preview currently
uses the same draft path but is non-gating:

```bash
install -d -m 0700 ~/.config/liveconv/ssh
umask 077
tee ~/.config/liveconv/ssh/config >/dev/null <<'EOF'
Host liveconv-audio
    HostName SERVER_HOST
    Port 22
    User liveconv-tunnel
    IdentityFile ~/.ssh/liveconv_client
    IdentitiesOnly yes
    UserKnownHostsFile ~/.config/liveconv/ssh/known_hosts
    GlobalKnownHostsFile none
    StrictHostKeyChecking yes
    UpdateHostKeys no
    BatchMode yes
    ExitOnForwardFailure yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ControlMaster no
    RequestTTY no
    ForwardAgent no
    ForwardX11 no
    PermitLocalCommand no
    LocalForward 127.0.0.1:8765 127.0.0.1:8765
EOF
chmod 0600 ~/.config/liveconv/ssh/config ~/.ssh/liveconv_client
```

The following Windows PowerShell configuration is a non-gating MS-5 preview.
Create
`%LOCALAPPDATA%\liveconv\ssh\config`:

```powershell
$sshDirectory = "$env:LOCALAPPDATA\liveconv\ssh"
$config = "$sshDirectory\config"
New-Item -ItemType Directory -Force $sshDirectory | Out-Null
@'
Host liveconv-audio
    HostName SERVER_HOST
    Port 22
    User liveconv-tunnel
    IdentityFile ~/.ssh/liveconv_client
    IdentitiesOnly yes
    UserKnownHostsFile ~/.ssh/liveconv_known_hosts
    GlobalKnownHostsFile none
    StrictHostKeyChecking yes
    UpdateHostKeys no
    BatchMode yes
    ExitOnForwardFailure yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ControlMaster no
    RequestTTY no
    ForwardAgent no
    ForwardX11 no
    PermitLocalCommand no
    LocalForward 127.0.0.1:8765 127.0.0.1:8765
'@ | Set-Content -Encoding ascii $config
$key = "$env:USERPROFILE\.ssh\liveconv_client"
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls.exe $config /inheritance:r
icacls.exe $config /grant:r "${account}:F"
icacls.exe $key /inheritance:r
icacls.exe $key /grant:r "${account}:F"
ssh-keygen.exe -y -f $key | Out-Null
Remove-Variable key, account
```

Replace `SERVER_HOST` and `22` with the approved server values. The dedicated
host-pin file is the only known-hosts source for this connection:
`GlobalKnownHostsFile none` prevents an unrelated system pin from silently
authorizing this server.

### Install the effective-configuration preflight

Before every foreground or supervised connection, the preflight runs
`ssh -F ... -G` and fails unless the effective result has the forwarding-only
user, the dedicated host-pin file, strict checking, `BatchMode`,
`ExitOnForwardFailure`, and exactly one IPv4-loopback local forward to the
remote Gateway loopback port. It also rejects dynamic or remote forwards. The
default forward is reported as
`localforward [127.0.0.1]:8765 [127.0.0.1]:8765`; no wildcard bind is accepted.

On Linux, create `~/.config/liveconv/ssh/preflight.sh`:

```bash
tee ~/.config/liveconv/ssh/preflight.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
config="$script_dir/config"
ssh_bin="/usr/bin/ssh"
fail() { printf 'liveconv SSH preflight: %s\n' "$*" >&2; exit 1; }
[[ -r "$config" ]] || fail "isolated config is unreadable: $config"
[[ -x "$ssh_bin" ]] || fail "SSH executable is unavailable: $ssh_bin"
effective="$("$ssh_bin" -F "$config" -G liveconv-audio)" || fail "cannot read effective config"

one_value() {
  local name="$1"
  local -a values=()
  mapfile -t values < <(awk -v name="$name" '$1 == name { $1 = ""; sub(/^ /, ""); print }' <<<"$effective")
  [[ ${#values[@]} -eq 1 ]] || fail "expected one $name value, got ${#values[@]}"
  printf '%s\n' "${values[0]}"
}

[[ "$(one_value user)" == "liveconv-tunnel" ]] || fail "unexpected SSH user"
known_hosts_value="$(one_value userknownhostsfile)"
read -r -a known_hosts_paths <<<"$known_hosts_value"
[[ ${#known_hosts_paths[@]} -eq 1 ]] || fail "expected exactly one UserKnownHostsFile path"
expected_known_hosts="$(realpath -e -- "$script_dir/known_hosts")" || fail "dedicated host-pin file is missing"
effective_known_hosts="$(realpath -e -- "${known_hosts_paths[0]}")" || fail "effective host-pin file is missing"
[[ "$effective_known_hosts" == "$expected_known_hosts" ]] || fail "unexpected host-pin file"
[[ "$(one_value globalknownhostsfile)" == "none" ]] || fail "global known-hosts source is enabled"
case "$(one_value stricthostkeychecking)" in yes|true) ;; *) fail "strict host-key checking is disabled" ;; esac
[[ "$(one_value batchmode)" == "yes" ]] || fail "BatchMode is disabled"
[[ "$(one_value exitonforwardfailure)" == "yes" ]] || fail "ExitOnForwardFailure is disabled"

mapfile -t forwards < <(awk '$1 == "localforward" { $1 = ""; sub(/^ /, ""); print }' <<<"$effective")
[[ ${#forwards[@]} -eq 1 ]] || fail "expected exactly one LocalForward, got ${#forwards[@]}"
[[ "${forwards[0]}" =~ ^\[127\.0\.0\.1\]:[1-9][0-9]*\ \[127\.0\.0\.1\]:8765$ ]] || fail "LocalForward is not loopback-only"
if awk '$1 == "dynamicforward" || $1 == "remoteforward" { exit 1 }' <<<"$effective"; then :; else
  fail "dynamic or remote forwarding is configured"
fi
printf '%s\n' 'liveconv SSH preflight passed'
EOF
chmod 0700 ~/.config/liveconv/ssh/preflight.sh
~/.config/liveconv/ssh/preflight.sh
```

Install `~/.config/liveconv/ssh/connect.sh` as the only supported Linux entry
point. It accepts no caller-defined SSH options. The three arguments accepted
internally are only for `autossh`, which invokes its configured SSH executable
with the same fixed `-N -T liveconv-audio` tuple on every reconnect:

```bash
tee ~/.config/liveconv/ssh/connect.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
config="$script_dir/config"
preflight="$script_dir/preflight.sh"
ssh_args=(-N -T)

if [[ $# -eq 1 && "$1" == "--verbose" ]]; then
  ssh_args=(-vvv -N -T)
elif [[ $# -eq 3 ]]; then
  [[ "$1" == "-N" && "$2" == "-T" && "$3" == "liveconv-audio" ]] || {
    printf '%s\n' 'liveconv SSH launcher: rejected SSH arguments' >&2
    exit 2
  }
elif [[ $# -ne 0 ]]; then
  printf '%s\n' 'liveconv SSH launcher: rejected SSH arguments' >&2
  exit 2
fi

"$preflight"
exec /usr/bin/ssh -F "$config" "${ssh_args[@]}" liveconv-audio
EOF
chmod 0700 ~/.config/liveconv/ssh/connect.sh
```

If `command -v ssh` does not report `/usr/bin/ssh`, replace that path in both
scripts with the verified absolute path before running either one. Do not invoke
the Linux tunnel with raw `ssh -F` commands: the launcher ensures every new
connection validates the then-current effective configuration immediately
before `exec`.

The PowerShell preflight below is a non-gating MS-5 preview. Create
`%LOCALAPPDATA%\liveconv\ssh\preflight.ps1` and run it:

```powershell
$sshDirectory = "$env:LOCALAPPDATA\liveconv\ssh"
$preflight = "$sshDirectory\preflight.ps1"
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
@'
$ErrorActionPreference = 'Stop'
$config = Join-Path $PSScriptRoot 'config'
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
    throw "liveconv SSH preflight: isolated config is missing: $config"
}
$effective = @(& "$env:WINDIR\System32\OpenSSH\ssh.exe" -F $config -G liveconv-audio)
if ($LASTEXITCODE -ne 0) { throw 'liveconv SSH preflight: cannot read effective config' }

function Require-OneValue([string]$Name, [string[]]$Allowed) {
    $matches = @($effective | Where-Object { $_ -match "^$Name " })
    if ($matches.Count -ne 1) { throw "liveconv SSH preflight: expected one $Name value" }
    $value = $matches[0].Substring($Name.Length).Trim()
    if ($Allowed -notcontains $value) { throw "liveconv SSH preflight: unexpected $Name value" }
}

Require-OneValue 'user' @('liveconv-tunnel')
Require-OneValue 'userknownhostsfile' @("$env:USERPROFILE\.ssh\liveconv_known_hosts")
Require-OneValue 'globalknownhostsfile' @('none')
Require-OneValue 'stricthostkeychecking' @('yes', 'true')
Require-OneValue 'batchmode' @('yes')
Require-OneValue 'exitonforwardfailure' @('yes')
$forwards = @($effective | Where-Object { $_ -match '^localforward ' })
if ($forwards.Count -ne 1 -or $forwards[0] -notmatch '^localforward \[127\.0\.0\.1\]:[1-9][0-9]* \[127\.0\.0\.1\]:8765$') {
    throw 'liveconv SSH preflight: LocalForward is not exactly one loopback-only Gateway forward'
}
if (@($effective | Where-Object { $_ -match '^(dynamicforward|remoteforward) ' }).Count -ne 0) {
    throw 'liveconv SSH preflight: dynamic or remote forwarding is configured'
}
Write-Output 'liveconv SSH preflight passed'
'@ | Set-Content -Encoding ascii $preflight
icacls.exe $preflight /inheritance:r
icacls.exe $preflight /grant:r "${account}:F"
& $preflight
Remove-Variable preflight, sshDirectory, config, account
```

Do not bypass a preflight failure with command-line `-o` settings. Correct the
isolated file and re-run the preflight. If the client port is occupied, change
the **left** port of its sole `LocalForward` to another explicit loopback port,
then use that same port in the Extension and HTTP checks. Do not add a second
forward or bind it to `0.0.0.0`, `::`, or `*`.

### Enroll the encrypted key in the platform agent

A passphrase-protected client key remains preferred. `BatchMode yes` means a
tunnel or supervisor cannot ask for that passphrase; unlock and verify the key
in the platform agent before it is started. Do not put a passphrase in a unit,
plist, task, script, or environment variable.

On Linux, in the interactive user session that owns the systemd user manager:

```bash
ssh-add ~/.ssh/liveconv_client
ssh-add -l
test -S "$SSH_AUTH_SOCK"
systemctl --user import-environment SSH_AUTH_SOCK
systemctl --user show-environment | grep '^SSH_AUTH_SOCK='
```

The `systemd --user` service uses the manager environment, not necessarily the
terminal environment. After every reboot, log in, repeat `ssh-add`, and repeat
the socket/import/visibility checks before starting or restarting the unit. User
lingering does not make an encrypted key available before login.

In the non-gating macOS preview, enroll the key in the logged-in user's
Keychain-backed agent before bootstrapping the launchd agent:

```bash
ssh-add --apple-use-keychain ~/.ssh/liveconv_client
ssh-add -l
```

After a reboot and GUI login, check `ssh-add -l` before `launchctl kickstart` or
starting the tunnel. If the identity is absent, run the enrollment command again
while Keychain is unlocked; do not replace the protected key with an unencrypted
one.

In the non-gating Windows preview, from an elevated PowerShell once, enable the
OpenSSH Authentication Agent, then add the key from the scheduled-task user's
interactive session:

```powershell
Set-Service -Name ssh-agent -StartupType Automatic
Start-Service -Name ssh-agent
ssh-add.exe "$env:USERPROFILE\.ssh\liveconv_client"
ssh-add.exe -l
```

After a reboot, verify the agent and loaded identity before starting the Task
Scheduler job:

```powershell
Get-Service ssh-agent
ssh-add.exe -l
Get-ScheduledTask -TaskName 'liveconv-tunnel' -ErrorAction SilentlyContinue |
  Get-ScheduledTaskInfo
```

If `ssh-add.exe -l` does not list the key, add it interactively again, then
start or restart the task. An unavailable agent causes the guarded SSH command
to fail closed rather than prompting in the background.

## Record the Extension identity

1. On the client, open `chrome://extensions`.
2. Enable Developer mode and choose **Load unpacked**.
3. Select the checkout's `apps/extension/` directory.
4. Record the 32-character lowercase Extension ID shown by Chrome.
5. Form the server allowlist entry as `chrome-extension://EXTENSION_ID`.

The exact ID must be configured before the Gateway starts. Each Chrome profile
or trusted client with a different ID needs its own comma-separated exact entry.
Wildcards, Web origins, paths, uppercase characters, and trailing slashes are
rejected. Recheck the ID after moving/reinstalling the unpacked Extension or
changing Chrome profiles.

## Prepare the remote Gateway without exposing the token

Run the following in Bash as the Gateway operator, not as `liveconv-tunnel`.
It generates a high-entropy token directly into a mode-0600 environment file;
the token is never a command argument, terminal output, or shell-history entry.

```bash
(
set -euo pipefail
install -d -m 0700 ~/.config/liveconv
read -r -p 'Chrome Extension ID: ' liveconv_extension_id
if [[ ! "$liveconv_extension_id" =~ ^[a-p]{32}$ ]]; then
  printf '%s\n' 'invalid Chrome Extension ID' >&2
  exit 2
fi
liveconv_env_tmp="$(mktemp ~/.config/liveconv/gateway.env.XXXXXX)"
trap 'rm -f "$liveconv_env_tmp"' EXIT
umask 077
{
  printf 'LIVECONV_API_TOKEN=0123456789ABCDEF'
  openssl rand -base64 48 | tr -d '\n'
  printf '\nLIVECONV_ALLOWED_ORIGINS=chrome-extension://%s\n' \
    "$liveconv_extension_id"
  printf '%s\n' \
    'LIVECONV_BIND_HOST=127.0.0.1' \
    'LIVECONV_BIND_PORT=8765'
} > "$liveconv_env_tmp"
chmod 0600 "$liveconv_env_tmp"
mv "$liveconv_env_tmp" ~/.config/liveconv/gateway.env
trap - EXIT
unset liveconv_env_tmp liveconv_extension_id
)
```

The generated token satisfies the Gateway's visible-ASCII, minimum 32-byte, and
minimum 16-distinct-character checks deterministically; its random suffix
provides 384 bits of input entropy. If more trusted Extension IDs are needed,
edit only the non-secret
`LIVECONV_ALLOWED_ORIGINS` line into a comma-separated list while preserving
file mode 0600. Provision the bearer token to the client through an approved
password manager or similarly private channel; do not send the environment
file or print the token into a shared terminal or log.

Start the development Gateway in the server checkout. This tmux example keeps
the process alive after the operator disconnects and preserves the loopback
bind:

```bash
tmux new-session -d -s liveconv-gateway \
  "cd /ABSOLUTE/PATH/TO/liveconv && \
   set -a && . ~/.config/liveconv/gateway.env && set +a && \
   exec uv run --frozen --all-packages python -m liveconv_audio"
```

Verify the remote listener and authenticated readiness without placing the
token in `curl`'s argument list:

```bash
set -a
. ~/.config/liveconv/gateway.env
set +a
ss -ltn 'sport = :8765'
curl --fail --silent --show-error --config - \
  http://127.0.0.1:8765/health/ready <<EOF
header = "Authorization: Bearer $LIVECONV_API_TOKEN"
EOF
unset LIVECONV_API_TOKEN
```

Expected response:

```json
{"status":"ready"}
```

The listener must be `127.0.0.1:8765`, not `0.0.0.0:8765` or `[::]:8765`.
The public liveness endpoint is not sufficient evidence that authentication,
the allowlist, and the profile registry are ready.

## Start and verify the tunnel

On the supported Linux client, run the guarded foreground tunnel and leave it
running:

```bash
~/.config/liveconv/ssh/connect.sh
```

The following Windows PowerShell foreground command remains a non-gating MS-5
preview:

```powershell
$config = "$env:LOCALAPPDATA\liveconv\ssh\config"
& "$env:LOCALAPPDATA\liveconv\ssh\preflight.ps1"
& "$env:WINDIR\System32\OpenSSH\ssh.exe" -F $config -N -T liveconv-audio
Remove-Variable config
```

`ExitOnForwardFailure` rejects an initial local bind failure. It cannot prove
that the Gateway is running: OpenSSH can establish its local listener before a
connection to the forwarded destination is attempted. Always run the HTTP
checks below.

If client port 8765 is already in use, change only the left side of
`LocalForward`:

```sshconfig
    LocalForward 127.0.0.1:18765 127.0.0.1:8765
```

Then use `http://127.0.0.1:18765` everywhere on the client. Do not add `-g` or
bind the client side to `0.0.0.0` or `::`.

First verify unauthenticated liveness:

```bash
curl --fail --silent --show-error http://127.0.0.1:8765/health/live
```

This proves that the local port reaches a live Gateway, but not that the bearer
token or Extension origin is accepted. The exact expected response is
`{"status":"live"}`; stop if another service responds.

### Authenticated verification on Linux

Run this in Bash. The token is read silently and supplied to `curl` through
standard input, so it is absent from shell history and process arguments:

```bash
read -r -s -p 'liveconv token: ' LIVECONV_CLIENT_TOKEN
printf '\n'
curl --fail --silent --show-error --config - \
  http://127.0.0.1:8765/health/ready <<EOF
header = "Authorization: Bearer $LIVECONV_CLIENT_TOKEN"
EOF
curl --fail --silent --show-error --config - \
  http://127.0.0.1:8765/v1/models <<EOF
header = "Authorization: Bearer $LIVECONV_CLIENT_TOKEN"
EOF
unset LIVECONV_CLIENT_TOKEN
```

### Authenticated verification on Windows PowerShell preview

`Invoke-RestMethod` keeps the token out of the PowerShell history and child
process arguments. The plaintext value exists only in this PowerShell process
for the request and is removed in `finally`:

```powershell
$secret = Read-Host 'liveconv token' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $headers = @{ Authorization = "Bearer $token" }
    Invoke-RestMethod `
      -Uri 'http://127.0.0.1:8765/health/ready' `
      -Headers $headers
    Invoke-RestMethod `
      -Uri 'http://127.0.0.1:8765/v1/models' `
      -Headers $headers
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    Remove-Variable token, headers, pointer, secret -ErrorAction SilentlyContinue
}
```

Use the alternate local port in these commands when configured. A successful
`/v1/models` response identifies the valid profile IDs for the popup.

## Configure and smoke-test the Extension

This section supplies the LV-049 minimum transport preflight and the client-side
steps for EXP-005. In MS-2, invoke all four frozen roster models: use the live
profile flow for RVC, Beatrice 2, and X-VC, and the explicit End-triggered
buffered-preview flow for OpenVoice. Record only non-sensitive metadata. MS-4
later repeats the route with its full security-negative and second-shell gate.

1. Open the liveconv Extension popup from a normal audible tab.
2. Set Gateway origin to exactly `http://127.0.0.1:8765`, or the chosen
   alternate client-loopback port.
3. Select a profile returned by `/v1/models`.
4. Paste the development bearer token directly from the approved secret channel
   and choose **Save session**. Approve the exact loopback host-permission
   request.
5. Choose **Start** from that tab as an explicit user gesture.
6. Confirm the popup reaches remote-ready state and perform one audible-tab
   check. Exercise **End**, **Interrupt**, and **Next** for the explicit
   generation lifecycle.
7. Choose **Stop** before intentionally stopping the tunnel or changing the
   Gateway configuration.

The bearer token is stored only in `chrome.storage.session`; the one-use
WebSocket ticket remains in Extension memory. Neither is placed in source, sync
storage, a URL, or status messages. Chrome internal and protected pages cannot
be captured. A popup-only check is not a replacement for one real audible-tab
smoke test with explicit user activation. See the
[Extension run guide](../../apps/extension/README.md) for the current controls.

## Reconnect, diagnose, recover, and tear down

Continue with the
[SSH tunnel operations and troubleshooting guide](ssh-tunnel-troubleshooting.md)
for Linux systemd and autossh, macOS launchd, Windows Task Scheduler, failure
modes, disconnect recovery, client revocation, and teardown. A supervisor
restores only SSH connectivity; after a break the supported Extension recovery
is still **Stop**, authenticated verification, then a fresh **Start**.

## Security checklist

- Both application endpoints are exact loopback addresses; neither forward uses
  a wildcard bind.
- The Gateway remains authenticated even though SSH authenticates the client
  host user.
- Every client has a separately revocable SSH key constrained by both
  `authorized_keys` and `sshd_config`.
- The client pins a host key obtained through an independent trusted channel and
  refuses unexpected changes.
- The Extension ID allowlist contains exact
  `chrome-extension://EXTENSION_ID` origins and no wildcard.
- Bearer tokens and tickets never appear in command history, URLs, source,
  supervisor files, or logs.
- A tunnel reconnect creates connectivity only; the Extension creates a fresh
  authenticated session and ticket.
- Native fallback and exclusive final playout remain owned by the Extension.
