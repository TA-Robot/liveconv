# EXP-042: reconstruction20 on frozen audio conditions

Status: ready evaluation render; operator hearing deferred

## Question

Does EXP-040's target-preserving reconstruction mixture improve robustness to
conditions outside the clean generated-pair training path without introducing
gross content corruption?

No training occurs. EXP-033's ten frozen rows cover six clean cross-speaker
sources plus tempo, pitch, 20 dB noise, and leading silence. Base X-VC, source
audio, target reference, seeds, and render path stay fixed. The comparison is
EXP-035 all-standard control69 versus EXP-040 reconstruction20.

## Done and stop

- Publish ten base/control69/reconstruction20 rows on port 8878.
- Record source-relative ASR and gross repetition by condition.
- Close reconstruction20 if it clearly regresses overall or fails to improve
  the existing noise weakness. Otherwise retain it only as an unheard
  candidate; no machine metric selects naturalness or target-voice fit.
- Replan the next X-VC training method after this single render.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_conditions.py \
  --candidate-kind reconstruction20 \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp040-reconstruction20-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp042-reconstruction-conditions-v1 \
  --listener-dir artifacts/ms3/listening/exp042-xvc-reconstruction-conditions-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
