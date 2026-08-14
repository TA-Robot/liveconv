# EXP-297: pseudoparallel robust semantic loss

Status: stopped at external7; broad EXP-298--302 skipped

## Goal

Test whether EXP-238's weight-1000 frame-aligned semantic MSE lets a small
number of large hidden-state residuals dominate retraining. Keep the complete
normal X-VC representation and inference path, but make only that semantic
reconstruction term linear for residual magnitudes above one. The question is
broad content and corruption robustness, not an audible winner.

## One change

Keep EXP-238's exact ordered CV48/JSUT85/JVS3/Hadou34 curriculum,
source-aligned frozen-control69 teacher WAVs, authorized real Amitaro
adversarial references, normal quantized source acoustics, control69 LoRA69
initialization and scope, speaker MSE, mel and VQ losses, real adversarial loss,
LR `1e-4`, 170 sequential updates, norm-5 clip, zero frame condition,
discriminator, and EMA.

Replace only the semantic decoder term:

```python
semantic = 2.0 * torch.nn.functional.smooth_l1_loss(
    outputs["pred"], outputs["ssl_feat"], beta=1.0
)
```

The existing weight remains `1000`. Multiplication by two matches ordinary MSE
for residual magnitudes below one, so this does not simply halve the semantic
weight; it changes only the tails from quadratic to linear. Candidate inference
has no wrapper or extra module.

## Gate

- Commit the method, focused tests, and this plan before CUDA.
- CPU admission must retain exact EXP-238 identities, composition, initialization,
  scope, and all non-semantic loss weights.
- CUDA smoke must show finite raw semantic MSE, raw SmoothL1, scale-matched
  robust semantic loss, unchanged standard non-semantic terms, finite total,
  `835,584` trainable LoRA69 parameters, and finite nonzero gradients.
- If admitted, run one 170-update gpu0 lane, publish external7 on port 8878,
  and apply only the fixed content/corruption screen.
- Render EXP-298--302 on fresh48, Hadou31, stress60, JSUT24, and expanded144
  only if external7 adds no gross row and does not increase decoder instability
  or trigger common-stable content regression.

Stop on loss-component, scale, gradient, identity, scope, call, or memory drift;
candidate-added gross corruption; increased decoder instability; or broad
common-stable content regression. Do not sweep beta, scale, semantic weight, or
mix MSE and SmoothL1 after a stop.

## Prior diagnostic evidence

A read-only gpu0 probe evaluated six frozen EXP-238 rows spanning JSUT, Common
Voice, Hadou, and JVS. Raw semantic MSE was `0.021768--0.061189`, while plain
SmoothL1(beta=1) was `0.010717--0.029361`, only `0.467720--0.492321` of MSE.
That exposed a confound in the initial unscaled proposal: it would mostly halve
the semantic weight. The scale-matched factor of two instead preserves local
MSE curvature and clips only residual tails. All substituted totals were finite;
peak allocation was `2,669,201,920` bytes. This admits a bounded smoke only.

## Decision boundary

This is a loss-shape method, not another acoustic representation edit, dataset
change, identity patch, or parameter sweep. External7 is compared first with
EXP-238 by exact source-ID/SHA joins, decoder stability, gross corruption, and
auxiliary source-relative content distance. A surviving unchanged adapter then
uses the five frozen broad surfaces. Machine diagnostics cannot select
naturalness, target identity, a keeper, or a product winner; all produced audio
remains unselected until hearing returns.

## Result

Commit `a9cf6f1` passed 147 focused runner/renderer tests, Ruff, control checks,
exact 170-row CPU admission, and a real CUDA gradient smoke. The smoke retained
`835,584` trainable LoRA69 parameters, produced finite gradients with `827,376`
nonzero elements and norm `5.000000`, and peaked at `4,638,480,384` allocated
bytes.

The only full lane completed all 170 ordered updates in `157.74` seconds and
peaked at `6,163,570,688` bytes. It published 35 external7 WAVs from the EMA
adapter whose weights SHA-256 is
`79349f5d34665e69e0efb2a1c85e6a1c4d66e7f21646523b464a69948c83062c`.

An exact `(source_id, source_sha256)` join against EXP-238 changed all seven
candidate outputs. Gross repetition stayed `0 -> 0`, but decoder instability
increased `1 -> 2`: `cv45141533` changed from stable to unstable while its
source-relative distance remained `0.75`. The five jointly stable, non-gross
rows were exact content ties, mean `0.256410 -> 0.256410`, W/T/L `0/5/0`.

The predeclared stability stop therefore fired. EXP-298--302 were not rendered.
Do not sweep beta, scale, semantic weight, or MSE/SmoothL1 mixtures. This result
rejects the scale-matched robust semantic-loss substitution for the current
EXP-238 contract; it does not make an audible-quality claim.
