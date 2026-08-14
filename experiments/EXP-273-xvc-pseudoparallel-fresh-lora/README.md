# EXP-273: fresh-LoRA X-VC pseudoparallel retraining

Status: completed and technically rejected; unheard and unselected

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

## Training and external result

Commits `500f6bb`, `24b491d`, and `c6e623a` passed 58 focused runner tests,
the exact 170-row CPU admission, and a finite two-row CUDA smoke with 835,584
trainable parameters. The full lane completed 170 updates in 148.09 seconds at
6,163,570,688 peak allocated bytes; the EMA adapter SHA-256 is
`3eb7b0753e4a87afc33458936457a861fa28dcf46a0dfbedd126b5c33600e245`.

All seven external WAVs changed and no gross row was added. On the five exact
jointly stable/non-gross rows versus EXP-238, source distance moved `0.306410 ->
0.312179`, W/T/L `1/2/2`; decoder instability moved `1 -> 2`. This is mixed
and too small to classify the initialization. EXP-274--278 therefore bind the
unchanged adapter to fresh48, Hadou31, stress60, JSUT24, and expanded144.

## Broad result and decision

EXP-274--278 published another 307 candidate WAVs on the five frozen broad
surfaces. Every candidate WAV changed. Fresh48 and the candidate each had two
gross rows, and no fresh48 gross row was added. The expanded144 candidate added
one gross row, while decoder instability increased from `33 -> 43` there and
from `6 -> 9` on fresh48.

On exact rows whose source identity and hash matched and whose EXP-238 and
EXP-273 outputs were both decoder-stable and non-gross, source-relative content
moved as follows:

| Surface | Common rows | EXP-238 | EXP-273 | W/T/L |
|---|---:|---:|---:|---:|
| fresh48 | 37 | 0.246354 | 0.291911 | 8/18/11 |
| Hadou31 | 25 | 0.110603 | 0.097179 | 8/11/6 |
| stress60 | 44 | 0.186276 | 0.276007 | 6/17/21 |
| JSUT24 | 22 | 0.123253 | 0.134617 | 2/17/3 |
| expanded144 | 98 | 0.358656 | 0.313699 | 21/58/19 |
| all | 226 | 0.256355 | 0.261410 | 45/121/60 |

Fresh initialization therefore does not remove the distributed robustness
failures and makes stress60 and decoder stability materially worse despite the
expanded144 common-row mean improvement. Reject this exact method. Close
initialization, rank, LR, scope, horizon, and EMA neighbors; retain the audio
only for later optional hearing. Machine screening does not decide audible
naturalness, target identity, or a keeper.
