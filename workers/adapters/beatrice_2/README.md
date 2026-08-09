# Beatrice 2 worker adapter

This adapter runs the pinned, MIT-licensed Beatrice Trainer 2.0.0-rc.0 graph
behind liveconv worker protocol v1. It does not load `beatrice.lib`. The process
accepts mono float32 48 kHz frames of exactly 20 ms, converts full 500 ms batches,
and drains a shorter final batch on `generation.end`. The official graph needs at
least 60 ms: 20 ms and 40 ms final drains are zero-padded to 60 ms for inference,
then trimmed back to their exact input length before output framing.

The worker preserves generation, sequence, frame length, and source monotonic
timestamps. It acknowledges cancellation without waiting for an in-flight model
call, discards results from the canceled epoch, and serializes the next generation
behind that call. Input and output PCM must be finite and normalized. Stdout is
reserved for newline-delimited worker-v1 messages; upstream prints are discarded
and diagnostics remain on stderr.

This implementation is technical evidence, not product approval. The official
pretrained converter contains 200 LibriTTS-R speakers rather than an authorized
liveconv target. Model-pack license, provenance, target authorization, Japanese
quality, and selection gates remain separate decisions.

## Pinned technical-validation artifacts

- Source: `fierce-cats/beatrice-trainer`
- Source revision: `f34836de014b86956096878aecb8d3b17feaaa0b`
- Source module SHA-256: `c191a4fabdb63730b749fc2fbbe27384223fc27862a06a0d9db713bdee688e83`
- Phone checkpoint SHA-256: `46e2d609825ace2158c83672cfc9cc1dcb3c2b7c8d294ee911fcb6840a592bae`
- Pitch checkpoint SHA-256: `174e5411009e0e4f6ee8a8c97c4cd2f646791eae1b9aa2b425acb797e0353ef4`
- Converter checkpoint SHA-256: `14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a`
- Runtime closure: `requirements-runtime.lock.txt`, with hashes for every wheel
- Python: 3.12
- Torch and torchaudio: `2.8.0+cu128`

Before adding the trainer root to `sys.path`, the worker verifies either a clean
pinned Git checkout or the complete manifest of every non-Git file in the source
tree. This rejects unbound import shadows such as top-level `torch.py` or
`numpy.py`. The source module and all three checkpoints are verified again inside
the worker; the Supervisor independently hashes those files and the retained
worker wheel before it spawns the process.

Before readiness, the worker hashes the retained wheel, validates both wheel and
installed `RECORD` files, compares every wheel member with its installed byte,
and binds the complete installed-distribution manifest. It also binds a manifest
of every project module executed by this adapter, including
`workers.runtime.codec`, and rejects any installed dependency inventory that is
not exactly the package set and versions pinned by the packaged runtime lock.
`worker.ready.weight_revision` identifies the converter checkpoint.

The worker derives its own `configuration_hash` from canonical JSON containing
the adapter/schema revisions, source revision and complete source-tree manifest,
all three checkpoint digests, wheel/RECORD/distribution/executed-module digests,
runtime-lock digest, target speaker ID, device, sample rate, 20 ms frame size,
500 ms batch size, and 60 ms minimum inference size. Startup is rejected unless
the result exactly matches `worker.hello.configuration_hash`.

## Runtime

Keep source, environments, weights, WAVs, and raw logs below ignored
`artifacts/`. The validation layout is:

```text
artifacts/beatrice-2/trainer-source/
artifacts/beatrice-2/trainer-source/assets/pretrained/104_3_checkpoint_00300000.pt
artifacts/beatrice-2/trainer-source/assets/pretrained/122_checkpoint_03000000.pt
artifacts/beatrice-2/trainer-source/assets/pretrained/151_checkpoint_libritts_r_200_02750000.pt.gz
artifacts/beatrice-2/runtime-isolated-v2/
artifacts/beatrice-2/wheels-v2/
artifacts/beatrice-2/evidence/
artifacts/beatrice-2/identity.json
artifacts/beatrice-2/identity.env
```

Required environment:

```text
LIVECONV_BEATRICE_SOURCE_ROOT
LIVECONV_BEATRICE_SOURCE_REVISION
LIVECONV_BEATRICE_SOURCE_MODULE
LIVECONV_BEATRICE_SOURCE_SHA256
LIVECONV_BEATRICE_SOURCE_TREE_SHA256
LIVECONV_BEATRICE_PHONE_CHECKPOINT
LIVECONV_BEATRICE_PHONE_SHA256
LIVECONV_BEATRICE_PITCH_CHECKPOINT
LIVECONV_BEATRICE_PITCH_SHA256
LIVECONV_BEATRICE_CONVERTER_CHECKPOINT
LIVECONV_BEATRICE_CONVERTER_SHA256
LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256
LIVECONV_BEATRICE_WORKER_WHEEL
LIVECONV_BEATRICE_WORKER_WHEEL_SHA256
LIVECONV_BEATRICE_TARGET_SPEAKER_ID=37
LIVECONV_BEATRICE_SAMPLE_RATE=48000
LIVECONV_BEATRICE_BATCH_MS=500
LIVECONV_BEATRICE_DEVICE=cpu
```

`LIVECONV_BEATRICE_DEVICE` accepts `cpu` or `cuda`; CPU is the conservative
default. Build the current versioned worker wheel, then install its complete
hash-verified model closure into a venv that cannot see system site packages:

```bash
uv venv --clear --python 3.12 artifacts/beatrice-2/runtime-isolated-v2
uv pip sync \
  --python artifacts/beatrice-2/runtime-isolated-v2/bin/python \
  --require-hashes \
  workers/adapters/beatrice_2/requirements-runtime.lock.txt
uv build --package liveconv-worker-runtime --wheel \
  --out-dir artifacts/beatrice-2/wheels-v2
uv pip install \
  --python artifacts/beatrice-2/runtime-isolated-v2/bin/python \
  --no-deps --reinstall \
  artifacts/beatrice-2/wheels-v2/liveconv_worker_runtime-0.1.0-py3-none-any.whl
```

The packaging audit launches
`artifacts/beatrice-2/runtime-isolated-v2/bin/python -m
workers.adapters.beatrice_2.worker` from `/tmp`, with `PYTHONPATH` absent, through
`WorkerSupervisor`. This proves imports come from the installed `0.1.0` wheel,
not the checkout. The resulting artifact/configuration identity is recorded in
ignored `artifacts/beatrice-2/identity.json` and shell-ready
`artifacts/beatrice-2/identity.env`.

Run the process only through `WorkerSupervisor`; a manual invocation waits for a
`worker.hello` message on stdin.

## Checks

```bash
uv run --frozen --all-packages pytest -q workers/adapters/beatrice_2/tests
uv run --frozen ruff check workers/adapters/beatrice_2
uv run --frozen ruff format --check workers/adapters/beatrice_2
```

The deterministic backend additionally requires
`LIVECONV_ENABLE_TEST_BACKEND=1`. It exists only to verify protocol behavior. The
real checkpoint smoke test is opt-in with `LIVECONV_RUN_BEATRICE_REAL=1`,
`LIVECONV_BEATRICE_PYTHON` pointing to the isolated interpreter, and the artifact
environment above.
