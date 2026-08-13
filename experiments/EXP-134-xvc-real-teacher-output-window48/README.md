# EXP-134: X-VC model-window-aware teacher pool

Status: completed; broad content signal retained, generic keeper rejected

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

## Bound input

- Manifest: `artifacts/xvc-source-diversity/exp134-window-teacher48-inputs-v1/training.json`
- SHA-256: `4b0e8627f9a6743cf966d3ec61ea51e2a0205cca741ddc00ea31012b70488a87`
- Composition: Common Voice 24, Hadou 21, JVS 3
- Hadou window positions: start 7, middle 7, end 7
- EXP-133 audit SHA-256: `641521ba94c9a7ee788e906c1bbfeeaaa97ea0525616b59d54ba411269687dd2`
- Method commit: `8e69a32`

## Definition of done and stop

Bind and commit the pool, pass one backward smoke, train once, then render the
same external7, frozen fresh48, and frozen Hadou31. Reject on an adapter-added
gross loop or a broad common-non-loop regression. Auxiliary ASR can reject
content corruption only; it cannot select naturalness, target identity, or a
winner.

## Result

One 1,044-update run completed in `322.89` seconds at `4.77 GiB` peak. Standard
loss moved `144.22 -> 131.99`; full-output teacher loss moved `161.02 ->
70.12`. External7 had no loop and improved control source-relative distance
`0.360 -> 0.320`, with known-text distance `0.399 -> 0.393`.

EXP-135's 46 common non-loop fresh rows favored this adapter 14/23/9 with mean
`0.341 -> 0.321`, median `0.275 -> 0.254`, and known-text mean `0.618 ->
0.589`. EXP-136's 30 common non-loop Hadou rows favored it 6/21/3 with mean
`0.185 -> 0.160` and known-text mean `0.441 -> 0.421`.

The no-added-loop gate still failed: `RECITATION324_138` produced the same
53-count repeated `三・四` pattern as EXP-124/130, while base and control did
not. The 209 frozen-base pseudo-teacher outputs contained no gross loop. Reject
EXP-134 as a generic keeper, retain its broad non-loop improvement as unheard
audio, close additional source-coverage selection points, and externally test
the preregistered low-semantic-token safety hypothesis before choosing between
fallback routing and a different training objective.
