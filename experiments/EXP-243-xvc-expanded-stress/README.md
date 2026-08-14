# EXP-243: length-balanced symmetric stress evaluation

Status: completed; technically stable and unheard

## Goal

Map where the unheard EXP-238 pseudoparallel technical survivor retains or
loses Japanese content before choosing another retraining method. The existing
five surfaces include broad speakers and corpora, but their stress set uses one
direction and one severity for speed, pitch, silence, and noise. This is an
evaluation intervention, not another EXP-238 training sweep.

## One evaluation change

Select sixteen disjoint Common Voice speakers from the frozen fresh48 set:
four metadata-spread rows in each normalized-text-length band `10--14`,
`15--21`, `22--30`, and `40+` characters. Cross every row with nine fixed
conditions: clean, noise at 30 and 10 dB SNR, 100 and 600 ms leading silence,
tempo `0.8` and `1.2`, and pitch `-3` and `+3` semitones. This freezes 144
inputs without adding a training variable.

Render source, target, base X-VC, frozen control69, and the exact EXP-238 EMA
checkpoint for every input, producing 720 WAVs on listener port 8878. Auxiliary
ASR/CER is used only to locate content loss, gross loops, or empty/corrupt
output. It cannot decide naturalness, target identity, emotion, preference, a
keeper, or a winner.

## Definition of Done

- Freeze exactly four unique speakers in each of four length bands and all
  nine exact transforms for 144 rows.
- Commit the materializer, renderer binding, tests, and this plan before CUDA.
- Materialize the fixed inputs, pass exact CPU admission, and render one GPU
  lane containing base, control69, and EXP-238 comparisons.
- Publish all 720 WAVs on port 8878 and screen exact common-stable rows by
  length band and condition.
- Use the observed failure strata to choose one genuinely different data,
  loss, conditioning, or learnable-function intervention. Do not sweep
  EXP-238 target, LR, scope, rank, horizon, or EMA.

## Stop conditions

Stop on source identity drift, fewer than four eligible speakers in any length
band, transform drift, nonfinite or empty conversion, malformed adapter, or a
candidate-added gross corruption. A technically stable matrix remains unheard
and unselected until the operator returns.

## Result

Commit `19abe49` froze 144 inputs and the GPU lane published 720 WAVs at
`artifacts/ms3/listening/exp243-xvc-pseudoparallel-expanded-stress144-v1`.
Rendering took 109.64 seconds and peaked at 5,126,684,160 allocated bytes. The
v4 auxiliary screen found no control or candidate gross row.

Across the 104 rows where source, control, and candidate transcripts were all
stable, source-relative distance moved `0.401210 -> 0.311316` with W/T/L
`17/74/13`. Long rows improved most (`0.922435 -> 0.423835`); medium, short,
and very-long rows were near mixed. The thirteen losses were spread over eight
speakers and no condition dominated them. Clean, noise30, pitch+3, and a few
other strata remain mixed, so this is not evidence for a single condition
augmentation or an automatic quality winner. The next training intervention
changes one source-corpus block to genuinely multi-speaker smartphone
recordings while keeping targets, objective, scope, LR, updates, and EMA fixed.
