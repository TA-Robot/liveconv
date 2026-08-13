# EXP-053: source-path scope on changed utterances

Status: ready evaluation render; operator hearing deferred

This is the changed-utterance part of EXP-052's mandatory combined gate. It
reuses twelve fixed Common Voice utterances from six held-out speakers, base
X-VC, EXP-035 control69, target reference, and seeds. Only the candidate adapter
changes to EXP-052 source36.

The machine screen may reject gross content corruption or repetition. It may
not select naturalness, target identity, or a product winner. Do not replan from
the seven external rows; EXP-054 must also finish.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind source36 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp052-source36-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp053-source36-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp053-xvc-source36-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
