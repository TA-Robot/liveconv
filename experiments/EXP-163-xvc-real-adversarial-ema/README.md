# EXP-163: upstream EMA for selective real-adversarial retraining

Status: ready for one bounded gpu0 lane

## Goal

Test whether the upstream-configured exponential moving average stabilizes the
ordinary-row gains of EXP-158 without its final online LoRA checkpoint's new
fresh48 collapse. The local tongue-twister is excluded.

## One method change

Repeat EXP-158 exactly: the same 170 ordered rows, selective generative targets,
original Amitaro discriminator-real targets, control69 initialization, LoRA69
scope, real-reference adversarial objective, optimizer, LR `1e-4`, norm-5 clip,
and zero frame condition. Change only the reported adapter state from the final
online parameters to EMA.

The pinned X-VC config declares `ema_update: True` and upstream constructs
`ema-pytorch==0.7.7` with no overrides. Reproduce those exact defaults:
beta `0.9999`, update-after-step `100`, update-every `10`, inverse-gamma `1`,
power `2/3`, and minimum `0`. Because only LoRA tensors mutate, tracking those
835,584 trainable parameters is functionally equivalent to averaging the full
model while avoiding a redundant immutable-model copy. Save both online and
EMA adapters; evaluate only the preregistered EMA arm.

## Definition of done and stop

Train once and publish external7. An unchanged survivor proceeds through frozen
fresh48, Hadou31, and stress60. Only all-survival opens untouched JSUT24. Reject
a candidate-added gross corruption or broad common-row regression. Machine
metrics cannot select naturalness, target identity, a keeper, or promotion.

Do not vary EMA beta, warmup, frequency, loss, LR, update count, scope, data,
retention ratio, or adversarial settings.
