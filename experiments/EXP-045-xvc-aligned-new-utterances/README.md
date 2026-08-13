# EXP-045: aligned conditions on new heldout utterances

Status: ready evaluation render; operator hearing deferred

## Question

Does EXP-044's strong non-corrupt seven-speaker result survive twelve different
utterances from six of the same heldout speakers?

No training occurs. This reuses EXP-039's frozen source windows, base X-VC,
EXP-035 control69, target reference, seeds, and render path. Only the candidate
adapter is EXP-044 alignment-preserving condition augmentation.

## Done and stop

- Publish twelve base/control69/aligned-condition rows on port 8878.
- Record source-window-relative ASR and gross repetition. A clear regression
  closes this method; otherwise render it once on the frozen ten audio
  conditions.
- Do not select naturalness, target voice, or a product winner by machine.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind aligned-conditions \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp044-aligned-augmentation-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp045-aligned-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp045-xvc-aligned-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
