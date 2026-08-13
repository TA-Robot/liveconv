# EXP-141: clean post-adaptation X-VC rehearsal

Status: prepared; one bounded gpu0 lane

## Goal

Test a two-stage optimization method instead of retraining target identity and
off-distribution stability together from the base model. Start from the frozen
EXP-035 control69 adapter, then make one optimizer pass over clean full-output
teacher pairs derived from EXP-138's broad real-source pool.

## Admission and one method change

EXP-138's fixed pseudo-teacher screen found two gross loops and 33 of 209 rows
at source-relative auxiliary ASR distance at least `0.5`. Admit the first row
for each teacher ID only when it has no gross repetition and distance `<0.5`.
This leaves 170 unique inputs: Common Voice 35, Hadou 132, and JVS 3. The
`0.5` diagnostic existed before this successor; it is not fitted to EXP-139 or
EXP-140 outputs.

- Bound manifest: `artifacts/xvc-source-diversity/exp141-clean-post-rehearsal-inputs-v1/training.json`
- SHA-256: `86822d41aaf0f76f3acb8057dfe0f81f0ec077e82ee2c671ae8ed050684fdebc`

Unlike EXP-138's fresh-base 835 standard plus 209 teacher mixture, EXP-141
imports the completed control69 adapter and performs exactly 170 teacher-only
updates at the same LR `1e-4`, gradient clip 5, standard upstream loss, target
reference, zero frame condition, LoRA topology, and seed family.

## Definition of done and stop

Bind and commit the 170-row manifest, pass one real backward smoke, train once,
then publish external7, frozen fresh48, and frozen Hadou31 on port 8878. Reject
on any adapter-added gross loop or broad common-non-loop regression. JSUT is a
later untouched third-corpus evaluation, not training data. Auxiliary ASR does
not select naturalness, target identity, a keeper, or promotion.

No threshold, LR, epoch, source-count, loss-weight, adversarial, conditioning,
or module-scope sweep is admitted.
