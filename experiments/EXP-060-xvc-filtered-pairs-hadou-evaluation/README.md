# EXP-060: content-filtered pseudo-pair X-VC retraining

Status: completed listen-now; filtered-pair method closed without a quality claim

## Method

Train control69 on EXP-059's best six nonempty, non-gross generated sources per
each of the same 87 Amitaro target windows, for two identical passes. Relative
to EXP-035, only the pseudo-source selection and ordering change. Target voice,
target text exposure, 1,044 optimizer updates, LoRA scope, loss, LR, seed, and
zero frame condition stay fixed. There is no keep-count or threshold sweep.

## Goal

Evaluate the one admitted pseudo-source-filtered X-VC adapter on a second human
source corpus, not the historical 8.17-second tongue twister. The set contains
all 31 Hadou ITA rows assigned to the existing heldout split whose already-run
full-utterance faster-whisper audit has character error at most 0.15.

The selection is frozen in [`hadou-evaluation.json`](hadou-evaluation.json).
Each source will be endpoint-trimmed and limited to the first 2.4 seconds, then
screened relative to ASR of that exact consumed window. The full official text
is displayed for listening context but is not treated as the window transcript.

This complements rather than replaces the nineteen existing Common Voice rows
and ten named clean/noise/silence/tempo/pitch conditions. Machine ASR can reject
empty output, content drift, or gross loops. It cannot select naturalness,
speaker identity, or a voice-quality winner.

## Result

The sole filtered6x2 adapter completed 1,044 updates in 196.15 seconds with
5.13 GB peak allocated GPU memory. Loss moved from 159.57 to 131.81 and 21
external-speaker comparison WAVs were published. The seven original external
rows were exactly equal to control69 on the machine content screen. The
mandatory EXP-061--063 evaluations did not establish robust improvement, so no
keep-count or threshold sweep is admitted. All audio remains unheard and
unselected.

## Training command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_filtered_pairs.py \
  --selection-audit artifacts/xvc-source-diversity/exp059-pseudo-content-audit-v1.json \
  --pseudo-root artifacts/xvc-source-diversity/exp035-cv12-v1/generated-source-pairs \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp060-content-filtered6x2-v1 \
  --listener-dir artifacts/ms3/listening/exp060-content-filtered6x2-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
