# EXP-040: target-preserving X-VC reconstruction regularization

Status: ready method pilot; operator hearing deferred

## Question

Can a small same-target reconstruction share regularize EXP-035's control69
adapter without EXP-036's reversed donor-target dilution?

EXP-036 copied the upstream 40/20/40 role mix. Its reversed 40% made Amitaro
the source and generated Common Voice donor audio the target, so 418 updates
trained away from the sole desired target voice. EXP-040 retains only the
target-preserving part: 835 standard conversions and 209 Amitaro
self-reconstructions, deterministically interleaved. Every update still has
Amitaro as the target; reversed count is exactly zero.

## Fixed boundary

- Same 87 Amitaro targets, twelve donors, exact 1,044 generated waveforms,
  ordering, and generation seeds as EXP-035.
- Every regenerated PCM and the aggregate inventory must match EXP-035.
- Same control69 rank-8 LoRA, AdamW `1e-4`, composite loss, gradient clipping,
  all-zero target condition, and total updates.
- Same seven disjoint external speakers for first admission.

The only change from EXP-035 is 209 role assignments from standard conversion
to same-Amitaro reconstruction. This is a single failure-driven decomposition,
not a role-ratio sweep.

## Done and stop

- Train exactly 1,044 updates on `gpu0`.
- Publish base, EXP-035 all-standard, and EXP-040 reconstruction20 on
  `http://127.0.0.1:8878/`.
- Screen content/repetition only. A gross external regression stops this role
  method; otherwise render it on EXP-039's twelve new utterances.

No machine result selects naturalness, target-voice fit, or a winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy standard-reconstruction --lora-scope control69 \
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
  --work-dir artifacts/xvc-source-diversity/exp040-reconstruction20-v1 \
  --listener-dir artifacts/ms3/listening/exp040-xvc-reconstruction20-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
