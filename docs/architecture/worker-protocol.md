# Private worker protocol version 1

Status: Accepted contract

Owner: primary integrator

This protocol isolates model dependencies and failure lifecycles from the public
gateway. It is private and does not change the Extension protocol. Version 1 uses
one supervised subprocess per loaded profile and newline-delimited UTF-8 JSON on
stdin/stdout. A later Unix-socket transport may replace it behind the supervisor.

## Process boundary

- The supervisor starts a new process group with an allowlisted environment.
- Stdout is protocol-only. Redacted diagnostics use stderr.
- Each JSON line is at most 16 KiB and contains exactly one object with no
  duplicate keys or non-finite numbers.
- PCM is mono float32 little-endian, base64 encoded, and limited to one negotiated
  20 ms frame per `audio.push` or `audio.output` message.
- Version 1 permits one active generation per process.
- The supervisor bounds queued input to the negotiated 500 ms budget.
- Artifact paths never cross stdout. Before spawn, the supervisor verifies every
  required artifact environment variable and its approved SHA-256 digest.

## Lifecycle

The supervisor sends `worker.hello` first:

```json
{"type":"worker.hello","worker_protocol_version":1,"rpc_id":1,"profile_id":"test.gain.v1","pipeline_id":"uuid","configuration_hash":"sha256"}
```

The process returns `worker.ready` with its immutable implementation and weight
identity. It must not accept audio before readiness. Handshake timeout is a worker
startup failure.

Control requests:

- `generation.start`: strictly increasing `generation_id`
- `generation.end`: drain accepted input without blocking supervisor control
- `generation.cancel`: invalidate pending output immediately
- `worker.health`: return readiness, active generation, queue depth, and capacity
- `worker.close`: release model state and terminate cleanly

Audio input includes `generation_id`, `sequence`, `sample_rate`, `channels`,
`samples_per_channel`, `source_monotonic_ns`, and `pcm_f32le_base64`. Output echoes
all timing and generation fields. Source timestamps may stay equal but never
decrease within a generation.

Worker events:

- `worker.ready`
- `audio.output`
- `generation.completed`
- `generation.canceled`
- `worker.health.result`
- `worker.error`
- `worker.closed`

Every control request and its result has an unsigned monotonic `rpc_id`. Audio
ordering uses `generation_id` and `sequence`. Unknown fields, message types,
versions, duplicate keys, invalid base64, non-finite PCM, and size mismatches are
fatal protocol violations.

## Failure semantics

- Gateway cancellation takes effect without waiting for the worker.
- A cancel acknowledgement has a bounded timeout. On timeout, the supervisor
  terminates the process group and reports `MODEL_TIMEOUT`.
- Unexpected exit reports `WORKER_CRASH`; unread output is discarded.
- First-output and stall deadlines come from the curated profile.
- After any fatal error, no output from the old process or generation is valid.
- Close waits for a bounded grace period, then sends terminate and finally kill.
- At most three automatic restarts are allowed in 60 seconds for one profile;
  exhaustion marks it unavailable until an explicit reload.

## Required conformance cases

The deterministic fake worker must support passthrough, gain, delayed, stalled,
crashed, malformed-output, and cancellation-race modes. Tests cover handshake,
round trip, output ordering, immediate cancel, asynchronous drain, queue overflow,
startup/first-output/stall timeout, crash recovery, restart exhaustion, artifact
digest mismatch, bounded close, and absence of orphan processes.

Real adapters cannot be selected until they pass the same conformance suite plus
their model-pack evidence gates.
