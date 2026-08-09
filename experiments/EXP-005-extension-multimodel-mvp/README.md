# EXP-005: ChatGPT tab multi-model Extension MVP

Status: draft until the deployment roster, client, prompts, profile identities,
and execution states are frozen.

This is the MS-2 hands-on gate. It tests the actual Extension, SSH local forward,
Gateway, and multiple real workers together before MS-3 selects a model.

The result is technical only. Poor quality is recorded, not hidden, and does not
invalidate executability. Native/remote overlap, stale output, missing fallback,
false model availability, sensitive-data retention, a missing attempt for any of
the four prepared models, or fewer than two audible live profiles invalidate the
run. OpenVoice must be invocable as a bounded End-triggered preview; a disabled
label does not satisfy “try every model.”

Manual Start, End, Interrupt, Next, and idle-boundary profile selection are the
supported ChatGPT lifecycle. The experiment does not scrape the DOM or infer
conversation boundaries.

Before changing `status` to `approved`:

1. freeze the complete four-model roster and safe execution/decision reason codes;
2. bind RVC, Beatrice 2, and X-VC live routes plus the OpenVoice buffered preview
   to exact identities, with no unavailable entry;
3. freeze the operator prompt sequence and non-sensitive environment fields;
4. implement the metadata-only runner/report and its schema;
5. run deterministic Extension, Gateway, switching, fallback, and secret tests;
6. obtain an independent Sol plan review.

## Metadata-only runner

`fixtures/four-model-roster.json` is the frozen safe roster fixture. It has
exactly four prepared entries in this order: `rvc-v2`, `beatrice-2`, `x-vc`, and
`openvoice-v2`. Every entry binds a public profile ID plus profile,
configuration, and pipeline SHA-256 identities. The first three entries are
live; OpenVoice is only `buffered_preview_after_end`.

`fixtures/operator-plan.json` freezes one manual sample per roster model,
manual lifecycle controls, and the native baseline/fallback steps. It retains no
prompt text, audio, account details, voice/reference data, credentials, worker
details, runtime locations, or host identifiers.

The runner accepts only boolean operator observations for each invocation and a
forced-failure fallback check. It writes no media and rejects free-form evidence
or metadata fields that could contain sensitive route material. A report always
remains technically scoped and `inconclusive` for quality, speaker, content,
latency, authorization, licensing, security, and release decisions.

Run its deterministic fake-route contract checks without Chrome, GPU, workers,
or model artifacts:

```bash
ROOT=experiments/EXP-005-extension-multimodel-mvp
uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" "$ROOT/exp005_tests"
uv run --frozen --all-packages ruff check "$ROOT"
uv run --frozen --all-packages ruff format --check "$ROOT"
```

For an actual approved operator run, use a manually completed JSON document with
only this shape; it is deliberately unable to carry notes or raw technical
values:

```json
{
  "attempts": {
    "rvc-v2": {"audible_changed_output": true, "end_triggered": false},
    "beatrice-2": {"audible_changed_output": true, "end_triggered": false},
    "x-vc": {"audible_changed_output": false, "end_triggered": false},
    "openvoice-v2": {"audible_changed_output": true, "end_triggered": true}
  },
  "forced_failure": {
    "native_fallback_observed": true,
    "native_remote_overlap_observed": false
  }
}
```

The command verifies that the supplied commit is `HEAD`, the checkout is clean,
and the report destination is outside the repository before writing. It does not
start Chrome, SSH, a Gateway, or a model worker.

```bash
ROOT=experiments/EXP-005-extension-multimodel-mvp
uv run --frozen --all-packages python -m liveconv_exp005_extension_multimodel_mvp \
  --roster "$ROOT/fixtures/four-model-roster.json" \
  --prompt-plan "$ROOT/fixtures/operator-plan.json" \
  --manual-evidence /approved/operator/exp-005-evidence.json \
  --git-commit "$(git rev-parse HEAD)" \
  --output /approved/operator/exp-005-report.json
```
