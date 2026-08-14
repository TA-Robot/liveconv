# EXP-171: category-balanced JSUT retention under the surviving EMA method

Status: rejected on frozen Hadou31; human listening pending

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

## Result

Commit `8d2d3cc` completed 170 updates in 146.49 seconds at 6.07 GB peak CUDA.
Loss moved from `298.40` to `114.65`; all generative, adversarial,
feature-matching, and discriminator components were finite. External7 added no
gross repetition. Source-relative mean exactly tied control69 at `0.3596`,
while known-text mean was worse (`0.3993 -> 0.4655`). Continue to the broader
independent gates; do not interpret the external7 tie as audible quality.

Frozen fresh48 added no gross failure beyond control69. Both arms shared the
natural repeated-source row and the same catastrophic `家族と家族` row. Across
the 46 common non-gross rows, candidate versus control69 source-relative W/T/L
was `14/24/8`, mean `0.341 -> 0.320`, and median `0.275 -> 0.177`; known-text
mean moved `0.618 -> 0.608`.

Hadou31 rejected the method. Control69 had zero gross rows, while the candidate
added a gross collapse on `RECITATION324_138`: after `笑いかけながら` it
repeated the number pattern `三、四` 53 times. The raw candidate mean improved
`0.210 -> 0.186`, but that average cannot override a candidate-added gross
failure. Do not run stress60 or JSUT24 and do not sweep the JSUT ratio or
category mix. Preserve the comparison audio for later human diagnosis; this is
not a naturalness or target-voice decision.
