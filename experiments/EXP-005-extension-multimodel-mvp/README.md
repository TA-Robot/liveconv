# EXP-005: ChatGPT tab multi-model Extension MVP

Status: draft. This is the MS-2 hands-on integration gate for one real audible
`chatgpt.com` tab, the unpacked Extension, the pinned SSH local forward, one
authenticated Gateway, and the four prepared model routes.

The result remains `inconclusive` for quality, speaker similarity, content,
latency, authorization, licensing, security, and release readiness. A technical
pass establishes only that the bounded MVP execution evidence was captured.

## Evidence Boundary

EXP-005 separates two evidence products:

- The Extension/Gateway runtime produces the machine receipt. Its source is
  exactly `extension_gateway_runtime`; it is not authored or completed by the
  operator.
- The operator records only four listening judgments in a separate document.
  Each judgment is bound to the receipt ID, runtime `pipeline_id`, and protocol-v1
  `generation_id` for its matching attempt.

A boolean-only listening document is not a reproduction and is rejected. A
deterministic fake may exercise the frozen four-model contract, but its report is
always `evidence_kind: contract_test` and `technical_outcome: inconclusive`.
It can never satisfy MS-2.

Reports are metadata-only. They reject raw media, credentials, route locations,
host identifiers, artifact paths, target/reference material, weights, free-form
notes, and producer error text.

## Frozen Inputs

`fixtures/four-model-roster.json` has exactly four prepared deployment entries,
in this order: `rvc-v2`, `beatrice-2`, `x-vc`, and `openvoice-v2`. Each binds the
exact deployed `profile_id`, `profile_hash`, and `configuration_hash`. There is
no `pipeline_hash`: protocol version 1 assigns a new UUID `pipeline_id` at
runtime for a selected profile/configuration pair.

`fixtures/operator-plan.json` freezes one manual sample per model, manual
lifecycle controls, a native baseline, and the forced-fallback step. Neither
fixture retains prompt text, audio, account details, voice/reference data,
credentials, worker details, runtime locations, or host identifiers.

Each fixture revision is a content digest, not an operator-selected label. It is
the SHA-256 of UTF-8 JSON formed from the complete object after removing its
revision field, serialized with `ensure_ascii=true`, sorted keys, and separators
`,` and `:`. Updating an exact deployment identity therefore requires updating
the fixture content and recomputing the revision; `load_roster` and
`load_prompt_plan` reject a mismatch.

## Runtime Receipt Contract

The receipt is schema version 1 and has no optional fields. It must include:

- `source: extension_gateway_runtime`, a canonical UUID `receipt_id`, and the
  exact frozen roster and operator-plan revisions.
- `chatgpt_tab` facts that an audible `chatgpt.com` tab was observed and capture
  began after a user gesture. Account authentication is not a machine claim.
- `ssh_loopback` facts that the configured local forward reached the Gateway,
  that client and remote bindings are loopback-only, and that a pinned server
  identity was configured. These facts do not claim a live SSH handshake or pin
  verification.
- `gateway_authentication` facts for the authenticated Gateway session, a
  single-use session grant, exact Extension Origin verification, and
  `max_sessions: 1`. These facts never carry the bearer credential or grant.
- Four ordered runtime attempts. Every attempt repeats the frozen model/profile
  identity, has a dynamic canonical UUID `pipeline_id`, a strictly increasing
  unsigned protocol-v1 `generation_id`, its route mode, and boolean facts for
  finite output, changed output, stale-output acceptance, exclusive playout, and
  End triggering.
- A fifth, dedicated forced-failure probe after the four attempts. Its
  `forced_failure_event` has `event_type: fallback.required`, exact OpenVoice
  profile/configuration identity, the fourth attempt's `pipeline_id`, and a new
  `generation_id` strictly greater than every attempt generation. It must carry
  the machine-only `failure_injected: true` fact; a spontaneous fallback does
  not satisfy this probe.
- A matching `native_fallback_event` with
  `event_type: extension.native_fallback_activated`, that same OpenVoice
  profile/pipeline/generation identity, native route active, and remote route
  inactive.

`report.schema.json` contains the complete report and receipt contract. The
required producer facts are deliberately stable, non-sensitive assertions; the
Extension and Gateway must emit them after real state transitions rather than
infer them from a hand-completed form.

The separately bound `manual_operator` document must additionally assert all of
the following as `true`: `chatgpt_account_authenticated_asserted`,
`ssh_tunnel_established_asserted`, and
`ssh_pinned_server_identity_verified_asserted`. These are operator assertions,
not machine-observed transport facts, and they are required for a technical pass.

## Pass Rule

A `runtime_receipt` report can pass only when all of these are true:

1. The required ChatGPT observation, SSH-loopback configuration,
   Gateway-authentication, four-attempt, and forced-fallback receipt facts
   validate against the exact frozen inputs. The separately bound operator
   evidence explicitly asserts account authentication, established SSH tunnel,
   and pinned server-identity verification.
2. At least two live attempts have finite, changed, non-stale, exclusively
   played output, and their separately bound manual judgments say that changed
   output was audible.
3. OpenVoice is a finite, changed, non-stale, exclusively played,
   End-triggered buffered preview with a matching audible judgment. It is never
   labelled live.
4. No attempt accepted stale output, all four attempts observed exclusive
   playout, and the dedicated fifth forced-failure probe restored exclusive
   native playout.
5. The report is written from the exact clean checked-out commit to a destination
   outside the repository.

## Producing A Report

The runtime producer writes the receipt outside Git after the real run. The
operator then writes a separate manual-judgment document containing the receipt
ID, the three explicit account/tunnel/pin assertions, and the four `{model_id,
pipeline_id, generation_id, audible_changed_output}` records. The CLI refuses
the older boolean-only shape.

```bash
ROOT=experiments/EXP-005-extension-multimodel-mvp
uv run --frozen --all-packages python -m liveconv_exp005_extension_multimodel_mvp \
  --roster "$ROOT/fixtures/four-model-roster.json" \
  --prompt-plan "$ROOT/fixtures/operator-plan.json" \
  --runtime-receipt /approved/operator/exp-005-runtime-receipt.json \
  --manual-audible-judgments /approved/operator/exp-005-audible-judgments.json \
  --git-commit "$(git rev-parse HEAD)" \
  --output /approved/operator/exp-005-report.json
```

Run the deterministic contract checks without Chrome, SSH, GPU, workers, or
model artifacts:

```bash
ROOT=experiments/EXP-005-extension-multimodel-mvp
uv run --frozen --all-packages pytest -q -c "$ROOT/pyproject.toml" "$ROOT/exp005_tests"
uv run --frozen --all-packages ruff check "$ROOT"
uv run --frozen --all-packages ruff format --check "$ROOT"
```
