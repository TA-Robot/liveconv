# EXP-334: X-VC real-reference adversarial feature statistics

Status: admitted listen-now method pilot; implementation in progress; unheard
and unselected

## Question

Can X-VC learn target-voice texture from unrelated-text real Amitaro references
without forcing their time-local discriminator features onto source-aligned
content?

EXP-238 correctly uses a frozen control69 conversion of the same source as its
complete generative target. Its real-wave adversarial path, however, uses an
unrelated-text real Amitaro window. The pretrained discriminator's current
generator-side feature loss compares every fake and real feature frame by
position. That can press unrelated phonetic timing into the converted output
even though the real reference is intended to provide realism and voice rather
than content.

## One method change

Reproduce EXP-238 from the same EXP-035 control69 LoRA69 initialization, exact
ordered CV48 + JSUT85 + JVS3 + Hadou34 170-row manifest, source-aligned
frozen-control69 teachers, ordered real Amitaro adversarial targets, upstream
complete generative loss, AdamW `1e-4`, sequential one-row updates, norm-5
clip, zero frame condition, 170-update horizon, and upstream EMA.

Change only the generator-side discriminator feature-matching term. For every
existing non-logit discriminator feature `F` with shape `[B, C, ...]` and rank
at least three, replace pointwise L1 matching with the same L1 function and
existing loss weight over:

```text
R = every axis after batch and channel
M(F) = concat(mean_R(F), sqrt(var_R(F, unbiased=False) + 1e-6))
```

The rank-3 waveform features therefore reduce time; rank-4 periodic and STFT
features reduce both of their spatial axes. Compare `M(F_fake)` with detached
`M(F_real)`. Keep the discriminator update
and loss, generator adversarial score loss, feature layers, real WAVs, and all
other loss values and weights unchanged. Add no coefficient, trainable module,
sidecar, inference input, or runtime behavior.

This is not a final-WAV speaker loss, semantic/output content loss, PCGrad,
speaker scope, condition calibrator, latent/control anchor, source-speaker GRL,
or data/window/LR/rank/horizon neighbor. It changes how an already-present
unpaired real-reference signal discards time order before feature matching.

## Gate and execution

1. Unit-test the statistic shape and finite contract, detached real branch,
   unchanged generator score and discriminator losses, unchanged complete
   generative loss, exact policy identity, and ordinary LoRA69 export/reload.
2. Commit the runner, this plan, and the fixed render bindings before CUDA.
3. Run exact 170-row CPU admission and one two-row CUDA smoke. The smoke must
   prove finite feature statistics on every existing feature layer, finite and
   nonzero statistic-loss gradients into LoRA69, no discriminator gradient in
   the generator update, unchanged ordinary inference shape, and memory.
4. Run exactly one 170-update `gpu0` lane and publish external7 on port 8878.
5. Continue the unchanged checkpoint through fresh48, Hadou31, stress60,
   JSUT24, and expanded144 only if external7 adds no consensus gross row, does
   not increase decoder instability, adds no newly unstable row, and does not
   regress common-stable source-relative content versus EXP-238.

Stop on any feature count/shape, target-lineage, loss-isolation, gradient,
memory, reload, or inference drift. Do not tune the statistic, epsilon, loss
weight, data, LR, horizon, scope, condition, optimizer, discriminator, or EMA.

## Listening boundary

The output is an unheard listen-now library. Auxiliary ASR may locate gross
repetition, empty output, decoder disagreement, or content drift. Speaker
embeddings may diagnose direction only. Neither establishes naturalness,
target identity, a keeper, a winner, promotion, or a product decision.
