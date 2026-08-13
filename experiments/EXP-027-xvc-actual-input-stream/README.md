# EXP-027: X-VC human87 horizons on actual streaming input

Status: **v1 technical stop; corrected v2 runner prepared**.

## Goal and Definition of Done

Use the actual 8.17-second pre-VC ChatGPT-tab recording to test whether the
EXP-026 human87 epoch 4/8/12 adapters remain intelligible and continuous under
the pinned upstream X-VC streaming algorithm.

Done means one explicit base/epoch4/epoch8/epoch12 comparison is published on
the fixed `http://127.0.0.1:8878/` listener, with exact source duration, valid
mono output, and CUDA-synchronized per-chunk compute P50/P95 including failures.
The operator records a preferred horizon or rejects the set.

## One comparison boundary

All four arms use the same actual source, authorized Amitaro runrun
`EMOTION100_003` train-role reference, zero frame condition, base checkpoint,
and upstream stream implementation. The fixed online window is 2400 ms total,
120 ms current, 20 ms smoothing overlap, 100 ms future, and 2160 ms history.
Only the adapter state changes: none, epoch 4, epoch 8, or epoch 12.

This run follows the active-thread instruction to keep one useful GPU lane
moving while listening is pending. It moves from short isolated utterances to
actual conversational input and therefore advances both quality search and the
realtime-system path. It does not measure network/playout or conversational
latency and does not qualify a route.

Stop before publication on source, adapter, EXP-026 result, or upstream-code
identity drift; malformed/nonfinite audio; output-length drift; CUDA failure;
or a partial variant set. Do not change the streaming window or choose a
horizon from numeric loss.

## Command

Run only after this runner and note are committed:

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/stream_actual_horizons.py \
  --manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --source-root artifacts/xvc-human-paired/source-audio/hadou-ita \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --exp026-work-dir artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-v1 \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp027-actual-input-stream-v2 \
  --listener-dir artifacts/ms3/listening/exp027-actual-input-stream-v2 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

Repair note: `v1` stopped before model load, adapter load, stream inference, or
listener publication. The exact 48-kHz source is 8.170667 seconds, while pinned
`process_audio` deterministically right-pads its 16-kHz model input to 131,840
samples (8.24 seconds, 103 latent hops). The corrected `v2` binds that model
sample count and trims every completed output to 130,731 samples, the nearest
16-kHz representation of the original duration. No audio, adapter, streaming
window, or comparison arm changed.

Not in scope: alternate streaming windows, another model family, more training,
automatic checkpoint selection, route qualification, Extension playback,
network latency, or product readiness.
