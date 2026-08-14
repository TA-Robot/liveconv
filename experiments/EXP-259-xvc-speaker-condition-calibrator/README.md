# EXP-259: X-VC target-speaker condition calibration

Status: completed and technically closed; unheard and unselected

## Goal

Retain EXP-252's consistent held-out target-speaker direction without sending
the new speaker gradient through EXP-238's 835,584 content/converter LoRA
parameters. EXP-252 improved independent ECAPA target cosine on every fixed
surface but regressed fresh48/stress60 content and decoder stability.

## One change

Freeze the exact EXP-238 EMA adapter and every X-VC parameter. Insert one
zero-initialized 192-value additive calibration immediately before the target
speaker embedding enters the acoustic converter. Train only those 192 values
with the exact EXP-252 objective: complete source-aligned pseudoparallel
generative loss, real-Amitaro adversarial/feature loss, and weight-10
final-WAV frozen-ERes2Net cosine.

The original speaker embedding returned to X-VC's internal speaker predictor
loss is unchanged. The delta affects only the speaker condition consumed by
the six converter AdaLNs and final conditional normalization. Curriculum,
source-aligned targets, assigned authorized real targets, LR `1e-4`, one
sequential step per row, 170 updates, clip 5, zero frame condition,
discriminator, and EMA stay fixed. This is not a speaker7 rank/scope neighbor
or PCGrad point; it changes the conditioning input while leaving the frozen
converter maps exact.

## Gate

Run exact no-CUDA admission, a real two-row backward smoke proving only 192
parameters move, then one 170-update gpu0 lane. Publish external7 first. Admit
the existing five broad surfaces only if there is no candidate-added gross
corruption or clear external collapse.

Stop on nonfinite condition delta, wrong trainable count, initial EXP-238
identity drift, zero delta gradient, OOM, malformed sidecar reload, gross
corruption, or broad content regression. Do not vary delta dimension,
initialization, weight, LR, horizon, data, objective, or EMA.

## Run result

The real two-row CUDA smoke proved exactly 192 trainable values and moved the
delta L2 norm from `0.00138564` to `0.00227872`. The full 170-update run from
commit `09c2e88` completed in 131.43 seconds with 6,152,130,048 peak allocated
bytes. Training-row frozen ERes2Net target cosine moved
`0.285343 -> 0.409610`; that is a speaker-direction diagnostic, not audible
quality evidence. The EMA delta L2 norm is `0.03662478`, and its sidecar
SHA-256 is
`a06a58adb205d4fdccb4e22986e0be2f3f0a1933a57f299b4ca9270744e138b9`.

External7 produced seven changed WAVs with no candidate-added gross row. On
the six exact jointly stable/non-gross EXP-238-to-EXP-259 rows, auxiliary
source distance was an exact tie (`0.338675 -> 0.338675`). Per the 13:50 Grok
audit, this admits only the already frozen fresh48, Hadou31, stress60, JSUT24,
and expanded144 renders. It does not admit a delta/LR/weight/scope neighbor or
any keep/winner claim.

All five broad surfaces completed. Across exact EXP-238-to-calibrator rows
that were jointly decoder-stable and non-gross, source-relative content moved:
external7 exact tie (6 rows), fresh48 `0.244284 -> 0.240444` (2/37/0),
Hadou31 exact tie (26), stress60 `0.214202 -> 0.217547` (0/45/1), JSUT24
exact tie (22), and expanded144 `0.370777 -> 0.372631` (0/107/2). All 314
candidate WAVs changed, no candidate-added gross row appeared, and decoder
instability increased by four rows in total.

EXP-265's independent ECAPA batch was flat/mixed: aggregate target cosine
moved `0.492870 -> 0.492741` (`-0.000129`), with 151 wins and 163 losses;
target-over-source advantage moved `-0.000168`. Close the exact 192-value
calibrator because it did not reproduce EXP-252's independent speaker
direction and has a small stability/content cost. Do not tune its dimension,
initialization, loss weight, LR, horizon, data, or mutable scope.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_post_rehearsal.py \
  --training-manifest artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1/curriculum.json \
  --source-work artifacts/xvc-source-diversity/exp213-cross-corpus-unpaired-inputs-v1 \
  --diverse-work artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1 \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --initial-adapter artifacts/xvc-source-diversity/exp238-cross-corpus-pseudoparallel-ema-v1/adapter-170 \
  --trainable-target speaker-condition-calibrator \
  --training-objective pseudoparallel-generative-real-adversarial-condition-calibrator \
  --adapter-ema \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp259-speaker-condition-calibrator-v1 \
  --listener-dir artifacts/ms3/listening/exp259-xvc-speaker-condition-calibrator-external7-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
