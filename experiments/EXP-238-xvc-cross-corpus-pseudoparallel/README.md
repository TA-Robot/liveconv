# EXP-238: X-VC cross-corpus source-aligned pseudoparallel retraining

Status: prepared; not run

## Goal

Test whether the recurring Hadou/noise versus ordinary-JSUT/tempo tradeoff is
caused by the unrelated source/target training contract. EXP-213--233 changed
the content representation, optimizer composition, and mutable function path,
but broad content still regressed. This pilot changes the target data contract
instead of adding another loss or scope rule.

## One method change

Reuse the exact ordered 170 training sources from EXP-213: 48 Common Voice
speakers, 85 disjoint JSUT utterances, three JVS speakers, and 34 Hadou windows.
Keep the same ordered assignment of 170 authorized real Amitaro target windows.
For each row, first render the frozen control69 conversion of that source under
its assigned Amitaro reference. Use that same-content converted WAV as the
complete generative target during retraining. Use the original real Amitaro WAV
only as the real side of the unchanged pretrained discriminator and feature
matching objective.

Start from the same control69 LoRA69 adapter and retain the upstream standard
generative loss, real-wave adversarial/feature loss, 170 optimizer steps, AdamW
LR `1e-4`, norm-5 clip, zero frame condition, and EMA schedule. This removes
the former instruction to infer source content while simultaneously matching
an unrelated-text target. It does not change corpus ratios, scope, loss
weights, LR, update count, condition, discriminator, or EMA.

## Definition of Done

- Unit-test the exact 170-row source order, same-content target manifest,
  policy isolation, real-reference adversarial boundary, and EXP-239--242
  render identities.
- Commit the materializer, trainer policy, tests, plan, and all five evaluation
  bindings before CUDA.
- Render exactly 170 training-only control69 targets, then run one real two-row
  backward smoke proving finite standard generative/adversarial gradients and
  memory.
- Run one 170-row/170-step pilot and publish the EMA checkpoint on external7,
  fresh48, Hadou31, stress60, and balanced JSUT24 to port 8878.
- Record candidate-added consensus corruption and exact common-stable auxiliary
  content movement. Do not infer naturalness, target identity, emotion, or a
  perceptual winner.

## Stop conditions

Stop on target/source identity drift, nonfinite or empty teacher WAV, nonfinite
loss or gradient, OOM, malformed adapter, candidate-added gross corruption, or
broad common-stable content regression. Do not tune teacher model, corpus
ratio, target assignment, loss weights, scope, LR, horizon, condition,
discriminator, or EMA after this run. A content-stable result is only an
unheard technical survivor until human listening returns.
