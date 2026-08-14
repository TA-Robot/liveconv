# EXP-265: speaker-condition calibrator direction screen

Status: completed auxiliary batch screen; exact calibrator closed

## Question

Did EXP-259's 192-value speaker-condition delta move its 314 broad outputs
toward the authorized Amitaro target in an independent ECAPA encoder, compared
with the exact frozen EXP-238 outputs?

## Decision boundary

The fixed content/corruption join found 314/314 changed WAVs and zero
candidate-added gross rows. Exact jointly stable rows were mostly ASR ties:
fresh48 had two improvements and no losses, Hadou31 and JSUT24 were exact ties,
stress60 had one loss, and expanded144 had two losses. Decoder instability rose
by four rows in total. This one batch diagnostic chooses only between:

- a consistent held-out target-speaker direction: retain EXP-259 as an unheard
  technical alternative because it changes speaker direction while leaving
  most content rows tied;
- flat, regressed, or broadly mixed direction: close the exact calibrator point
  because its small content/stability cost has no independent speaker benefit.

Do not infer naturalness, identity, prosody, emotion, or a perceptual winner.
Do not admit a delta, weight, LR, horizon, data, objective, or scope neighbor
from this metric.

## Result

Commit `f97f956` embedded 943 unique WAV identities across 314 paired rows.
Aggregate target-to-output cosine moved `0.492870 -> 0.492741`, delta
`-0.000129`, with 151 increases and 163 decreases. Target-over-source
advantage moved `-0.000168`. External7, Hadou31, and expanded144 had tiny
positive mean target deltas; fresh48, stress60, and JSUT24 had tiny negative
deltas. This is flat and broadly mixed rather than a held-out speaker
direction.

Report SHA-256 is
`450edcf9681f006167142d8957c46e9dc8974e8d6fff36bab54a6c21de2b43c4`.
Combined with four additional decoder-unstable rows and three content losses
on the strict broad join, this closes the exact EXP-259 calibrator. It does not
select an audible winner or authorize an adjacent calibrator point.

## Command

```bash
HF_HUB_OFFLINE=1 artifacts/shared/speaker/runtime/bin/python \
  tools/xvc-source-diversity/screen_speaker_fit.py \
  --surface-plan experiments/EXP-265-xvc-speaker-condition-fit-direction/surface-pairs.json \
  --target-manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --model-artifact artifacts/shared/speaker/ecapa-runtime-model \
  --model-sha256 8addaeebdfb312b55d9f7c020f4e6529c65ce4e4fb0772af40398a66b9aa6ea8 \
  --device cuda \
  --output artifacts/xvc-source-diversity/exp265-speaker-condition-fit-direction-v1/speaker-fit-screen.json
```
