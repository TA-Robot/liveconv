# ADR-0001: Evaluation-first hybrid architecture

Status: Accepted

Date: 2026-08-08

## Context

The observed Japanese quality problem may arise from several independent causes:
timbre, source prosody, pronunciation, text normalization, phrase commitment, or
playout behavior. A timbre-only voice converter and an external TTS pipeline
solve different subsets and have different latency and interruption costs.

Selecting one model before measuring these causes would entangle product
requirements with a vendor or research implementation.

## Decision

Build a shared evaluation and routing foundation that compares three conditions:

1. native realtime audio with an improved Japanese prompt
2. streaming voice conversion of the native audio
3. committed text normalized and rendered through external Japanese TTS

Keep model implementations behind adapters. Implement the audio loopback and
measurement path before integrating a model. Promote a candidate only through a
phase gate with reproducible evidence.

## Consequences

### Positive

- Separates voice similarity from Japanese pronunciation and conversation flow.
- Produces a permanent baseline for future models.
- Makes latency, interruption, and audio defects first-class outcomes.
- Reduces the cost of replacing a model.

### Negative

- Requires more initial harness work before a polished voice demo.
- Maintains two experimental paths for several phases.
- Requires careful fixture and state management.

## Rejected alternatives

- **Choose a VC model immediately:** fast to demo but may preserve the source
  Japanese defects and cannot establish causality.
- **Replace all audio with TTS immediately:** improves reading control but hides
  the full-duplex and interruption cost.
- **Train a custom Japanese voice first:** expensive before requirements and
  evaluation data are stable.

## Revisit condition

Revisit after the baseline, router, first VC, and first TTS experiments have
comparable Japanese-quality and conversational-latency results.
