# Contributing

## Before changing code

Link the change to a requirement (`FR-*` or `NFR-*`), experiment (`EXP-*`),
architecture decision (`ADR-*`), or backlog item (`LV-*`). If none exists, add
the smallest missing record before implementation.

## Branches and commits

- `spec/<topic>` for requirements and architecture
- `exp/<id>-<topic>` for experimental work
- `feat/<topic>` for accepted product behavior
- `fix/<topic>` for defects
- `chore/<topic>` for tooling and maintenance

Keep commits reviewable and avoid mixing generated artifacts with source changes.

## Pull requests

A pull request must state:

- the question or behavior being addressed
- source-of-truth identifiers
- what changed and what intentionally did not
- validation commands and observed results
- latency or quality impact when audio behavior changes
- privacy, security, and voice-consent implications
- follow-up work and unresolved uncertainty

Run `make check` before requesting review.

## Experiments

Create experiments with:

```bash
make experiment ID=EXP-002 SLUG=audio-loopback TITLE="Audio loopback"
```

Fill the generated plan before execution. Track aggregate results and decisions
in Git; store restricted recordings and large artifacts outside the repository.
