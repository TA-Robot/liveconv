# EXP-081: source-hidden semantic supervision

Status: completed; mixed technical result retained for broader stress evaluation

## Question

Does supervising X-VC's semantic decoder with the input source's frozen Whisper
hidden states preserve unseen content better than supervising it with the
target-voice hidden states?

EXP-035 already feeds source semantic tokens but computes semantic MSE against
the target waveform's hidden states. This point changes only that learning
target. Target waveform reconstruction and target speaker similarity remain
Amitaro; loss weights remain semantic 1000, mel 15, speaker 10, and VQ 1.
Generated data, 87 target texts, twelve donors, control69 LoRA, `1e-4`, seed,
zero target condition, and 1,044 updates remain fixed. This is not another loss
multiplier, scope, horizon, or tongue-twister point.

## Done and stop

- Commit the tensor-binding implementation and pass focused tests plus exact
  CPU admission before one GPU run.
- Publish seven external rows, then reuse the frozen 12 + 10 + 31 + 33 screens.
- Reject gross corruption or broad content regression; do not rank naturalness,
  target-voice fit, or a winner by ASR.
- Do not sweep source/target blend weights from this result.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy source-semantic --lora-scope control69 \
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
  --work-dir artifacts/xvc-source-diversity/exp081-source-semantic-v1 \
  --listener-dir artifacts/ms3/listening/exp081-source-semantic-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

## Result

All 1,044 updates completed in 280.32 seconds at 5.13 GB peak allocation; loss
moved from 135.04 to 96.75. On seven external rows the candidate produced two
wins, four ties, and one loss against control69, improving mean
source-relative distance from `0.360` to `0.299` and maximum from `0.571` to
`0.556`, without gross repetition. The larger screens are mixed, so this is an
unheard candidate rather than a selected method. Do not sweep a source/target
blend weight.
