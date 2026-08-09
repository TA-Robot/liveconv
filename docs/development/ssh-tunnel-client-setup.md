# Client setup over an SSH tunnel

Status: Accepted development and controlled-experiment path

This path lets a Chrome client use a Gateway on a remote machine without
publishing the Gateway port. OpenSSH carries the local HTTP and WebSocket
connections inside one encrypted local-forwarding tunnel:

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

The Gateway remains bound to remote loopback. The Extension sees a client
loopback origin, so its loopback-only HTTP allowance applies; the WebSocket URL
is derived from the same origin and crosses the same tunnel. The bearer token,
one-use WebSocket ticket, and exact Extension `Origin` checks still apply.

Use this path for trusted development and controlled experiments. It is not a
replacement for the reviewed public TLS deployment in `deploy/remote/` or for a
multi-user identity boundary.

## Prerequisites

Remote server:

- the repository and locked Python environment are installed
- the Gateway can start on `127.0.0.1:8765`
- OpenSSH server access works with host-key verification and key authentication
- SSH TCP forwarding is allowed to `127.0.0.1:8765`
- the API token and allowed Extension origin are stored outside Git

Client terminal:

- Chrome 116 or newer
- an OpenSSH client
- a checkout containing `apps/extension/`
- the API token delivered through an approved private channel

Node.js is required to run the Extension tests, but not to load the unpacked
Extension in Chrome.

## One-time Extension identity

1. On the client, open `chrome://extensions`.
2. Enable Developer mode and choose **Load unpacked**.
3. Select the checkout's `apps/extension/` directory.
4. Record the 32-character Extension ID shown by Chrome.
5. Form the server allowlist value as `chrome-extension://<extension-id>`.

The exact ID must be present in `LIVECONV_ALLOWED_ORIGINS` before the remote
Gateway starts. For several trusted clients, use a comma-separated list of exact
origins. Do not use a wildcard.

## Remote Gateway preparation

On the server, create a private environment file. The values below are examples;
generate a distinct random token and substitute the real Extension origin.

```bash
install -d -m 0700 ~/.config/liveconv
umask 077
${EDITOR:-vi} ~/.config/liveconv/gateway.env
```

```dotenv
LIVECONV_API_TOKEN=replace-with-a-random-visible-ascii-token
LIVECONV_ALLOWED_ORIGINS=chrome-extension://replace-with-extension-id
LIVECONV_BIND_HOST=127.0.0.1
LIVECONV_BIND_PORT=8765
```

Start the development Gateway in the server checkout. A terminal multiplexer or
service manager keeps it alive after the interactive SSH login closes. This tmux
example deliberately keeps the application on loopback:

```bash
tmux new-session -d -s liveconv-gateway \
  "cd /absolute/path/liveconv && \
   set -a && . ~/.config/liveconv/gateway.env && set +a && \
   exec uv run --frozen --all-packages python -m liveconv_audio"
```

Verify the remote listener and authenticated readiness from the server:

```bash
set -a
. ~/.config/liveconv/gateway.env
set +a
ss -ltnp 'sport = :8765'
curl --fail --silent --show-error \
  -H "Authorization: Bearer $LIVECONV_API_TOKEN" \
  http://127.0.0.1:8765/health/ready
```

The listener must be `127.0.0.1:8765`, not `0.0.0.0:8765`.

## Start the client tunnel

Run this on the client machine and keep it open:

```bash
ssh -N -T \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:8765:127.0.0.1:8765 \
  SERVER_USER@SERVER_HOST
```

The same OpenSSH options work in a macOS/Linux terminal and in Windows
PowerShell with the built-in OpenSSH client. In PowerShell, enter the command on
one line or replace the Bash continuation backslashes with PowerShell backticks.
Add `-p SSH_PORT` when the server does not use port 22. Do not add `-g`, do not
bind the local side to `0.0.0.0`, and do not enable SSH `GatewayPorts` for this
path.

For a reusable client configuration, add a host entry to the client's
`~/.ssh/config`:

```sshconfig
Host liveconv-audio
    HostName SERVER_HOST
    User SERVER_USER
    IdentityFile ~/.ssh/liveconv_client
    ExitOnForwardFailure yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    LocalForward 127.0.0.1:8765 127.0.0.1:8765
```

Then start only the tunnel with:

```bash
ssh -N -T liveconv-audio
```

If client port 8765 is occupied, use another client-loopback port while leaving
the remote port unchanged:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:18765:127.0.0.1:8765 \
  SERVER_USER@SERVER_HOST
```

Use `http://127.0.0.1:18765` as the Extension Gateway origin in that case.

## Verify from the client

The unauthenticated liveness check proves that the TCP forward reaches a
Gateway. It does not prove that the token or Extension origin is correct.

```bash
curl --fail --silent --show-error http://127.0.0.1:8765/health/live
```

For an authenticated check from Bash, keep the token out of command history with
a silent prompt:

```bash
read -r -s -p 'liveconv token: ' LIVECONV_CLIENT_TOKEN
printf '\n'
curl --fail --silent --show-error \
  -H "Authorization: Bearer $LIVECONV_CLIENT_TOKEN" \
  http://127.0.0.1:8765/health/ready
curl --fail --silent --show-error \
  -H "Authorization: Bearer $LIVECONV_CLIENT_TOKEN" \
  http://127.0.0.1:8765/v1/models
unset LIVECONV_CLIENT_TOKEN
```

Expected ready response:

```json
{"status":"ready"}
```

## Configure and use the Extension

1. Open the liveconv Extension popup.
2. Set Gateway origin to `http://127.0.0.1:8765`, or the alternate local port.
3. Select a profile returned by `/v1/models`.
4. Enter the development API token and choose **Save session**.
5. Open a normal audible tab, open the popup from that tab, and choose **Start**.
6. Use **End**, **Interrupt**, and **Next** for the explicit generation lifecycle.
7. Choose **Stop** before intentionally closing the tunnel.

The token is stored only in `chrome.storage.session`. The one-use WebSocket
ticket remains in Extension memory. Neither credential is written into the
checkout or a URL.

Chrome internal pages and some protected pages cannot be captured. A successful
popup/status smoke does not replace one audible-tab test with an explicit user
gesture.

## Disconnect and recovery

An unexpected SSH disconnect makes the remote route fail and the Extension
returns to its native path. The old remote session may remain until its bounded
server lifetime expires if the DELETE request could not cross the broken
tunnel.

1. Re-establish the SSH tunnel.
2. Confirm `/health/live` and authenticated `/health/ready`.
3. Choose **Stop** in the Extension to clear local state.
4. Choose **Start** to create a new server session and one-use ticket.

The current client does not promise transparent session resumption across a
tunnel break. A new Start is the supported recovery path.

## Troubleshooting

| Symptom | Check |
|---|---|
| `bind: Address already in use` | Use an alternate client port such as 18765. |
| SSH reports `administratively prohibited` | Allow local forwarding or `PermitOpen 127.0.0.1:8765` in the SSH policy. |
| `/health/live` cannot connect | Confirm the tunnel process, remote Gateway, and both loopback port numbers. |
| `/health/ready` returns 401 | The client token differs from `LIVECONV_API_TOKEN`. |
| Gateway is not ready | Check token policy, exact allowed Origin, profile registry, and the server log. |
| Popup cannot save the Gateway | Confirm the origin is exactly `http://127.0.0.1:PORT` and grant its requested host permission. |
| WebSocket attach fails | Confirm the server allowlist contains the exact current Chrome Extension ID. |
| Start fails on one tab | Use a normal capturable tab and invoke Start from the popup as an explicit user gesture. |
| Tunnel reconnects but remote audio does not | Stop, verify readiness, and Start a new session. |

Use `ssh -vvv` only for transport diagnosis and review its output before sharing;
hostnames, usernames, key paths, and network topology may be sensitive.

## Security boundary

- SSH encrypts the network hop, but Gateway bearer authentication remains
  mandatory.
- Both ends of the forwarded application connection stay on loopback.
- The Gateway and worker ports are never exposed directly to the client network.
- SSH host-key verification and key management remain the operator's
  responsibility.
- The shared development token is suitable only for trusted clients. Public or
  multi-user service requires the reviewed TLS deployment and a production
  identity design.
- Raw audio and transcripts are not persisted by the tunnel or Gateway.
