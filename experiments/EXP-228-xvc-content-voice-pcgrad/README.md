# EXP-228: X-VC content-versus-voice gradient surgery

Status: admitted listen-now training pilot; not selected

## Goal

Test whether EXP-213's recurring cross-domain tradeoff comes from destructive
gradient interference rather than another inadequate content representation.
EXP-213 improved Hadou and noise without candidate-added gross corruption, but
left tempo and ordinary JSUT mixed. EXP-218 and EXP-223 changed the final-WAV
content representation and worsened fresh or JSUT behavior. This experiment
therefore returns to EXP-213's pointwise frozen-Whisper MSE and changes only how
its content and target-voice gradients are combined.

## One method change

Reuse EXP-213's exact ordered CV48 + JSUT85 + JVS3 + Hadou34 source rows,
ordered 170-window Amitaro target multiset, final-WAV Whisper MSE and weight,
target-speaker MSE and weight, real-wave adversarial/feature objective,
control69 LoRA69 initialization, 170 rows and optimizer steps, learning rate,
gradient clip, zero frame condition, discriminator update, and upstream EMA.

For each unchanged row at one shared parameter state, treat the weighted
final-WAV content loss as one task and the weighted target-speaker plus
adversarial/feature loss as the other. If their gradient dot product is
negative, apply the existing symmetric two-task PCGrad projection and sum the
projected gradients. If it is nonnegative, sum the original gradients. This is
not EXP-176's hard-row/easy-row pairing: it preserves one optimizer step per
training row and separates objectives within that row.

This is one optimizer-composition point. It is not a content weight,
adversarial weight, projection rule, task grouping, data, scope, LR, horizon,
or EMA sweep.

## Definition of Done

- Unit-test exact policy isolation, task-sum equivalence, conflict projection,
  and EXP-229--232 render identities.
- Commit code, tests, plan, and all five fixed evaluation surfaces before CUDA.
- Run one real two-row backward smoke proving finite content/voice gradients,
  conflict geometry, final-WAV frontend equivalence, and memory.
- Run one 170-row/170-step pilot and publish the unchanged EMA checkpoint on
  external7, fresh48, Hadou31, stress60, and JSUT24 to port 8878.
- Record conflict frequency, candidate-added consensus corruption, and exact
  common-stable auxiliary content movement. Do not infer naturalness, target
  identity, emotion, or a perceptual winner.

## Stop conditions

Stop on task-sum drift, zero/nonfinite task geometry, nonfinite loss or
gradient, OOM, malformed adapter, candidate-added gross corruption, or broad
common-stable regression. Do not tune task weights/grouping, projection,
content frontend, data, scope, LR, horizon, discriminator, or EMA after this
run. If content/voice conflicts are rare, or common JSUT still regresses, close
this route and move away from loss/optimizer surgery.
