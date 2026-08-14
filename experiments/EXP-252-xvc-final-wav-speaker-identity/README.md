# EXP-252: X-VC final-WAV speaker identity supervision

Status: trained; broad corruption screen admitted; unheard and unselected

## Goal

Test whether supervising target identity on the final converted waveform fixes
a blind spot in the retained EXP-238 pseudoparallel method. The current
`sim_mse_loss` trains a speaker predictor from the converter latent `x`; it does
not measure the waveform emitted by the frozen acoustic decoder. The predictor
can therefore improve without proving that target identity reached the WAV.

## One change

Starting from the same control69 LoRA69 adapter and exact EXP-238
CV48/JSUT85/JVS3/Hadou34 curriculum, add a weight-10 cosine loss between:

- the final differentiable reconstructed waveform embedded by X-VC's frozen
  ERes2Net speaker encoder; and
- the assigned original, operator-authorized Amitaro target window embedded by
  the same frozen encoder.

The implementation calls the frozen ERes2Net directly so its inference wrapper
does not detach the output-WAV gradient. It leaves the encoder in evaluation
mode and does not unfreeze or update its parameters.

All source-aligned control69 generative targets, real-wave discriminator
targets, internal speaker-predictor loss, loss weights, LoRA scope, learning
rate, sequential optimizer, 170 updates, gradient clip, zero frame condition,
and EMA remain fixed. Weight 10 matches the existing internal speaker-loss
coefficient; there is no weight sweep.

## Gate

Run a two-row finite/gradient smoke, then one gpu0 170-update lane. Publish the
standard external7 comparison first and reuse the established broad surfaces
only if no candidate-added gross corruption appears. ECAPA and ASR are
auxiliary direction/corruption screens only; neither can declare naturalness,
identity quality, a keeper, or a winner.

Stop on a detached/zero waveform gradient, nonfinite ERes2Net features, target
lineage drift, gross corruption, or broad content regression. Do not vary the
speaker weight, encoder, curriculum, scope, LR, horizon, or EMA in this lane.

## Training result

The committed 170-update gpu0 run completed from `f513614` in 145.88 seconds
with 6,161,235,968 peak allocated bytes. The frozen final-WAV ERes2Net cosine
increased from `0.318931` on the first update to `0.412770` on the last update.
The resulting EMA adapter SHA-256 is
`c4a2d6779384d10238c99cda816a84e23ab53c596c76e847470d58a2549dbbd8`.

External7 produced no candidate-added gross repetition. On the five rows whose
candidate decoding was stable for both EXP-238 and EXP-252, auxiliary
source-relative distance moved `0.256410 -> 0.223077` (one improvement, four
ties, zero regressions). This is only a corruption/content admission result;
it does not establish audible identity, naturalness, or a winner. Reuse the
fixed fresh48, Hadou31, stress60, JSUT24, and expanded144 surfaces next, with
no retraining or weight neighbor.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_post_rehearsal.py \
  --training-manifest artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1/curriculum.json \
  --source-work artifacts/xvc-source-diversity/exp213-cross-corpus-unpaired-inputs-v1 \
  --diverse-work artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1 \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --training-objective pseudoparallel-generative-real-adversarial-output-speaker \
  --adapter-ema \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp252-output-speaker-ema-v1 \
  --listener-dir artifacts/ms3/listening/exp252-xvc-output-speaker-external7-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
