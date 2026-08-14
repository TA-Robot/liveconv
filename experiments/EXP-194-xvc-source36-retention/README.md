# EXP-194: source-path-only X-VC retention

Status: completed mixed; method family closed

## Goal

Test whether EXP-186's remaining ordinary/tempo/pitch forgetting is caused by
updating condition-side and speaker-modulation LoRA paths that are not needed to
repair source content.

## One method change

Keep EXP-186's balanced 48-speaker easy85 retention data, speech-active source
windows, hard85 repair rows, control69 initialization, frozen targets,
real-reference adversarial objective, 170 sequential updates, learning rate,
AdamW, clipping, zero frame condition, and upstream EMA exact.

Change only which already-loaded control69 LoRA tensors remain mutable. EXP-186
updates all 69 attention, condition, feed-forward, and speaker-modulation paths.
EXP-194 updates the contained 36 source-side attention and `ff_x` paths and
freezes the other control69 adapter tensors at their initialization values.

This is not a retry of EXP-052. That experiment trained source36 from a fresh
base with 1,044 standard generated-pair updates and had no selective repair,
retention distillation, real-reference adversarial objective, or EMA. EXP-194
tests function placement inside the later surviving method while holding its
data and objective fixed.

## Definition of done and stop

Commit the contained-scope implementation and focused tests before CUDA. Run a
hard/easy smoke, then exactly one 170-update lane. Before seeing its result,
freeze two evaluation surfaces: external7 plus the existing stress60 clean/
noise20/pitch+3/silence300/tempo1.2 matrix. Publish both to port 8878 and close
the family. Do not add fresh48, Hadou, JSUT, an adjacent scope, rank, LR, epoch,
ratio, or condition point. Candidate-added consensus gross corruption or broad
common-stable regression rejects the method; neither gate can select
naturalness, identity, a keeper, or promotion.

## Result and decision

The hard/easy smoke exposed exactly 442,368 mutable parameters across 72 LoRA
tensors and was finite. The one 170-update lane completed in 140.4 seconds at
5.73 GiB peak; total loss moved `298.40 -> 136.76` and 35 external7 WAVs were
published. EXP-195 then published the prebound 300 stress60 WAVs from the same
checkpoint. Neither surface contains a candidate-added gross row.

On five external7 common stable rows, source-relative distance moved
`0.256 -> 0.268` and known-text distance `0.371 -> 0.283`; both W/T/L were
`2/1/2`. On 45 stress60 common stable rows, source distance moved
`0.212 -> 0.214` with `7/27/11`, and known-text moved `0.591 -> 0.592` with
`7/31/7`. Noise20 improved, but tempo1.2 was `0/5/2` on both diagnostics and
silence300 regressed. Source36 placement did not repair the motivating residual
and is closed without adjacent scope points.
