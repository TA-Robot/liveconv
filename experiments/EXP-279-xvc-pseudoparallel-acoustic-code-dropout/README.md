# EXP-279: pseudoparallel acoustic-code dropout

Status: broad-content stop fired; technically rejected, unheard, and unselected

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

## Training and external result

Commit `485380d` passed 61 focused runner tests, Ruff, exact CPU admission, and
a real two-row CUDA smoke. The smoke observed 122,867 nonzero quantized values
on the clean row. The masked row's real quantizer output had 122,866 nonzero
values and exactly zero values after the training-only mask. It exercised one
clean and one masked call, 835,584 trainable LoRA69 parameters, finite losses,
and 4,636,175,872 peak allocated bytes.

The one full lane completed 170 updates in 143.93 seconds at 6,163,570,688 peak
bytes. Its first/last total losses were `106.4064` and `224.2843`; this increase
is diagnostic, not a quality decision. The EMA adapter SHA-256 is
`2e22fb2ef6ac36e1347f4321ab5d95358f3c0ebfcc7f71773ebf0246106fe867`.
The result receipt initially counted seven unmasked external inference calls as
training calls (`92` instead of `85`); the runner now records the immutable
training schedule and the ignored result was corrected without retraining or
changing the adapter/audio.

External7 published seven changed candidate WAVs with no gross row. On six
exact source-ID/hash rows where EXP-238 and EXP-279 were both decoder-stable
and non-gross, source-relative distance moved `0.338675 -> 0.298077`, W/T/L
`2/4/0`; decoder instability stayed `1 -> 1`. This admits EXP-280--284 on the
unchanged adapter for fresh48, Hadou31, stress60, JSUT24, and expanded144. It
does not establish audible quality or a winner.

## Broad result

Commit `9e0f052` rendered the unchanged adapter on all five frozen broad
surfaces and published 1,535 WAVs on port 8878. Exact source-ID/SHA joins against
EXP-238 changed all 307 candidate WAVs and added no gross row (`2 -> 2`). Decoder
instability moved `59 -> 61`. On 238 rows where both candidates were stable and
non-gross, source-relative distance regressed `0.257143 -> 0.286194`, W/T/L
`28/189/21`.

The result was mixed by surface: Hadou31 improved `0.127328 -> 0.111925`
(`4/21/1`) and JSUT24 improved `0.123253 -> 0.104194` (`3/19/0`), while
fresh48 moved `0.219160 -> 0.237139` (`4/30/4`), stress60 regressed `0.214202 ->
0.271894` (`4/34/8`), and expanded144 regressed `0.349024 -> 0.390505`
(`13/85/8`). One expanded long/noise10 row contributed a `0 -> 10` outlier,
but stress regressions also appeared across clean, noise, silence, and pitch;
the stop is therefore not based on a single phrase or condition.

The broad common-stable content stop fired. Close this exact whole-acoustic-code
dropout method and its dropout-share/pattern neighbors. Retain its unheard audio
only for later operator diagnosis; it is not a keeper, winner, or product
decision.
