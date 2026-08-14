# EXP-233: X-VC voice-only speaker-path overlay

Status: admitted listen-now training pilot; not selected

## Goal

Test a function-path intervention after four final-WAV content objectives and
content/voice PCGrad failed to remove the ordinary-JSUT tradeoff. EXP-228
showed that weighted content and voice gradients conflict on 92 of 170 rows,
but projecting those gradients still regressed JSUT. This pilot therefore
stops updating the content converter instead of adding another content loss or
optimizer rule.

## One method change

Merge the frozen EXP-035 control69 adapter into the X-VC base, preserving its
existing content conversion exactly at initialization. Add a fresh rank-8 LoRA
only to the seven speaker-conditioned AdaLN linears: one `attn_norm_x.linear`
in each of six converter blocks and `norm_out.linear`. Train only those 166,400
parameters with the unchanged weight-10 target-speaker MSE plus the pretrained
real-wave adversarial/feature objective.

Reuse the exact ordered CV48 + JSUT85 + JVS3 + Hadou34 source rows, ordered 170
Amitaro target windows, one optimizer step per row, AdamW LR `1e-4`, norm-5
clip, zero frame condition, discriminator update, and upstream EMA schedule.
All merged control69 content/condition weights, encoders, decoder, and speaker
encoder stay frozen.

This is not EXP-038 speaker7. EXP-038 trained speaker7 from the unmerged base
on 1,044 aligned synthetic same-text pairs with the full standard generative
loss. EXP-233 is a second-stage overlay on the frozen control69 converter using
cross-corpus real sources, unrelated real Amitaro targets, and only the voice
plus waveform-realism objective.

## Definition of Done

- Unit-test exact policy isolation, voice-only loss, 166,400-parameter overlay
  topology, reload format, and EXP-234--237 render identities.
- Commit code, tests, plan, and all five evaluation bindings before CUDA.
- Run one real two-row backward smoke proving finite speaker-path gradients,
  adapter identity, and memory.
- Run one 170-row/170-step pilot and publish the EMA overlay over merged
  control69 on external7, fresh48, Hadou31, stress60, and JSUT24 to port 8878.
- Record candidate-added consensus corruption and exact cross-arm common-stable
  auxiliary content movement. Leave naturalness, target identity, emotion, and
  preference to later human listening.

## Stop conditions

Stop on nonfinite loss or gradient, OOM, malformed/reload-incompatible overlay,
wrong trainable count, candidate-added gross corruption, or broad common-stable
content regression. Do not tune rank, scope, speaker/adversarial weights, data,
LR, horizon, condition, discriminator, or EMA. A content-stable result is only
an unheard technical survivor; auxiliary ASR cannot establish that the voice
overlay improved sound quality.
