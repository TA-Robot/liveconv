# EXP-086: source-semantic multi-speaker stress matrix

Status: preparing frozen inputs; operator hearing deferred

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
