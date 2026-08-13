# EXP-086: source-semantic multi-speaker stress matrix

Status: completed; source-semantic robustness rejected; operator hearing deferred

## Question

Does EXP-081's apparent improvement on noise and leading silence survive across
twelve real Common Voice utterances instead of one row per limitation?

Cross EXP-039's twelve changed utterances with five deterministic conditions:
clean, white noise at 20 dB SNR, 300 ms leading silence, tempo 1.2x, and pitch
+3 semitones. This produces 60 evaluation-only rows from six speakers. Compare
X-VC base, EXP-035 control69, and EXP-081 source-semantic. No training data,
model weights, or historical tongue-twister audio enter this experiment.

## Done and stop

- Materialize and freeze all 60 source identities before the GPU render.
- Publish 180 model outputs plus source/target references on 8878.
- Report per-condition source-relative ASR and gross repetition only.
- Do not rank naturalness, target voice, or a winner. Do not tune transform
  levels from the result.

## Result

All 60 rows and 180 model outputs were published. Against control69,
source-semantic changed the per-condition source-relative means as follows:

- clean `0.260 -> 0.233` (3 wins / 8 ties / 1 loss)
- noise20 `0.397 -> 1.247` (3 / 5 / 4) with one new gross repeated-character loop
- leading silence `0.288 -> 0.322` (4 / 7 / 1)
- tempo1.2 `0.374 -> 0.241` (6 / 4 / 2)
- pitch+3 `0.279 -> 0.379` (3 / 4 / 5)

The 60-row macro regressed from `0.320` to `0.484`. The one-row condition gain
did not generalize, so direct source-hidden supervision and any blend sweep are
closed. Machine ASR still does not judge naturalness or target voice.
