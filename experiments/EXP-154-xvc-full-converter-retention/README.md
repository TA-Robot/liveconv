# EXP-154: selective retention with a full acoustic converter

Status: rejected after frozen fresh48

## Goal

Test whether EXP-150's useful anti-drift learning-target policy failed to repair
heldout collapse because its 69-module LoRA target could not express or reach a
general repair. The local tongue-twister is excluded from training and gating.

## One method change

Keep EXP-150's exact committed 170-position curriculum, 85 base-teacher hard
repair targets, 85 frozen control69 retention targets, target references,
upstream X-VC loss, LR `1e-4`, norm-5 clip, update order, and zero frame
condition. Start from the same control69 function by merging its adapter into
base X-VC, then change only the trainable target from its 69 LoRA modules to all
`42,357,760` parameters under `acoustic_converter`.

The trained converter is stored separately. Evaluation reconstructs base plus
merged control69 and replaces only that converter, preventing an accidental
change outside the admitted trainable target.

## Definition of done and stop

Train once and publish external7 on port 8878. Continue unchanged through
frozen fresh48 and Hadou31 only if the earlier screen has no candidate-added
gross corruption or broad common-row regression. Run untouched balanced
JSUT24 only if all three gates survive. Auxiliary ASR rejects loops and content
collapse only; it cannot select naturalness, target identity, a keeper, or a
product route.

Do not tune LR, loss, update count, curriculum ratio, retention blend, failure
threshold, frame condition, or converter sub-scope in this lane.

## Result

Commit `7afe5c5` trained all 42,357,760 converter parameters for 170 updates in
117.83 seconds at 5.56 GiB peak, with loss `227.96 -> 44.63`. External7 had no
gross repetition and tied control69 on source-relative mean (`0.360 -> 0.358`),
but known-text mean regressed `0.399 -> 0.494` and maximum source-relative
distance rose `0.571 -> 1.0`.

The frozen fresh48 gate rejected the unchanged checkpoint. It added a new
gross collapse on `cv39028774f`: `ご視聴ありがとうございました` became a
223-character run of `ん`. Across the 45 rows where neither control nor
candidate was gross, source-relative W/T/L was `9/25/11`, mean regressed
`0.326 -> 0.353`, and median regressed `0.250 -> 0.294`. Full-converter capacity
did not generalize selective hard repair and broadened failure risk. Close
trainable-scope neighbors; do not run Hadou31 or JSUT24 for this checkpoint.
