# Luna parallel review

Read `AGENTS.md` and inspect the current branch against `main`.

Spawn four generic subagents in parallel without a custom agent type or model so
they inherit Luna. They are read-only reviewers for:

1. correctness and state-machine defects
2. audio timing, buffering, cancellation, and stale-generation risks
3. privacy, secrets, voice authorization, and license risk
4. missing tests, experiment evidence, and source-of-truth drift

Wait for all reviewers. Deduplicate their findings, verify every cited file and
line in the parent, and report findings by severity. Do not edit files.
