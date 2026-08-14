# EXP-198: X-VC acoustic-encoder adaptation with upstream EMA

Status: Completed listen-now comparison; rejected as a general retraining
direction; audio remains unheard and unselected

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

## Result

The hard/easy smoke was finite. The single 170-update run completed in 132.0
seconds with 21,521,536 trainable parameters and about 5.78 GiB peak allocated
CUDA memory. Total training loss moved from `298.554` to `117.298`. The exact
119-tensor acoustic-encoder checkpoint has SHA-256
`642a8f85450d08a078001da68ff6661fbbba7c31889315540ac9cb95f85b1db2`.

The unchanged checkpoint produced 850 comparison WAVs across the five frozen
surfaces. It introduced no consensus gross-repetition row. On cross-arm common
stable rows, however, the auxiliary source-relative distance moved as follows:

- external7: `0.256 -> 0.238` on 5 rows;
- fresh48: `0.205 -> 0.323` on 31 rows;
- Hadou31: `0.149 -> 0.114` on 26 rows;
- stress60: `0.206 -> 0.237` on 43 rows, including tempo1.2
  `0.156 -> 0.268`;
- JSUT24: `0.115 -> 0.145` on 22 rows.

The target helped the heldout Hadou surface but regressed disjoint speakers,
tempo, and balanced JSUT. This rejects acoustic-encoder adaptation as the next
general X-VC retraining direction. Do not open encoder-depth, learning-rate,
freeze-scope, or adjacent-module points. The machine screen is only a coarse
content/corruption diagnostic; it does not judge naturalness, target identity,
or audible quality, and it does not replace later operator hearing.
