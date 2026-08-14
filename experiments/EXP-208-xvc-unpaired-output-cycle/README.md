# EXP-208: X-VC final-waveform content cycle

Status: Prepared listen-now training pilot; unselected

## Goal

Close the concrete mismatch exposed by EXP-203: internal semantic-decoder MSE
can improve Hadou rows while the final waveform still develops repetition and
tempo regressions. Make linguistic preservation a constraint on the converted
audio itself without returning to parallel waveform alignment.

## One method change

Reuse EXP-203's exact 170 unique Hadou source windows, unrelated-text Amitaro
speaker/reference windows, control69 LoRA69 initialization, target-speaker
loss, real-reference adversarial/feature objective, optimizer, learning rate,
clip, zero frame condition, update count, and upstream EMA.

Replace only EXP-203's weight-1000 MSE on the converter's internal semantic
decoder with weight-1000 MSE between the frozen source Whisper hidden states
and hidden states obtained by applying the same frozen Whisper encoder through
a differentiable log-mel frontend to the final converted WAV. Frames remain in
their original positions; no stretch, DTW, transcript, target-content waveform,
or heldout row is used.

This is output-level linguistic cycle consistency. It is not the closed
semantic-weight, temporal sample-difference, activity-envelope, teacher-waveform,
alignment, pairing, LR, scope, or horizon family.

## Definition of Done

- Verify the differentiable frontend against X-VC's frozen Whisper path and run
  one real two-row finite backward smoke before training.
- Commit the method, tests, plan, and external7/fresh48/Hadou31/stress60/JSUT24
  identities before one 170-update CUDA run.
- Publish the unchanged EMA checkpoint on all five surfaces to port 8878.
- Record candidate-added consensus corruption and cross-arm common-stable
  auxiliary content movement only; do not infer naturalness, identity, or a
  perceptual winner.

## Stop conditions

Stop on frontend mismatch, missing waveform-to-content gradient, nonfinite
loss/gradient, OOM, malformed adapter, candidate-added gross corruption, or
broad common-stable content regression. Do not tune the cycle weight, frontend,
data, pair rotation, windows, scope, LR, horizon, or EMA after this one run.

## Runtime admission

Commit `9e23e62` passed the two-row real-model backward smoke. The differentiable
frontend matched X-VC's detached helper with maximum absolute hidden-state
difference `0.00026691` under the fixed `0.001` tolerance and mean difference
`0.00000336`. Both final-WAV content-cycle updates were finite, with content
MSE `0.06174` and `0.13544`, 835,584 trainable parameters, and
5,366,944,768 peak allocated GPU bytes. PyTorch emitted one warn-only notice
that reflection-padding backward lacks a deterministic CUDA implementation;
the backward completed and no nonfinite value or OOM occurred.
