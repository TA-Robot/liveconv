# EXP-238: X-VC cross-corpus source-aligned pseudoparallel retraining

Status: completed technical survivor; unheard and unselected

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

## Result

Commit `edbe8c5` passed 248 focused tests, control validation, exact 170-row
CPU admission, and a real two-row backward smoke. The smoke proved 835,584
trainable LoRA69 parameters, finite complete-generative and real-reference
adversarial updates, and 4,636,175,872 peak allocated bytes.

The frozen control69 materializer produced 170 same-content training targets in
95.37 seconds at 2,668,426,752 peak bytes. The single pilot completed 170
updates in 136.83 seconds at 6,163,570,688 peak bytes. The EMA adapter SHA-256
is `778b430133b5397d86bd70bd7c9fa7bd4f7f9cc4d737ca94e4b91e5c7bc8a9da`.
Training loss moved `106.41 -> 124.30`; this non-monotonic discriminator-coupled
trajectory is recorded but is not treated as a quality decision.

The unchanged checkpoint published and screened 850 WAVs across external7,
fresh48, Hadou31, stress60, and JSUT24. There was no candidate-added consensus
gross row on any surface. On exact cross-arm common-stable rows, source-relative
auxiliary distance moved external7 `0.256410 -> 0.256410` (W/T/L `0/5/0`),
fresh48 `0.214090 -> 0.206909` (`4/30/3`), Hadou31
`0.148912 -> 0.127328` (`3/22/1`), stress60 `0.222702 -> 0.193036`
(`7/36/2`), and JSUT24 `0.115028 -> 0.123253` (`1/20/1`). Exact common-stable
known-text distance improved on all five surfaces.

Within stress60, clean, noise20, and silence300 improved, tempo1.2 tied exactly,
and pitch+3 had one loss among eight common-stable rows. JSUT's only
source-relative loss was `basic5000_4688`, where known-text distance instead
improved; the only other changed row was a larger loanword improvement. This
does not meet the predefined broad-regression stop. Retain this exact checkpoint
as an unheard technical survivor. It is not a perceptual winner, keeper, route,
or promotion; naturalness, target voice, and emotion remain human-listening
questions.
