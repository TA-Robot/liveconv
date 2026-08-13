# EXP-054: source-path scope on frozen audio conditions

Status: ready evaluation render; operator hearing deferred

This is the condition part of EXP-052's mandatory combined gate. It renders six
clean cross-speaker rows plus fixed tempo, pitch, 20 dB noise, and leading-
silence rows. Base, EXP-035 control69, sources, target, and seeds stay fixed;
the only candidate is EXP-052 source36.

Use machine diagnostics only for content corruption and gross repetition.
Replan a single genuinely different training method only after the seven-row,
EXP-053 twelve-row, and EXP-054 ten-condition evidence is complete.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_conditions.py \
  --candidate-kind source36 \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp052-source36-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp054-source36-conditions-v1 \
  --listener-dir artifacts/ms3/listening/exp054-xvc-source36-conditions-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
