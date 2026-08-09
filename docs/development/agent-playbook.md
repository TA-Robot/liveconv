# Codex multi-agent playbook

Status: Accepted process

## Operating model

The primary Codex agent owns intent, decomposition, cross-cutting decisions,
integration, and the final response. Project subagents use `gpt-5.6-luna` by
default for narrow, high-volume work. The primary remains responsible for
checking their evidence.

Project configuration lives in `.codex/config.toml`; custom roles live in
`.codex/agents/`. Built-in subagents are the low-latency coordination tier. The
[external Codex pool](external-codex-pool.md) is the overflow tier for disjoint
implementation, test, documentation, and read-only Sol review tasks; its tmux
processes remain subject to the same ownership and evidence rules.

## Critical-path pipeline

Use the dependency graph and dispatcher in `docs/planning/critical-path.md`.
The active user outcome and six delivery gates are in
`docs/planning/roadmap.md`; review findings use
`docs/planning/review-triage.md`. Agents judge a finding against that milestone
rather than silently importing post-v1 production requirements. Built-in and
external execution tiers may expose different limits. Work is
spawned from the Ready frontier rather than to fill a fixed team chart; the
external pool can be raised as high as 32 only when host resources and exclusive
leases permit it.

For different backlog nodes, keep three engineering stages active at once:

1. **Test N+1:** Luna `test_author` prepares deterministic failing acceptance
   tests and synthetic fixtures for the next accepted interface.
2. **Implement N:** a Luna worker implements the current Ready node in an
   exclusive directory or worktree against already accepted tests.
3. **Review N-1:** Sol `qa_reviewer` at `max` attacks the previous integrated
   checkpoint for races, security, regressions, privacy, and missing evidence.

The primary recomputes dependencies after every merge. It first assigns nodes on
the active milestone critical path, then nodes with the greatest downstream fan-out, then
research or test work that removes a named blocker. It may run up to six disjoint
writers and eight Sol reviewers. If two checkpoints wait for integration, new
writer slots rotate to review and repair until the merge queue drains.

Keep a slice small enough to review in one pass. It should normally have one
observable outcome, one ownership zone, focused tests, and no root lockfile or
backlog edits. The parent owns shared contracts, root tooling, integration, and
checkpoint commits; it does not co-author leaf implementation while a worker owns
that directory.

As soon as a slice reaches `Checkpoint`, commit it with its backlog item still in
`Review` and place it in the merge queue. Do not wait for an entire phase or
several packages to reach Gate Done. Integrate in dependency order, review the
integration SHA, and push a green checkpoint after two or three leaves. Run the
full root suite for every shared-contract change and every SHA used as the base of
new worktrees; leaf workers run focused checks while they iterate.

A worker stops and returns evidence when its stop condition is met. If it expands
scope, changes a shared file, or cannot produce a focused failing/passing test, the
parent interrupts and reissues a smaller brief. Long status narration is not a
deliverable.

## Luna execution modes

### Native custom-agent mode

Use this when the active Codex client allows `gpt-5.6-luna` as a spawned-agent
model. Ask for `spec_analyst`, `research_scout`, or another project role directly.
The agent file pins its model and behavior.

Configuration intent is not execution evidence. Record Luna as the worker model
only when the active client or invocation metadata confirms it. Some orchestration
APIs expose only Sol/Terra child overrides even when these project files request
Luna; those workers are useful fallbacks but must not be described as Luna runs.

### Inherited Luna swarm mode

The currently tested IDE execution surface can run Luna directly but exposes only
Sol and Terra as explicit child-model overrides. For that surface, run the
research batch in the default read-only sandbox:

```bash
make luna PROMPT_FILE=prompts/luna/phase0-kickoff.md
```

The launcher starts a read-only parent with `gpt-5.6-luna`. Its generic children
inherit both Luna and the process sandbox. Use this mode for research, test maps,
fixture preparation, and implementation briefs. It never supplies the independent
review required by the Definition of Done. A separate Sol primary or
`qa_reviewer` performs that review. Run `make luna-smoke` after a Codex upgrade or
environment change to retest the capability.

The launcher defaults to `read-only`. Do not combine a read-only preparation
swarm and repository integration in one invocation. After the primary agent
accepts the test or research handoff, use a separate, narrowly scoped writer invocation with
`LUNA_SANDBOX=workspace-write`, and do not spawn reviewer children from it.

Do not treat the custom-agent retry error as evidence that Luna itself is
unavailable. Check direct Luna execution and inherited child execution separately.

For parallel test preparation that must not write production code, set the parent
sandbox explicitly:

```bash
LUNA_SANDBOX=read-only make luna PROMPT_FILE=prompts/luna/test-design.md
```

Some container hosts block the user namespaces required by Codex read-only and
workspace-write sandboxes. `make luna-smoke` verifies an actual repository read so
this failure is visible. Do not run a swarm unsandboxed. On an already isolated,
disposable development container only, the smoke test accepts a deliberate
two-flag diagnostic fallback:

```bash
LIVECONV_ALLOW_UNSANDBOXED=1 \
LUNA_SANDBOX=danger-full-access \
make luna-smoke
```

Never use that fallback on an untrusted checkout or a general-purpose host. It is
only a capability diagnostic, not permission to run normal agent work without a
sandbox. The prompt and `AGENTS.md` must also prohibit reading ignored credentials
such as the workspace `key` file.

## When to delegate

Delegate when at least two workstreams can proceed independently and each has a
clear stop condition. Good first uses are:

- primary-source research on different candidates
- mapping separate ownership zones
- test execution across independent suites
- log and benchmark analysis
- specification review versus implementation review
- independent correctness, privacy, and audio-quality reviews

Keep work in the parent when it is a single short edit, a decision depends on the
immediately preceding result, or coordination costs exceed the work.

## Parallel write safety

Preferred order:

1. parallel read-only agents gather evidence
2. parent decides interfaces and ownership
3. write agents receive disjoint directories or worktrees
4. parent integrates one result at a time
5. independent reviewer checks the combined diff

Never let parallel writers share a package manifest, lockfile, protocol file,
root configuration, experiment registry, or ADR. Give one agent ownership or
serialize those edits.

## Task brief contract

Every delegated task includes:

```text
Goal:
Why now:
Inputs and source-of-truth IDs:
Owned files or read-only scope:
Required evidence:
Do not change:
Stop condition:
Return format:
```

For an experiment runner, also include the experiment ID, frozen commit, fixture
version, artifact policy, and invalidation conditions.

## Recommended orchestrations

### Research decision

```text
Have research_scout verify candidate A and candidate B in separate bounded tasks.
Have experiment_designer produce a comparison plan from the requirements only.
Wait for all results. Reconcile claims, then propose one approved experiment.
```

### Feature delivery

```text
Have test_author prepare accepted tests for node N+1 while the owning worker
implements node N and a Sol qa_reviewer reviews integrated node N-1. Recompute the
Ready frontier after each merge and immediately dispatch newly independent nodes.
```

### Cross-zone integration

```text
Freeze the shared protocol in the parent. Assign extension_worker and audio_worker
to separate worktrees with the frozen fixtures. Integrate sequentially and run
contract tests before end-to-end tests.
```

## Context hygiene

- Ask agents for distilled conclusions and file references, not raw logs.
- Store durable decisions in repository records instead of relying on chat memory.
- Close completed agents after their result is integrated.
- Start a new bounded subagent for a materially different question.
- Do not paste credentials, private audio, or restricted content into prompts.

## Model and effort

- Default: Luna at `xhigh` effort for scoped research, documentation, experiments,
  and implementation.
- Use Luna at `max` effort for experiment design, test authoring, audio
  concurrency implementation, and deterministic failure harnesses.
- Use Sol at `max` for independent correctness, race, security, privacy, and
  evidence review. Do not use Luna as the acceptance reviewer for Luna-authored
  work.
- Keep critical-path changes, ambiguous architecture, integration, and
  cross-system decisions in the Sol primary agent.
- Measure quality and cost before raising effort globally.

## Review sequence

1. Luna `test_author` lands or hands off accepted tests before implementation.
2. Owning Luna worker runs focused checks and self-reviews its diff.
3. Sol parent inspects the diff and integrates contracts.
4. Sol `qa_reviewer` reviews the integrated behavior read-only.
5. Parent reproduces or rejects each material finding, then assigns exactly one
   disposition: `fix-now`, `scheduled`, `accepted-risk`, or `out-of-scope`.
6. Owning worker addresses only `fix-now` findings; the reviewer does not author
   fixes. Scheduled work gets a named `MS-*` issue rather than holding the merge.
7. Reviewer performs one bounded re-review. A new non-stop-line Medium or Low is
   scheduled or accepted rather than recursively reopening the checkpoint.
8. Parent runs `make check` and the active milestone's real acceptance checks.
9. `docs_curator` updates approved records only after the decision is clear.

## Milestone replanning

After every green checkpoint or material blocker change, the primary:

1. updates the finding ledger and removes completed owners;
2. freezes what the checkpoint proved and what it did not prove;
3. marks newly satisfied dependencies in the active `MS-*` gate;
4. schedules later quality, performance, security, operations, or public-service
   concerns to their owning milestone;
5. dispatches all independent Ready work that fits ownership and resource leases;
6. stops alternate-model work after MS-3 unless a bounded issue can change the
   recorded model decision.

Default triage is fast: two hours to reproduce and normally one owner-day for a
current-milestone fix. Larger findings are split into the smallest safety fix
needed now plus a scheduled follow-up. Native fallback, exclusive playout,
generation isolation, sensitive-data handling, current SSH/auth boundaries,
evidence integrity, and expected-path boundedness remain stop-the-line concerns.

## Example kickoff prompt

```text
Work on LV-001 and LV-002 as a coordinated read-heavy batch. Delegate smoke-corpus
coverage to spec_analyst, the EXP-001 protocol to experiment_designer, and current
official API constraints to research_scout. Wait for all three. Do not edit files
from the subagents. Reconcile their evidence in the parent, update only the
approved experiment and backlog records, run make check, and report open decisions.
```

For inherited Luna mode, use the prepared prompt under
`prompts/luna/phase0-kickoff.md`; it embeds the same role boundaries without
requesting a custom agent type.
