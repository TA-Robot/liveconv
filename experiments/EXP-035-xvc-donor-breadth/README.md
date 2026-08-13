# EXP-035: X-VC donor breadth at fixed exposure

Status: ready method pilot; operator hearing deferred

## Question

Does replacing EXP-033's three generated-source donor speakers repeated over
four epochs with twelve distinct donor speakers in one epoch prevent the
external-speaker corruption seen in EXP-034?

The donor-pool construction is the only method change. Both runs use the same
87 Amitaro targets, twelve source exposures per target, 1,044 optimizer
updates, control69 LoRA, AdamW `1e-4`, composite loss, target voice, and zero
target waveform conditioning. Donors and evaluation speakers are disjoint.

## Data and evaluation

[`donors.json`](donors.json) freezes twelve distinct Mozilla Common Voice 25.0
Japanese speakers. [`external-evaluation.json`](external-evaluation.json)
freezes seven other speakers. All nineteen passed a source-only admission
screen on the first 2.4 seconds with known-text distance at or below `0.375`.
This gate rejects obviously undecodable input; it does not rank voice quality.

The exact files came from the named read-only Hugging Face mirror revision.
The official Common Voice catalog identifies the Japanese scripted-speech
release as CC0. Git retains file and client-ID hashes, not raw client IDs or
audio.

## Done and stop

- Generate `87 x 12 = 1,044` same-content pseudo-source pairs with base X-VC.
- Train exactly one pass / 1,044 adapter updates on `gpu0`.
- Publish base, EXP-033 JVS3, and EXP-035 CV12 outputs for the seven disjoint
  speakers on `http://127.0.0.1:8878/`.
- Run one content/repetition screen. Stop and replan after the result.

No auxiliary ASR result can select naturalness, target-voice fit, or a product
winner. No EXP-024 retry or human87 epoch/LR/scope sweep is reopened.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_breadth.py \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp033-jvs3-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp035-cv12-v1 \
  --listener-dir artifacts/ms3/listening/exp035-xvc-cv12-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
