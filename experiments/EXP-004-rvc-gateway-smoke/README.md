# EXP-004 retained RVC Gateway smoke

`EXP-004` is the MS-1 / `LV-038` route check for one current retained RVC
technical-validation profile. It binds that profile through catalog, session,
configuration, and pipeline hashes rather than a semantic model-version label.
It is intentionally narrower than `EXP-003`: it does not compare or switch
between profiles, and it cannot make any quality, speaker, Japanese-content,
latency, authorization, license, security, or production-readiness claim.

The runner uses the shared protocol-v1 frame and control types plus the existing
`liveconv_audio` Gateway and worker profile boundary. It generates deterministic
non-speech float32 PCM only in memory. Generation 1 sends 28 frames at 20 ms
pace: the normal 25-frame RVC batch plus a three-frame tail before
`generation.end`. Its trace proves the Gateway-visible 50-frame ingress credit,
the client high-water mark within that credit, and all 28 frames draining.
The service-level delayed-worker regression separately proves the private
WorkerBridge accepted cap of 25; both results are required. Generation 2 covers
cancel/stale rejection. The emitted trace is metadata-only and rejects
credentials, tickets, voice IDs, artifact/runtime paths, worker endpoints,
payload digests, raw PCM, and free-form server errors.

Both external and auto-launched runs require one ignored retained profile
configuration. The runner validates it through `ProfileRegistry` with technical
profiles enabled, requires exactly one technical RVC worker profile, and binds
its public profile and configuration hashes to a catalog containing exactly one
matching entry before creating a session. Auto-launch pins the Gateway's base
ingress budget to 500 ms; the retained profile's 500 ms minimum context yields
the required exact session advertisement of 1000 ms and 50 frames.

Ordinary HTTP, WebSocket, and post-start server-event operations use the short
control timeout (`LIVECONV_EXP004_TIMEOUT_SECONDS`, default 10 seconds).
Auto-launch readiness and each bounded `generation.ready` wait instead use the
larger of 180 seconds and the selected profile's `first_output_ms` envelope.
This cold-start allowance does not change the required 20 ms input pacing.

## Checks

The deterministic fake requires no RVC artifact, Gateway process, GPU, or
ignored environment. It proves catalog/session identity handling, authenticated
HTTP plus exact-Origin attach wiring, the paced 25-frame batch plus three-frame
tail, output integrity rejection, stale-output gating, and acknowledged close
followed by already-absent DELETE/GET 404 teardown.

```bash
ROOT=experiments/EXP-004-rvc-gateway-smoke
uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" "$ROOT/exp004_tests"
uv run --frozen --all-packages ruff check "$ROOT"
uv run --frozen --all-packages ruff format --check "$ROOT"
```

## Opt-in live run

Live execution is destructive only to its disposable session and is disabled
unless `LIVECONV_EXP004_RUN_REAL=1`. A persisted trace also requires an exact
clean Git checkout: the supplied commit must equal `git rev-parse HEAD`, and
`git status --porcelain --untracked-files=all` must be empty. The trace path
must be outside the repository.

With no `LIVECONV_EXP004_GATEWAY_URL`, the runner starts the repository Gateway
on an ephemeral `127.0.0.1` port, forces technical profiles on, and forces
`max_sessions=1`. Supply the current ignored retained RVC profile configuration
and runtime environment; the runner forwards those inputs to the launched
Gateway but never writes them to its trace.

```bash
export LIVECONV_EXP004_RUN_REAL=1
export LIVECONV_EXP004_PROFILE_CONFIG='/approved/ignored/rvc-profile.json'
export LIVECONV_EXP004_PROFILE_ID='vc.rvc.synthetic-ja.v1'
export LIVECONV_EXP004_ORIGIN='chrome-extension://abcdefghijklmnopabcdefghijklmnop'
export LIVECONV_EXP004_TRACE='/tmp/exp-004-rvc-gateway-smoke.json'
export LIVECONV_EXP004_GIT_COMMIT="$(git rev-parse HEAD)"

uv run --frozen --all-packages python -m liveconv_exp004_rvc_gateway_smoke
```

To use an already running disposable Gateway, set
`LIVECONV_EXP004_GATEWAY_URL` and `LIVECONV_API_TOKEN` instead. Plain HTTP is
accepted only for a loopback URL, and HTTPS must also name a loopback host.
The existing Gateway must already be loopback-bound, set
`LIVECONV_ALLOW_TECHNICAL_PROFILES=1`, use
`LIVECONV_MAX_SESSIONS=1`, and select the same retained RVC profile.

The environment-gated test is equivalent:

```bash
ROOT=experiments/EXP-004-rvc-gateway-smoke
LIVECONV_EXP004_RUN_REAL=1 \
  uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" \
  "$ROOT/exp004_tests/test_live.py"
```

Exit zero means only `technical_outcome=passed`; `decision_status` remains
`inconclusive` in every trace.
