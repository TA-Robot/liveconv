# ADR-0002: Remote generation-bound model router

Status: Accepted

Date: 2026-08-09

## Context

The Chrome Extension must send captured conversation audio to this GPU server,
receive transformed audio, and compare multiple model candidates without changing
its transport contract for every model. A remote failure must never remove the
user's ability to hear the native conversation.

Model repositories have incompatible Python, CUDA, weight, license, sample-rate,
and lifecycle assumptions. Loading them into the public gateway would couple
transport safety to model behavior and make cross-model experiments unreliable.

## Decision

Build an authenticated HTTP/WebSocket gateway behind a protected transport with
four boundaries:

1. The Extension owns capture, the always-available native path, exclusive final
   playout, stale-frame rejection, and emergency fallback.
2. The gateway owns authentication, session negotiation, generation state,
   bounded flow control, protocol validation, model-profile selection, and trace
   metadata. It never owns final user playout.
3. A curated profile registry maps stable public profile IDs to immutable model,
   weight, configuration, license, and resource records.
4. Each real model runs in an independently supervised worker process or
   container behind a private worker protocol. Model libraries and weight paths
   never load into or leak through the public gateway.

A selected `pipeline_id` is immutable for one generation. Switching a model is
legal only while no generation is active. Mid-utterance switching and crossfade
are excluded from protocol version 1.

Protocol version 1 uses authenticated HTTPS for session creation and a
single-use short-lived WSS ticket when the Gateway is network-reachable. The
personal loopback plus SSH deployment exception is defined by ADR-0003. Both
transports carry the same JSON control messages and binary little-endian float32
PCM frames with a fixed 32-byte network-order header. The initial negotiated
format is mono 48 kHz with 20 ms frames. Codec transport is a later independent
experiment.

## Safety rules

- A cancel gates old output in the Extension immediately; no server response is
  required for safety.
- `generation_id` strictly increases and is never reused in a session.
- A queue overflow, sequence gap, worker crash, stall, or authentication failure
  invalidates the transformed generation and requests local fallback.
- After `fallback.required`, no output for that generation is valid.
- Native and transformed audio are never intentionally mixed outside a future
  explicit comparison mode.
- Client and server monotonic clocks have different `clock_id` values and are
  never directly subtracted.

## Consequences

### Positive

- Model integrations are replaceable and dependency-isolated.
- Extension behavior remains stable while candidates change.
- Local fallback survives gateway and worker failures.
- Every render can bind an immutable profile, code revision, weight digest, and
  configuration hash.
- Deterministic passthrough and DSP profiles can validate the complete system
  before a research model is trusted.

### Negative

- Worker supervision and profile lifecycle add infrastructure before the first
  polished model demo.
- Uncompressed PCM uses more bandwidth than an audio codec.
- Model switching waits for a generation boundary.
- The personal ChatGPT Web proof of concept needs a temporary, fallible way to
  infer generation boundaries; production must receive them from an
  application-owned supported API integration.

## Rejected alternatives

- **Load every model in the gateway:** simpler initially, but one dependency or
  CUDA failure can break every session and prevent clean license isolation.
- **Let the server own native fallback:** remote failure would also break the
  fallback path.
- **Expose raw model names and parameters to the Extension:** couples the public
  protocol to research implementations and permits unreviewed configurations.
- **Switch models per frame:** cannot provide coherent model state, cancellation,
  or interpretable experiment evidence.
- **Use waveform difference as the conversion verdict:** gain, phase, or
  resampling can change samples without changing speaker identity.

## Validation

Before a real VC adapter is eligible, the same contract must pass:

1. byte-preserving passthrough transport
2. deterministic DSP transformation and model switching
3. cancellation, sequence, overflow, worker-failure, and fallback tests
4. signal-change, integrity, STT-content, and authorized speaker-evidence lanes
5. the approved experiment's latency and quality decision rule

The exact contract is defined in `docs/architecture/remote-protocol.md`.
