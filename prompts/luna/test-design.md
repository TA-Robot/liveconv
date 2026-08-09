# Luna parallel test design

Read `AGENTS.md`, `docs/planning/critical-path.md`, and the accepted contracts.

Spawn generic Luna children only for independent test-design questions. Divide
the assigned next critical-path nodes by exclusive test directory. Produce
deterministic acceptance tests, synthetic fixtures, failure cases, and focused
commands. Do not review an implementation, approve a checkpoint, or make a
product decision.

Wait for all children. Deduplicate overlapping cases and return a test handoff for
each node. The Sol reviewer and primary integrator remain responsible for
independent review and acceptance.
