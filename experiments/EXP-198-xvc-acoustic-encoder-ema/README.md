# EXP-198: X-VC acoustic-encoder adaptation with upstream EMA

Status: Prepared listen-now training pilot; unselected

## Goal

Test whether the recurring content/timing residual is upstream of the acoustic
converter. Converter LoRA placement, retention data, condition replay, and an
explicit output-envelope objective all left tempo/silence tradeoffs. If the
frozen source acoustic representation loses useful boundary information,
converter-only adaptation cannot reconstruct it later.

## One method change

Merge the immutable EXP-035 control69 adapter into the X-VC base, freeze every
module except the source `acoustic_encoder`, and train its exact 21,521,536
parameters. Keep EXP-163's frozen CV/Hadou/JVS hard85/easy85 curriculum,
repair/retention targets, real-reference waveform adversarial objective, 170
sequential updates, learning rate, AdamW, gradient clipping, zero frame
condition, and upstream EMA schedule.

This is a representation-learning target, not another converter LoRA scope or
timing-loss point. One finite smoke decides only whether the target is
technically trainable. No adjacent encoder layer, LR, freeze-depth, or loss
variant is admitted.

## Definition of Done

- Commit the target setter, exact checkpoint format/reload, focused tests, and
  all evaluation identities before CUDA training.
- Run one hard/easy smoke and exactly one 170-update pilot.
- Publish the unchanged checkpoint on external7, fresh48, Hadou31, stress60,
  and balanced JSUT24 to port 8878, then close the lane.
- Record candidate-added consensus gross corruption and common-stable auxiliary
  content movement only. Do not infer naturalness, identity, or a winner.

## Frozen evaluation contract

The five surfaces are fixed before training: external7, 48 disjoint Common
Voice speakers/texts, 31 heldout Hadou sentences, the 60-row clean/noise20/
pitch+3/silence300/tempo1.2 matrix, and balanced 24-row JSUT categories. No set
is added or removed after seeing a result.

## Not in this experiment

No EXP-186/196 neighbor, PCGrad/L2-SP retry, encoder-depth sweep, new corpus,
human87 horizon/LR/scope retry, EXP-024 DTW retry, legacy tongue-twister
optimization, machine quality selection, promotion, or route claim.
