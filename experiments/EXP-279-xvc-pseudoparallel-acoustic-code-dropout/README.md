# EXP-279: pseudoparallel acoustic-code dropout

Status: committed listen-now pilot; unheard and unselected

## Goal

Test whether EXP-238's remaining speaker-distributed and condition-sensitive
failures come from over-reliance on the quantized source-acoustic branch that is
concatenated with frozen semantic tokens before the X-VC converter.

## One change

Keep EXP-238's exact ordered CV48/JSUT85/JVS3/Hadou34 curriculum,
source-aligned frozen-control69 teacher WAVs, authorized real Amitaro
adversarial references, control69 LoRA69 initialization and scope, complete
generative and adversarial losses, LR `1e-4`, 170 sequential updates, norm-5
clip, zero frame condition, discriminator, and EMA.

Change only the source representation during training: on the 85 odd-indexed
rows in the fixed 170-row order, replace the acoustic quantizer's `zq_a` output
with zeros before it is concatenated with the unchanged semantic embedding.
The other 85 rows are exact EXP-238 inputs. VQ bookkeeping outputs, targets,
losses, and update order remain unchanged. Listen-now inference uses the normal,
unmasked acoustic code; no runtime model contract or output metric changes.

This is the opposite direction from rejected EXP-100, which corrupted semantic
tokens to force reliance on the acoustic branch. It is not an audio-condition
augmentation, dropout-rate sweep, identity loss, conditioning patch, corpus
substitution, or fresh initialization retry.

## Gate

- Commit the method, tests, and this plan before CUDA.
- CPU admission must retain the exact EXP-238 170 rows and report 85 clean / 85
  masked source-representation rows.
- A two-row CUDA smoke must exercise one clean and one masked quantizer call,
  preserve all non-`zq_a` quantizer outputs, expose exactly 835,584 trainable
  LoRA69 parameters, and produce finite nonzero generator gradients.
- If admitted, run one 170-update gpu0 lane and publish external7 on port 8878.
  Use the existing fixed broad surfaces only after external corruption/content
  screening.

Stop on nonfinite loss or gradient, OOM, wrong mask counts, a masked row whose
`zq_a` remains nonzero, candidate-added gross corruption, or broad common-stable
content regression. Do not sweep dropout share/pattern, rank, LR, scope,
horizon, data mix, target, loss, or EMA. Machine diagnostics cannot select
naturalness, target identity, emotion, a keeper, or a winner.
