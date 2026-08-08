# Architecture overview

Status: Proposed

## Design goal

Create one observable routing layer that can compare native audio, streaming
voice conversion, and external TTS while keeping model-specific behavior behind
adapters.

## Personal Web proof of concept

```text
ChatGPT tab
    |
    | tabCapture after explicit user action
    v
Chrome MV3 Extension
    |- service worker: lifecycle and permissions
    |- offscreen document: long-lived media graph
    |- AudioWorklet: frame capture and playout
    |- mode controller: native / VC / TTS / bypass
    |- bounded jitter buffer
    |
    | authenticated binary WebSocket for audio
    v
Audio gateway
    |- session and generation state
    |- timestamped input/output frames
    |- reference and voice registry
    |- VC adapter
    |- TTS adapter
    |- normalization service
    |- metrics and traces
    v
Authorized model runtime
```

DOM-derived response text is an explicitly temporary input for the personal
proof of concept. It must not become the production contract.

## Production direction

```text
Application UI
    |- microphone and playout
    |- application-owned conversation state
    |- interruption controller
    |
    +--> supported realtime API transport
    |
    +--> committed text
           -> deterministic Japanese normalization
           -> external TTS adapter
           -> application-owned playout queue
```

Production must know what audio was actually played. Generated text, committed
text, synthesized audio, and played audio are distinct states.

## Core state

Every session carries:

```text
session_id
generation_id
mode
input_sample_rate
output_sample_rate
voice_id
style_id
capture_started_at
```

Every audio frame carries at least:

```text
session_id
generation_id
sequence
capture_timestamp
sample_rate
channels
sample_format
payload
```

The exact wire encoding is deferred until the router experiment. The semantic
fields are stable enough to build tests around.

## Generation lifecycle

```text
idle -> capturing -> generating -> playing -> completed
                    |             |
                    +-> canceled <-+
```

When a new generation begins or interruption occurs:

1. increment `generation_id`
2. cancel model or synthesis work when supported
3. clear not-yet-played frames for older generations
4. reject late frames whose generation ID is stale
5. preserve the native bypass path

## Adapter boundary

Adapters expose capabilities rather than model names:

```text
prepare_voice(reference_metadata) -> voice_id
start_session(session_config) -> adapter_session
push_audio(frame) -> zero or more output frames
push_text(committed_spoken_text) -> zero or more output frames
cancel(generation_id)
close()
health()
```

An adapter declares supported sample rates, minimum context, streaming behavior,
voice preparation, style control, cancellation, and licensing constraints.

## Buffering rules

- Capture, network, model, and playout buffers are measured separately.
- Queues are bounded by time, not only by item count.
- Overflow behavior is explicit: drop stale generation, degrade to bypass, or
  stop with a visible error.
- Crossfade may conceal a boundary but must not reorder content.
- Warmup is separated from steady-state measurement.

## Spoken-text pipeline

```text
display text
  -> commit boundary
  -> deterministic normalization
  -> pronunciation dictionary
  -> spoken text segments
  -> TTS adapter
  -> playout accounting
```

The LLM may suggest phrasing, but critical number and identifier readings are not
delegated to an unconstrained model on the hot path.

## Security boundary

- The Extension never contains long-lived cloud credentials.
- Audio transport is authenticated and encrypted outside localhost.
- Reference voice authorization is checked before adapter preparation.
- Logs contain identifiers and timings, not raw text or audio by default.
- Large artifacts use an access-controlled store with retention rules.

## Deferred decisions

- Binary wire encoding and transport framing
- First VC model
- First external TTS model
- Voice registry persistence layer
- Cloud provider and GPU class
- Final text commit algorithm

Each deferred decision needs an experiment or ADR before implementation becomes
shared infrastructure.
