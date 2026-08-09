# Audio transformation validation

Status: Proposed for EXP-002 pilot

Passing STT or changing waveform samples is not sufficient evidence that voice
conversion worked. Each render receives four independent audio verdicts; a
streaming run adds a fifth operations verdict for routing and interruption.

## Evidence lanes

1. **Signal change:** input/output hashes, level-normalized waveform correlation,
   sample delta, log-spectral distance, duration, and alignment metadata.
2. **Content preservation:** STT revision, Japanese normalization revision, kana
   CER, insertions/deletions, and exact high-consequence entities compared with
   the known fixture reference.
3. **Speaker change:** source and authorized-target embedding distributions,
   calibrated on same-speaker and different-speaker pilot data.
4. **Integrity:** decode, finite samples, clipping, true peak, loudness, unexpected
   silence, duplicate regions, discontinuities, stale frames, and latency.
5. **Streaming operations (run only):** sequence/generation safety, cancellation,
   fallback, queue bounds, and same-clock latency accounting.

Waveform and spectrogram plots support diagnosis but do not replace metrics.
PESQ or STOI must not be a primary VC verdict because a correct speaker change
can look like distortion to an intrusive source-reference metric.

## Initial pilot guardrails

These values are hypotheses to freeze in an approved experiment, not claims or
permanent product requirements.

| Metric | Initial proposal |
|---|---:|
| Decode success | 100% |
| NaN or infinite samples | 0 |
| VC output/input speech duration | 0.90-1.10 |
| Full-scale consecutive clipping | 0 samples |
| True peak | <= -1 dBTP unless explicitly exempted |
| Loudness delta from source | <= 3 LU |
| New interior silence >= 150 ms | 0 regions |
| New repeated region >= 80 ms | 0 regions |
| Japanese kana CER | <= 10% |
| Paired CER degradation, bootstrap 95% upper bound | <= 3 percentage points |
| Telephone/address/ID exact match | 100% |
| High-consequence entity omissions | 0 |
| Accepted or played stale frames | 0 |

Speaker cosine thresholds are intentionally absent. Freeze them only after an
authorized pilot estimates within-speaker and between-speaker distributions for
the selected embedding model.

## Transformation verdict

A candidate is `changed` only when its sample and spectral differences exceed the
P99 distribution of identity, gain-only, and resample-only controls. That verdict
does not mean `voice_converted`.

A real VC profile is eligible for a positive experiment decision only when:

- signal change is detected
- content and integrity guardrails pass
- source similarity decreases and authorized-target similarity increases under
  a preregistered calibrated rule
- blinded Japanese ratings satisfy the experiment decision rule

Any missing speaker calibration or insufficient sample count yields
`inconclusive`, not `pass`.

## STT policy

- Compare source and transformed transcripts separately against known reference
  text; do not compare output only to possibly incorrect source STT.
- Record provider/model revision, decoding configuration, language, timestamps,
  and Japanese normalization revision.
- Preserve digits and identifiers in an operational exact-match lane even when a
  kana-normalized lane ignores punctuation or spacing.
- STT is an integrity proxy. It does not certify naturalness, prosody, or absence
  of all audio defects.

## Artifact flow

```text
fixture manifest + checksum
  -> native / passthrough / DSP controls / model profiles
  -> external render artifacts + frame traces
  -> STT + signal + speaker + integrity metrics
  -> schema-valid render records
  -> aggregate report and mechanical guardrail verdicts
  -> anonymized listening manifest
```

Raw and generated audio, speaker embeddings, and restricted transcripts stay in
authorized external storage. Git stores schemas, synthetic in-memory generators,
checksums, non-sensitive locators, aggregate reports, and decisions.

## Statistical note

The Phase 1 target of 200 turns can report an observed defect rate. It cannot
demonstrate a two-sided 95% upper confidence bound below 0.5% with zero defects;
roughly 600 eligible turns are needed for that stronger claim. Reports must state
whether a threshold applies to the point estimate or confidence bound.
