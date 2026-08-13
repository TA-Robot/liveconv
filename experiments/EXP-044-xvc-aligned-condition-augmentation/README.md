# EXP-044: alignment-preserving condition augmentation

Status: ready method pilot; operator hearing deferred

## Question

Can X-VC learn varied source limitations when the target supervision remains
temporally and prosodically coherent?

EXP-043 applied tempo, pitch, noise, and leading silence to pseudo-sources but
kept every Amitaro target clean. Its last tempo update had loss 800.8 and the
seven-speaker screen regressed on every aggregate diagnostic. That result
supports a label-alignment failure, not a useful augmentation-ratio sweep.

EXP-044 keeps EXP-043's exact 626 clean / 418 varied source schedule. Noise
remains source-only to train a clean target. Tempo 1.2, pitch +3, and leading
300 ms are applied identically to the exact 2.4-second pseudo-source and target
windows, and target SSL features are recomputed from the transformed target.
The twelve donors, 87 targets, update count, control69 scope, LR, loss, seed,
and zero target conditioning remain fixed.

## Done and stop

- Train exactly 1,044 fresh-base updates on `gpu0`.
- Publish base, EXP-035 all-clean, and EXP-044 aligned-condition outputs for
  the seven disjoint Common Voice speakers.
- A clear external content regression closes this method. If it survives,
  reuse the twelve changed utterances and ten frozen audio conditions before
  any other training job.
- Machine diagnostics cannot select naturalness, target voice, or a winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy paired-augmentation --lora-scope control69 \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --predecessor-result artifacts/xvc-source-diversity/exp035-cv12-v1/result.json \
  --predecessor-pseudo-root artifacts/xvc-source-diversity/exp035-cv12-v1/generated-source-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp044-aligned-augmentation-v1 \
  --listener-dir artifacts/ms3/listening/exp044-xvc-aligned-augmentation-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
