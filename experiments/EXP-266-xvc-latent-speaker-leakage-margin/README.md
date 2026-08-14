# EXP-266: X-VC latent source-speaker leakage margin

Status: stopped at real CUDA smoke; no full training and no listening audio

## Goal

Test one method-level explanation for EXP-243's distributed losses: the
converter latent can still describe the input speaker even though X-VC's
existing speaker predictor is pulled toward the target. The 13 strict EXP-243
losses span eight speakers and are not dominated by a text-length or recording
condition band, so another condition-specific patch is not admitted.

## One change

Start from the same control69 LoRA69 adapter and exact EXP-238
CV48/JSUT85/JVS3/Hadou34 curriculum. Preserve the complete source-aligned
pseudoparallel generative loss and real-Amitaro adversarial/feature loss. Add
one hinge term to X-VC's converter-latent speaker prediction:

```text
10 * relu(0.1 - (cos(predicted, target) - cos(predicted, source)))
```

`target` is the existing frozen X-VC ERes2Net embedding of the assigned
pseudoparallel target. `source` is a no-gradient embedding of the current
source window from the same frozen encoder. The hinge is zero when target
similarity already exceeds source similarity by 0.1. It does not supervise the
final WAV, add a sidecar, change the decoder, or train the speaker encoder.

Data, generated same-content targets, real discriminator targets, existing
target-speaker MSE, LoRA69 scope, learning rate `1e-4`, sequential optimizer,
170 updates, gradient clip 5, zero frame condition, discriminator, and EMA
remain exact. Weight 10 matches the existing internal speaker-prediction
coefficient. There is no margin, weight, source-encoder, or curriculum sweep.

## Gate

Run the exact no-CUDA admission and focused tests. Then run a real two-row CUDA
backward smoke. Admit the single 170-update lane only if the margin is finite,
active on at least one smoke row, reaches LoRA69 gradients, and stays within
the established memory envelope. Publish external7 on port 8878, then apply
only the existing coarse content/corruption screen.

Stop on a detached/zero margin gradient, zero active smoke rows, source/target
embedding shape drift, nonfinite loss, OOM, candidate-added gross corruption,
or broad content regression. Machine ASR and speaker embeddings cannot select
naturalness, audible identity, a keeper, or a winner. If external7 admits
broader rendering, reuse the already frozen fresh48, Hadou31, stress60,
JSUT24, and expanded144 surfaces; do not design another evaluation set.

## Result

Commit `2fa5abd` passed 56 focused runner tests and exact 170-row no-CUDA
admission. The two-row real CUDA smoke completed at 4,636,186,112 peak
allocated bytes, but both rows had `active_fraction = 0.0` and margin loss
`0.0`. Target-over-source advantage was already `+0.752988` and `+0.965543`;
target cosine was `0.942703` and `0.938061`.

The stop condition fired, so no 170-update lane or listening audio was
produced. Close this exact latent-margin hypothesis and its margin/weight
neighbors. The evidence says the post-converter speaker predictor is already
strongly aligned with its generated target; it does not prove the final WAV is
aligned with the real target speaker.

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
  --training-objective pseudoparallel-generative-real-adversarial-latent-speaker-margin \
  --adapter-ema \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp266-latent-speaker-margin-ema-v1 \
  --listener-dir artifacts/ms3/listening/exp266-xvc-latent-speaker-margin-external7-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
