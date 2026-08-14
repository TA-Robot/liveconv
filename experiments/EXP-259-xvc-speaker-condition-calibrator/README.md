# EXP-259: X-VC target-speaker condition calibration

Status: admitted one-point retraining lane; unheard and unselected

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
