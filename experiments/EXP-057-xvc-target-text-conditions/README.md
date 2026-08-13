# EXP-057: target275 on frozen audio conditions

Status: ready evaluation render; operator hearing deferred

Render EXP-055 on the frozen six clean plus tempo, pitch, 20 dB noise, and
leading-silence conditions. Base, EXP-035 control69, sources, target, and seeds
stay fixed. Machine diagnostics are content/corruption evidence only.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_conditions.py \
  --candidate-kind target275 \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp055-target275-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp057-target275-conditions-v1 \
  --listener-dir artifacts/ms3/listening/exp057-xvc-target275-conditions-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
