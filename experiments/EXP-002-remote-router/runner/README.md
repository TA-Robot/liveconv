# EXP-002 remote router runner

This package runs a bounded route smoke against the real version 1 gateway with
synthetic canonical PCM. It records protocol metadata and payload digests, never
raw audio, bearer tokens, or WebSocket tickets.

A green command means only that the eight named route-smoke cases passed. Every
trace remains `decision_status: inconclusive` for EXP-002 and lists the missing
full-experiment lanes. It does not collect the frozen 40-fixture/600-turn corpus,
STT, exact-entity, integrity-confidence, or paired-latency evidence required for
an EXP-002 decision.

With no URL, the CLI launches the repository gateway on a free loopback port:

```bash
uv run --project experiments/EXP-002-remote-router/runner \
  --extra test liveconv-router-experiment \
  --trace /tmp/liveconv-exp-002-trace.json
```

To connect to an existing gateway, provide its HTTPS base URL and put the bearer
credential in an environment variable. Plain HTTP is accepted only on loopback.

```bash
LIVECONV_API_TOKEN='...' \
uv run --project experiments/EXP-002-remote-router/runner \
  liveconv-router-experiment \
  --gateway-url https://audio.example.test \
  --origin chrome-extension://abcdefghijklmnopabcdefghijklmnop \
  --trace /tmp/liveconv-exp-002-trace.json
```

The suite covers passthrough, deterministic gain, bad bearer authentication,
one-use ticket replay, sequence gaps, stale frames after cancellation, model
switching during an active generation, and HTTP session deletion.

Run focused checks with:

```bash
RUNNER=experiments/EXP-002-remote-router/runner
uv run --project "$RUNNER" --extra test pytest "$RUNNER/tests"
uv run --project "$RUNNER" --extra test ruff check "$RUNNER"
uv run --project "$RUNNER" --extra test ruff format --check "$RUNNER"
```

The environment-gated `live` pytest case runs the same destructive fault suite
and therefore requires a disposable gateway, not a shared service.
