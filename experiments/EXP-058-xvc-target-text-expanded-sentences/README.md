# EXP-058: target275 on 33 additional sentences

Status: completed listen-now; mixed machine screen; operator hearing deferred

Render all rows in EXP-055's `expanded-evaluation.json`. The selection was
frozen before training and contains every locally materialized Common Voice
clip whose filename was unused by EXP-035 donors/evaluation and EXP-039. This
is sentence diversity, not a claim that all speakers are new relative to older
sets.

Base, EXP-035 control69, source files, target reference, and seeds stay fixed;
only the EXP-055 candidate adapter changes. The machine screen transcribes the
source reference itself, so long clips are compared against the same consumed
first 2.4-second window. No naturalness or identity winner is inferred.

The render completed 33 rows and published 99 candidates in 106.39 seconds.
Raw source-relative mean moved from control69 1.084 to target275 0.762, but the
mean is not a robust advancement: one gross-loop row improved from 12.333 to
1.583 while remaining gross-looped, and two empty-source-ASR rows produced
opposing extreme distances. Excluding the gross-loop row left six target275
wins, nineteen ties, seven losses, means 0.732 versus 0.736, and identical
0.600 medians. Excluded-row known-text mean and median regressed. This set
exposed evaluation outliers and supplied listening audio; it did not select a
method or quality winner.

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/render_new_utterances.py \
  --candidate-kind target275-expanded \
  --evaluation-set experiments/EXP-055-xvc-target-text-breadth/expanded-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --candidate-adapter artifacts/xvc-source-diversity/exp055-target275-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp058-target275-expanded-v1 \
  --listener-dir artifacts/ms3/listening/exp058-xvc-target275-expanded-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
