# EXP-203: X-VC unpaired human content/identity factorization

Status: Prepared listen-now training pilot; unselected

## Goal

Test a different data and objective architecture after converter placement,
retention replay, explicit timing loss, and acoustic-encoder adaptation failed
to improve all broad surfaces. Use substantially broader human Japanese speech
without forcing source and target waveforms into a false frame alignment.

## One method change

Select 170 Hadou source windows spread deterministically across all 334 train
IDs in the existing human manifest. Pair every source with a real Amitaro
`runrun` target window 167 train positions away, so the reference text is
different. Each side contributes one guarded maximum-energy 2.4-second active
window. There is no stretch, DTW, phoneme alignment, target-content loss, or
heldout access.

Start from the immutable control69 adapter and update its same 69 LoRA modules
for one 170-row pass. The source supplies semantic tokens and frozen Whisper
content supervision. The unrelated Amitaro window supplies the global speaker
condition, speaker-prediction target, and real side of the pretrained waveform
adversarial/feature-matching objective. The frame condition remains zero.
AdamW, learning rate `1e-4`, gradient clipping, and the established upstream EMA
schedule remain fixed.

This is an alignment-free factorized human-data objective, not another
retention corpus, LoRA placement, encoder depth, timing-loss weight, human87
horizon, or EXP-024 DTW retry.

## Definition of Done

- Commit the materializer, factorized loss, runner identity, tests, and all
  evaluation identities before CUDA training.
- Run one two-row finite smoke and exactly one 170-update pilot.
- Publish the unchanged checkpoint on external7, fresh48, Hadou31, stress60,
  and balanced JSUT24 to port 8878, then close the lane.
- Record candidate-added consensus gross corruption and cross-arm common-stable
  auxiliary content movement only. Do not infer naturalness, identity, or a
  winner.

## Frozen evaluation contract

The five existing surfaces remain fixed: external7, 48 disjoint Common Voice
speakers/texts, 31 heldout Hadou sentences, the 60-row clean/noise20/pitch+3/
silence300/tempo1.2 matrix, and balanced 24-row JSUT categories. No evaluation
set is added or removed after seeing a result.

## Stop conditions

Stop on input or split drift, same-text source/reference pairing, nonfinite
loss/gradient, malformed adapter, OOM, candidate-added gross corruption, or
broad common-stable content regression. Do not tune semantic/speaker/
adversarial weights, target rotation, window selection, update count, LR,
scope, or EMA after this run. Generated audio remains unheard and unselected.
