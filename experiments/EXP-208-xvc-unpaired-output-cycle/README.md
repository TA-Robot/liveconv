# EXP-208: X-VC final-waveform content cycle

Status: Completed listen-now training pilot; technically rejected and unselected

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

## Result

Commit `712d55f` completed 170 updates in 152.17 seconds at 5,875,919,872
peak allocated bytes. The EMA adapter SHA-256 is
`c8b1e28ac138bf0d63d86ad2745a584eb4f2c71e3f4beea046d9413334f57092`.
The unchanged checkpoint produced 35 external7, 240 fresh48, 155 Hadou31, 300
stress60, and 120 balanced-JSUT24 WAVs on port 8878: 850 total.

On cross-arm common-stable rows, source-relative distance moved external7
`0.256 -> 0.272` (`0/4/1`), fresh48 `0.202 -> 0.219` (`8/19/9`), Hadou31
`0.149 -> 0.124` (`9/15/2`), stress60 `0.215 -> 0.180` (`11/26/6`), and
JSUT24 `0.115 -> 0.114` (`6/13/3`). Clean, noise20, and leading-silence300
stress rows improved, but tempo1.2 remained worse at `0.262 -> 0.267`
(`1/5/2`).

Fresh48 added one consensus gross failure on `cv44571685f`, a source whose
auxiliary source transcript was empty. The candidate repeated a short phrase
through a 334-character transcript; control69 was non-gross on that row. This
satisfies the predeclared stop. Final-WAV content cycling yields a real broad
stress/Hadou signal but does not solve low-information collapse or tempo, so the
exact objective is rejected. Do not tune its weight, frontend, data, pairing,
scope, LR, horizon, or EMA. No perceptual conclusion is made.
