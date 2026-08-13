# EXP-047: authentic anchor on changed utterances

Status: ready evaluation render; operator hearing deferred

EXP-046 regressed on the original seven external rows, but that small set
produced a false positive for EXP-044. The 14:20 Grok progress audit therefore
requires the combined twelve changed-utterance and ten fixed-condition screen
before another training method is selected.

This render changes no training state. It holds EXP-039's twelve sources,
base, control69, target, and seeds fixed, and substitutes only the EXP-046
authentic-anchor adapter. Machine output is corruption/content evidence only.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind authentic-anchor \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp046-authentic-anchor-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp047-authentic-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp047-xvc-authentic-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
