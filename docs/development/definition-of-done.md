# Definition of Done

Status: Accepted process

A change reaches a gate only when every applicable item is satisfied. Small,
reviewable checkpoints may be committed earlier under the rules below so work
does not accumulate into one integration batch.

## Checkpoint versus gate

`Checkpoint` means a coherent slice is safe to commit and push while its backlog
item remains `Review`:

- one owner and one ownership zone
- traceable behavior, explicit non-scope, and no shared-contract ambiguity
- accepted tests or explicit acceptance cases existed before implementation when
  the interface was already stable
- focused success, failure, and regression tests pass
- `make control-check`, Ruff on changed Python, and `git diff --check` pass
- no credential, private audio, model weight, or generated artifact is tracked
- the next reviewer can understand the slice without unpublished chat context

`Gate Done` means the full checklist in this document passes and the backlog item
may move to `Done`. A checkpoint is not experiment evidence, production approval,
or permission to bypass later independent review.

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
- A read-only Sol reviewer, separate from the Luna implementation and test-author
  roles, checks correctness, regressions, privacy, and test gaps on the integrated
  SHA. Luna self-review is useful but does not satisfy this item.
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
- A client-facing route documents prerequisites, trust boundary, setup,
  authenticated health checks, disconnect recovery, and one real-client smoke.
