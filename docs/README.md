# Documentation map

The documentation is organized by the kind of claim it contains.

| Area | Purpose | Key entry point |
|---|---|---|
| Product | User problem, scope, and requirements | `product/brief.md` |
| Architecture | System boundaries and accepted decisions | `architecture/overview.md` |
| Research | Candidate technologies and evidence gaps | `research/model-matrix.md` |
| Experiments | Method, metrics, and experiment lifecycle | `experiments/README.md` |
| Planning | Phase gates and prioritized work | `planning/roadmap.md` |
| Development | Agent workflow, environment, and done criteria | `development/agent-playbook.md` |
| Risks | Active technical, product, and governance risks | `risks/register.md` |

## Record types

- `FR-*`: functional requirement
- `NFR-*`: non-functional requirement
- `ADR-*`: accepted architecture decision
- `EXP-*`: controlled experiment
- `LV-*`: deliverable backlog item
- `R-*`: tracked risk

A record may link to another record, but it must not silently replace it. For
example, an experiment can support an ADR, but it does not become an ADR until
the decision is recorded.

## Document states

- **Draft**: open for substantial change
- **Proposed**: ready for review against evidence
- **Accepted**: current source of truth
- **Superseded**: retained for history with a replacement link
