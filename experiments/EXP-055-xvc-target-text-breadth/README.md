# EXP-055: broader target-text coverage at fixed updates

Status: completed listen-now; mixed machine screen; operator hearing deferred

## Goal

Test whether the current X-VC adapter is overfitting 87 target-text prefixes by
redistributing the same 1,044-update budget across substantially more authorized
Amitaro runrun utterances.

The frozen manifest contains 334 train rows. Exactly 275 have at least 1.8
seconds of endpoint-guarded active target speech. EXP-055 takes the first active
2.4 seconds, right-padding 86 shorter rows and truncating 189 longer rows. The
first 219 targets receive four generated-source donors and the remaining 56
receive three; all twelve Common Voice donors receive exactly 87 exposures.
Thus target-text coverage changes from 87 to 275 while update count, donor pool,
control69 scope, loss, LR, seed, target voice, and zero condition stay fixed.

This is not another donor-count, role-mix, horizon, LR, or adjacent-scope point.
It also does not retry EXP-024 DTW. Pseudo sources are regenerated from each new
target window with the frozen base X-VC and the already-fixed donor references.

## Definition of Done

- Complete exactly 1,044 fresh-base control69 updates and publish seven external
  comparisons on port 8878.
- Render and machine-screen the frozen twelve changed utterances, ten audio
  conditions, and all 33 locally materialized Common Voice clips not used by
  EXP-035/039.
- Treat ASR and repetition as corruption screens only. No machine naturalness,
  identity, or product winner is allowed.
- Replan once from the complete 7 + 12 + 10 + 33 bundle; do not sweep target
  counts or per-text exposure ratios.

The 33-row sentence expansion is frozen in
[`expanded-evaluation.json`](expanded-evaluation.json). Its filenames are
disjoint from the existing donors and evaluation rows. Speaker overlap with the
older sets is permitted and recorded; this is a sentence-diversity set, not an
unseen-speaker claim.

## Result

The single admitted run completed all 1,044 updates in 270.50 seconds with
5.13 GB peak GPU allocation, and published 21 comparison files. Loss moved from
144.22 to 88.42. The seven-row external screen regressed control69 from 0.360
to 0.389 source-relative distance and from 0.399 to 0.457 known-text distance.

EXP-056's twelve changed utterances were source-relative identical to control69
at 0.184 and slightly better on known text, 0.576 to 0.559. EXP-057's ten
condition rows were identical to control69 in every aggregate and condition.
EXP-058 initially appeared to improve 33-row source-relative mean from 1.084 to
0.762, but that average was dominated by one gross-loop row and two rows whose
source ASR was empty. Excluding the gross-loop row produced six wins, nineteen
ties, seven losses, means 0.732 versus 0.736, and equal 0.600 medians. Known-text
mean and median also regressed after that exclusion. Both arms gross-looped the
same one row.

Target breadth therefore remains an unheard candidate, not a robust machine
content advancement. The method is closed without a target-count or exposure
ratio sweep. ASR did not judge naturalness, speaker identity, or voice quality.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_target_breadth.py \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --evaluation-set experiments/EXP-035-xvc-donor-breadth/external-evaluation.json \
  --source-root artifacts/xvc-method-reset/commonvoice25-ja \
  --target-manifest artifacts/xvc-human-paired/runrun-human-paired.manifest.json \
  --target-archive /tmp/liveconv-ms3-intake/amitaro-full-data/downloads/ITAcorpus_amitaro_runrun.zip \
  --control-adapter artifacts/xvc-source-diversity/exp035-cv12-v1/adapter-1044 \
  --xvc-source-root artifacts/x-vc/source \
  --xvc-config artifacts/x-vc/xvc-local.yaml \
  --checkpoint artifacts/x-vc/checkpoint/xvc.pt \
  --work-dir artifacts/xvc-source-diversity/exp055-target275-v1 \
  --listener-dir artifacts/ms3/listening/exp055-xvc-target275-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
