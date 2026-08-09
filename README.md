# liveconv

Specification-led experiments for making realtime AI speech sound natural in
Japanese while preserving conversational responsiveness.

The project evaluates two complementary paths:

- streaming voice conversion applied to the existing realtime audio
- controlled text normalization followed by an external Japanese TTS engine

The repository starts with the operating system for the work: product
requirements, architecture decisions, experiment records, Codex subagents,
and repeatable checks. Application code is added only after a milestone gate makes
its contract clear.

## Start here

1. Read [AGENTS.md](AGENTS.md) for repository-wide execution rules.
2. Read [docs/product/brief.md](docs/product/brief.md) for the product intent.
3. Read [docs/planning/roadmap.md](docs/planning/roadmap.md) for milestone gates.
4. Read [docs/development/agent-playbook.md](docs/development/agent-playbook.md)
   before delegating parallel work.
5. Use [review finding triage](docs/planning/review-triage.md) to decide what
   blocks now, moves to a later milestone, is accepted, or is post-v1.
6. Run `make doctor` and `make check`.

To connect a Chrome client to a loopback-only Gateway on a remote machine, use
the [SSH tunnel client setup](docs/development/ssh-tunnel-client-setup.md).

## Common commands

```bash
make doctor
make check
make server
make git-auth KEY=/workspace/liveconv/key
make experiment ID=EXP-002 SLUG=audio-loopback TITLE="Audio loopback"
make lock-dev
make luna PROMPT_FILE=prompts/luna/phase0-kickoff.md
```

## Repository map

```text
.codex/          Project Codex configuration and custom subagents
.devcontainer/   Reproducible CPU-side development environment
.github/         CI and contribution templates
apps/            Loadable Chrome MV3 capture and exclusive playout Extension
docs/            Product, architecture, research, planning, and operations
deploy/          Hardened remote Gateway deployment and TLS termination
experiments/     Machine-readable experiment plans and tracked conclusions
packages/        Wire protocol, evaluation, and revision-pinned STT libraries
services/audio/  Authenticated remote PCM and model-profile gateway
workers/         Isolated real-model runtimes added one candidate at a time
schemas/         Schemas for experiment metadata and other contracts
scripts/         Bootstrap, validation, and workflow helpers
```

Large model files, recordings, generated audio, credentials, and raw experiment
artifacts do not belong in Git. Track only metadata, small fixtures with explicit
permission, aggregate measurements, and conclusions.

The Luna swarm command starts a Luna parent and asks it to spawn generic children
that inherit Luna. This is the tested fallback for Codex clients whose native
custom-agent spawn surface currently exposes only Sol and Terra overrides.

## Current stage

The project is closing MS-1, the executable multi-model lab. The bounded remote
router, Extension, worker supervisor, evaluation/STT packages, package gate, and
SSH client path are implemented. Multiple real model engines have technical
execution evidence; RVC is the first rolling Gateway integration candidate.
Current model quality failures and unassessed lanes keep those profiles technical
and nonselectable until MS-2 chooses a useful primary.

The six-milestone target is a lightweight personal v1 reached through an SSH
local forward to a loopback-only remote Gateway. Public DNS/TLS ingress,
multi-user operation, HA, an uptime SLA, and enterprise operations are post-v1
and do not block this path.
