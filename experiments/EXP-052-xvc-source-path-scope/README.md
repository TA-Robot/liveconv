# EXP-052: source-path-only LoRA

Status: ready method pilot; operator hearing deferred

## Question

Does excluding the frame-condition branch from adaptation improve X-VC
generalization when listen-now inference supplies a zero frame condition?

Control69 adapts 69 attention/FFN linears in the acoustic converter. Thirty-six
belong to the source/acoustic `x` path (`to_q/k/v`, `to_out`, and `ff_x`), while
the rest update the target-mel frame-condition `c` path. Training sees target
mel, but the current comparison route intentionally supplies an all-zero target
condition. EXP-052 changes only LoRA targets to those 36 source-path linears.

It restores EXP-035's twelve synthetic donors, standard loss weights, all-
standard roles, 87 targets, 1,044 updates, `1e-4`, seed, target voice, and zero
inference condition. This is not the rejected speaker7 scope, which adapted
only seven global-speaker modulators.

## Done and stop

- Train exactly 1,044 fresh-base updates and publish seven external rows.
- Reuse the mandatory twelve changed utterances and ten frozen conditions
  regardless of seven-row result.
- Machine diagnostics reject corruption only; no voice-quality winner.
- Do not sweep adjacent module counts.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy all-standard --lora-scope source36 \
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
  --work-dir artifacts/xvc-source-diversity/exp052-source36-v1 \
  --listener-dir artifacts/ms3/listening/exp052-xvc-source36-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
