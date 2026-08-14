# EXP-186: speaker-balanced Common Voice retention under the X-VC EMA method

Status: all frozen technical gates complete; mixed survivor; hearing pending

## Goal

Test whether retention diversity should come from many speakers rather than
mostly one-speaker Hadou content or one-speaker category-balanced JSUT. This is
the next distinct data-construction point after the parameter-anchor method
failed to preserve fresh, pitch, silence, and tempo behavior.

## One method change

Repeat EXP-163's hard85/easy85, real-reference adversarial, 170 sequential
updates, control69 initialization, LoRA69 scope, optimizer, LR, clipping, zero
frame condition, and upstream EMA schedule. Keep all 85 hard repair rows exact.

Replace only the 85 easy retention rows with sources from EXP-114's frozen 48
training-only Common Voice speakers and their newly frozen control69 outputs.
Before slot binding, decode each complete frozen MP3 and apply one output-blind
window policy to all 48 speakers: among 2.4-second windows at 100 ms hops,
maximize samples above absolute amplitude 0.01, then squared energy, then prefer
the earliest start. This reads no text, ASR, model output, or evaluation score.
Every speaker appears once; 37 speakers selected by equal-width index centers
appear a second time, so exposure differs by at most one. Each exposure stays
attached to the original easy slot's Amitaro target ID. External7, expanded33,
fresh48, and every Hadou, stress, and JSUT evaluation row remain excluded from
source selection.

This intentionally trades the prior easy set's 66 one-speaker Hadou utterances
for 48-speaker source diversity. It is one bounded corpus-role comparison, not
a speaker-count or exposure sweep. The 48 sources were used previously in a
different full-output-teacher objective; that failure does not answer whether
they work as control69 retention replay inside the surviving selective method.

## Definition of done and stop

Commit the source binder, target renderer, curriculum binder, tests, and this
plan before CUDA. Render exactly 85 control69 training targets, reject any
candidate-added gross target corruption, then train exactly one 170-update
EXP-163-style EMA lane and publish external7 on port 8878.

If external7 survives, use the same frozen checkpoint on fresh48, Hadou31, and
stress60. JSUT24 opens only if those gates do not show candidate-added gross
corruption or broad common-stable regression. Do not tune speaker count,
duplicate count, source selection, ratio, LR, scope, EMA, or objective. Machine
ASR remains a content/corruption screen, never naturalness, identity, a keeper,
or promotion.

## Source-window preflight

The first target preflight reused EXP-114's historical leading 2.4-second
windows. It rendered 85 control69 targets in 106.4 seconds at 2.49 GiB peak,
but the consensus two-decode screen found one candidate-added gross loop. More
importantly, 12/85 exposures (six speakers) produced only zero to three source
characters under both decoders. The gross row's complete MP3 contains clear
speech later, while its leading window decoded as only `ん`.

That v1 target set is stopped and must not train. No row is removed or replaced
from the speaker schedule. The v2 speech-active policy is instead applied to
all 48 original MP3s by signal only; for the gross row it moves the frozen
window from 0.0 to 3.7 seconds. This is part of the one data-construction method,
not an ASR-selected repair. Render all 85 v2 control targets and enforce the
same zero-consensus-gross admission rule before the single 170-update lane.

## Training and external7

V2 rendered all 85 targets in 98.4 seconds at 2.49 GiB peak with zero
consensus gross row. The final curriculum contains Common Voice 125 and Hadou
45 rows while retaining the exact 85 repair / 85 retention split. A hard/easy
smoke was finite, then the one committed lane completed 170 optimizer updates
in 125.9 seconds at 5.74 GiB peak. Total recorded loss moved from 298.40 to
140.30; the upstream-equivalent EMA made 170 calls and six moving-average
updates. Adapter SHA-256 is
`a505c8eda3bf2cffe588cdf4a340733b5799a2392a33b4cb8bc02cfcd8cf0102`.

External7 adds 35 WAVs on port 8878 and zero consensus gross rows. Across the
five control69/candidate rows that are decoder-stable and non-gross in both
arms, source-relative distance moves `0.256 -> 0.206` and known-text distance
moves `0.371 -> 0.254`; both have win/tie/loss `3/1/1`. This admits the frozen
fresh48 gate as EXP-187. It is auxiliary content evidence, not naturalness,
target identity, a keeper, or a product winner.

## Frozen follow-up gates

The unchanged adapter completed EXP-187 fresh48, EXP-188 Hadou31, EXP-189
stress60, and EXP-190 JSUT24. The family now contributes 850 WAVs on port 8878.

- Fresh48: the candidate and control69 share the same two gross rows and the
  candidate adds none. Across 35 common stable rows, source distance moves
  `0.210 -> 0.203` with W/T/L `6/24/5`; known text moves `0.560 -> 0.550`
  with `8/23/4`.
- Hadou31: zero gross rows. Across 24 common stable rows, source moves
  `0.119 -> 0.0777` with `5/19/0`; known text moves `0.351 -> 0.323` with
  `5/18/1`.
- Stress60: zero gross rows. Across 44 common stable rows, source is nearly
  neutral at `0.216 -> 0.212` while known text is mixed at `0.591 -> 0.601`.
  Noise20 and leading silence improve; pitch is mixed; tempo1.2 has zero wins,
  four ties, and four losses on both diagnostics.
- JSUT24: zero gross rows. Across 22 common stable rows, source moves
  `0.115 -> 0.131` with `2/16/4`; known text moves `0.553 -> 0.543` with
  `4/17/1`. Category directions are mixed.

The combined speech-active/multi-speaker retention construction is therefore a
stronger technical survivor for ordinary fresh and Hadou content, not a generic
constraint solution. Preserve it for hearing and close this training family.
The next method must address its tempo/pitch residual without tuning EXP-186.
