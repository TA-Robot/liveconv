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
3. Open the popup, enter the gateway origin and development token, choose
   **Load profiles**, select a verified compatible catalog profile, then choose
   **Save session**. Chrome grants only that gateway host at runtime.
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

The client accepts the real route's 25-frame/500 ms output batch into one bounded
staging budget and paces at most 10 frames/200 ms into the AudioWorklet. Capture
credits come from the session's negotiated ingress capacity and are replenished
only after the WebSocket client accepts a frame. Cold `generation.start` waits
up to 190 seconds while native remains audible; the popup reports the profile as
loading and returns to native fallback on timeout.

The popup exposes the supported manual generation lifecycle: End performs a
bounded drain, Interrupt invalidates local remote playout before cancellation is
acknowledged, and Next starts the next strictly increasing generation. A catalog
profile can be selected only after End or Interrupt, and its hashes are checked
across catalog, HTTP session creation, WSS attachment, selection, and generation
start. Automatic
conversation boundaries require a future supported application or Realtime API
contract and are not inferred by DOM scraping.

## EXP-005 Receipt

The popup has four collector-only messages, deliberately absent from the normal
UI: `exp005.trial.begin`, `exp005.trial.inject-failure`,
`exp005.trial.export`, and `exp005.trial.clear`. They
are accepted only when sent by the Extension popup itself. The producer compares
bounded PCM frames in Offscreen memory, then discards them before sending only
finite/changed facts to the service worker. Tickets, bearer values, media, tab
details, host names, and paths do not enter the receipt.

Before an actual run, open the unpacked Extension popup on the authenticated
`https://chatgpt.com` tab and keep it open. Begin the receipt with a frozen
trial JSON containing only `roster_revision`, `plan_revision`, and
`roster_entries`, plus the successful LV-049 preflight JSON. The collector uses
only a local Chrome DevTools endpoint and executes the message in that existing
popup target:

```bash
npm run collect:exp005 -- begin \
  --cdp-url http://127.0.0.1:9337 \
  --extension-id EXTENSION_ID \
  --trial /secure/operator/exp005-trial.json \
  --ssh-preflight /secure/operator/ms2-ssh-preflight-pass.json
```

Perform the four real trials through the normal popup controls. After the
OpenVoice attempt is terminal, choose Next once without changing the model,
then inject the dedicated fifth-generation failure probe:

```bash
npm run collect:exp005 -- inject-failure \
  --cdp-url http://127.0.0.1:9337 \
  --extension-id EXTENSION_ID
```

The injection command is accepted only for that active post-attempt OpenVoice
generation. A spontaneous Gateway fallback cannot satisfy the forced-failure
gate. Export is refused until all terminal runtime evidence is present and
the destination must be outside this repository:

```bash
npm run collect:exp005 -- export \
  --cdp-url http://127.0.0.1:9337 \
  --extension-id EXTENSION_ID \
  --output /secure/operator/exp005-runtime-receipt.json
```

Use `clear` to discard an incomplete receipt. This does not make an incomplete
or failed run pass; it only removes volatile Extension-side evidence.

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
