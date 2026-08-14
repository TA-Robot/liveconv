# EXP-267: X-VC real target-speaker conditioning

Status: committed listen-now training pilot; unheard and unselected

## Goal

Correct one target-contract mismatch in EXP-238 without adding another
identity loss. EXP-238's source-aligned control69 output is useful as a
same-content semantic/mel teacher, but X-VC also derives its global speaker
condition and internal speaker-prediction target from that generated waveform.
The model is therefore asked to reproduce the teacher's emitted voice rather
than the assigned real Amitaro speaker embedding.

EXP-266 confirmed the consequence on two real rows: the existing internal
speaker predictor already gave the generated target a cosine advantage of
`+0.753` and `+0.966` over the source, so a source-negative hinge was inactive
on both. More pressure on that already-satisfied generated-speaker target is
not admitted.

## One change

Start from the same control69 LoRA69 adapter and exact EXP-238
CV48/JSUT85/JVS3/Hadou34 curriculum. During X-VC forward only, replace
`target_wav` with that row's assigned, authorized original Amitaro window so
the frozen ERes2Net global condition and existing `sim_mse_loss` use the real
speaker. Keep the source-aligned control69 output as `outputs["audios"]`,
`ssl_feat`, and the exact semantic/mel reconstruction target. The original
Amitaro window remains the discriminator-real target as in EXP-238.

This separates content/audio supervision from speaker supervision using the
existing X-VC losses and condition path. It adds no loss, final-WAV identity
term, sidecar, new parameter, or encoder update.

Curriculum, row order, generated targets, real targets, complete loss and all
weights, LoRA69 scope, learning rate `1e-4`, sequential optimizer, 170 updates,
gradient clip 5, zero frame condition, discriminator, and EMA remain exact.
There is no target mixture, speaker-loss weight, scope, LR, or horizon sweep.

## Gate

Run exact no-CUDA admission and a real two-row CUDA backward smoke proving the
separate target contract remains finite within the established memory
envelope. If admitted, run one 170-update gpu0 lane and publish external7 on
port 8878. Apply only the existing content/corruption screen. Machine ASR and
speaker embeddings cannot decide naturalness, audible identity, a keeper, or
a winner.

Stop on target-lineage drift, model/generator target aliasing, nonfinite loss or
gradient, OOM, candidate-added gross corruption, or broad content regression.
If external7 admits broader rendering, reuse only the frozen fresh48, Hadou31,
stress60, JSUT24, and expanded144 surfaces.

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
  --training-objective pseudoparallel-generative-real-adversarial-real-speaker-condition \
  --adapter-ema \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp267-real-speaker-condition-ema-v1 \
  --listener-dir artifacts/ms3/listening/exp267-xvc-real-speaker-condition-external7-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
