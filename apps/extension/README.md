# liveconv Chrome Extension

This directory is a loadable Chrome 116+ Manifest V3 extension. The service
worker owns explicit session lifecycle and authenticated HTTP session creation.
The Offscreen Document owns the tab `MediaStream`, WebSocket, `AudioContext`, and
AudioWorklets, so PCM never crosses extension runtime messaging.

## Local browser run

1. Start the audio gateway with its API token and set
   `LIVECONV_ALLOWED_ORIGINS` to the unpacked extension's actual
   `chrome-extension://<id>` origin.
2. Open `chrome://extensions`, enable Developer mode, and load this directory as
   an unpacked extension.
3. Open the popup, enter the gateway origin, profile, and development token, then
   choose **Save session**. Chrome grants only that gateway host at runtime.
4. On the tab whose audio should be routed, open the popup and choose **Start**.
   Choose **Stop** before changing configuration or selecting another tab.

For a Gateway running on another machine, keep the Gateway bound to remote
loopback and forward it to client loopback with OpenSSH. The complete server,
tunnel, client verification, reconnect, and troubleshooting procedure is in
[`docs/development/ssh-tunnel-client-setup.md`](../../docs/development/ssh-tunnel-client-setup.md).
The Extension Gateway origin remains `http://127.0.0.1:<local-forward-port>`;
both HTTP and WebSocket traffic cross the same tunnel.

The bearer credential is stored only in `chrome.storage.session`. The one-use
WebSocket ticket exists only in memory while the Service Worker passes it to the
Offscreen Document. Neither value is returned by status messages.

Native and remote samples share one delayed AudioWorklet playout head. The
bounded 200 ms native shadow lets each quantum fall back locally without moving
backward on the captured source timeline; remote PCM replaces native PCM only
when its echoed source frame aligns with that same playhead.

The popup exposes the supported manual generation lifecycle: End performs a
bounded drain, Interrupt invalidates local remote playout before cancellation is
acknowledged, and Next starts the next strictly increasing generation. Automatic
conversation boundaries require a future supported application or Realtime API
contract and are not inferred by DOM scraping.

## Checks

```bash
npm test
```

The Node suite covers Chrome API command ordering, native-first failure paths,
exclusive gains, generation cancellation, protocol framing, and Worklet buffer
behavior. An installed-Chrome run is still required to verify real
`tabCapture`/Offscreen user activation, device scheduling, audible continuity,
and the gateway Origin/TLS handshake.

With a Chrome remote-debugging endpoint running on port 9337, verify unpacked
registration, Service Worker startup, popup rendering, and popup-to-worker status
messaging with:

```bash
npm run smoke:chrome -- http://127.0.0.1:9337
```
