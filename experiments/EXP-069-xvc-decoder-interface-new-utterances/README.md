# EXP-069: decoder-interface X-VC on changed Common Voice utterances

Status: completed; rejected changed-utterance content result

Render EXP-068 on the existing twelve changed utterances from six heldout
Common Voice speakers against the exact EXP-035 adapter. This is a
content/corruption screen only; it cannot select naturalness or identity.

All 36 model outputs avoided gross repetition, but output2 had zero wins, five
ties, and seven losses against control69. Mean source-relative distance worsened
from `0.184` to `0.375`, and the maximum worsened from `0.571` to `1.000`.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind output2 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp068-output2-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp069-output2-new-v1 \
  --listener-dir artifacts/ms3/listening/exp069-output2-new-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
