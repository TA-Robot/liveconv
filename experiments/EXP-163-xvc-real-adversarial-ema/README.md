# EXP-163: upstream EMA for selective real-adversarial retraining

Status: technical survivor; human listening pending

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

## Result

Commit `7658d61` completed the same 170 online updates in 155.74 seconds at
5.47 GiB peak, then reported the preregistered EMA state after 11 copy updates
and six moving-average updates (last decay `0.93547`). External7 had no gross
loop but regressed source-relative mean `0.360 -> 0.411` and known-text mean
`0.399 -> 0.421`.

The broader frozen gates did not reproduce that regression as a generic
failure. Fresh48 added no gross row and improved the 46 common non-gross rows:
source-relative W/T/L `12/25/9`, mean `0.341 -> 0.328`, median
`0.300 -> 0.235`; known-text mean `0.618 -> 0.607`. Hadou31 had no gross row,
source-relative W/T/L `6/23/2`, and means `0.210 -> 0.171` source-relative and
`0.436 -> 0.425` known-text. The prior `RECITATION324_138` loop did not recur.

Stress60 added no gross row. Macro source-relative was tied
`0.31959 -> 0.32000`, while known-text improved `0.6726 -> 0.6588`; noise and
leading-silence means improved, while clean, pitch, and tempo source-relative
means worsened slightly. Untouched JSUT24 also added no gross row and improved
source-relative macro `0.165 -> 0.142`, W/T/L `3/21/0`; known-text W/T/L was
`0/20/4` and mean regressed `0.552 -> 0.571`.

This is a technical survivor and a new listening candidate, not a keep,
naturalness winner, target-voice winner, route decision, or promotion. Preserve
the exact EMA checkpoint and stop EMA or adversarial sweeps until human hearing.
