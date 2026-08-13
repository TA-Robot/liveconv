# EXP-068: decoder-interface X-VC adaptation

Status: committed listen-now method; waiting for one GPU run

## Question

Does adapting only the final speaker-conditioned normalization and the
converter-to-decoder projection produce a viable X-VC listening candidate?

## One changed variable

The exact EXP-035 generated-source inventory digest `e909e465`, twelve Common
Voice donor speakers, 87 Amitaro target windows, all-standard roles, upstream
generative loss, 1,044 updates, LR `1e-4`, rank 8, gradient clip 5, seed, and
zero frame condition stay fixed. The control adapts 69 attention/FFN linears;
EXP-068 adapts only:

- `acoustic_converter.norm_out.linear`
- `acoustic_converter.proj_out`

This is 22,016 trainable LoRA parameters. It tests the converter/frozen-decoder
interface as one functional unit, not another attention-count sweep. The final
normalization overlaps speaker7, but `proj_out` was not in that isolated scope.

## Decision boundary

Publish the seven external rows and then EXP-069--071's twelve changed
utterances, ten named conditions, and 31 clean Hadou sentences. Machine ASR may
reject empty, grossly repeated, or content-drifted output. It cannot measure
naturalness, target identity, or select a winner. Retain viable audio unheard
until operator listening returns. Do not sweep adjacent output layers or rank.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy all-standard --lora-scope output2 \
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
  --work-dir artifacts/xvc-source-diversity/exp068-output2-v1 \
  --listener-dir artifacts/ms3/listening/exp068-output2-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
