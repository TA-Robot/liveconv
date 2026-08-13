# EXP-032: X-VC streaming lookahead floor

Status: **completed; operator hearing pending; lookahead sweep closed**.

The 100- and 125-ms endpoint controls reproduced exactly. Auxiliary Whisper
showed gross repetition at 100 ms, shorter repetition at 110 ms, and no gross
repetition at 120/125 ms. The lowest diagnostic candidate is therefore future
120 ms: 260 ms of model context plus measured CUDA compute P50 26.19 ms and P95
32.84 ms across 69 failure-free chunks. Network, playout, conversational
latency, naturalness, route qualification, and product selection remain open.

EXP-031 found no gross auxiliary-ASR repetition at 125, 150, 175, or 200 ms,
while EXP-030 reproduced the gross repetition at 100 ms. This final bounded
diagnostic tests 100, 110, 120, and 125 ms. The endpoint controls must reproduce
their earlier WAV hashes exactly.

All arms are below 265 ms of model context (`120 current + 20 smoothing +
future`) before compute/network/playout. Done means four candidates appear on
fixed port 8878, receive the same auxiliary Whisper screen, and the streaming
lookahead sweep stops. The lowest non-repeating arm is only a candidate for
operator hearing; it is not automatically selected or route-qualified.

Stop on any inherited identity or control mismatch, malformed audio, CUDA
failure, or partial publication. Do not open another lookahead experiment after
this result.

## Candidate system-path probe

The next bounded step reuses this EXP rather than opening another quality
sweep. `tools/xvc-human-paired/system_path_smoke.py` supplies the measured
epoch-8/future-120-ms geometry to the existing `XvcWorker` queue and generation
state machine without changing or activating the retained Gateway identity. It
cancels generation 1 during real inference and requires zero stale output, then
paces the actual input at 20 ms into generation 2 and publishes one WAV on
`8878`. This is the implementation bridge before a keep, not route binding.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-human-paired/system_path_smoke.py \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --adapter-dir artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-v1/adapter-0696 \
  --target-reference artifacts/xvc-human-paired/listen-now/exp026-human87-horizon-v1/train-pairs/EMOTION100_003/target-48k.wav \
  --actual-source artifacts/ms3/listening/exp020-human-rvc-smoke-8s-plain-20260812/00-native-source.wav \
  --work-dir artifacts/xvc-human-paired/listen-now/exp032-system-path-v4 \
  --listener-dir artifacts/ms3/listening/exp032-system-path-v4 \
  --confirm-gpu-lease gpu0 --device cuda:0
```

Repair note: `v1` stopped before model load, inference, or listener publication
because the isolated Torch runtime requires `cuda:0` to be selected before its
peak-memory counter can be reset. `v2` adds that ordering call only; the model,
adapter, stream geometry, input, cancellation probe, and retained generation do
not change.

`v2` then stopped after checkpoint/adapter load but before condition completion,
window inference, or publication: deterministic Torch requires
`CUBLAS_WORKSPACE_CONFIG=:4096:8` before its first cuBLAS operation. `v3` sets
that standard deterministic-runtime value before importing Torch. No candidate
input or worker behavior changes.

`v3` reached the real canceled inference, then its next generation overflowed
the direct worker queue because the probe paced input but did not reproduce the
Gateway bridge's output-backed 25-frame credit. It published nothing, and the
stuck exception-exit process was terminated and released its GPU memory. `v4`
waits for output whenever credit is full and records both credit wait and
maximum in-flight frames; model and audio conditions remain unchanged.
