# EXP-033: X-VC generated-source diversity

Status: ready listen-now method pilot; operator hearing deferred

## Question

At the same 87 Amitaro target texts, 12 target exposures per text, 1,044
optimizer updates, control69 LoRA scope, AdamW `1e-4`, zero target waveform
conditioning, and unchanged X-VC loss, does replacing the single Hadou source
speaker with three generated same-content JVS source voices reduce cross-speaker
and audio-condition content failures?

This is a new data-construction method, not another epoch, learning-rate, or
LoRA-scope point. It follows the upstream X-VC idea of training with generated
same-content pairs, but it is a small adaptation pilot rather than a reproduction
of upstream's large multilingual training.

## Definition of Done

- The committed runner creates `87 targets x 3 JVS donors = 261` generated
  source pairs with the immutable base X-VC.
- It trains exactly four passes over those pairs (`1,044` updates) on `gpu0`.
- It publishes base, legacy human87 control69-e12, and the new adapter on the
  fixed ten-row evaluation set to `http://127.0.0.1:8878/`.
- A coarse source-relative ASR/repetition screen is recorded by evaluation
  group. Human listening remains required for naturalness and target-voice fit.

## Fixed evaluation

[`evaluation-set.json`](evaluation-set.json) has ten rows: three official JVS
sample speakers, three source-only Hadou heldout rows, and one each for 1.20x
tempo, +3-semitone pitch, 20 dB deterministic noise, and 300 ms leading silence.
The previously mislabeled 8.17-second tongue-twister diagnostic is not included.

## Not in this run

- No full JVS/JSUT download, SpeechBSD gated data, Common Voice mirror, TTS-as-VC
  training data, target-conditioning change, loss change, or several sweep jobs.
- No retry of EXP-024 DTW or the closed human87 epoch/LR/scope points.
- No perceptual winner, promotion, route binding, or realtime-quality claim.

## Command

Run only after this note, evaluation set, runner, and tests are committed:

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run.py \
  --evaluation-set experiments/EXP-033-xvc-source-diversity/evaluation-set.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --jvs-root artifacts/xvc-method-reset/jvs-samples \
  --heldout-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/render-sources \
  --legacy-adapter artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp033-jvs3-v1 \
  --listener-dir artifacts/ms3/listening/exp033-xvc-source-diversity-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
