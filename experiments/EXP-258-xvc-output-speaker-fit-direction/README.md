# EXP-258: final-WAV speaker-fit direction screen

Status: completed auxiliary screen; no perceptual selection

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
  weight-10 LoRA69 lane and move the mutable function to the target-speaker
  conditioning input;
- flat, regressed, or broadly mixed ECAPA direction means the direct objective
  did not generalize reliably; close the objective and choose a different
  speaker-supervision formulation.

Do not sweep the speaker weight, encoder, data, horizon, scope, LR, or EMA.
ECAPA cannot measure naturalness, prosody, emotion, personal identity, or a
perceptual winner. The output remains auxiliary and unselected.

## Result

Commit `74b1c88` embedded 943 unique WAV identities across 314 paired rows.
Aggregate target-to-output cosine moved `0.492870 -> 0.500499`, delta
`+0.007629`, with 232 increases and 82 decreases. Target-over-source advantage
improved by `+0.007835`. Every surface improved its mean target cosine:
external7 `+0.012176`, fresh48 `+0.006355`, Hadou31 `+0.007691`, stress60
`+0.007762`, JSUT24 `+0.007358`, and expanded144 `+0.007810`.

Report SHA-256 is
`14e06ed6bb28f9359bfc514a4f55c3b85d8727ce20fb60c5a0b0a36df7c8b54f`.
Combined with EXP-252's mixed content result, this selects a conditioning-path
method, not another loss weight or symmetric gradient projection. EXP-228
already closed neighboring optimizer surgery. No audible winner is claimed.

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
