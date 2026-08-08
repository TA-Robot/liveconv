# Codex multi-agent playbook

Status: Accepted process

## Operating model

The primary Codex agent owns intent, decomposition, cross-cutting decisions,
integration, and the final response. Project subagents use `gpt-5.6-luna` by
default for narrow, high-volume work. The primary remains responsible for
checking their evidence.

Project configuration lives in `.codex/config.toml`; custom roles live in
`.codex/agents/`.

## Luna execution modes

### Native custom-agent mode

Use this when the active Codex client allows `gpt-5.6-luna` as a spawned-agent
model. Ask for `spec_analyst`, `research_scout`, or another project role directly.
The agent file pins its model and behavior.

### Inherited Luna swarm mode

The currently tested IDE execution surface can run Luna directly but exposes only
Sol and Terra as explicit child-model overrides. For that surface, run the
research batch in the default read-only sandbox:

```bash
make luna PROMPT_FILE=prompts/luna/phase0-kickoff.md
```

The launcher starts a read-only parent with `gpt-5.6-luna`. Its generic children
inherit both Luna and the process sandbox. The batch returns recommendations to
the invoking primary agent, which performs any approved integration separately.
This path was verified with a real child turn. Run `make luna-smoke` after a Codex
upgrade or environment change to retest the capability.

The launcher defaults to `read-only`. Do not combine a read-only review swarm and
repository integration in one invocation. After the primary agent accepts the
recommendations, use a separate, narrowly scoped writer invocation with
`LUNA_SANDBOX=workspace-write`, and do not spawn reviewer children from it.

Do not treat the custom-agent retry error as evidence that Luna itself is
unavailable. Check direct Luna execution and inherited child execution separately.

For a review that must not write, set the parent sandbox explicitly:

```bash
LUNA_SANDBOX=read-only make luna PROMPT_FILE=prompts/luna/review.md
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
Have spec_analyst trace acceptance criteria and qa_reviewer identify likely test
risks in parallel. After both return, assign exactly one owning worker to the
implementation zone. Run qa_reviewer again on the final diff.
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

- Default: Luna at medium effort for scoped research, documentation, experiments,
  and implementation.
- Use Luna at high effort for bounded correctness and race-condition review.
- Keep ambiguous architecture and cross-system decisions in the primary agent.
- Measure quality and cost before raising effort globally.

## Review sequence

1. Owning worker runs focused checks.
2. Parent inspects the diff and integrates contracts.
3. `qa_reviewer` reviews the final combined behavior read-only.
4. Owning worker or parent addresses findings.
5. Parent runs `make check` and any phase-specific end-to-end checks.
6. `docs_curator` updates approved records only after the decision is clear.

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
