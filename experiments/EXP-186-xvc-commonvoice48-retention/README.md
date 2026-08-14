# EXP-186: speaker-balanced Common Voice retention under the X-VC EMA method

Status: prepared; training-data render pending

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
Every speaker appears once; 37 speakers selected by equal-width index centers
appear a second time, so exposure differs by at most one and no model output or
evaluation score selects the data. Each exposure stays attached to the original
easy slot's Amitaro target ID. External7, expanded33, fresh48, and every Hadou,
stress, and JSUT evaluation row remain excluded from source selection.

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
