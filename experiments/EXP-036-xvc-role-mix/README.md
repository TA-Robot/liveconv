# EXP-036: X-VC upstream role assignment at fixed exposure

Status: ready method pilot; operator hearing deferred

## Question

Does restoring X-VC's official training-role proportions improve robustness
over EXP-035's all-standard fine-tuning when the generated pairs, update count,
LoRA scope, learning rate, loss, target voice, and zero target conditioning are
held fixed?

The pinned upstream config uses `0.2` reconstruction and `0.4` reversed
examples, leaving `0.4` standard conversion examples. EXP-036 deterministically
interleaves the closest exact allocation over 1,044 updates: 418 standard, 208
reconstruction, and 418 reversed.

## Fixed data boundary

- Same 87 Amitaro target windows and twelve admitted Common Voice donors as
  EXP-035.
- Same donor order, target order, base model, seeds, and 1,044 generated pairs.
- Each generated waveform must reproduce the corresponding EXP-035 PCM hash
  before it can enter training. Training uses the regenerated pre-quantization
  tensor, matching EXP-035 rather than reading the PCM back.
- Same seven Common Voice evaluation speakers, disjoint from the twelve donors.
- Same control69 LoRA, AdamW `1e-4`, gradient clipping, composite generative
  loss, and all-zero target waveform condition.

For a standard update, generated donor audio is source and Amitaro is target.
For reconstruction, Amitaro is both source and target. For reversed, Amitaro is
source and the generated donor audio is target. Semantic tokens and target SSL
features follow the assigned waveform roles.

## Done and stop

- Train exactly 1,044 updates on `gpu0`.
- Publish base, EXP-035 all-standard, and EXP-036 role-mix outputs for the same
  seven disjoint speakers on `http://127.0.0.1:8878/`.
- Run content/repetition screening only. A gross external regression stops this
  role mix; otherwise render it once on the frozen ten conditions.

Auxiliary ASR cannot select naturalness, target-voice fit, or a winner. This
does not reopen donor count, human87 horizon/LR/scope, or EXP-024 DTW retries.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
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
  --work-dir artifacts/xvc-source-diversity/exp036-role-mix-v1 \
  --listener-dir artifacts/ms3/listening/exp036-xvc-role-mix-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
