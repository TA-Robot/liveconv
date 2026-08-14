# EXP-171: category-balanced JSUT retention under the surviving EMA method

Status: external7 rendered; independent gates pending

## Goal

Test a method-level data change rather than another LoRA, LR, adversarial, or
EMA setting. Keep EXP-163's hard85 base-repair rows, 170 ordered updates,
control69 LoRA69 initialization, real-reference adversarial objective, original
Amitaro discriminator-real waveforms, optimizer, LR, norm-5 clip, zero frame
condition, and exact upstream EMA schedule. Replace only easy85 retention rows
with precommitted, category-balanced JSUT sources and their frozen control69
outputs.

The 85 JSUT sources exclude every JSUT24 evaluation ID and were selected by
transcript-order bin centers before model output. No row is replaced after the
teacher screen. Five source-relative ASR distances are at least 0.5, but no
teacher has a gross repetition; those rows remain in the one method pilot
rather than being output-filtered.

## Gate and stop

External7 is followed by fresh48, Hadou31, and stress60. Only survival of those
independent frozen gates opens JSUT24, which is sentence/category-heldout but
not speaker-heldout. A candidate-added gross corruption stops immediately.
Machine ASR can screen content/corruption only; it cannot select naturalness,
voice identity, a keeper, or promotion.

## Initial result

Commit `8d2d3cc` completed 170 updates in 146.49 seconds at 6.07 GB peak CUDA.
Loss moved from `298.40` to `114.65`; all generative, adversarial,
feature-matching, and discriminator components were finite. External7 added no
gross repetition. Source-relative mean exactly tied control69 at `0.3596`,
while known-text mean was worse (`0.3993 -> 0.4655`). Continue to the broader
independent gates; do not interpret the external7 tie as audible quality.
