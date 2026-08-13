# EXP-041: reconstruction20 on new heldout utterances

Status: ready evaluation render; operator hearing deferred

## Question

Does EXP-040's non-corrupt seven-row result survive EXP-039's twelve different
utterances from six of the same heldout speakers?

No training occurs. The only comparison change from EXP-039 is replacing the
rejected speaker7 adapter with EXP-040 reconstruction20. Base and EXP-035
control69, the source windows, target reference, seeds, and render path stay
fixed.

The decision-relevant machine diagnostic is source-window-relative content and
gross repetition. Most full Common Voice sentences exceed X-VC's 2.4-second
input window, so their full-text distance is reported only as context and
cannot reject a candidate.

## Done and stop

- Publish twelve base/control69/reconstruction20 rows on port 8878.
- Record the source-relative screen. A clear regression closes this role
  method; otherwise render it once on the frozen ten condition rows.
- Do not select naturalness, target voice, or a product winner by machine.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind reconstruction20 \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp040-reconstruction20-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp041-reconstruction-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp041-xvc-reconstruction-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
