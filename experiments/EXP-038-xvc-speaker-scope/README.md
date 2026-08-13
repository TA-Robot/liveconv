# EXP-038: X-VC speaker-conditioning-only LoRA

Status: ready method pilot; operator hearing deferred

## Question

Does adapting only the X-VC linears directly driven by the global speaker
embedding preserve external content better than EXP-035's control69
attention/FFN scope while still producing a target-voice candidate for later
hearing?

The new `speaker7` scope contains the six
`transformer_blocks.*.attn_norm_x.linear` modules and
`acoustic_converter.norm_out.linear`. These AdaLN projections turn the frozen
speaker embedding into attention/MLP gates, shifts, and scales. At LoRA rank 8
they contain 166,400 trainable parameters. EXP-035 control69 instead adapts
835,584 parameters across 69 attention and FFN linears.

## Fixed boundary

- Same 87 Amitaro targets, twelve Common Voice donors, exact 1,044 generated
  waveforms, target/donor order, and generation seeds as EXP-035.
- Each regenerated PCM hash and the aggregate inventory must match EXP-035.
- Same 1,044 all-standard updates, AdamW `1e-4`, rank 8, alpha 8, composite
  loss, target voice, and all-zero target waveform condition.
- Same seven disjoint Common Voice evaluation speakers.

The only training change is LoRA target topology: `control69` versus
`speaker7`. This is not another control69/expanded79 capacity point; all content
attention and FFN weights remain frozen in the candidate.

## Done and stop

- Train exactly 1,044 updates on `gpu0`.
- Publish base, EXP-035 control69, and EXP-038 speaker7 outputs on
  `http://127.0.0.1:8878/`.
- Screen content/repetition only. A gross external regression stops speaker7;
  otherwise render it once on the frozen ten conditions.

No machine result selects naturalness, target-voice fit, or a winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy all-standard --lora-scope speaker7 \
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
  --work-dir artifacts/xvc-source-diversity/exp038-speaker7-v1 \
  --listener-dir artifacts/ms3/listening/exp038-xvc-speaker7-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
