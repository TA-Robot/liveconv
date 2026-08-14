# EXP-150: selective repair and retention distillation

Status: prepared; one bounded gpu0 lane

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
