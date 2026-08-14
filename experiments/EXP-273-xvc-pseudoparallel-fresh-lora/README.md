# EXP-273: fresh-LoRA X-VC pseudoparallel retraining

Status: committed listen-now training pilot; unheard and unselected

## Goal

Test whether EXP-238's remaining distributed losses and inherited fresh48
failures come from continuing optimization inside the already-trained EXP-035
control69 adapter rather than from the source-aligned teacher itself.

## One change

Keep EXP-238's exact CV48/JSUT85/JVS3/Hadou34 curriculum, ordered source-aligned
control69 teacher WAVs, assigned authorized real Amitaro discriminator WAVs,
complete generative and real-adversarial losses, LoRA69 scope/rank/alpha, LR
`1e-4`, sequential 170 updates, norm-5 clip, zero frame condition,
discriminator, and EMA. Change only initialization: attach a new zero-initialized
rank-8 LoRA69 adapter to the frozen base X-VC instead of reopening EXP-035
control69's trained LoRA parameters.

The teacher still carries the desired same-content control69 conversion, so
this is fresh distillation of the retained data target, not base-voice training
or a new target mixture. It does not add a loss or alter evaluation.

## Gate

Commit the method and plan, pass exact CPU admission, then run a two-row CUDA
backward smoke. The smoke must show exactly 835,584 trainable parameters,
finite nonzero gradients, and finite adversarial/generative losses. If admitted,
run one 170-update gpu0 lane and publish external7 to port 8878. Use only the
existing content/corruption screen. Stop on nonfinite loss, OOM, candidate-added
gross corruption, or broad content regression. Do not sweep initialization,
rank, LR, scope, horizon, target mix, or loss weights.
