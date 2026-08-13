# EXP-076: waveform-adversarial X-VC on 33 unused Common Voice speakers

Status: committed evaluation; waiting for one render

## Question

Does the retained, unheard EXP-064 waveform-adversarial candidate avoid content
corruption on 33 locally unused Common Voice utterances from 33 speakers?

## Boundary

The evaluation manifest was frozen before EXP-064 training and used only for
the earlier target275 evaluation. None of its audio enters EXP-064 training.
This adds speaker and sentence diversity to the 7 + 12 + 10 + 31 gate without
changing or retraining the candidate. Render base, EXP-035 control69, and
EXP-064 once. Auxiliary ASR may identify empty output, drift, or gross loops;
it cannot rank naturalness, target identity, or select a winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind wave-adversarial-expanded \
  --evaluation-set experiments/EXP-055-xvc-target-text-breadth/expanded-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp064-wave-adversarial-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp076-wave-adversarial-expanded-v1 \
  --listener-dir artifacts/ms3/listening/exp076-wave-adversarial-expanded-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
