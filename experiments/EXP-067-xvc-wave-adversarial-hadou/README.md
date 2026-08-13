# EXP-067: waveform-adversarial X-VC on 31 clean Hadou sentences

Status: evaluation policy ready before candidate training

Render EXP-064 on the already-materialized, pre-training-frozen 31 Hadou
2.4-second windows against EXP-035. Compare machine transcripts only with the
exact source windows; official full-sentence text is listening context, not a
valid CER reference for a truncated window.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind wave-adversarial-hadou \
  --evaluation-set artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1/evaluation.json \
  --source-root artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1 \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp064-wave-adversarial-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp067-wave-adversarial-hadou31-v1 \
  --listener-dir artifacts/ms3/listening/exp067-wave-adversarial-hadou31-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
