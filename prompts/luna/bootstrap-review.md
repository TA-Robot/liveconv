# Initial workspace parallel review

Read `AGENTS.md`. Review the staged initial repository state before its first
commit. There is no prior `main` commit, so inspect `git diff --cached` and the
staged files directly.

Spawn exactly four generic subagents in parallel. Do not select a custom agent
type and do not specify a model; each child must inherit this Luna parent. All
agents are read-only and must not edit files.

1. Review `.codex/`, `AGENTS.md`, the Luna scripts, and prompts for current config
   validity, contradictory orchestration rules, unsafe autonomy, and workflows
   that cannot execute.
2. Review experiment schema, EXP-001, registry, Makefile, and validation scripts
   for data-contract bugs, false-positive checks, portability problems, and
   destructive behavior.
3. Review product, architecture, roadmap, backlog, evaluation, and risk documents
   for contradictions, accidental decisions, missing phase gates, and broken
   traceability.
4. Review `.gitignore`, GitHub files, Dev Container, SSH setup, and security docs
   for secret leakage, excessive permissions, CI failures, and unsafe voice-data
   handling.

Wait for all four. In the parent, verify every claimed issue against the staged
files. Return findings first, ordered by severity, with file and line references.
If there are no findings, say so and list only material residual risks. Do not
edit files.
