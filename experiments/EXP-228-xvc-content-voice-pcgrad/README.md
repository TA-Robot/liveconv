# EXP-228: X-VC content-versus-voice gradient surgery

Status: completed and technically rejected; not selected

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

## Result

Commit `33be19c` passed 240 focused tests, exact no-CUDA admission, and a real
two-row backward smoke. The smoke used 5,371,280,896 peak allocated bytes and
observed a real content/voice conflict with cosine `-0.08924`. The single
admitted pilot then completed 170 updates in 127.28 seconds at 5,872,224,256
peak allocated bytes. Conflicts occurred on 92 of 170 rows (54.1%), with
cosine mean `-0.02275`, minimum `-0.95679`, and maximum `0.77897`. The EMA
adapter SHA-256 is
`6d09a5bd053e448cdc56b90a3aa5890bb903278620cf4c4aae1991e95080ccb0`.

The unchanged checkpoint published and screened 850 WAVs across external7,
fresh48, Hadou31, stress60, and JSUT24. No candidate-added consensus gross row
appeared; fresh48 retained control69's same two gross rows. On exact cross-arm
common-stable rows, source-relative auxiliary distance moved external7
`0.256410 -> 0.223077` (W/T/L `2/2/1`), fresh48 `0.195897 -> 0.187880`
(`8/22/5`), Hadou31 `0.148912 -> 0.129832` (`6/17/3`), and stress60
`0.221115 -> 0.198264` (`14/19/12`). Within stress60, clean, silence300, and
tempo1.2 improved; noise20 was mixed and pitch+3 regressed.

The predefined stop fired on ordinary JSUT: its 22 common-stable rows regressed
`0.115028 -> 0.145764` with W/T/L `2/17/3`, including basic5000
`0.103554 -> 0.170221`. PCGrad exposed frequent objective conflict but did not
repair the motivating broad-JSUT residual and was worse there than EXP-213.
Reject this exact optimizer-composition method and close loss weights, task
grouping, projection rules, and adjacent optimizer-surgery points. The audio
remains available for optional diagnosis; it is not a keeper or perceptual
winner. The next pilot must change the mutable function path, data target, or
conditioning contract rather than another content loss or gradient rule.
