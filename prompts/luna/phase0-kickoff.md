# Phase 0 Luna swarm kickoff

Read `AGENTS.md`, `docs/product/requirements.md`,
`docs/experiments/evaluation.md`, `docs/planning/roadmap.md`,
`docs/planning/backlog.md`, and the EXP-001 files first.

Coordinate a read-heavy preparation batch for LV-001 and LV-002. Do not begin
LV-018 or collect experiment results.

This entire invocation is read-only. Spawn exactly three generic subagents in
parallel. Do not select a custom agent type and do not specify a model; each child
must inherit this Luna parent and its read-only process sandbox.

1. **Specification analyst:** check whether the proposed 40-utterance smoke
   categories cover JP-001 through JP-008 and identify precise missing acceptance
   cases. Return a compact coverage table and open decisions.
2. **Experiment designer:** turn EXP-001 into a pre-registration-ready protocol.
   Propose frozen variables, warmup, sample count, randomization, numeric decision
   thresholds, invalidation conditions, and minimum aggregate result fields.
3. **Research scout:** verify the current official OpenAI documentation relevant
   to Japanese realtime prompting, output text availability, interruption, and
   supported Web or API capture constraints. Return direct official links,
   version-sensitive caveats, and no implementation guesses.

Wait for all three agents. Reconcile conflicts in the parent. Then:

- return exact proposed edits for EXP-001 planning files and
  `docs/planning/backlog.md` where evidence makes the next step unambiguous
- leave product or architecture decisions open when user intent is required
- do not collect experiment results
- do not create application code
- do not edit any repository file or run a command that writes into the repository
- report the proposed plan, evidence, target files, and remaining decisions
