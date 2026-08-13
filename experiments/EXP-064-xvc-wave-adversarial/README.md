# EXP-064: pretrained waveform-adversarial X-VC adaptation

Status: completed listen-now; viable unheard candidate, no quality claim

## Question

Does restoring X-VC's pretrained waveform discriminator, adversarial generator
loss, and discriminator feature matching produce a viable listening candidate
when the training data and adapter topology are otherwise identical to EXP-035?

## One changed variable

EXP-035 and this candidate both use the exact generated-source inventory digest
`e909e465`, twelve Common Voice donor speakers, 87 Amitaro target windows,
1,044 updates, control69 LoRA, LR `1e-4`, gradient clip 5, seed, zero frame
condition, and base generative loss. EXP-064 additionally restores the upstream
alternating discriminator update and generator-side waveform adversarial plus
feature-matching losses. The pretrained 324-tensor discriminator is loaded from
the same pinned X-VC checkpoint; it is not initialized from scratch.

The upstream warmup has already elapsed in the pretrained checkpoint. The
adversarial branch is therefore active from the first adaptation update. This
is one method point, not a weight, warmup, or D/G-rate sweep.

## Decision boundary

Publish the seven external rows, then EXP-065--067's twelve changed utterances,
ten named conditions, and 31 Hadou sentences. Machine ASR may reject empty,
content-drifted, or gross-loop output. It cannot evaluate the intended
naturalness effect, speaker identity, or select a winner. Keep all viable audio
unheard until operator listening returns.

## Result

The fixed-data adapter completed 1,044 alternating D/G updates in 330.37
seconds at 5.13 GB peak allocated GPU memory. The discriminator loss moved
from 1.686 to 0.387; total generator-side loss moved from 199.76 to 181.57.
The complete EXP-064--067 bundle produced no gross loop across 60 evaluation
rows. Seven external rows and ten named conditions were machine-identical to
control69. Twelve changed utterances moved from 0.184 to 0.204 mean
source-relative distance. Hadou31 moved from 0.210 to 0.186 with five lower,
twenty-four equal, and two higher rows. The adapter remains a
naturalness-motivated hearing candidate because machine ASR cannot decide its
intended effect. No adversarial weight, warmup, or optimizer sweep is admitted.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_breadth.py \
  --training-objective upstream-adversarial \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp064-wave-adversarial-v1 \
  --listener-dir artifacts/ms3/listening/exp064-wave-adversarial-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
