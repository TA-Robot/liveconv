# EXP-154: selective retention with a full acoustic converter

Status: ready for one bounded gpu0 lane

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
