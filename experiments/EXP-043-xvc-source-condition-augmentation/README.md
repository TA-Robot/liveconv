# EXP-043: source-condition augmentation

Status: ready method pilot; operator hearing deferred

## Question

Does training on the audio limitations the realtime route must tolerate improve
X-VC robustness without corrupting clean unseen speech?

EXP-042 showed that target reconstruction changed none of the ten frozen
condition diagnostics and did not repair the 20 dB noise weakness. EXP-043
therefore returns to all-standard control69 training and changes only source
acoustics. Across the same 1,044 target/donor updates it assigns 626 clean, 105
20 dB noise, 105 tempo 1.2, 104 pitch +3 semitones, and 104 leading-300 ms
source windows. The clean Amitaro targets, twelve donors, exposure count, LoRA
scope, LR, loss, seed, and zero target condition remain fixed.

## Done and stop

- Train exactly 1,044 fresh-base updates on `gpu0`.
- Publish base, EXP-035 all-clean, and EXP-043 augmented outputs for the seven
  disjoint Common Voice speakers.
- Reject only on gross repetition/content corruption. If it survives, render
  the same adapter on EXP-039's twelve new utterances and EXP-033's ten frozen
  conditions before any other training variation.
- Machine diagnostics cannot select naturalness, target voice, or a winner.

No donor-count, epoch, LR, scope, or reconstruction-ratio sweep is reopened.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy source-augmentation --lora-scope control69 \
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
  --work-dir artifacts/xvc-source-diversity/exp043-source-augmentation-v1 \
  --listener-dir artifacts/ms3/listening/exp043-xvc-source-augmentation-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
