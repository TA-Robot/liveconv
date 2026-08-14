# EXP-181: control69 parameter anchor on the surviving X-VC method

Status: external7 complete; fresh48 pending

## Goal

Test whether light parameter-space retention can preserve EXP-163's useful
hard-repair, Hadou, and noise behavior while reducing its tempo and ordinary
content forgetting. This is a training-method test; it does not optimize the
historical local tongue twister and does not use or claim ChatGPT-browser audio.

## One method change

Keep the exact EXP-163 hard85/easy85 curriculum, frozen learning targets,
control69 initialization, real-reference adversarial and feature-matching
objective, 170 sequential optimizer updates, AdamW, learning rate `1e-4`,
norm-5 clipping, LoRA69 scope, zero frame condition, and pinned upstream EMA
schedule.

Add only this generator regularizer over the 835,584 trainable LoRA parameters:

```text
L_anchor = 0.5 * 1.0 * ||theta - theta_control69||^2
```

The reference tensors are immutable clones captured before the first update.
Coefficient `1.0` is one precommitted point, not a sweep. Applied post hoc to
EXP-163's online endpoint it would contribute about `4.19` versus that run's
final total objective `102.46`, so the intended pressure is light rather than a
rollback to control69. EMA still determines the published adapter exactly as in
EXP-163.

## Definition of done and stop

Commit the runner and plan before CUDA. A two-row smoke must persist finite
adversarial components, a zero first anchor loss, and a finite nonzero second
anchor loss. Run one full 170-update lane and publish external7 comparison audio
on port 8878.

Reject on candidate-added consensus gross corruption. Otherwise pass the same
unchanged checkpoint through fresh48, Hadou31, stress60, and balanced JSUT24,
one frozen gate at a time. Use v4 only as a coarse content/corruption screen.
Do not tune the coefficient, EMA, data ratio, LR, scope, horizon, or optimizer
from this run, and do not claim naturalness, identity, a keeper, or promotion
without human listening.

## Result so far

Commit `f43df26` completed all 170 updates in 155.73 seconds at 5.74 GiB peak.
The anchor loss moved from zero to `1.348`, with final online squared distance
`2.697`. For comparison, the unchanged EXP-163 online adapter's squared
distance from control69 was about `8.386`; the anchor constrained drift without
returning the adapter to its initialization. All generative, adversarial,
feature-matching, discriminator, anchor, and EMA values remained finite.

External7 published 35 WAVs and added no consensus gross row. On five cross-arm
common decoder-stable rows, source-relative mean moved slightly from control69
`0.256 -> 0.268` and known-text mean improved `0.371 -> 0.283`; both comparisons
had W/T/L `2/1/2`. This mixed small set does not trigger a broad-regression stop
and cannot decide perceptual quality. Continue the unchanged checkpoint to
frozen fresh48 as EXP-182.
