# liveconv audio gateway

This service implements the LV-020 gateway boundary for protocol version 1. It
loads a curated profile registry and dispatches only statically reviewed builtin
or model-worker registrations. Each attached session runs conversion through an
isolated, supervised subprocess; cancellation and shutdown are bounded and
terminate the worker process group when cooperative cleanup fails. Technical
GPU profiles require an explicit opt-in and retain their failed, unassessed, or
nonselectable evidence labels. Persistent sessions and public deployment
identity are intentionally out of scope for the personal SSH route.

## Run locally

Set the values documented in `.env.example`, then run from this directory:

```bash
uv run --extra test python -m liveconv_audio
```

The default bind is `127.0.0.1:8765`. Do not expose the development server
directly to a network. Production deployment requires reviewed TLS ingress.
Startup readiness requires an API token of at least 32 bytes with at least 16
distinct characters and exact Chrome Extension origins of the form
`chrome-extension://<32 lowercase a-p characters>`.

A trusted remote development client can reach this loopback listener through an
OpenSSH local forward without changing the bind address. Follow
[`docs/development/ssh-tunnel-client-setup.md`](../../docs/development/ssh-tunnel-client-setup.md);
do not publish port 8765 or bind it to `0.0.0.0` for that workflow.

For the MS-2 four-model lab, first build the external technical registry with
[`scripts/build-ms2-profile-registry.py`](../../scripts/build-ms2-profile-registry.py)
and provide the private model environment bindings documented by each adapter.
Set `LIVECONV_PROFILE_CONFIG` to that generated file,
`LIVECONV_ROSTER_CONFIG` to `config/model-roster.json`,
`LIVECONV_ALLOW_TECHNICAL_PROFILES=1`, and `LIVECONV_MAX_SESSIONS=1`.
The opt-in makes technical routes invocable for the personal trial; it does not
approve their quality, license, security, or release status.

For the first MS-3 voice-lab wave, fetch and verify the four official Amitaro
RVC styles, prepare their distinct profiles, and seal one deployment. Keep all
downloaded voices, private authorization records, and generated identity files
outside the repository:

```bash
MS3_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/liveconv/ms3-amitaro-rvc-v1"

uv run --frozen python scripts/fetch-ms3-rvc-amitaro.py \
  --output "$MS3_ROOT/candidates"

uv run --frozen python scripts/prepare-ms3-rvc-variants.py \
  --base-registry artifacts/rvc-v2/gateway-profile.json \
  --candidate-root "$MS3_ROOT/candidates" \
  --output "$MS3_ROOT/prepared"

uv run --frozen python scripts/fetch-ms3-openvoice-amitaro.py \
  --output "$MS3_ROOT/references"

uv run --frozen python scripts/prepare-ms3-openvoice-variants.py \
  --openvoice-identity-env artifacts/openvoice-v2/identity.env \
  --prepared "$MS3_ROOT/prepared" \
  --reference-root "$MS3_ROOT/references" \
  --output "$MS3_ROOT/prepared-six"

uv run --frozen python scripts/prepare-ms3-xvc-variants.py \
  --xvc-identity-env artifacts/x-vc/identity.env \
  --prepared "$MS3_ROOT/prepared-six" \
  --reference-root "$MS3_ROOT/references" \
  --output "$MS3_ROOT/prepared-eight"

uv run --frozen python scripts/build-ms3-deployment-bundle.py \
  "$MS3_ROOT/prepared-eight/draft.json" \
  "$MS3_ROOT/prepared-eight/authorization-registry.json" \
  "$MS3_ROOT/deployment"
```

Then use the same launcher for terminal preflight and the real Gateway. Pass
the retained RVC runtime identity and the generated variant identity; the
launcher parses literal
`LIVECONV_*` assignments without executing the files, removes Python path
overrides, validates the current authorization time and exact bundle/profile
identity, and runs a no-worker Gateway construction during `--check`.

```bash
uv run --frozen python scripts/run-ms3-gateway.py \
  --deployment "$MS3_ROOT/deployment" \
  --identity-env artifacts/rvc-v2/identity.env \
  --identity-env "$MS3_ROOT/prepared/identity.env" \
  --identity-env artifacts/openvoice-v2/identity.env \
  --identity-env "$MS3_ROOT/prepared-six/identity.env" \
  --identity-env artifacts/x-vc/identity.env \
  --identity-env "$MS3_ROOT/prepared-eight/identity.env" \
  --check

uv run --frozen python scripts/run-ms3-gateway.py \
  --deployment "$MS3_ROOT/deployment" \
  --identity-env artifacts/rvc-v2/identity.env \
  --identity-env "$MS3_ROOT/prepared/identity.env" \
  --identity-env artifacts/openvoice-v2/identity.env \
  --identity-env "$MS3_ROOT/prepared-six/identity.env" \
  --identity-env artifacts/x-vc/identity.env \
  --identity-env "$MS3_ROOT/prepared-eight/identity.env"
```

The API token and exact Extension origin stay in the caller's environment and
are never written into the generated directory. `--check` hashes every common
runtime artifact and every selected checkpoint/index before a worker or GPU is
started; do not launch the Gateway when it fails.

## HTTP API

- `GET /health/live` is the only unauthenticated endpoint.
- `GET /health/ready` requires `Authorization: Bearer <token>`.
- `GET /v1/runtime-boundary` returns the authenticated, non-secret loopback,
  one-use-ticket, and session-cap facts used by the MS-2 runtime receipt.
- `GET /v1/models` returns public capability metadata without runtime paths.
- `GET /v1/model-roster` returns the authenticated MS-2 four-model display
  roster. It separates execution state from decision evidence, includes only
  fixed reason codes, and never authorizes a session by itself.
- `GET /v1/deployment-manifest` returns the authenticated public projection of
  the active MS-3 bundle, or `404` when no bundle is active.
- `POST /v1/sessions` creates a session and returns one plaintext WSS ticket.
- `GET /v1/sessions/{session_id}` returns state without ticket material.
- `DELETE /v1/sessions/{session_id}` invalidates the session.

`POST /v1/sessions` uses the request contract from
`docs/architecture/remote-protocol.md`. The response includes `websocket_path`
(`/v1/ws`), a one-use `ticket`, `ticket_expires_in_seconds`, and negotiated queue
limits. The in-memory store retains only `sha256(ticket)`.

## WebSocket API

Connect to `/v1/ws` with an exact `Origin` listed in
`LIVECONV_ALLOWED_ORIGINS`. The first text message must be `session.attach` with
the one-use ticket. Subsequent text controls are `model.select`,
`generation.start`, `generation.end`, `generation.cancel`, `ping`, and
`session.close`.

`generation.end` has no immediate acknowledgement. It schedules a bounded
drain and eventually emits `generation.completed`; `generation.cancel` can
interrupt that drain and prevents a later completion event. Request IDs are
idempotent within a session, including state failures. The default hard bounds
are 64 concurrent sessions, a 30-minute session lifetime, and 1,024 cached
request IDs per session. Exceeding the request cache closes the session.

Each binary message is one protocol v1 input PCM frame. Live workers return
accepted frames with `kind=OUTPUT`; the bounded OpenVoice sample route withholds
candidate output until explicit `generation.end`. The gateway never runs model
conversion in its shared thread executor. Gap, malformed active audio, worker
timeout/crash, and ingress overflow invalidate the transformed generation and
emit both `error` and `fallback.required`. Stale frames are rejected without
damaging a newer active generation.

Application logs must never include bearer tokens, WSS tickets, raw audio,
payload-derived values, or raw text. This implementation does not log request or
audio bodies.

Uvicorn and the application boundary both reject WebSocket messages over 16
KiB. Runtime worker endpoints and private/path-like configuration keys are never
included in public profile identity.

## Test

```bash
uv run --extra test pytest
uvx ruff check .
uvx ruff format --check .
```
