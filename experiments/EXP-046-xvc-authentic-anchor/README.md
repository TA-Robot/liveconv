# EXP-046: authentic-source anchor in synthetic diversity

Status: ready method pilot; operator hearing deferred

## Question

Does replacing one of twelve synthetic donor exposures per target with the
authorized, aligned human source anchor X-VC adaptation to real acoustics while
retaining synthetic speaker diversity?

EXP-035 used twelve generated donor voices and generalized better than the
three-donor schedule, but remained mixed. EXP-044's augmentation improvement
did not survive changed utterances. Both methods rely entirely on base-X-VC
generated training sources. EXP-046 changes only that construction: each of
the same 87 Amitaro targets receives eleven distinct synthetic donor sources
and its one existing aligned Hadou source, for the same twelve exposures and
1,044 total updates. Training roles, control69 scope, LR, loss, seed, target
voice, and zero target conditioning stay fixed.

This is a mixed-data method, not another epoch/LR/scope point or an EXP-024 DTW
retry. It uses the already-materialized, authorized EXP-026 train pairs and no
validation or heldout training audio.

## Done and stop

- Train exactly 1,044 fresh-base updates on `gpu0`.
- Publish base, EXP-035 synthetic-only, and EXP-046 authentic-anchor outputs
  for seven disjoint Common Voice speakers.
- A clear content regression closes the method. If it survives, reuse the
  twelve changed utterances and ten frozen conditions before another train.
- Machine diagnostics cannot select naturalness, target voice, or a winner.

## Command

```bash
HF_DATASETS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  artifacts/exp007/peft-resolve-20260811/runtime-1e52ef9ab8f1/bin/python \
  tools/xvc-source-diversity/run_role_mix.py \
  --training-policy authentic-anchor --lora-scope control69 \
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
  --work-dir artifacts/xvc-source-diversity/exp046-authentic-anchor-v1 \
  --listener-dir artifacts/ms3/listening/exp046-xvc-authentic-anchor-v1 \
  --confirm-gpu-lease gpu0 --device cuda:0
```
