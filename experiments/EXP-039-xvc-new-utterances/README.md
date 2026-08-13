# EXP-039: same-speaker, new-utterance X-VC evaluation

Status: ready evaluation render; operator hearing deferred

## Question

Does EXP-038's external content improvement survive when the speakers stay
familiar to the evaluation but their utterances, lengths, and sentence types
change?

The first external set had seven speakers but only one utterance per speaker.
This set adds twelve new utterances from six of those speakers at the exact
Common Voice revision already in use. Durations range from 2.184 to 9.612
seconds; X-VC receives the first 2.4-second window, right-padding only the one
shorter item. The admission ASR for every chosen window is non-empty and at
least seven normalized characters.

Full reference sentences are retained as provenance, but most audio exceeds
the model window. The decision-relevant machine diagnostic is therefore
distance from each output to ASR of its own frozen source window, not distance
to the untruncated sentence. This screens corruption; it cannot rank voice
quality.

## Done and stop

- Render base, EXP-035 control69, and EXP-038 speaker7 on all twelve rows.
- Publish 36 candidates on `http://127.0.0.1:8878/`.
- Record source-relative content/repetition by row and aggregate. Then decide
  whether speaker7 merits the already-frozen ten-condition render.

No training, product selection, or perceptual winner is part of EXP-039.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --evaluation-set experiments/EXP-039-xvc-new-utterances/inputs.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp038-speaker7-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp039-new-utterances-v1 \
  --listener-dir artifacts/ms3/listening/exp039-xvc-new-utterances-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
