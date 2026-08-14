# EXP-218: X-VC contrastive final-waveform content cycle

Status: Admitted listen-now training pilot; not selected

## Goal

Test one explicit anti-collapse objective after EXP-213--217 established that
source diversity removes the candidate-added low-information loop but still
leaves pointwise-MSE tradeoffs on tempo and ordinary JSUT. Pointwise regression
can reduce loss by moving many inputs toward a shared average representation;
make the converted waveform discriminate its own source content from a frozen
unrelated utterance instead.

This direction is informed by contrastive/Siamese content disentanglement in
ACE-VC (`https://arxiv.org/abs/2302.08137`) and iterative content-preserving
self-transformation in SelfVC (`https://openreview.net/forum?id=jHdz0CIS2y`).
It is one bounded adaptation of the local X-VC path, not a reproduction or a
claim that either paper validates this exact loss.

## One method change

Reuse EXP-213's exact ordered CV48 + JSUT85 + JVS3 + Hadou34 source rows, exact
ordered 170-window Amitaro target multiset, target-speaker loss, real-wave
adversarial/feature objective, control69 LoRA69 initialization, 170 updates,
LR, optimizer, clip, zero frame condition, and upstream EMA.

Replace only weight-1000 pointwise MSE between source and final-WAV frozen
Whisper hidden states with a two-way framewise cosine InfoNCE classification:
the positive is the row's own frozen source hidden sequence and the negative is
the next row in the already-frozen mixed schedule, wrapping at row 170. Use one
fixed temperature `0.1`. No transcript, heldout audio, additional corpus row,
alignment path, or batch-mined negative enters training.

This is a single anti-collapse content architecture point. It is not a corpus,
negative-count, negative-mining, temperature, weight, frontend, scope, LR, or
horizon sweep.

## Definition of Done

- Prove the policy admits only the exact cross-corpus manifest and a distinct
  deterministic negative for every row.
- Commit the objective, tests, plan, and
  external7/fresh48/Hadou31/stress60/JSUT24 identities before CUDA.
- Run one real two-row finite backward smoke, then one 170-update CUDA pilot.
- Publish the unchanged EMA checkpoint on all five surfaces to port 8878.
- Record candidate-added consensus corruption and exact cross-arm common-stable
  auxiliary content movement. Do not infer naturalness, target identity,
  emotion, or a perceptual winner.

## Stop conditions

Stop on a missing/same-row negative, content-shape drift, missing waveform
gradient, frontend mismatch, nonfinite loss/gradient, OOM, malformed adapter,
candidate-added gross corruption, or broad common-stable regression. Do not
tune temperature, negative identity/count, content weight, data, pairing,
frontend, scope, LR, horizon, or EMA after this run.

If it avoids added corruption and improves the broad fixed contract, retain it
unheard for operator comparison. If not, close contrastive neighbors and move
to a different representation or decoding architecture rather than adding
more negatives.

## Admission

Focused policy, loss, runner, and render tests passed `97/97`. Exact CPU
admission on curriculum SHA-256
`44d2ba9c03d44437711c7b7d359f519672dca32696ba73b3fcd178b07024b931`
reported 170 training rows and seven external evaluation rows. A real-model
two-row backward is still required before the full lane.
