# EXP-071: decoder-interface X-VC on 31 clean Hadou sentences

Status: frozen; waiting for EXP-068

Render EXP-068 on the already-materialized 31 Hadou 2.4-second windows against
EXP-035. Compare machine transcripts with the exact source windows. Official
full-sentence text is listening context and is not a valid CER reference for a
truncated window. This set is broader than the misidentified tongue-twister
artifact and does not represent retained ChatGPT browser audio.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind output2-hadou \
  --evaluation-set artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1/evaluation.json \
  --source-root artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1 \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp068-output2-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp071-output2-hadou31-v1 \
  --listener-dir artifacts/ms3/listening/exp071-output2-hadou31-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
