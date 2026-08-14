# EXP-150: selective repair and retention distillation

Status: rejected after one bounded gpu0 lane

## Goal

Repair control69's training-only collapse triggers without broadly replacing
its normal behavior with base-X-VC teacher behavior. Heldout fresh48, Hadou31,
JSUT24, and the local tongue-twister are excluded from learning-target choice.

## One method change

Keep EXP-146's exact 170-position alternating curriculum, control69
initialization, 85 hard/85 easy positions, hard-row exposure counts, source
inputs, target references, standard upstream loss, LR `1e-4`, norm-5 clip,
control69 LoRA scope, and zero frame condition. Change only the easy-row
learning target:

- 85 hard positions use their clean frozen base-X-VC output as a repair target.
- 85 easy positions use their already-rendered, non-gross, distance-`<0.5`
  control69 output as a retention target.

This asks whether EXP-146's broad drift came from overwriting normal control69
behavior while still allowing direct repair where the control failed.

- Manifest: `artifacts/xvc-source-diversity/exp150-selective-retention-inputs-v1/training.json`
- SHA-256: `6322a9c530614fc142ca4d896f28b4aecee01daabdd74ea1286499ea3ab0718e`
- Composition: Common Voice 56, Hadou 111, JVS 3

## Definition of done and stop

Train once, publish external7, then frozen fresh48 and Hadou31 on port 8878.
Reject on any candidate-added gross loop or broad common-non-gross regression.
Only a surviving unchanged checkpoint may consume frozen JSUT24. Do not vary
repair/retention blend, hard/easy ratio, exposure, threshold, LR, loss, or
scope. Auxiliary ASR is only a content/corruption screen, never a naturalness,
target-voice, keeper, or promotion decision.

## Result

Commit `eb82428` completed 170 updates in 115.62 seconds at 5.10 GiB peak,
moving composite loss `227.88 -> 45.00`. It published external7, fresh48, and
Hadou31 comparison audio on port 8878.

Retention targets removed EXP-146's broad Common Voice drift. On 46 common
non-gross fresh rows, source-relative mean improved `0.341 -> 0.310` with
`12/22/12`, while known-text mean improved `0.618 -> 0.610` with `13/24/9`.
The candidate added no fresh gross row but retained control69's `32.4` family
collapse. On 30 non-gross Hadou rows it improved mean `0.185 -> 0.170` with
`5/23/2`.

The mandatory-stop `RECITATION324_138` still gross-looped, repeating `9`
through a 66-character run. Reject this exact method and do not tune its blend,
ratio, exposure, or threshold. The contrast with EXP-146 supports retention as
a useful anti-drift mechanism, but the control69 LoRA target scope did not make
failure repair generalize. Do not run EXP-153.
