# EXP-223: X-VC discrete final-waveform semantic cycle

Status: Admitted listen-now training pilot; not selected

## Goal

Test a categorical content representation after EXP-218--222 showed that an
arbitrary negative can improve tempo but destabilize unknown speakers and
ordinary JSUT. Avoid both pointwise hidden-state averaging and negative
selection: require the converted waveform to recover the exact frozen
WhisperVQ semantic token IDs that X-VC already extracted from its source.

This uses X-VC's existing frozen GLM-4-Voice tokenizer contract and 16,384-entry
codebook; it does not add a text model, transcript target, or new trainable
encoder. The X-VC paper and official implementation describe the frozen
semantic tokenizer boundary (`https://arxiv.org/abs/2604.12456`).

## One method change

Reuse EXP-218's exact ordered CV48 + JSUT85 + JVS3 + Hadou34 source rows, exact
ordered 170-window Amitaro target multiset, target-speaker loss, real-wave
adversarial/feature objective, control69 LoRA69 initialization, 170 updates,
LR, optimizer, clip, zero frame condition, and upstream EMA.

Replace only source-versus-negative final-WAV InfoNCE with direct frozen
semantic-token classification. Apply the already-validated differentiable
Whisper frontend/encoder to the final WAV, take the encoder's existing 50 Hz
states, apply the official four-frame pooling boundary, and compute the same
squared Euclidean distance to every frozen WhisperVQ codebook entry. Optimize
cross-entropy against the row's existing source `semantic_tokens`, divided by
`log(16384)` to produce a vocabulary-size-normalized content loss, then retain
the existing weight 1000.

This is one discrete-representation point. It is not a token-weight,
temperature, codebook, pooling, layer, data, scope, LR, or horizon sweep.

## Definition of Done

- Prove the frozen codebook is exactly 16,384 by 1,280, pooled logits match the
  existing source-token shape, and loss reaches the final WAV in a unit test.
- Commit the method, tests, plan, and
  external7/fresh48/Hadou31/stress60/JSUT24 identities before CUDA.
- Run one real two-row finite backward smoke, then one 170-update CUDA pilot.
- Publish the unchanged EMA checkpoint on all five surfaces to port 8878.
- Record candidate-added consensus corruption and exact cross-arm common-stable
  auxiliary content movement only. Do not infer naturalness, target identity,
  emotion, or a perceptual winner.

## Stop conditions

Stop on codebook/vocabulary drift, pooled/token shape mismatch, missing waveform
gradient, frontend mismatch, nonfinite logits/loss/gradient, OOM, malformed
adapter, candidate-added gross corruption, or broad common-stable regression.
Do not tune token weight, distance scale, codebook, pooling, layer, data,
pairing, scope, LR, horizon, or EMA after this run.

## Admission

Focused policy, codebook-loss, runner, and render tests passed `100/100`. Exact
CPU admission on curriculum SHA-256
`44d2ba9c03d44437711c7b7d359f519672dca32696ba73b3fcd178b07024b931`
reported 170 training rows and seven external evaluation rows. A real-model
two-row backward must still prove the actual 50 Hz / pooled-token boundary.
