# OpenVoice V2 offline adapter

This adapter runs the official MyShell OpenVoice V2 tone-color converter behind
the private worker-v1 JSON protocol. It performs real mono PCM to PCM conversion
for bounded offline utterances by extracting a source embedding from each
utterance and a target embedding once during warmup.

OpenVoice V2 is a whole-utterance converter. This adapter therefore buffers a
bounded generation and emits its transformed frames after `generation.end`. It
is an offline experiment adapter, not a realtime Gateway profile. Although the
Gateway can pump a bounded batch concurrently, this adapter exposes only a
60-to-500-ms whole-generation contract and has no rolling context, incremental
output, or streaming-latency evidence. Do not represent offline success as
streaming readiness.

Consequently this adapter is not a Gateway/Extension release-path dependency and
must not unlock a streaming or client-E2E gate. It is an offline evaluation
control until a separately accepted architecture supports utterance buffering.
It remains unregistered, nonselectable, and `ready_for_runtime: false`.

The private worker protocol accepts 3 through 25 20-ms frames per non-empty
generation, for a 60-to-500-ms conversion window. Longer evaluation clips must
be segmented and joined by an offline harness. This can introduce boundary
discontinuities and is part of the suitability result, not an implementation
detail to hide.

## Required environment

Every source, model, and reference input is local and digest-pinned:

```text
LIVECONV_OPENVOICE_V2_SOURCE_ROOT
LIVECONV_OPENVOICE_V2_SOURCE_TREE_SHA256
LIVECONV_OPENVOICE_V2_CONFIG_PATH
LIVECONV_OPENVOICE_V2_CONFIG_SHA256
LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH
LIVECONV_OPENVOICE_V2_CHECKPOINT_SHA256
LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH
LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256
LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX
LIVECONV_OPENVOICE_V2_PYVENV_SHA256
LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH
LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256
LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256
LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256
LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256
LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256
LIVECONV_OPENVOICE_V2_RUNTIME_LOCK_SHA256
LIVECONV_OPENVOICE_V2_DEVICE                 # cpu or cuda:N
LIVECONV_OPENVOICE_V2_TAU                    # optional, default 0.3
LIVECONV_OPENVOICE_V2_SEED                   # optional uint63, default 0
```

The target reference is voice data. Its use requires authorization and explicit
provenance. The official demo reference used for technical validation is not a
production voice selection.

Build the actual `liveconv-worker-runtime` wheel from a snapshot staged under the
ignored artifact root, then install it into the dedicated interpreter:

```bash
uv venv --python 3.12 artifacts/openvoice-v2/runtime
uv pip sync --python artifacts/openvoice-v2/runtime/bin/python \
  workers/adapters/openvoice_v2/requirements-runtime.lock

mkdir -p artifacts/openvoice-v2/wheel-source artifacts/openvoice-v2/wheels
cp -a workers/. artifacts/openvoice-v2/wheel-source/
uv build --offline --wheel \
  --out-dir artifacts/openvoice-v2/wheels \
  artifacts/openvoice-v2/wheel-source
uv pip install --offline --no-deps --reinstall \
  --python artifacts/openvoice-v2/runtime/bin/python \
  artifacts/openvoice-v2/wheels/liveconv_worker_runtime-0.1.0-py3-none-any.whl

cd /tmp
env -u PYTHONPATH \
  /workspace/liveconv/artifacts/openvoice-v2/runtime/bin/python -I \
  -m workers.adapters.openvoice_v2
```

`requirements-runtime.txt` records direct requirements. The generated
`requirements-runtime.lock` freezes the complete Linux/Python 3.12 transitive
closure with wheel hashes used by the RTX 5090/CUDA 12.8 validation. Recreate the
environment rather than enabling system site packages.

After creation, `include-system-site-packages` in `pyvenv.cfg` must be `false`.
The worker rejects a non-venv `sys.prefix`, a mismatched `pyvenv.cfg`, an
executable path outside the declared prefix, a distribution outside that prefix,
or a nonempty `PYTHONPATH`.

The configured seed is reset inside an isolated Torch RNG context for every
conversion. Evidence must record the seed and `tau`; an older unseeded render is
historical only and cannot satisfy a reproducibility gate.

Before upstream OpenVoice or numerical-library imports, the worker duplicates
the original protocol stdout descriptor and redirects ordinary process FD 1 to
a sink. The locked NDJSON emitter owns the duplicate. Consequently Python
`print`, C/native writes, and `os.write(1, ...)` from initialization or a
concurrent inference thread cannot enter the protocol stream.

The worker verifies the wheel SHA-256, the archive RECORD and every archive
member, the installed RECORD and every installed wheel member, and the executing
module origins. Its implementation manifest covers these installed sources:

```text
workers/adapters/openvoice_v2/__init__.py
workers/adapters/openvoice_v2/__main__.py
workers/adapters/openvoice_v2/engine.py
workers/adapters/openvoice_v2/network_isolation.py
workers/adapters/openvoice_v2/worker.py
workers/runtime/codec.py
```

The configuration hash binds the wheel, wheel RECORD, installed RECORD, full
installed-distribution manifest, implementation manifest, `pyvenv.cfg`, and
runtime lock digests in addition to the model, reference, device, seed, and tau.
Compute attested values only from the installed runtime, with the wheel retained
at its declared path:

```bash
cd /tmp
env -u PYTHONPATH \
  LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH=/workspace/liveconv/artifacts/openvoice-v2/wheels/liveconv_worker_runtime-0.1.0-py3-none-any.whl \
  /workspace/liveconv/artifacts/openvoice-v2/runtime/bin/python -I -c \
  'import json, os; from dataclasses import asdict; from pathlib import Path; from workers.adapters.openvoice_v2.engine import attest_worker_distribution, sha256_file; wheel=Path(os.environ["LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH"]); print(json.dumps(asdict(attest_worker_distribution(wheel, sha256_file(wheel))), sort_keys=True))'
```

`worker.ready.implementation_revision` contains the implementation-manifest
digest. A repository commit alone is insufficient; evidence records the commit,
worktree state, wheel and RECORD digests, installed manifest, implementation
manifest, `pyvenv.cfg`, and runtime-lock digest together. Any mismatch fails
before `worker.ready`.

Cancellation acknowledgement is a publication barrier: any output already
published precedes `generation.canceled`, and no audio or completion can follow
it. If completion wins the lifecycle lock, `generation.completed` precedes the
cancel request's `INVALID_STATE` response. Upstream inference is cooperative
rather than preemptible, so health reports not-ready until an in-flight canceled
call returns.

## Focused checks

Pytest is part of the digest-locked runtime so engine checks never borrow audio
or Torch packages from the development environment. Copy the tests outside the
repository package tree so collection cannot make mutable repository modules win
import resolution:

```bash
test_dir=$(mktemp -d /tmp/liveconv-openvoice-tests.XXXXXX)
cp /workspace/liveconv/workers/adapters/openvoice_v2/tests/test_engine.py \
  "$test_dir/test_engine.py"
cp /workspace/liveconv/workers/adapters/openvoice_v2/tests/test_worker.py \
  "$test_dir/test_worker.py"
cd /tmp
env -u PYTHONPATH \
  LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH=/workspace/liveconv/artifacts/openvoice-v2/wheels/liveconv_worker_runtime-0.1.0-py3-none-any.whl \
  LIVECONV_OPENVOICE_V2_TEST_PYTHON=/workspace/liveconv/artifacts/openvoice-v2/runtime/bin/python \
  /workspace/liveconv/artifacts/openvoice-v2/runtime/bin/python -I -m pytest \
  --import-mode=importlib -q "$test_dir/test_engine.py" "$test_dir/test_worker.py"
```

This command executes 25 tests. The engine tests retain dependency guards for
collection by the general workspace suite. When the development interpreter
lacks model dependencies but the ignored runtime exists, one workspace test
delegates the complete engine module to that runtime and fails if it does not
pass; it does not silently replace dependency-backed cases with skips. The
isolated 25-test command above has no permitted dependency skips. Set
`LIVECONV_OPENVOICE_V2_TEST_PYTHON` only to select an equivalent recreated
digest-locked runtime for workspace delegation.

The opt-in real-model regression requires pinned digests for the authorized WAV,
the exact first 500 ms of float32 protocol input, and expected float32 protocol
output. It runs two identical generations under a Linux seccomp filter:

```bash
LIVECONV_OPENVOICE_V2_RUN_REAL_SMOKE=1 \
LIVECONV_OPENVOICE_V2_WORKER_PYTHON=artifacts/openvoice-v2/runtime/bin/python \
LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX=/workspace/liveconv/artifacts/openvoice-v2/runtime \
LIVECONV_OPENVOICE_V2_PYVENV_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH=/workspace/liveconv/artifacts/openvoice-v2/wheels/liveconv_worker_runtime-0.1.0-py3-none-any.whl \
LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_SMOKE_INPUT_PATH=/authorized/input.wav \
LIVECONV_OPENVOICE_V2_SMOKE_INPUT_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_SMOKE_PCM_INPUT_SHA256=<sha256> \
LIVECONV_OPENVOICE_V2_SMOKE_OUTPUT_SHA256=<sha256> \
env -u PYTHONPATH \
  /workspace/liveconv/artifacts/openvoice-v2/runtime/bin/python -I -m pytest \
  --import-mode=importlib -q /tmp/test_real_smoke.py
```

The test fails when the dedicated interpreter, its model dependencies,
libseccomp, required digests, or syscall filter are unavailable. Before any
worker thread starts, the filter denies creation of every socket domain except
`AF_UNIX`; it is inherited by the inference thread and any descendants. The
worker subprocess receives only stdin/stdout/stderr pipes and no network file
descriptors. This is bounded OS-enforced socket isolation for the smoke process,
not an API monkeypatch and not a claim that an ordinary manual worker invocation
is network-sandboxed.

Stdout is protocol-only. Initialization and conversion errors are redacted.
