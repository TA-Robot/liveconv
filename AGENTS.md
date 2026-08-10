# liveconv agent guide

## Mission

Build an evidence-driven system that improves Japanese speech produced during
realtime AI conversations. Preserve turn-taking, interruption behavior, and
operational safety while comparing voice conversion with external TTS.

## Source-of-truth order

When documents disagree, use this order and repair the lower-priority document:

1. User instruction in the active thread
2. Accepted ADR under `docs/architecture/adr/`
3. `docs/product/requirements.md`
4. `docs/architecture/overview.md`
5. Active experiment plan under `experiments/`
6. `docs/planning/backlog.md`
7. Remaining notes and historical results

Do not silently convert a hypothesis into a requirement or an experiment result
into a product decision. Record decisions explicitly.

## Default workflow

1. Inspect the relevant source-of-truth documents and current Git state.
2. State the active milestone outcome, task boundary, expected evidence, and
   affected ownership zones.
3. Apply the milestone relevance gate below before assigning review or fixes.
4. Delegate independent work when two or more bounded workstreams exist.
5. Keep the parent agent responsible for decisions, integration, and user-facing
   conclusions.
6. Implement only after the owning requirement or experiment is identifiable.
7. Run only the validation tier required by the changed surface. Full
   `make check` is reserved for implementation integration, a shared production
   contract, or milestone close; planning-only work uses planning/control checks.
8. Update the experiment, ADR, backlog, or risk record when the work changes what
   the project knows.

## Milestone relevance gate

Milestones exist to prevent technically valid but currently unnecessary work.
Before reviewing, fixing, testing, or documenting a finding, answer:

1. Does it prevent an explicit deliverable or real run in the active milestone?
2. Can it make the active milestone falsely pass, lose user data or secrets, or
   violate a safety invariant exercised by that milestone?
3. Is it explicitly required by the active milestone gate or the user's current
   instruction?

Only work with at least one `yes` is eligible for `fix-now`. Ease, severity in a
hypothetical deployment, or proximity to edited files is not enough. Everything
else receives `scheduled`, `accepted-risk`, or `out-of-scope` and must not be
implemented or re-reviewed in the current milestone.

Review is not a default stage and has no quota. Before starting one, record the
current-milestone decision it can change, the plausible review outcomes, and the
different action taken for each outcome. If no plausible result changes what is
built, run, selected, or accepted in the active milestone, do not perform the
review. Continue reviewing only while it supplies information needed for that
decision; stop when the decision is supported.

## Multi-agent policy

Use project agents from `.codex/agents/`. The default subagent model is
`gpt-5.6-luna`, chosen for narrow, repeatable, and high-volume work.

- Recompute the Ready frontier in `docs/planning/critical-path.md` after every
  green checkpoint and delegate all independent bounded nodes that fit the
  available slots and resource leases.
- Use Luna for bounded implementation, test authoring, research, fixture work,
  test execution, and log analysis.
- Use `qa_reviewer` on `gpt-5.6-sol` for independent correctness, security, and
  evidence review. Luna output never satisfies the independent-review gate.
- Independent review is required only when its result can change an integrated
  implementation or milestone-evidence decision. A planning edit does not imply
  review by itself.
- Give every subagent a bounded question, expected output, and stop condition.
- Wait for all delegated work that can affect the decision before integrating.
- Return summaries and evidence to the parent; do not flood the main thread with
  raw logs.
- Run write-heavy agents in separate ownership zones or separate Git worktrees.
- Never assign two agents to edit the same file set concurrently.
- The parent owns cross-cutting files including `AGENTS.md`, root configs,
  architecture contracts, the experiment registry, and release decisions.
- A subagent may spawn another agent only when explicitly asked by the parent.

Suggested roles:

- `spec_analyst`: resolve requirements and acceptance criteria without editing.
- `research_scout`: verify models, APIs, licenses, and benchmarks from primary
  sources.
- `experiment_designer`: propose controlled experiments and decision rules.
- `experiment_runner`: run one approved experiment and record reproducible data.
- `extension_worker`: own isolated Chrome Extension implementation tasks.
- `audio_worker`: own isolated audio service and DSP implementation tasks.
- `test_author`: write deterministic acceptance tests for the next critical-path
  node without editing production code.
- `qa_reviewer`: use Sol to independently review correctness, regressions, and
  evidence after integration.
- `docs_curator`: update explicitly assigned documentation after decisions.

### Luna runtime compatibility

Some Codex clients list `gpt-5.6-luna` as a runnable model but do not yet expose
Luna as an explicit `spawn_agent` override. In that environment, do not repeatedly
retry a custom agent that pins Luna. Start the parent through
`scripts/luna-swarm.sh`, then spawn generic children without specifying a model or
custom agent type. They inherit the Luna parent and can follow role briefs from
the prompt and this file. See `docs/development/agent-playbook.md`.

Inherited Luna swarms are preparation or implementation tools, not final
reviewers. Run the Sol reviewer from a separate parent or custom-agent invocation.

Never read the ignored workspace file named `key`. Git authentication uses the
installed copy selected by repository-local Git configuration; agents have no
reason to inspect private-key content.

## Ownership zones

Until application scaffolds exist, create code only in an approved backlog item.
Expected zones are:

```text
apps/extension/        Chrome MV3 capture, routing, controls, and playout
services/audio/        Streaming conversion and TTS gateway
packages/protocol/     Shared event and binary-frame contracts
packages/evaluation/   Metrics, fixtures, and report generation
workers/               One isolated runtime per real model profile
experiments/<ID>/      One experiment's plan, aggregate results, and decision
```

Changes across more than one zone require a short integration plan. Shared
protocol changes require consumer tests or fixtures on both sides.

## Experiment discipline

- Every model or architecture claim starts as a hypothesis.
- Assign an `EXP-NNN` identifier before running a comparison.
- Freeze input fixtures and configuration before collecting comparative results.
- Record environment, commit, model revision, parameters, warmup, sample count,
  and raw-artifact location.
- Report P50 and P95 for latency. Do not present a single best run as typical.
- Separate added pipeline latency from end-to-end conversational latency.
- Include failure cases, not only representative successes.
- Do not declare a winner until the experiment's decision rule is satisfied.

## Product invariants

- Bypass must always remain available when audio transformation fails.
- Original and transformed audio must not play simultaneously by accident.
- Interruption must cancel queued synthesis or conversion from an older
  generation.
- Display text and spoken text are separate data products.
- Voice references require authorization and explicit provenance.
- Raw user audio, reference voices, credentials, and model weights are never
  committed.
- DOM scraping is acceptable only for a personal Web proof of concept; production
  architecture must use supported APIs and explicit contracts.

## Engineering rules

- Prefer deterministic normalization for telephone numbers, addresses, IDs,
  money, dates, units, and approved pronunciation dictionaries.
- Carry monotonic timestamps and `generation_id` through streaming boundaries.
- Keep model adapters behind a common contract; do not leak model-specific state
  into the Extension protocol.
- Treat ADR-0002 and `docs/architecture/remote-protocol.md` as the frozen version
  1 contract. A model worker never edits the gateway or shared protocol.
- Keep final playout and immediate native fallback in the Extension. The remote
  gateway returns candidate PCM but never becomes the only audible route.
- Bound queues and define overflow behavior.
- Keep default fixtures synthetic or redistributable.
- Verify current APIs, model behavior, and license terms from primary sources
  before depending on them.
- Avoid broad refactors during experiments. Change one independent variable when
  possible.

## Validation

At implementation integration or milestone close, run:

```bash
make check
```

For planning-only edits, run syntax/schema checks for changed records,
`make control-check`, and `git diff --check`. For a leaf implementation, run its
focused zone tests. Do not run unrelated Python, browser, audio, packaging, or
GPU suites merely because they exist. As code arrives, add zone-specific checks
behind `make check`. A successful command is evidence, not the whole Definition
of Done; consult
`docs/development/definition-of-done.md`.

## Git and secrets

- Use short-lived branches named `spec/`, `exp/`, `feat/`, `fix/`, or `chore/`.
- Keep commits scoped to one coherent claim or behavior.
- Do not commit `key`, `.env`, private recordings, generated audio, weights, or
  access tokens.
- Do not place secrets in remote URLs, command examples, issue text, logs, or
  experiment metadata.
- Use `scripts/setup-git-auth.sh` when the workspace filesystem does not preserve
  private-key permissions.
