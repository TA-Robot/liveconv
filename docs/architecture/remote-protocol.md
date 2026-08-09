# Remote audio protocol version 1

Status: Accepted contract

Owner: `packages/protocol`

This contract is model-independent. Model-specific controls exist only inside a
curated server profile and its immutable configuration hash.

## Topology

```text
Extension AudioWorklet
  -> local native route (always available, exclusively gated)
  -> WSS input PCM
       -> authenticated gateway
       -> session and generation router
       -> profile registry
       -> isolated model worker
  <- WSS output PCM
  -> generation gate -> bounded jitter buffer -> exclusive playout selector
```

Only the gateway is public. Worker ports, weight paths, model credentials, and
artifact storage are private.

## HTTP control plane

All `/v1` endpoints except liveness require an HTTPS bearer credential. The first
proof of concept may use one manually provisioned development credential stored
in Extension session memory, never bundled source or persistent sync storage.

```text
GET    /health/live
GET    /health/ready
GET    /v1/models
POST   /v1/sessions
GET    /v1/sessions/{session_id}
DELETE /v1/sessions/{session_id}
```

`POST /v1/sessions` accepts:

```json
{
  "protocol_version": 1,
  "profile_id": "test.passthrough.v1",
  "input": {
    "sample_rate": 48000,
    "channels": 1,
    "sample_format": "f32le",
    "frame_ms": 20
  },
  "voice_id": null
}
```

It returns a UUID `session_id`, UUID `pipeline_id`, negotiated immutable limits,
and an opaque one-use WSS ticket with a 30-second default expiry. The gateway
stores only a digest of the ticket. The client sends the ticket in the first WSS
control message so it does not enter a URL or proxy access log.

Production TLS terminates at a reviewed reverse proxy or load balancer. The
gateway checks the configured `chrome-extension://<extension-id>` Origin before
accepting WSS. Development defaults bind only to loopback.

## Model profiles

The public catalog exposes only reviewed capability metadata:

```json
{
  "profile_id": "test.gain.v1",
  "kind": "deterministic_test",
  "adapter_api_version": 1,
  "implementation_revision": "builtin-v1",
  "weight_revision": null,
  "streaming": true,
  "cancellation": "immediate",
  "input_sample_rates": [48000],
  "output_sample_rates": [48000],
  "frame_ms": 20,
  "voice_requirement": "none",
  "readiness": "ready"
}
```

Real profiles additionally bind a license record, immutable code revision, weight
digest, native sample rate, minimum context, warmup policy, resource class, and
timeouts. Filesystem paths, worker endpoints, credentials, and secret-like runtime
configuration are neither public fields nor inputs to a public profile hash.

## WSS attachment

The first message must arrive before the attachment timeout:

```json
{
  "type": "session.attach",
  "protocol_version": 1,
  "request_id": "01J...",
  "session_id": "uuid",
  "ticket": "opaque-secret"
}
```

The ticket is consumed once. Success returns `session.ready` with the active
profile, `pipeline_id`, limits, and server `clock_id`. Reuse returns
`AUTH_FAILED`.

## Control messages

Every post-attachment command includes `type`, `protocol_version`, `request_id`,
and `session_id`. Generation commands also include `generation_id`. The first
parsed outcome for a `request_id`, including a state-validation error, is cached
with the command fingerprint. Replaying the same command returns that outcome
without reapplying state; reusing the ID for a different command is rejected. The
cache is bounded. Exhaustion closes the session instead of evicting history and
allowing an old command to execute again.

Client messages:

- `model.select`: allowed only with no active generation; returns a new
  `pipeline_id`
- `generation.start`: binds a strictly increasing ID to the current pipeline
- `generation.end`: drains accepted input and completes normally
- `generation.cancel`: invalidates all unplayed output immediately
- `ping`: carries a client monotonic timestamp and `clock_id`
- `session.close`: closes workers and invalidates the ticket/session

Server messages:

- `session.ready`
- `model.selected`
- `generation.ready`, `generation.completed`, `generation.canceled`
- `fallback.required`
- `error`, `pong`

`model.loading` and `flow.credit` are deferred until the worker supervisor and
credit algorithm are frozen. They are not valid version 1 events in the current
strict server-event parser.

`model.select` never changes an active generation. The client must cancel or end
it first. A `pipeline_id` identifies the profile revision plus configuration and
is immutable for the generation.

`generation.end` starts an asynchronous bounded drain; it does not block the WSS
receive loop. A later `generation.cancel` is processed immediately and suppresses
`generation.completed`. A drain timeout, worker failure, or disconnected output
invalidates the generation and requires fallback.

## Binary PCM frame

Each WSS binary message is exactly one header plus one interleaved PCM payload.
Header integers are network byte order. Payload samples are little-endian
float32. Version 1 negotiates mono, 48 kHz, 20 ms, so a normal payload contains
960 samples and 3,840 bytes.

```text
offset  size  field
0       2     magic = 0x4c56 ("LV")
2       1     protocol_version = 1
3       1     kind: 1=input, 2=output
4       2     flags
6       2     header_length = 32
8       4     generation_id
12      4     sequence
16      4     sample_rate
20      2     channels
22      2     samples_per_channel
24      8     source_monotonic_ns
32      ...   PCM payload
```

The WSS connection implies `session_id`; the active generation implies
`pipeline_id`. Server output echoes `generation_id`, `sequence`, and the client's
source timestamp. Traces add separate server `{clock_id, monotonic_ns}` values.
Within one generation, `source_monotonic_ns` must not decrease. This detects a
client capture/order defect without comparing the client timestamp to server time.

## State machines

Streaming uses three orthogonal state machines:

```text
Transport: DISCONNECTED -> CONNECTING -> READY -> DEGRADED -> CLOSED
Route:     NATIVE -> REMOTE_PENDING -> REMOTE -> FALLBACK -> NATIVE
Generation:
  IDLE -> STARTING -> STREAMING -> DRAINING -> COMPLETED
                        |             |
                        +-> CANCELING -> CANCELED
                        `-> FAILED
```

The Extension gates output by current `generation_id` before jitter buffering.
Canceling locally does not wait for the server. WSS ordering does not replace
explicit duplicate, gap, and stale-generation checks.

## Initial experimental queue budgets

These are EXP-002 configuration values, not product targets:

| Boundary | Initial budget | Overflow behavior |
|---|---:|---|
| Extension uplink | 250 ms | cancel transformed generation, use native |
| Gateway ingress | 500 ms | `QUEUE_OVERFLOW`, require fallback |
| Worker input | 500 ms | terminate worker generation, require fallback |
| Extension jitter target | 80 ms | remain remote |
| Extension jitter maximum | 200 ms | require fallback |
| Session request history | 1,024 commands | close before accepting a new ID |
| Gateway sessions | 64 sessions | reject creation until capacity is released |
| Session lifetime | 30 minutes | invalidate the session and close its WSS |

Arbitrary speech frames are never discarded to make a stale queue appear
healthy.

The reference Uvicorn boundary caps each WebSocket message at 16 KiB before
application parsing. HTTP DELETE and terminal disconnect invalidate the attached
connection; after DELETE returns 204, no audio or control output from that session
is valid.

## Stable errors

Version 1 reserves:

```text
AUTH_FAILED
UNSUPPORTED_PROTOCOL
INVALID_STATE
MODEL_UNAVAILABLE
MODEL_TIMEOUT
QUEUE_OVERFLOW
SEQUENCE_GAP
STALE_GENERATION
UNSUPPORTED_AUDIO
WORKER_CRASH
```

Every error includes `recoverable` and `required_action`. After
`fallback.required`, output for that generation must be rejected even if it
arrives later.

## Adapter SPI

The process boundary and failure lifecycle are frozen in
`docs/architecture/worker-protocol.md`.

```text
describe() -> capabilities
prepare(session_config) -> adapter_session
push_audio(adapter_session, frame) -> async zero or more output frames
end_generation(generation_id)
cancel(generation_id)
close()
health() -> readiness and capacity
```

Adapters receive normalized PCM and timing metadata. They do not parse WSS,
authenticate users, select Extension UI state, or write raw audio to logs.
