# EXP-134: X-VC model-window-aware teacher pool

Status: prepared; awaiting bound manifest and one gpu0 lane

## Goal

Test whether selecting the exact source windows consumed by X-VC, rather than
full-utterance metadata whose later sounds may never enter the model, improves
broad content stability without adding repetition.

## One change

Keep EXP-130's CV24, JVS3, 48-source total, 209 full-output teacher positions,
835 standard positions, 1,044 updates, objective, target, control69 LoRA, LR,
and seed. Replace Hadou21 with 21 unique training-only model windows selected
from EXP-133: seven start, seven middle, and seven end 2.4-second windows. Use
only rows with full-utterance auxiliary CER at most 0.15, no source-ASR gross
repetition, and at least four normalized characters; greedily maximize new
window-ASR 1/2/3-grams.

## Definition of done and stop

Bind and commit the pool, pass one backward smoke, train once, then render the
same external7, frozen fresh48, and frozen Hadou31. Reject on an adapter-added
gross loop or a broad common-non-loop regression. Auxiliary ASR can reject
content corruption only; it cannot select naturalness, target identity, or a
winner.
