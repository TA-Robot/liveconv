# EXP-037: content-safe X-VC target frame context

Status: render admission before retraining; operator hearing deferred

## Question

Can X-VC use its upstream target frame-conditioning path on the disjoint
Common Voice evaluation without content corruption, before spending a full
1,044-update context-aware retrain?

All prior local fine-tuning and inference passed an all-zero
`target_wav_cond`. Upstream masked inference instead supplies target reference
audio followed by a zeroed 2.4-second current window. This pilot uses Amitaro
`EMOTION100_009` as a separate context utterance, while preserving
`EMOTION100_003` as the target speaker/reference waveform. The context therefore
cannot leak the current source text.

## Admission render

- Same frozen seven Common Voice speakers used by EXP-035/036.
- Same EXP-035 all-standard adapter and inference seeds.
- Two arms only: all-zero condition and separate-target-context plus a zeroed
  current window.
- No training. Stop if contextual inference introduces an empty output, gross
  repetition, or clear aggregate content regression.

If admitted, the successor retrains the exact EXP-035 generated pairs for
1,044 all-standard updates, changing only the target condition policy. Machine
ASR remains a content/corruption screen and cannot select naturalness or voice
quality.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_context.py \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp037-context-render-v1 \
  --listener-dir artifacts/ms3/listening/exp037-xvc-context-render-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
