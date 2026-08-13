# EXP-072: real-speech rehearsal during X-VC target adaptation

Status: completed; rejected for changed-content regression and one gross loop

## Question

Does rehearsing real Japanese donor speech during target-voice adaptation reduce
the changed-utterance forgetting repeatedly seen in generated-pair methods?

## One changed variable

EXP-035's exact twelve admitted Common Voice training donors, 87 Amitaro target
windows, generated-source inventory digest `e909e465`, control69 rank-8 LoRA,
generative loss, 1,044 total updates, LR `1e-4`, gradient clip 5, seed, and zero
frame condition remain fixed. EXP-072 uses 835 standard generated-source to
Amitaro updates and replaces 209 standard updates with self-reconstruction of
the corresponding real Common Voice donor window.

The auxiliary rows use the donor's real waveform, semantic tokens, waveform
target, and SSL target together. They are not pseudo audio and do not use any
evaluation speaker. This is one fixed 80/20 rehearsal point, not a ratio sweep.
Unlike EXP-040's Amitaro self-reconstruction, it exposes the adapter to real
multi-speaker waveforms as reconstruction targets while keeping 80% of updates
target-voice specific.

## Decision boundary

Publish seven external rows and then EXP-073--075's twelve changed utterances,
ten conditions, and 31 Hadou sentences. Machine ASR only screens empty output,
content drift, and repetition. It cannot rank naturalness or target identity.
A gross loop or robust changed-utterance regression rejects the method. Do not
sweep the rehearsal ratio.

## Result

Training completed 1,044 updates in 286.81 seconds at 5.13 GB peak; loss moved
from 144.22 to 131.44. Seven external rows worsened from control69 mean `0.360`
to `0.411`. Twelve changed utterances were two wins, four ties, six losses and
mean `0.232` versus `0.184`, despite a lower worst case. Ten conditions were one
win and nine ties. Hadou was four wins, 21 ties, six losses and added one gross
number-loop. Reject the method and do not sweep its ratio.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy real-reconstruction20 --lora-scope control69 \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --predecessor-result artifacts/xvc-source-diversity/exp035-cv12-v1/result.json \
  --predecessor-pseudo-root artifacts/xvc-source-diversity/exp035-cv12-v1/generated-source-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp072-real-rehearsal-v1 \
  --listener-dir artifacts/ms3/listening/exp072-real-rehearsal-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
