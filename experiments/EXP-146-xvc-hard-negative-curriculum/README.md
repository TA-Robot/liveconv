# EXP-146: failure-triggered X-VC curriculum

Status: rejected after one bounded gpu0 lane

## Goal

Repair the control69 collapse mechanism reproduced by EXP-145 without reading
or training on fresh48, Hadou31, JSUT24, or the local tongue-twister. Start
from frozen control69 and keep the clean base-X-VC teacher targets, loss, LR
`1e-4`, norm-5 clip, control69 LoRA topology, target references, zero frame
condition, and 170 total updates fixed.

## One method change

EXP-145 found 11 of 170 training-only inputs at source-relative distance at
least `0.5`, including one control-only gross collapse where the admitted base
teacher had distance `0.0`. Replace EXP-141's one-pass sampling with 170
alternating positions: 85 round-robin hard positions and 85 distinct,
domain-stratified easy positions. This exposes each of the 11 hard rows seven
or eight times without changing total updates or fitting a heldout failure.

- Manifest: `artifacts/xvc-source-diversity/exp146-hard-negative-curriculum-inputs-v1/training.json`
- SHA-256: `419fd1a93f9505134efcd7ac8fccf763d52f5df368430a06e625d5703adaeec7`
- Composition: Common Voice 56, Hadou 111, JVS 3

## Definition of done and stop

Pass one real backward smoke, train once, then publish external7, frozen
fresh48, and frozen Hadou31 on port 8878. Reject on any candidate-added gross
loop or broad common-non-loop regression. Only after those screens survive may
the unchanged candidate consume the frozen JSUT24 evaluation. No hard/easy
ratio, exposure count, threshold, LR, loss, scope, or curriculum neighbor is
admitted. Auxiliary ASR cannot select naturalness, target identity, a keeper,
or promotion.

## Result

Commit `3c158df` completed the real backward smoke, 170 updates, and the
external7/fresh48/Hadou31 render-and-screen chain. Training took 149.62 seconds
at 5.10 GiB peak and moved composite loss `227.88 -> 66.92`.

The candidate added no external7 loop, but regressed source-relative mean from
control69's `0.360` to `0.455`. On the 46 common non-gross fresh rows it scored
`10/20/16` wins/ties/losses, regressing mean `0.341 -> 0.402` and median
`0.275 -> 0.326`. On 30 non-gross Hadou rows it improved mean `0.185 -> 0.153`
and scored `9/18/3`, but it added the mandatory-stop numeric loop on
`RECITATION324_138`, repeating `24` through a long tail.

Reject this sampling method. Do not run EXP-149, fit a hard/easy ratio, change
the threshold, or vary exposure count. The next training point must change the
loss, conditioning, or learning-target policy while keeping heldout evaluation
closed to training.
