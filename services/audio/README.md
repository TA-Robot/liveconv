# liveconv audio gateway

This service implements the LV-020 gateway boundary for protocol version 1. It
loads the curated repository profile registry and exposes only ready
`passthrough` and `gain` builtin profiles. Each attached session runs conversion
through an isolated, supervised subprocess; cancellation and shutdown are
bounded and terminate the worker process group when cooperative cleanup fails.
TLS termination, GPU models, persistent sessions, and production identity are
intentionally out of scope.

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

## HTTP API

- `GET /health/live` is the only unauthenticated endpoint.
- `GET /health/ready` requires `Authorization: Bearer <token>`.
- `GET /v1/models` returns public capability metadata without runtime paths.
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

Each binary message is one protocol v1 input PCM frame. Accepted frames are
returned with `kind=OUTPUT`; passthrough preserves payload bytes and gain applies
the registry's deterministic factor. The gateway never runs conversion in its
shared thread executor. Gap, malformed active audio, worker timeout/crash, and
ingress overflow invalidate the transformed generation and emit both `error`
and `fallback.required`. Stale frames are rejected without damaging a newer
active generation.

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
