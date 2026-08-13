# EXP-145: control69 hard-negative discovery

Status: prepared; training-only diagnostic

## Goal

Explain the failure left by EXP-141 before choosing another X-VC learning
objective. Render the frozen EXP-035 control69 adapter on all 170 clean,
unique, training-only real sources admitted before EXP-141. Compare those
outputs with each source and with the already-frozen non-gross base-X-VC
teacher output.

## Decision

If control69 gross-collapses on a source whose base teacher did not, that row is
a genuine training-only hard negative. Such rows may admit one later
anti-collapse curriculum whose single change is failure-triggered sampling.
If no such rows exist, do not train: the heldout collapse is not reproduced by
this pool, so change loss, conditioning, or trainable target instead.

This is not another source-count, window, threshold, or generic coverage point.
No fresh48, Hadou31, JSUT24, or local tongue-twister row is read or trained on.
The diagnostic does not evaluate naturalness, target identity, a keeper, or
promotion.
