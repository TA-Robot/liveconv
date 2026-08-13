# EXP-061: filtered-pair X-VC on changed Common Voice utterances

Status: completed; changed-utterance content screen regressed

Render EXP-060 on the frozen twelve changed utterances from six heldout Common
Voice speakers. Base, EXP-035 control69, sources, target reference, and seeds
remain fixed. This is a corruption screen, not a naturalness or identity score.

The candidate published 36 comparison WAVs with no gross repetition. Against
control69, mean source-relative distance regressed from 0.184 to 0.222; the
secondary full-text distance changed only from 0.576 to 0.573. This is a
technical non-improvement, not a perceptual-quality judgment.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind content-filtered6x2 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp060-content-filtered6x2-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp061-content-filtered-new-v1 \
  --listener-dir artifacts/ms3/listening/exp061-content-filtered-new-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
