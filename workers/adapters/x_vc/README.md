# X-VC worker adapter

Status: research-only and nonselectable for Japanese conversations.

This adapter runs the pinned official X-VC streaming forward behind liveconv
worker protocol v1. It accepts finite normalized mono float32 PCM as exact 20 ms,
48 kHz frames and emits one output frame for every accepted input frame. All
frame identity fields are preserved; only PCM changes.

Passing the adapter checks does not make X-VC selectable. The existing frozen
Japanese evidence fails content preservation and speaker-change rules. See
`VALIDATION.md` for the decision boundary.

## Streaming behavior

The upstream implementation is windowed rather than stateful incremental
inference. This adapter mirrors the official default temporal geometry:

```text
fixed model window: 2400 ms at 16 kHz
history:            2160 ms
current output:      120 ms (six worker frames)
smoothing overlap:    20 ms
future lookahead:     100 ms
```

The worker retains at most 2.16 s of already-emitted source context. It starts a
window when six current frames plus six overlap/lookahead frames are available,
or right-pads a final window after `generation.end`. The worker's outstanding
input remains separately bounded to 500 ms (25 frames). It never retains an
unbounded utterance.

The real backend calls the pinned upstream `run_stream_chunk_forward` unchanged.
It precomputes and reuses the authorized target's speaker embedding and mel
condition at worker initialization. The 48 kHz gateway window is VHQ-resampled
to the model's 16 kHz rate, then uses the pinned upstream volume-normalization and
40 Hz high-pass functions before the official forward. Target preparation uses
upstream `process_audio` exactly.

There is one explicit source-preprocessing deviation: upstream file inference
normalizes the complete source utterance before windowing, but an unbounded future
utterance does not exist in a live worker. This adapter applies those same pinned
functions to each bounded 2.4 s model window and binds that behavior as
`xvc-bounded-official-functions-v1`. The real smoke validates execution and PCM
integrity only. No Japanese quality evidence exists for this bounded preprocessing
variant, so the deviation is an additional reason the adapter remains
nonselectable; prior failed quality evidence is retained conservatively.

The official 20 ms tail crossfade is applied at the native model rate before
resampling output to 48 kHz. The resampler does not restart on bare 120 ms chunks:
`torchaudio-sinc-hann-overlap-v1` carries the prior generation's last 20 ms and
uses the model's full 120 ms right lookahead, then crops the current interval. An
isolated-runtime test compares its chunked output with one continuous reference
to within `1e-6`. Output is rejected if it has the wrong shape or any nonfinite
value; the real backend clips finite output to normalized `[-1, 1]` before
protocol encoding.

## Worker-v1 lifecycle

- A configuration mismatch is rejected before model loading and `worker.ready`.
- Generation IDs and control RPC IDs strictly increase; audio sequence and
  source timestamps cannot decrease.
- `generation.end` seals input, drains all accepted frames in order, and emits
  exactly one completion.
- `generation.cancel` invalidates the generation immediately. Epoch checks drop
  both PCM and completion produced by an older in-flight CUDA call.
- A newer generation may queue behind that noninterruptible call, but it cannot
  receive the older result or target/source state.
- Stdout contains only encoded newline-delimited worker-v1 messages. Upstream
  Python stdout is redirected to a private null stream; diagnostics use stderr.
- `worker.close` seals all generations and acknowledges before process teardown.

## Immutable identity and authorization

Before readiness, both the Supervisor and worker verify every declared file
artifact. The worker rejects tracked changes plus **all** untracked or ignored
files in the executable upstream checkout; this includes shadow modules and
stale `__pycache__` bytecode. Real runs set `PYTHONDONTWRITEBYTECODE=1`.

The worker also verifies the exact installed adapter source bytes, retained
liveconv worker wheel, CPython executable, complete runtime lock, installed
worker distribution version, and a non-sensitive target-authorization record.
`configuration_hash` canonically binds their digests and the Python
implementation/version alongside the source revision, checkpoint, YAML, GLM
tokenizer, ERes2Net model, target digest, CUDA device, and streaming settings.
It also binds the bounded-source-preprocessing and output-resampler revisions.

Authorization is a JSON artifact, not a Boolean. Its SHA-256 is verified by the
Supervisor and worker and is part of `configuration_hash`. The strict record
contains an authorization ID, owner, authorization record, permitted purpose,
retention policy, deletion path, classification, and the exact target-reference
SHA-256. The target digest in the record must match the configured WAV.

Before any real model import, the worker installs an irreversible seccomp rule
that denies `socket(2)` for every domain except `AF_UNIX`. Failure to install the
rule aborts initialization. Regression tests prove `AF_INET` and `AF_INET6` are
denied while the private Unix-domain option remains usable. Offline library
flags remain defense in depth and are not treated as network enforcement.

Pinned technical artifacts:

```text
source commit:        49df8c591eafc48b096e466d96f9839f9c0dd739
checkpoint:           sha256:1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687
local YAML:           sha256:5f9aae0487ffcf1b69f5833317d068bfe62c6de1a12b0921abebe742b39c3be7
GLM weights:          sha256:2800bd503f52b51e45f0c53cfd5c31dcfe8ef7f13d22b396aa3d53e0280dd1e4
ERes2Net weights:     sha256:d8941f5952e31820173c8854562cb6d7897aaa58cd65c18f30d5a2e52d30847d
```

Required environment:

```text
LIVECONV_XVC_SOURCE_ROOT
LIVECONV_XVC_SOURCE_REVISION
LIVECONV_XVC_CONFIG_PATH
LIVECONV_XVC_CONFIG_SHA256
LIVECONV_XVC_CHECKPOINT_PATH
LIVECONV_XVC_CHECKPOINT_SHA256
LIVECONV_XVC_GLM_ROOT
LIVECONV_XVC_GLM_CONFIG_SHA256
LIVECONV_XVC_GLM_PREPROCESSOR_SHA256
LIVECONV_XVC_GLM_MODEL_SHA256
LIVECONV_XVC_ERES_ROOT
LIVECONV_XVC_ERES_CONFIG_SHA256
LIVECONV_XVC_ERES_MODEL_SHA256
LIVECONV_XVC_TARGET_REFERENCE_PATH
LIVECONV_XVC_TARGET_REFERENCE_SHA256
LIVECONV_XVC_TARGET_AUTHORIZATION_PATH
LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256
LIVECONV_XVC_ADAPTER_SOURCE_SHA256
LIVECONV_XVC_RUNTIME_LOCK_PATH
LIVECONV_XVC_RUNTIME_LOCK_SHA256
LIVECONV_XVC_WORKER_WHEEL_PATH
LIVECONV_XVC_WORKER_WHEEL_SHA256
LIVECONV_XVC_INTERPRETER_PATH
LIVECONV_XVC_INTERPRETER_SHA256
LIVECONV_XVC_PYTHON_IMPLEMENTATION=CPython
LIVECONV_XVC_PYTHON_VERSION=3.12.3
LIVECONV_XVC_WORKER_PACKAGE_VERSION=0.1.0
LIVECONV_XVC_DEVICE=cuda:0
```

The real smoke additionally requires the source-fixture path/digest and
`LIVECONV_XVC_SMOKE_REPORT_PATH` for its ignored aggregate report. Run the
production backend only through `WorkerSupervisor`; a manual process invocation
waits for `worker.hello` on stdin.

The validated local runtime is `artifacts/x-vc/runtime-py312/bin/python`
(CPython 3.12.3, torch/torchaudio 2.8.0+cu128). The tracked lock contains the
complete 123-distribution dependency closure with hashes; the retained
`liveconv-worker-runtime==0.1.0` wheel is the sole additional distribution. The
smoke requires its 124-package inventory to equal lock plus wheel exactly and
requires the worker module to resolve inside the isolated runtime.

Build and install from the repository root:

```bash
uv build --wheel --out-dir artifacts/x-vc/wheels workers
uv venv --clear --python /usr/bin/python3.12 artifacts/x-vc/runtime-py312
uv pip sync --require-hashes --index-strategy unsafe-best-match \
  --python artifacts/x-vc/runtime-py312/bin/python \
  workers/adapters/x_vc/requirements-runtime.lock
uv pip install --no-deps \
  --python artifacts/x-vc/runtime-py312/bin/python \
  artifacts/x-vc/wheels/liveconv_worker_runtime-0.1.0-py3-none-any.whl
```

The two package indexes named in the lock are both required because CUDA wheels
come from the official PyTorch index and general dependencies come from PyPI.
Hashes, exact versions, inventory equality, and the wheel digest remain the
acceptance controls; index strategy does not relax them.

The actual real smoke is launched from `/tmp` with isolated mode and repository
path injection removed:

```bash
cd /tmp
env -u PYTHONPATH -u PYTHONHOME \
  /workspace/liveconv/artifacts/x-vc/runtime-py312/bin/python -I \
  -m workers.adapters.x_vc.real_smoke
```

The worker profile independently uses `/tmp` as its cwd, invokes the retained
interpreter with `-I -B`, and imports `workers.adapters.x_vc` from the installed
wheel. `-B` is explicit because isolated mode ignores `PYTHONDONTWRITEBYTECODE`;
it prevents verified upstream imports from recreating ignored bytecode. This
differs from upstream's torch 2.5.1 requirements and is supported only by the
recorded technical smoke, not as a general compatibility claim.

## Focused checks

```bash
uv run --frozen --all-packages pytest -q workers/adapters/x_vc/tests
uv run --frozen ruff check workers/adapters/x_vc
uv run --frozen ruff format --check workers/adapters/x_vc
```

The deterministic backend additionally requires
`LIVECONV_ENABLE_TEST_BACKEND=1`; it is inaccessible without the hidden CLI flag
and exists only for protocol tests. The official test is opt-in with
`LIVECONV_RUN_XVC_REAL=1`, the complete pinned environment above, and a CUDA GPU.
