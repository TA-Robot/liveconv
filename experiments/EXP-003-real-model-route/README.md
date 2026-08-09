# EXP-003 real-model Gateway route harness

This directory contains a reusable protocol-v1 client for a disposable Gateway
configured with an external curated model-profile registry. It sends deterministic
synthetic mono float32 PCM at 48 kHz in real-time-paced 20 ms frames and receives
output concurrently, which lets a batch-delayed worker fill and flush without
deadlocking the client.

Every emitted trace is explicitly `evidence_scope: technical_route_smoke` and
`decision_status: inconclusive`. A green run proves only the named route checks.
Sample change is not evidence of voice conversion, speaker change, Japanese
quality, content preservation, latency compliance, authorization, licensing, or
production readiness; the schema fixes all of those claims to `false`.

## Route checks

For every selected profile, the harness verifies:

- the Gateway catalog and session identities match hashes computed from the
  external registry;
- `session.ready.limits.max_ingress_frames` and `ingress_budget_ms` advertise
  enough static version-1 ingress credit for one configured worker batch;
- sent-minus-accepted-output frames never exceed that server-advertised credit;
- capture timestamps advance by exactly 20 ms while wall-clock sends are paced
  rather than burst into the Gateway, including after a worker/credit delay;
- output generation, contiguous sequence, and echoed source timestamp match;
- every output sample is finite and within normalized `[-1, 1]`, and at least one
  output sample changes across the completed generation;
- `generation.end` flushes a deliberately partial final batch without padding or
  loss;
- cancel closes the local output gate before the control message is sent, and
  later output from that invalidated generation is excluded;
- selection of each next distinct profile occurs only between generations and
  produces a new pipeline identity;
- the closed disposable session is explicitly invalidated through HTTP DELETE.

Version 1 has no dynamic `flow.credit` event. Its accepted credit advertisement
is the immutable `session.ready.limits` object. The harness uses the smaller of
`max_ingress_frames` and `ingress_budget_ms / 20 ms`, then maintains a local
outstanding-frame window against that bound.

The session is bootstrapped with the selected registry profile having the largest
`minimum_context_ms`. This gives the current Gateway an opportunity to advertise
enough static session credit before the harness switches through profiles. The
run fails rather than overrun or deadlock if advertised credit is smaller than
`LIVECONV_EXP003_BATCH_FRAMES`.

## Metadata and trust boundary

The harness reads exactly one explicitly supplied registry JSON file and direct
environment values. It does not load `.env`, key, credential, audio, checkpoint,
or worker files. Bearer credentials and optional voice IDs are held in redacted
dataclass fields and are used only in the HTTP request body/header required by the
Gateway.

Traces omit raw PCM, payload digests, bearer credentials, tickets, voice IDs,
registry paths, worker endpoints, runtime configuration values, license text,
and free-form server errors. They contain protocol identity, frame-header timing,
aggregate signal checks, credit accounting, and environment/runtime versions.
Raw synthetic PCM exists only in memory for input/output comparison.

The external registry remains the Gateway's source of truth. The harness parses
the same strict schema-v1 profile shape and computes the same public profile and
configuration hashes, but never launches a Gateway or worker and never mutates
the registry.

## Disposable real run

Use a disposable Gateway: this smoke creates a session, ends generations, cancels
one generation, and switches every named model profile. At least two distinct,
ready, streaming profiles are required. The profiles must support mono 48 kHz,
20 ms input and output. If a selected profile declares
`authorized_target_required`, set an already approved opaque voice ID.

Provide secrets directly in the process environment; do not point the harness at
credential files:

```bash
export LIVECONV_EXP003_RUN_REAL=1
export LIVECONV_EXP003_GATEWAY_URL='https://audio.example.test'
export LIVECONV_EXP003_ORIGIN='chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
export LIVECONV_EXP003_PROFILE_REGISTRY='/approved/config/model-profiles.json'
export LIVECONV_EXP003_PROFILE_IDS='vc.first.profile.v1,vc.second.profile.v1'
export LIVECONV_API_TOKEN='<session-only-bearer-value>'
export LIVECONV_EXP003_TRACE='/tmp/exp-003-real-route.json'
export LIVECONV_EXP003_BATCH_FRAMES=25
export LIVECONV_EXP003_PARTIAL_FRAMES=3
export LIVECONV_EXP003_CANCEL_FRAMES=2
export LIVECONV_EXP003_GIT_COMMIT="$(git rev-parse HEAD)"
export LIVECONV_EXP003_WORKTREE_CLEAN=true
```

Optional values are:

```text
LIVECONV_EXP003_VOICE_ID
LIVECONV_EXP003_TIMEOUT_SECONDS       default: 10
```

Run either the environment-gated integration test:

```bash
ROOT=experiments/EXP-003-real-model-route
uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" \
  "$ROOT/exp003_tests/test_live.py"
```

or the package CLI (non-secret settings may also be supplied as CLI options):

```bash
uv run --frozen --all-packages python -m liveconv_real_model_route
```

Exit zero means only `technical_outcome=passed`; the printed and serialized
experiment decision remains `inconclusive`. Exit one is a completed technical
failure. Exit two is configuration or transport setup failure.

## Deterministic checks and build

The fake Gateway delays output until a full batch, flushes a partial end batch,
injects a stale post-cancel frame, and supplies two profile/pipeline identities.
Fault variants prove rejection of sequence, timestamp, non-finite, normalized
range, and unchanged-output violations.

```bash
ROOT=experiments/EXP-003-real-model-route
uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" \
  "$ROOT/exp003_tests"
uv run --frozen --all-packages ruff check "$ROOT"
uv run --frozen --all-packages ruff format --check "$ROOT"
uv build --project "$ROOT" --out-dir "$ROOT/dist"
```

Build products under `dist/`, traces, and real-model artifacts are run outputs,
not experiment evidence to commit.
