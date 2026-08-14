# EXP-258: final-WAV speaker-fit direction screen

Status: admitted auxiliary screen; no perceptual selection

## Question

Did EXP-252's final-WAV speaker loss move its 314 broad evaluation outputs
toward the authorized Amitaro target in an independent ECAPA encoder, compared
with the exact EXP-238 survivor?

## Decision boundary

EXP-252 increased its training-time frozen ERes2Net target cosine, while the
fixed ASR corruption surfaces were mixed: no new gross repetition, but fresh48
and stress60 regressed on their jointly stable rows and decoder instability
increased. This one batch diagnostic chooses the next method family:

- consistent ECAPA target-similarity and target-advantage improvement means the
  speaker objective reached held-out WAVs but conflicts with content; close the
  weight-10 lane and test one gradient-arbitration method from EXP-238;
- flat, regressed, or broadly mixed ECAPA direction means the direct objective
  did not generalize reliably; close the objective and choose a different
  speaker-supervision formulation.

Do not sweep the speaker weight, encoder, data, horizon, scope, LR, or EMA.
ECAPA cannot measure naturalness, prosody, emotion, personal identity, or a
perceptual winner. The output remains auxiliary and unselected.

## Command

```bash
HF_HUB_OFFLINE=1 artifacts/shared/speaker/runtime/bin/python \
  tools/xvc-source-diversity/screen_speaker_fit.py \
  --surface-plan experiments/EXP-258-xvc-output-speaker-fit-direction/surface-pairs.json \
  --target-manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --model-artifact artifacts/shared/speaker/ecapa-runtime-model \
  --model-sha256 8addaeebdfb312b55d9f7c020f4e6529c65ce4e4fb0772af40398a66b9aa6ea8 \
  --device cuda \
  --output artifacts/xvc-source-diversity/exp258-output-speaker-fit-direction-v1/speaker-fit-screen.json
```
