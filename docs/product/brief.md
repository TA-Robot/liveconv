# Product brief

Status: Draft

## Problem

Realtime AI voice can preserve conversational flow while still sounding
unnatural in Japanese. Typical failure modes include pitch accent, mora timing,
phrase boundaries, sentence-final intonation, numbers, addresses, identifiers,
and domain-specific names. Changing timbre alone may reproduce those defects in
a different voice.

The project needs to determine which defects can be improved without losing the
full-duplex qualities that make realtime conversation useful.

## Initial users

1. A developer evaluating ChatGPT Web audio in a personal Chrome proof of
   concept.
2. A product team evaluating a supported Realtime API architecture.
3. A contact-center team that needs intelligible Japanese readings, controlled
   pronunciation, interruption, and observable latency.

The personal Web proof of concept and a production contact-center system are
different products. The former may use tab capture and temporary DOM-derived
text; the latter must use supported APIs and application-owned state.

## Desired outcomes

- Natural and intelligible standard Japanese across ordinary conversation and
  operational utterances.
- Explicit control over target voice when the reference is authorized.
- Fast response start and reliable interruption.
- Reproducible evidence that separates voice quality from conversational quality.
- A model-independent architecture that can compare candidates without rewriting
  the whole audio path.

## Candidate modes

### Mode A: Streaming voice conversion

Capture the existing realtime output audio and convert timbre or style before
playout. This path may preserve response timing, but a timbre-only model can
retain the source prosody and pronunciation defects.

### Mode B: External Japanese TTS

Consume committed response text, normalize it for speech, and synthesize new
audio. This path can control readings and phrasing, but it introduces text
commit, synthesis, queue, and interruption complexity.

### Mode C: Native baseline

Use the original realtime voice with a carefully specified Japanese prompt. This
is the control condition and remains the fallback path.

## Product principles

- Evaluate before selecting a model.
- Preserve bypass and interruption before optimizing quality.
- Separate display text from spoken text.
- Prefer deterministic rules for high-consequence readings.
- Make latency and audio quality observable at every boundary.
- Store the minimum sensitive audio needed for the shortest practical period.
- Require authorization and provenance for every target voice.

## Non-goals for the first proof of concept

- Training a foundation speech model from scratch
- An unattended impersonation or voice-cloning service
- Production dependence on ChatGPT DOM structure
- A broad model marketplace
- Multi-tenant billing, user management, or long-term recording storage
- Declaring a universal best Japanese TTS or VC model

## Open product questions

- Which Japanese defects dominate perceived quality for the target workflow?
- Is timbre control required for the first useful milestone, or is natural
  pronunciation alone sufficient?
- What maximum added latency remains acceptable in real conversations?
- Which audio data may be retained for evaluation, and under what consent model?
- Which production integration target is first: personal tool, internal demo, or
  contact-center application?
