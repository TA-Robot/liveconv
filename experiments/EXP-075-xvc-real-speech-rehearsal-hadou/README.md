# EXP-075: real-speech rehearsal on 31 clean Hadou sentences

Status: frozen; waiting for EXP-072

Render EXP-072 on the same pre-training-frozen 31 Hadou 2.4-second windows.
These files are evaluation-only and never enter rehearsal. Compare ASR with the
exact source windows; full-sentence text is listening context only. This is not
the misidentified local tongue-twister or ChatGPT browser audio.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind real-reconstruction20-hadou \
  --evaluation-set artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1/evaluation.json \
  --source-root artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1 \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp072-real-rehearsal-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp075-real-rehearsal-hadou31-v1 \
  --listener-dir artifacts/ms3/listening/exp075-real-rehearsal-hadou31-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
