# EXP-285: pseudoparallel continuous acoustic latent

Status: committed pilot; CUDA smoke and external7 are next

## Goal

Test whether the X-VC converter is being limited by the quantizer boundary: at
both training and inference, replace only the quantized source-acoustic tensor
with the frozen quantizer's projected continuous pre-VQ representation. The
question is robustness across speakers and conditions, not an audible winner.

## One change

Keep EXP-238's exact ordered CV48/JSUT85/JVS3/Hadou34 curriculum,
source-aligned frozen-control69 teacher WAVs, authorized real Amitaro
adversarial references, control69 LoRA69 initialization and scope, complete
generative and adversarial losses, LR `1e-4`, 170 sequential updates, norm-5
clip, zero frame condition, discriminator, and EMA.

Change only the source representation at the quantizer boundary. The frozen
quantizer still runs and returns its normal indices, commitment/codebook losses,
perplexity, and cluster bookkeeping, but the first output is replaced by
`out_project(in_project(acoustic_encoder_out))`. The same wrapper remains active
for candidate inference, including external7. No dropout share/pattern, rank,
LR, scope, data, target, loss, condition, or initialization change is admitted.

## Gate

- Commit the method, focused tests, and this plan before CUDA.
- CPU admission must retain exact EXP-238 data and policy identity, with
  `835,584` trainable LoRA69 parameters in the unchanged full lane.
- CUDA smoke must make exactly two wrapper calls: one training forward and one
  inference forward. It must preserve non-first quantizer outputs, produce
  finite loss and gradients, and report nonzero quantized/continuous values,
  finite positive RMS values, and a finite positive continuous/quantized RMS
  ratio.
- If admitted, run one 170-update gpu0 lane, keep the wrapper active while
  rendering external7 on port 8878, and run the fixed broad surfaces only when
  external7 adds no gross row and has no common-stable content regression.

Stop on shape drift, nonfinite or zero quantized/continuous representation,
nonfinite loss/gradient/RMS ratio, OOM, wrong call count, candidate-added gross
corruption, or broad common-stable content regression. Diagnostics are
auxiliary content/corruption evidence only; they cannot select naturalness,
target identity, a keeper, or a product winner.

## Prior diagnostic evidence

Read-only projected-latent probes on stress clean/noise20/silence300/tempo120/
pitchp3 and expanded `cv40748214f-noise10` produced shape `(1, 1024, 120)`;
all values were finite and nonzero. Continuous-to-quantized RMS ratios were
`1.131306–1.225896`, with cosine similarity `0.932890–0.948859`, and peak
allocated memory was `2,544,361,984` bytes. These probes support the smoke
hypothesis but are not a quality claim.

## Decision boundary

The pilot is a single source-representation change. External7 is evaluated
first against EXP-238 by exact source-ID/SHA joins, decoder stability, gross
corruption, and auxiliary CER/content distance. If the common-stable set
regresses or a candidate adds gross corruption, close EXP-285 and do not tune
the continuous path. If it survives, retain the unheard listener audio and
consider the fixed broad queue; no human listening means no keeper or winner.
