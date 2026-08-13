# EXP-049: doubled semantic reconstruction loss

Status: ready method pilot; operator hearing deferred

## Question

Does increasing the content-preservation objective reduce X-VC's external
pronunciation corruption while retaining its waveform and speaker objectives?

The combined 7 + 12 + 10 gate closed source augmentation and authentic-source
mixing. EXP-049 returns to EXP-035's twelve synthetic donors, 87 targets, all-
standard roles, 1,044 updates, control69 LoRA, `1e-4`, seed, and zero target
condition. It changes only X-VC's semantic SSL reconstruction loss weight from
1000 to 2000. Mel stays 15, speaker similarity 10, and VQ 1; no quality term is
removed.

## Done and stop

- Train exactly 1,044 fresh-base updates and publish seven external rows.
- Regardless of the seven-row result, reuse the twelve changed utterances and
  ten frozen conditions before the method decision.
- Machine diagnostics reject corruption only. They do not rank naturalness,
  target voice, or a product winner.
- Do not sweep another loss multiplier from this result.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy semantic2x --lora-scope control69 \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --predecessor-result artifacts/xvc-source-diversity/exp035-cv12-v1/result.json \
  --predecessor-pseudo-root artifacts/xvc-source-diversity/exp035-cv12-v1/generated-source-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp049-semantic2x-v1 \
  --listener-dir artifacts/ms3/listening/exp049-xvc-semantic2x-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
