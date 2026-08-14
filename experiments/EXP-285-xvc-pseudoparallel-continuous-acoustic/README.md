# EXP-285: pseudoparallel continuous acoustic latent

Status: broad-content stop fired; technically rejected, unheard, and unselected

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

## Training and external result

Commit `d088ef7` passed 134 combined runner/renderer tests, Ruff, exact CPU
admission, and the two-call CUDA smoke. The smoke retained nonzero quantized
and projected tensors, observed a continuous/quantized RMS ratio of `1.16852`
at inference, exposed `835,584` trainable LoRA69 parameters, and produced
finite nonzero gradients at `4,598,926,848` peak allocated bytes.

The only full lane completed 170 updates in 139.56 seconds at
`6,163,570,688` peak bytes. Loss moved `57.6864 -> 87.5233`; this trajectory is
diagnostic only. The EMA adapter SHA-256 is
`cd090f984506f7b45c551fc541cd578b9eebfec5b840ec5c7d9fa5ac42faedaa`.
It published 35 external comparison WAVs. No gross row was added, but decoder
instability moved `1 -> 2`. On five exact source-ID/SHA rows where EXP-238 and
EXP-285 were both stable and non-gross, source-relative content distance moved
`0.256410 -> 0.241026`, W/T/L `1/4/0`. That admitted the fixed broad surfaces
to decide whether the extra unstable row was isolated.

## Broad result

EXP-286--290 published 1,535 WAVs on the five frozen surfaces. Exact
source-ID/SHA joins against EXP-238 changed all 307 candidate outputs and added
no gross row (`2 -> 2`), but decoder instability increased `59 -> 68`. On 232
rows where both candidates were stable and non-gross, source-relative distance
regressed `0.227246 -> 0.264113`, W/T/L `43/156/33`.

By surface, fresh48 was nearly flat on the restricted rows
(`0.244284 -> 0.242421`, `5/25/9`) but instability rose `6 -> 7`; Hadou31
improved (`0.110603 -> 0.073590`, `7/17/1`) while instability rose `5 -> 6`;
stress60 regressed (`0.198327 -> 0.217207`, `7/31/7`) with instability
`13 -> 14`; JSUT24 was nearly flat (`0.123253 -> 0.121321`, `3/17/2`); and
expanded144 regressed (`0.285076 -> 0.371649`, `21/66/14`) while instability
rose `33 -> 39`.

The broad stop fired. Removing the acoustic nearest-code boundary is closed,
including adjacent continuous/quantized blends. The mixed Hadou benefit may be
heard later, but neither it nor auxiliary ASR establishes naturalness, target
identity, a keeper, or a winner.
