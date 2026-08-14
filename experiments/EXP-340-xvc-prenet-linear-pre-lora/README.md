# EXP-340: X-VC prenet input-fusion LoRA

Status: admitted listen-now method pilot; implementation in progress; unheard
and unselected

## Question

Can a small adaptation at the semantic/acoustic fusion entrance improve X-VC
without changing the already-closed loss, data, speaker-adversary, or acoustic
representation families?

## One method change

Keep EXP-238's exact ordered 170-row CV48 + JSUT85 + JVS3 + Hadou34 manifest,
source-aligned control69 teachers, real Amitaro adversarial targets, complete
generative and real-adversarial objective, AdamW `1e-4`, one-row updates,
norm-5 clip, zero frame condition, 170-update horizon, and EMA. Load the same
EXP-035 control69 initialization and retain its existing converter LoRA69.

Change only trainable adapter topology by adding rank-8, alpha-8, dropout-0,
B-zero LoRA to `model.prenet.linear_pre`. Do not target any other prenet,
semantic adapter, semantic decoder, acoustic decoder, AdaLN, speaker predictor,
or condition module. Add no loss, data row, sidecar, inference input, wrapper,
or runtime behavior.

The new module is the 2048-to-768 projection immediately before the frozen
acoustic converter. It tests a narrow fusion-boundary correction, not full
prenet training or another converter scope/rank sweep.

## Gate and execution

1. Prove the exact additional target and trainable count, B-zero step-0
   equivalence, unchanged manifest and objective, and ordinary adapter export.
2. In a two-row CUDA smoke, require finite nonzero gradients in both the
   existing converter LoRA and the new prenet LoRA, normal reload, unchanged
   inference shape, and bounded memory.
3. Commit the plan and implementation before one 170-update `gpu0` lane.
4. Publish external7 on port 8878. Stop on candidate-added consensus gross,
   instability above EXP-238's one row, a newly unstable EXP-238-stable row,
   or common-stable source-relative regression.
5. Only if external7 passes, render the already-fixed fresh48, Hadou31,
   stress60, JSUT24, and expanded144 surfaces as EXP-341--345.

Do not tune rank, alpha, module scope, loss, data, LR, horizon, initialization,
condition, optimizer, or EMA after seeing external7.

## Listening boundary

The result is unheard listen-now audio. Auxiliary ASR can reject corruption or
content instability only. It cannot establish naturalness, target identity,
latency quality, a keeper, a winner, promotion, or a product decision.
