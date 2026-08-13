# EXP-048: authentic anchor on frozen audio conditions

Status: ready evaluation render; operator hearing deferred

This is the condition half of the combined post-EXP-046 gate requested by the
14:20 Grok audit. It renders six clean cross-speaker rows plus frozen tempo,
pitch, 20 dB noise, and leading-silence rows. Base, EXP-035 control69, sources,
target, and seeds stay fixed; the only candidate is EXP-046 authentic-anchor.

Do not select naturalness, target voice, or a winner by machine. Replan one
loss/conditioning/learning-target method only after EXP-047 and EXP-048 are
both screened.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_conditions.py \
  --candidate-kind authentic-anchor \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp046-authentic-anchor-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp048-authentic-conditions-v1 \
  --listener-dir artifacts/ms3/listening/exp048-xvc-authentic-conditions-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
