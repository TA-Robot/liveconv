# EXP-194: source-path-only X-VC retention

Status: prepared; one bounded gpu0 lane

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
hard/easy smoke, then exactly one 170-update lane and publish external7 to port
8878. Stop on candidate-added consensus gross corruption or broad common-stable
regression. Only survival admits one frozen fresh48 render. Do not run adjacent
scope, rank, LR, epoch, ratio, or condition points. Machine ASR remains a coarse
content/corruption diagnostic and cannot select naturalness, identity, a keeper,
or promotion.
