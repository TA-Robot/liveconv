# EXP-073: real-speech rehearsal on changed Common Voice utterances

Status: completed; mixed worst-case reduction but mean regression

Render EXP-072 on the existing twelve changed utterances from six heldout
Common Voice speakers against EXP-035. None of these speakers is one of the
twelve real rehearsal donors. This is a content/corruption screen only.

No gross loop occurred. Against control69 the candidate had two wins, four
ties, and six losses; mean distance worsened `0.184` to `0.232`, while the
maximum improved `0.571` to `0.455`. This is not a robust rehearsal win.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind real-reconstruction20 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp072-real-rehearsal-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp073-real-rehearsal-new-v1 \
  --listener-dir artifacts/ms3/listening/exp073-real-rehearsal-new-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
