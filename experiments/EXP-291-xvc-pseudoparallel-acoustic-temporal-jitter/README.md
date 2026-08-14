# EXP-291: pseudoparallel acoustic temporal jitter

Status: external decoder-stability stop fired; technically rejected and unselected

## Goal

Test whether EXP-238's converter over-relies on exact frame alignment in the
quantized source-acoustic branch. Preserve the checkpoint's discrete acoustic
codes, but train the unchanged LoRA69 converter to tolerate a one-frame timing
offset on exactly half of the frozen curriculum. The question is broad content
and corruption robustness, not an audible winner.

## One change

Keep EXP-238's exact ordered CV48/JSUT85/JVS3/Hadou34 curriculum,
source-aligned frozen-control69 teacher WAVs, authorized real Amitaro
adversarial references, control69 LoRA69 initialization and scope, complete
generative and adversarial losses, LR `1e-4`, 170 sequential updates, norm-5
clip, zero frame condition, discriminator, and EMA.

Change only the quantized source-acoustic tensor during training on the odd
deterministic 85 rows:

```python
shifted = torch.cat([zq_a[..., :1], zq_a[..., :-1]], dim=-1)
```

The even 85 rows use the normal `zq_a`. Quantizer indices, VQ losses,
perplexity, cluster bookkeeping, tensor shape, and amplitude remain intact.
Candidate inference always uses the normal unshifted quantized tensor. No
dropout share/pattern, continuous pre-VQ path, rank, LR, scope, data, target,
loss, condition, initialization, or horizon change is admitted.

## Gate

- Commit the method, focused tests, and this plan before CUDA.
- CPU admission must retain exact EXP-238 identities and composition, prove an
  exact 85 normal / 85 shifted alternating schedule, and retain `835,584`
  trainable LoRA69 parameters.
- CUDA smoke must exercise one normal training row, one shifted training row,
  and normal candidate inference. It must preserve nonzero count and shape,
  report finite positive input/shifted RMS, and produce finite nonzero
  gradients.
- If admitted, run one 170-update gpu0 lane, disable the training wrapper for
  external7 inference, publish the comparison on port 8878, and apply only the
  fixed content/corruption screen.
- Render EXP-292--296 on fresh48, Hadou31, stress60, JSUT24, and expanded144
  only if external7 adds no gross row and does not trigger the common-stable
  content stop.

Stop on schedule, shape, nonzero-count, RMS, wrapper-mode, inference-mode,
loss, gradient, or memory drift; candidate-added gross corruption; increased
decoder instability; or broad common-stable content regression. Do not tune
the shifted-row share, shift length, or interpolation after a stop.

## Prior diagnostic evidence

A read-only gpu0 probe covered stress clean/noise20/silence300/tempo120/pitchp3
and expanded `cv40748214f-noise10`. All six quantized tensors had shape
`(1, 1024, 120)`, remained finite, and kept all `122,880` values nonzero after
the shift. Original RMS was `2.617043--2.737110`; shifted RMS was
`2.611289--2.734129`. Original-to-shifted cosine was `0.128388--0.649042`, so
this is a material temporal perturbation rather than a no-op. Peak allocation
was `2,569,888,256` bytes. The probe admits a bounded smoke only; it is not
quality evidence.

## Decision boundary

This pilot is a training-only robustness method that retains normal quantized
inference, unlike EXP-279's zeroed branch and EXP-285's continuous train/eval
representation. External7 is screened first against EXP-238 by exact
source-ID/SHA joins, decoder stability, gross corruption, and auxiliary
source-relative content distance. If it survives, the same unchanged adapter
is evaluated on the five frozen broad surfaces. Without human hearing, all
audio remains unselected and no naturalness, target-identity, keeper, or
product claim is allowed.

## Training and external result

Commit `ddefe76` passed 141 combined runner/renderer tests, Ruff, control
checks, exact CPU admission, and the three-mode CUDA smoke. The smoke exercised
one normal training call, one shifted training call, and one normal inference
call. The shifted tensor retained `122,866` nonzero values and moved RMS only
`2.768492 -> 2.770483`; `827,376` gradient elements were nonzero with L2 norm
approximately `5`. Peak allocation was `4,636,022,272` bytes.

The only full lane completed 170 updates in 133.40 seconds at
`6,163,570,688` peak bytes. It recorded exact 85 normal / 85 shifted training
calls followed by seven normal inference calls. Loss moved `55.2390 ->
140.1747`; the EMA adapter SHA-256 is
`e1c9e1f6d7501f0fcd6b610d40178596d74973f76e258315d615abf0f12ec046`.
It published 35 external comparison WAVs.

Exact source-ID/SHA comparison with EXP-238 changed all seven candidate WAVs
and added no gross row (`0 -> 0`). The five jointly stable/non-gross rows were
exact content ties (`0.256410 -> 0.256410`, W/T/L `0/5/0`), but decoder
instability increased `1 -> 2`: `cv45141533` became unstable while its
source-relative distance stayed `0.75`. The predeclared stability stop fired,
so EXP-292--296 were not rendered. Close one-frame jitter, shift-length/share/
interpolation neighbors, and the broader acoustic-representation manipulation
path. Retain the external audio unheard and unselected; do not infer audible
quality from the machine stop.
