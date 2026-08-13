# EXP-118: X-VC full-output teacher with FFN-only LoRA

Status: completed; rejected as a generic keeper

## Question

Can freezing attention adaptation retain EXP-116's broad content signal without
adding local repetition failures?

## Independent variable

Keep EXP-116's frozen train48 pool, complete converted-output teacher targets,
835 standard and 209 teacher positions, 1,044 updates, LR, rank, seed, zero
frame condition, and Amitaro target fixed. Change only the LoRA target scope:

- EXP-116: 69 converter attention and feed-forward linears;
- EXP-118: the contained 22 feed-forward linears, with all 47 attention targets
  frozen.

The FFN-only scope contains ten `ff_c` and twelve `ff_x` linears and 450,560
trainable LoRA parameters. This is one method-level freeze point, not a scope
sweep.

## Stop

Commit method and focused tests before gpu0. Pass one real-model full-output
backward smoke, then train once. Render external7 and frozen fresh48. Stop before
stress60 on any added gross loop or broad common-non-loop regression. Do not fit
fresh48 or open neighboring scope points. Machine metrics cannot select
naturalness, target voice, or a winner.

## Runtime admission

Commit `481efb9` passed 52 focused tests and exact CPU admission for 835 standard
plus 209 full-output teacher rows. The committed FFN-only real-model smoke
produced a 38,400-sample teacher target, full composite loss `161.0455`, LoRA
gradient norm `11.5205`, and 3.28 GiB peak GPU allocation with exit status zero.

## Result

Commit `b01793e` completed 1,044 updates in 310.78 seconds at 4.77 GiB peak.
Standard loss moved `144.22 -> 135.37`; full-output teacher loss moved
`161.05 -> 72.51`. External7 had no gross loop and improved control69
source-relative `0.360 -> 0.290` and known-text `0.399 -> 0.383`.

EXP-119 rejected the method on frozen fresh48. The candidate retained
control69's catastrophic repeated-family failure and added a separate
110-character `ぃ` run. On the 45 rows where no arm looped it was nearly tied
with control69: 14/21/10 W/T/L, source-relative mean `0.329` versus `0.326`,
and median `0.273` versus `0.250`. Attention adaptation is therefore necessary
to remove at least one known failure, but EXP-116 already showed it is not
sufficient. Stop the scope branch; do not run stress60 or adjacent scopes.
