# EXP-066: waveform-adversarial X-VC on frozen audio conditions

Status: evaluation policy ready before candidate training

Render EXP-064 on the ten clean/noise/leading-silence/tempo/pitch rows against
the exact EXP-035 adapter. This is a content/corruption screen only.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_conditions.py \
  --candidate-kind wave-adversarial \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp064-wave-adversarial-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp066-wave-adversarial-conditions-v1 \
  --listener-dir artifacts/ms3/listening/exp066-wave-adversarial-conditions-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
