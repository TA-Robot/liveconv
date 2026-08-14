# EXP-297: pseudoparallel robust semantic loss

Status: planned listen-now pilot; implementation and commit precede CUDA

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
