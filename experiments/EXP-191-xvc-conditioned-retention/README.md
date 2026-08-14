# EXP-191: condition-balanced control69 retention replay

Status: fresh48 technical gate passed; stress60 final gate next

## Goal

Test whether the surviving hard-repair/EMA method can retain rate, pitch,
silence, and noise behavior when the easy branch distills control69 directly on
conditioned real sources. This targets EXP-186's clear tempo1.2 residual while
preserving its fresh48 and Hadou gains.

## One method change

Keep EXP-186's 48 speaker identities, speech-active windows, 85 easy-slot
bindings, hard85 repair rows, 170 sequential updates, control69 initialization,
LoRA69 scope, real-reference adversarial objective, optimizer, LR, clipping,
zero frame condition, and upstream EMA exact.

Change only the easy source/teacher condition policy. Cycle the 85 frozen easy
exposures through 17 rows each of clean, deterministic 15 dB noise, tempo1.1,
pitch +2 semitones, and 150 ms leading silence. Generate a new frozen control69
output from each conditioned source and use that output as its retention target.
Condition assignment is manifest-order only and reads no text, ASR, model
output, evaluation score, or previous result.

The heldout stress matrix is not identical: cleaner 20 dB noise, faster
tempo1.2, pitch +3, and 300 ms silence on disjoint speakers/texts. Results
therefore test transfer across severity, not only replay of exact evaluation
transforms.

## Why this is not EXP-043 or EXP-044

EXP-043 changed pseudo-source timing while supervising an unmodified clean
Amitaro target and regressed. EXP-044 applied tempo/pitch/silence to both source
and target waveforms across 1,044 fresh-base standard updates; it improved seven
rows but regressed the changed-utterance set and is closed.

EXP-191 instead keeps the surviving EXP-186 initialization, selective 85/85
curriculum, adversarial objective, EMA, and 170-update budget. Its easy target is
the control69 conversion generated from the already-conditioned real source, so
the teacher defines the aligned retention behavior rather than mechanically
warping a clean target. It is one new retention-target construction, not an
augmentation-ratio retry.

## Definition of done and stop

Commit the condition binder/renderer/curriculum changes and tests before CUDA.
Render exactly 85 conditioned control69 targets and stop on any candidate-added
consensus gross row. Otherwise train one 170-update lane and publish external7.
If external7 has no gross or broad common-stable regression, render fresh48 and
then stress60 from the unchanged checkpoint. Do not tune condition counts,
severities, schedule, objective, LR, scope, EMA, or update count. Machine ASR is
only a content/corruption diagnostic; it cannot select naturalness, identity, a
keeper, or promotion.

## External7 result

Commit `376348f` produced 85 conditioned control69 teachers with zero consensus
gross-repetition row. The hard/easy smoke was finite. The one admitted
170-update lane completed in 141.1 seconds at 5.74 GiB peak, with total loss
`298.40 -> 128.46`, and published 35 WAVs at
`artifacts/ms3/listening/exp191-xvc-conditioned-retention-ema-v1`.

The external7 screen found no gross repetition. On the five rows stable under
both control69 and EXP-191 decoders, source-relative distance moved
`0.256 -> 0.191` and known-text distance `0.371 -> 0.254`; both comparisons had
W/T/L `3/1/1`. This admits the unchanged checkpoint to frozen fresh48. It does
not establish naturalness, identity, a keeper, or promotion.

## Fresh48 result

EXP-192 reused the unchanged checkpoint on 48 disjoint speakers and texts and
published 240 WAVs. Control69 and EXP-191 share the same two gross rows, so the
candidate adds none. On 37 cross-arm common stable rows, source-relative
distance is effectively flat at `1.074 -> 1.076` with W/T/L `5/24/8`; known-text
distance moves `0.811 -> 0.807` with `8/23/6`.

This is a mixed technical survivor rather than a broad regression. It admits
the final stress60 transfer test because condition retention is the stated
question. No Hadou or JSUT cascade is reserved for this family.
