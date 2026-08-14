# EXP-171: category-balanced JSUT retention under the surviving EMA method

Status: completed v4 technical survivor; human listening pending

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

The original beam-5-only Hadou screen falsely rejected the method. The same
2.4-second source produced a physically impossible 428-character number
sequence under beam 5, while greedy decoding returned a short plausible
sentence. The candidate's alleged 53 repetitions therefore were ASR search
hallucination, not supported acoustic evidence. V4 now requires greedy/beam-5
agreement for gross repetition and compares content only on cross-arm common
decoder-stable, non-gross rows.

Under v4, the unchanged checkpoint added zero consensus gross rows across all
five frozen gates. Common stable results versus control69 were:

- external5: source-relative `0.256 -> 0.253`, known-text `0.371 -> 0.283`;
- fresh33: source-relative `0.198 -> 0.187`, known-text `0.545 -> 0.523`;
- Hadou25: source-relative `0.133 -> 0.108`, known-text `0.369 -> 0.347`;
- stress44: source-relative `0.218 -> 0.212`, known-text effectively tied
  `0.598 -> 0.599`; noise and leading silence improved, tempo1.2 regressed;
- JSUT22: source-relative regressed `0.115 -> 0.134`, while known-text improved
  `0.553 -> 0.544`; counters, loanwords, and most other rows tied.

The 850 comparison WAVs across external7, fresh48, Hadou31, stress60, and
balanced JSUT24 remain on port 8878. This is an unselected mixed technical
survivor, not a naturalness, identity, keeper, or promotion decision. Do not
sweep JSUT share or category counts.
