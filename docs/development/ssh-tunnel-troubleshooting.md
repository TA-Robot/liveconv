# SSH tunnel operations and troubleshooting

Status: Accepted Linux procedure; macOS and Windows preview

This is the operations companion to the
[SSH tunnel client setup](ssh-tunnel-client-setup.md). It assumes the Gateway,
least-privilege SSH account, pinned host key, isolated `liveconv-audio`
configuration, loopback forward, bearer token, and exact Chrome Extension origin
allowlist have already passed that guide's authenticated checks.
Linux is the initial supported personal-client platform. The macOS and Windows
sections are best-effort MS-5 previews and do not satisfy the MS-4 gate.

## Keep the tunnel connected

Supervision re-establishes the SSH transport; it does not resume a Gateway
session or make a consumed WebSocket ticket reusable. After any tunnel break,
run the health checks, choose **Stop**, and choose **Start** to create a new
Gateway session and ticket.

`ServerAliveInterval 30` and `ServerAliveCountMax 3` make OpenSSH abandon an
unresponsive transport after roughly 90 seconds. The supervisors below then
restart it. Because `BatchMode yes` forbids interactive prompts, host-key and key
agent preparation and the effective-configuration preflight must already be
complete. After a reboot, perform the platform agent visibility check in the
[client setup](ssh-tunnel-client-setup.md#enroll-the-encrypted-key-in-the-platform-agent)
before enabling or restarting a supervisor.

### Linux: systemd user service

Confirm the launcher and preflight use the absolute path reported by
`command -v ssh`, then create
`~/.config/systemd/user/liveconv-tunnel.service`:

```ini
[Unit]
Description=liveconv SSH local-forwarding tunnel
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=%h/.config/liveconv/ssh/connect.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Enable it for the logged-in user:

```bash
systemctl --user daemon-reload
systemctl --user enable --now liveconv-tunnel.service
systemctl --user is-active liveconv-tunnel.service
journalctl --user-unit liveconv-tunnel.service --since=-10m
```

By default this starts within that user's login session. If policy permits the
tunnel to run before login and after logout, an administrator can enable user
lingering explicitly:

```bash
sudo loginctl enable-linger CLIENT_LOGIN
```

For an interactive portable alternative, install `autossh` and run its guarded
isolated-config form:

```bash
AUTOSSH_GATETIME=0 \
AUTOSSH_PATH="$HOME/.config/liveconv/ssh/connect.sh" \
  autossh -M 0 -N -T liveconv-audio
```

`AUTOSSH_PATH` makes each reconnect invoke the guarded launcher, so it validates
the current effective configuration before every SSH process. With `-M 0`,
autossh relies on the configured OpenSSH server-alive checks. Do not run autossh
and the systemd unit on the same local port.

### macOS preview: launchd user agent

This draft does not gate MS-4. Bash 3.2 compatibility and launchd enrollment
ordering remain scheduled MS-5 validation work.

Create `~/Library/LaunchAgents/dev.liveconv.tunnel.plist` with mode 0600:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.liveconv.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>"$HOME/.config/liveconv/ssh/preflight.sh" &amp;&amp; exec /usr/bin/ssh -F "$HOME/.config/liveconv/ssh/config" -N -T liveconv-audio</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
```

Validate and load it:

```bash
chmod 0600 ~/Library/LaunchAgents/dev.liveconv.tunnel.plist
plutil -lint ~/Library/LaunchAgents/dev.liveconv.tunnel.plist
launchctl bootstrap gui/"$(id -u)" \
  ~/Library/LaunchAgents/dev.liveconv.tunnel.plist
launchctl print gui/"$(id -u)"/dev.liveconv.tunnel
```

If it is already loaded, use `launchctl kickstart -k` with the printed service
target rather than starting a second tunnel.

### Windows preview: PowerShell loop and Task Scheduler

This draft does not gate MS-4. Windows path normalization and agent/task startup
ordering remain scheduled MS-5 validation work.

For a visible, manually stoppable reconnect loop:

```powershell
$config = "$env:LOCALAPPDATA\liveconv\ssh\config"
& "$env:LOCALAPPDATA\liveconv\ssh\preflight.ps1"
while ($true) {
    & "$env:WINDIR\System32\OpenSSH\ssh.exe" -F $config -N -T liveconv-audio
    Start-Sleep -Seconds 5
}
```

For reconnect after logon, create
`%LOCALAPPDATA%\liveconv\keep-tunnel.ps1` containing:

```powershell
$directory = "$env:LOCALAPPDATA\liveconv"
$null = New-Item -ItemType Directory -Force $directory
$config = "$directory\ssh\config"
$preflight = "$directory\ssh\preflight.ps1"
$log = "$directory\tunnel.log"
$oldLog = "$directory\tunnel.log.1"
while ($true) {
    if ((Test-Path $log) -and ((Get-Item $log).Length -gt 1MB)) {
        Remove-Item $oldLog -Force -ErrorAction SilentlyContinue
        Move-Item $log $oldLog
    }
    try {
        & $preflight
    }
    catch {
        $_ | Out-File -Append -Encoding utf8 $log
        Start-Sleep -Seconds 5
        continue
    }
    & "$env:WINDIR\System32\OpenSSH\ssh.exe" `
      -F $config -N -T liveconv-audio 2>> $log
    Start-Sleep -Seconds 5
}
```

Register it from PowerShell as the current user's limited, interactive task:

```powershell
$script = "$env:LOCALAPPDATA\liveconv\keep-tunnel.ps1"
$action = New-ScheduledTaskAction `
  -Execute 'powershell.exe' `
  -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal `
  -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive `
  -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -StartWhenAvailable
Register-ScheduledTask `
  -TaskName 'liveconv-tunnel' `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Settings $settings `
  -Description 'liveconv SSH local-forwarding tunnel' `
  -Force
Start-ScheduledTask -TaskName 'liveconv-tunnel'
Get-ScheduledTask -TaskName 'liveconv-tunnel' | Get-ScheduledTaskInfo
```

Organization policy may block user-created scheduled tasks or PowerShell
scripts. In that case use the visible loop, WSL with the Linux procedure, or an
administrator-approved service wrapper. The tunnel log can contain hostnames,
usernames, key paths, and network errors; it must not contain tokens or tickets.

## Failure modes

| Symptom | Meaning and safe action |
|---|---|
| Host-key verification failed or the key changed | Stop. Verify an authorized server rotation out of band and rebuild the dedicated pin. Never disable strict checking. |
| `Permission denied (publickey)` | Confirm the per-client public key, file ownership/modes, SSH agent state, `IdentitiesOnly`, user name, and `AuthenticationMethods`. |
| `bind: Address already in use` | Another process owns the client port. Identify it or use local port 18765; do not expose a wildcard listener. |
| `channel ... open failed: administratively prohibited` | The `permitopen` value, `PermitOpen`, or `AllowTcpForwarding` does not exactly allow `127.0.0.1:8765`. Keep the restriction and fix the intended destination. |
| SSH stays open but `/health/live` reports connection reset/refused | The remote Gateway is stopped, listening on the wrong port/interface, or the forward points to the wrong destination. `ExitOnForwardFailure` does not test the application destination. |
| `/health/live` reaches an unexpected service | A non-SSH process owns the local port or the forward target is wrong. Stop and identify the listener before sending a token. |
| `/health/ready` returns 401 | The client bearer token differs from `LIVECONV_API_TOKEN`. Reprovision or rotate it; never paste it into diagnostic output. |
| `/health/ready` returns 503 | Inspect redacted Gateway logs for token-policy, allowlist, profile-registry, or worker readiness errors. Liveness alone is not readiness. |
| Popup rejects the Gateway origin | Use exactly `http://127.0.0.1:PORT` with no path/query/credentials, then approve its requested optional host permission. |
| Popup works with `localhost` intermittently | Use `127.0.0.1`; an IPv6 `localhost` resolution cannot reach this IPv4-only forward. |
| WebSocket closes before attachment | Check the exact current Extension ID in `LIVECONV_ALLOWED_ORIGINS`, ticket expiry/reuse, the 5-second attachment timeout, and same-origin WebSocket derivation. |
| Gateway returns `AUTH_FAILED` | The bearer token, one-use ticket, ticket lifetime, or exact Extension origin is invalid. Create a fresh session; do not reuse the ticket. |
| Chrome cannot capture one tab | Use a normal audible tab and invoke **Start** from its popup as an explicit user gesture; internal/protected pages are not capturable. |
| Supervisor reconnects but remote audio does not resume | Verify liveness/readiness, choose **Stop**, then **Start**. Protocol v1 has no transparent session or ticket resumption. |
| Connection drops about 90 seconds after network loss | This is the configured server-alive failure window. The supervisor should start a new SSH process afterward. |

Public HTTPS/WSS and Caddy are post-v1 and are not a tunnel recovery route.

On the supported Linux client, use
`~/.config/liveconv/ssh/connect.sh --verbose` only while diagnosing SSH. This
runs the same preflight immediately before the verbose connection. The macOS
preview uses `ssh -F ~/.config/liveconv/ssh/config -vvv liveconv-audio`; the
Windows preview uses
`ssh.exe -F "$env:LOCALAPPDATA\liveconv\ssh\config" -vvv liveconv-audio`.
Stop the diagnostic command after the failure is understood. Review output
before sharing because hostnames, usernames, key paths, IP addresses, proxy
jumps, and network topology may be sensitive. Gateway logs must never contain
bearer tokens, tickets, raw audio, or raw text.

## Recovery after a disconnect

The Extension immediately rejects the failed remote path and retains native
fallback. A broken tunnel can prevent `DELETE /v1/sessions/...` from reaching
the server, so the old session may remain until its bounded server lifetime
expires.

1. Let the supervisor re-establish SSH, or restart the tunnel manually.
2. Verify unauthenticated liveness and authenticated readiness as described in
   the [client setup](ssh-tunnel-client-setup.md).
3. Choose **Stop** in the Extension to clear the old local route/session state.
4. Choose **Start** to create a new server session and one-use ticket.
5. Repeat the audible-tab smoke after a material server, key, origin, or network
   change.

## Teardown and revocation

Choose **Stop** in the Extension before stopping the tunnel so it can close the
Gateway session cleanly. Then stop the platform supervisor.

Linux systemd:

```bash
systemctl --user disable --now liveconv-tunnel.service
```

macOS launchd:

```bash
launchctl bootout gui/"$(id -u)" \
  ~/Library/LaunchAgents/dev.liveconv.tunnel.plist
```

Windows Task Scheduler:

```powershell
Stop-ScheduledTask -TaskName 'liveconv-tunnel'
Unregister-ScheduledTask -TaskName 'liveconv-tunnel' -Confirm:$false
```

For a foreground `ssh`, `autossh`, or PowerShell loop, use Ctrl-C. Verify that
no listener remains before considering teardown complete.

Linux:

```bash
ss -ltnp 'sport = :8765'
```

macOS:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Windows PowerShell:

```powershell
Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 `
  -ErrorAction SilentlyContinue
```

Use the alternate local port when applicable. Closing the tunnel does not erase
the token from `chrome.storage.session`; close all Chrome processes or remove
the unpacked Extension when client-side credential removal is required.

To revoke a client, remove only that client's line from the server account's
`authorized_keys`, terminate its existing SSH connection, and rotate the
Gateway token if that client knew it. Restarting the Gateway invalidates all
in-memory sessions. When retiring the route completely, also remove the client
private key and host-pin files, the supervisor definition, and the forwarding
account after confirming no other authorized client uses it.
