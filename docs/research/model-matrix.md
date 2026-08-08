# Candidate model matrix

Status: Working hypothesis

This file is a research queue, not a claim that any model is suitable. Before an
experiment, `research_scout` must verify the current official repository, model
card, paper, license, revision, supported languages, sample rate, streaming
contract, hardware, and benchmark definition.

| Candidate | Path | Why evaluate | Primary unknown | Planned experiment |
|---|---|---|---|---|
| Native realtime voice plus Japanese prompt | Baseline | Lowest integration cost and preserves conversation behavior | How much pronunciation and prosody improve without audio replacement | EXP-001 |
| MeanVC2 | VC | Working low-latency, lightweight streaming candidate from prior research | Japanese quality, source-prosody retention, reproducible end-to-end latency | EXP-003 |
| X-VC | VC | Codec-space streaming comparison candidate | Japanese evidence and deployability | Later |
| Qwen3-TTS 0.6B CustomVoice | TTS | Working first external-TTS candidate with voice control | Current availability, license, Japanese readings, commit-to-audio latency | EXP-004 |
| Fun-CosyVoice 3 | TTS | Alternate streaming and zero-shot comparison | Japanese pronunciation controls and operational complexity | EXP-005 |
| MOSS-TTS-Nano | TTS | Potential CPU or browser-side path | Current browser runtime, quality, redistribution terms | Later |
| Sarashina TTS family | Evaluation reference | Japanese reading-focused comparison from prior research | Current model/license suitability and benchmark use | Later |

## Evidence checklist

For every candidate, capture:

- canonical URL and immutable revision
- release and last-update dates
- code, weights, and data licenses separately
- commercial-use and redistribution constraints
- training or reference-voice consent implications
- supported Japanese evidence and exact evaluation set
- parameter count, precision, sample rate, and channels
- required input context and chunk size
- first-packet, algorithmic, and steady-state latency definitions
- hardware and runtime used for published numbers
- streaming state, cancellation, and batching behavior
- voice, timbre, style, accent, and emotion controls
- known artifacts and failure cases

## Decision rule

Published benchmark numbers may prioritize an experiment but cannot satisfy a
phase gate. Only measurements from the project's frozen harness count as project
results.
