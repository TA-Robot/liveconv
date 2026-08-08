# Definition of Done

Status: Accepted process

A change is done only when every applicable item is satisfied.

## Traceability

- The change links to an FR, NFR, JP, GOV, ADR, EXP, risk, or backlog ID.
- Scope and intentional non-scope are explicit.
- Changed behavior and compatibility impact are documented.

## Implementation

- Ownership boundaries and shared contracts are respected.
- Bypass, cancellation, bounded queues, and stale-generation behavior remain safe.
- Error and fallback behavior are intentional and observable.
- No private audio, model weights, generated artifacts, or credentials are added.

## Verification

- Focused unit or contract tests cover the new behavior and failure path.
- Relevant integration, browser, or audio tests pass.
- Latency-affecting changes report warmup, P50, P95, sample count, and environment.
- Audio-quality claims include blinded or deterministic evidence as appropriate.
- `make check` passes from the repository root.

## Review

- The author inspects the complete diff.
- A read-only reviewer checks correctness, regressions, privacy, and test gaps.
- Material findings are fixed or explicitly accepted with an owner.

## Records

- Experiment status and result are updated when evidence changes.
- ADR and requirements are updated only when a decision changes.
- Backlog state reflects reality.
- New or changed risks have an owner and mitigation.

## Delivery

- Commit scope is coherent.
- The branch is pushable without local-only artifacts.
- Rollback or bypass is documented for user-facing audio changes.
