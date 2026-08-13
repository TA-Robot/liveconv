# EXP-056: target275 on changed utterances

Status: completed listen-now; operator hearing deferred

Render EXP-055 against the frozen twelve changed Common Voice utterances. Base,
EXP-035 control69, sources, target reference, and seeds stay fixed. Only the
candidate adapter changes. Machine ASR may reject corruption; it cannot select
naturalness, target identity, or a winner. EXP-057 and EXP-058 remain mandatory
regardless of this result.

The render completed twelve rows and published 36 candidates in 96.09 seconds.
No arm gross-looped. Target275 exactly matched control69's 0.184 source-relative
mean and 0.571 maximum; known-text mean moved from 0.576 to 0.559. This is coarse
content evidence only and does not select a quality winner.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind target275 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp055-target275-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp056-target275-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp056-xvc-target275-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
