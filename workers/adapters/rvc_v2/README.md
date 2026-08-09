# RVC v2 worker adapter

This adapter runs the pinned upstream RVC v2 realtime engine behind liveconv
worker protocol v1. It accepts mono float32 20 ms frames, converts bounded
500 ms batches with the upstream rolling-context and SOLA engine, and restores
the original generation, sequence, frame length, and monotonic timestamp. One
inference batch is 25 frames and total worker residency is bounded at 50 frames:
25 in flight plus 25 pending. A push that would make 51 resident frames is
rejected. Cancel immediately drops pending frames and stale output, but canceled
in-flight occupancy remains resident until that call releases; a new generation
can use only the capacity that remains.

The adapter does not make a checkpoint safe to use. A selectable profile still
needs authorized target provenance and the model-pack quality gates. Canceling
a generation immediately discards queued and late output; the next generation
resets rolling model state. Only `CooperativeConversionCanceled` from an already
canceled epoch is nonfatal. Any other inference exception, including one raised
by a canceled epoch, terminates the worker so that bypass/restart policy owns
recovery.

## Pinned technical-validation runtime

- Upstream: `RVC-Project/Retrieval-based-Voice-Conversion-WebUI`
- Source commit: `81eed5e8f68b6bed1789f682fe78cdd324495afc`
- Official model repository: `lj1995/VoiceConversionWebUI`
- Model revision: `e6d0c1a17da07c33557852f9dfa2bd44cc75737d`
- Adapter revision: `liveconv-rvc-v2-worker-v1.4`
- Python: 3.12
- Torch and torchaudio: `2.7.1+cu128`

Primary sources:

- <https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI>
- <https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/81eed5e8f68b6bed1789f682fe78cdd324495afc/LICENSE>
- <https://huggingface.co/lj1995/VoiceConversionWebUI/tree/e6d0c1a17da07c33557852f9dfa2bd44cc75737d>

The official v2 generator is a training base, not a target-speaker checkpoint.
Do not present the base generator as a usable target voice.

## Configuration identity contract

The Gateway and worker bind the same exact JSON shape. Runtime artifact values
are shown as placeholders because embedding a wheel's own digest inside that
wheel would be self-referential. The ignored smoke report and manifest record
the concrete retained values after build:

```json
{
  "worker_module": "workers.adapters.rvc_v2.worker",
  "adapter_revision": "liveconv-rvc-v2-worker-v1.4",
  "source_revision": "81eed5e8f68b6bed1789f682fe78cdd324495afc",
  "artifacts": {
    "checkpoint_sha256": "46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c",
    "index_sha256": "1cec842c048757af4bc6dc7ab7ac9fa8e7ce7226b297c82c6837c8639ee04003",
    "hubert_config_sha256": "0346950779dfb7f9316fa74ed846e2b8a22a08eedfdc5387b73f327cb1a4a7cf",
    "hubert_preprocessor_sha256": "7c1976a680fb7acc757cd36fb08eef878fa36c70b4c9d2d595df9c608bbbbf0e",
    "hubert_weights_sha256": "cc8c20f4b90a520757260197a3ff2505705a7adbd20ad9eeaa4e1a9b38442ef5",
    "rmvpe_sha256": "6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193",
    "worker_wheel_sha256": "${WORKER_WHEEL_SHA256}",
    "worker_wheel_record_sha256": "${WORKER_WHEEL_RECORD_SHA256}",
    "worker_module_sha256": "${WORKER_MODULE_SHA256}",
    "backend_module_sha256": "${BACKEND_MODULE_SHA256}",
    "network_isolation_module_sha256": "${NETWORK_ISOLATION_MODULE_SHA256}",
    "requirements_lock_sha256": "a722f050fd44030ce73e4b5f54e051d94759fe78bcddd98b0a7710280fc68679"
  },
  "settings": {
    "speaker_id": 0,
    "pitch_shift": 0,
    "f0_method": "rmvpe",
    "index_rate": 0.75,
    "rms_mix_rate": 1.0,
    "sample_rate": 48000,
    "block_ms": 500,
    "crossfade_ms": 50,
    "context_ms": 2500,
    "frame_ms": 20,
    "inference_batch_frames": 25,
    "queue_capacity_frames": 25,
    "resident_capacity_frames": 50,
    "formant_shift": 0.0,
    "threshold_dbfs": -60.0
  }
}
```

Serialize with `json.dumps(value, ensure_ascii=True, separators=(",", ":"),
sort_keys=True).encode("ascii")`; `configuration_hash` is `sha256:` followed
by that byte string's lowercase digest. Use the concrete post-build artifact
digests, never the placeholder strings, to calculate `configuration_hash`.

The Gateway must use that digest in `WorkerProfile.configuration_hash`, verify
checkpoint and index paths with `ArtifactSpec`, and set:

```text
implementation_revision=liveconv-rvc-v2-worker-v1.4+rvc.81eed5e8f68b6bed1789f682fe78cdd324495afc
weight_revision=sha256:46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c
```

The worker independently resolves effective settings; verifies source HEAD and
tracked cleanliness; and hashes the checkpoint, index, HuBERT, RMVPE, retained
wheel, wheel RECORD, installed worker/backend/network-isolation modules, and
packaged dependency lock. It compares every wheel RECORD entry and installed
file byte-for-byte, then compares the complete installed distribution inventory
with the lock plus `liveconv-worker-runtime==0.1.0`. It rejects any mismatch and
a different `worker.hello.configuration_hash` before backend load, and only
echoes its computed identity in `worker.ready`.

Before real backend initialization, the worker entrypoint installs an
irreversible Linux seccomp filter that allows only `AF_UNIX` socket creation.
It fails closed when `no_new_privs`, libseccomp, or the filter cannot be
installed. `UpstreamRvcBackend` also refuses to initialize unless the filter is
already active. This is an OS boundary inherited by inference threads and child
processes; running an imported backend manually does not install it.

## Environment contract

Required for a real profile:

```text
LIVECONV_RVC_SOURCE_ROOT
LIVECONV_RVC_SOURCE_REVISION
LIVECONV_RVC_V2_CHECKPOINT_PATH
LIVECONV_RVC_V2_CHECKPOINT_SHA256
LIVECONV_RVC_V2_WORKER_WHEEL_PATH
LIVECONV_RVC_V2_WORKER_WHEEL_SHA256
```

Settings, with worker defaults shown:

```text
LIVECONV_RVC_V2_SPEAKER_ID=0
LIVECONV_RVC_V2_PITCH_SHIFT=0
LIVECONV_RVC_V2_F0_METHOD=rmvpe
LIVECONV_RVC_V2_INDEX_RATE=0
LIVECONV_RVC_V2_RMS_MIX_RATE=1
LIVECONV_RVC_V2_SAMPLE_RATE=48000
LIVECONV_RVC_V2_BLOCK_MS=500
LIVECONV_RVC_V2_CROSSFADE_MS=50
LIVECONV_RVC_V2_CONTEXT_MS=2500
```

`LIVECONV_RVC_V2_INDEX_PATH` and `LIVECONV_RVC_V2_INDEX_SHA256` are an
all-or-nothing pair and are required when index rate is nonzero. Do not set
`LIVECONV_RVC_V2_PROTECT`: the realtime upstream call has no effective protect
control, so this adapter rejects the variable instead of advertising a no-op.

## Isolated installation

Keep source, environments, weights, indexes, corpora, wheels, and evidence under
ignored `artifacts/`. Reproduce the retained environment as two bound layers:
the complete hash-locked model dependency set and one versioned worker wheel.

```bash
uv venv --python 3.12 artifacts/rvc-v2/runtime
uv pip sync --python artifacts/rvc-v2/runtime/bin/python \
  --require-hashes workers/adapters/rvc_v2/requirements-runtime.lock
uv build --package liveconv-worker-runtime --wheel \
  --out-dir artifacts/rvc-v2/dist
sha256sum artifacts/rvc-v2/dist/liveconv_worker_runtime-0.1.0-py3-none-any.whl
uv pip install --python artifacts/rvc-v2/runtime/bin/python --no-deps \
  artifacts/rvc-v2/dist/liveconv_worker_runtime-0.1.0-py3-none-any.whl
uv pip check --python artifacts/rvc-v2/runtime/bin/python
```

Run `uv pip sync` before the wheel install; a later sync intentionally removes
the wheel because it is the separately digested application layer. The evidence
harness rejects missing, extra, or version-mismatched packages relative to the
lock plus `liveconv-worker-runtime`, verifies the wheel digest and version, and
requires the imported worker module to live inside the retained runtime.

The dependency-lock and wheel digests are both deployment and configuration
bindings. The retained wheel path remains available to the child, allowing it
to hash the original archive and compare all archive files with the installed
distribution. The evidence harness additionally records a composite
`runtime_binding_sha256` for runtime reproduction.

It also starts the subprocess with `cwd=/tmp` and no `PYTHONPATH`. A direct
isolation check is:

```bash
cd /tmp
env -u PYTHONPATH \
  /workspace/liveconv/artifacts/rvc-v2/runtime/bin/python -I -c \
  'import workers.adapters.rvc_v2.worker as w; print(w.__file__)'
```

## Real evidence harness

`tools/real_smoke.py` is tracked. It records configuration material, complete
package inventory, GPU/host, lock/wheel/runtime binding digests, OS socket
isolation, a continuous generation longer than the 25-frame Supervisor credit,
PCM metrics, frame identity, cancellation, cold/warm timing, and a render-bound
streaming lane. The deterministic worker tests exercise the internal 50-frame
resident double buffer directly. Supply only absolute or repository-relative
paths under ignored artifacts.

Cold start is a fresh subprocess through `worker.ready` and includes upstream
model load plus prewarm. Run at least one complete excluded warmup generation.
Warm P50/P95 uses at least two subsequent complete generations in the same
process; the retained validation uses one warmup and five measured generations.

```bash
uv run --frozen --all-packages python -m \
  workers.adapters.rvc_v2.tools.real_smoke \
  --runtime-python artifacts/rvc-v2/runtime/bin/python \
  --runtime-lock workers/adapters/rvc_v2/requirements-runtime.lock \
  --worker-wheel artifacts/rvc-v2/dist/liveconv_worker_runtime-0.1.0-py3-none-any.whl \
  --worker-wheel-sha256 "$WORKER_WHEEL_SHA256" \
  --worker-package-version 0.1.0 --worker-cwd /tmp \
  --source-root artifacts/rvc-v2/upstream \
  --source-revision 81eed5e8f68b6bed1789f682fe78cdd324495afc \
  --checkpoint artifacts/rvc-v2/upstream/assets/weights/liveconv-synthetic-ja-v1.pth \
  --checkpoint-sha256 46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c \
  --index artifacts/rvc-v2/upstream/logs/liveconv-synthetic-ja-v1/added_IVF1758_Flat_nprobe_1_liveconv-synthetic-ja-v1_v2.index \
  --index-sha256 1cec842c048757af4bc6dc7ab7ac9fa8e7ce7226b297c82c6837c8639ee04003 \
  --index-rate 0.75 \
  --source-wav artifacts/shared/synthetic-ja-v1/source/LV001-JA-001.wav \
  --output-wav artifacts/rvc-v2/evidence/rvc-v2-output.wav \
  --report artifacts/rvc-v2/evidence/rvc-v2-smoke.json \
  --streaming-report artifacts/rvc-v2/evidence/rvc-v2-streaming.json \
  --warmup-runs 1 --measured-runs 5
```

## Checks

```bash
uv run --frozen --all-packages pytest -q workers/adapters/rvc_v2/tests
uv run --frozen --all-packages ruff check workers/adapters/rvc_v2
uv run --frozen --all-packages ruff format --check workers/adapters/rvc_v2
```

The deterministic backend is gated by `LIVECONV_ENABLE_TEST_BACKEND=1` and is
never a conversion profile. See `VALIDATION.md` for the real checkpoint result.
