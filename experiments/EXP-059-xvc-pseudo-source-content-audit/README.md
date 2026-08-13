# EXP-059: X-VC pseudo-source content audit

Status: ready training-input audit; no quality claim

## Goal

Before another X-VC retraining run, measure whether EXP-035's 1,044 generated
pseudo sources preserve the content of the exact 2.4-second Amitaro target
window they were generated from. Select the best six nonempty, non-gross donor
renders per target and repeat that 522-pair set twice, preserving twelve target
exposures and exactly 1,044 optimizer updates.

This changes training-input content quality rather than target count, horizon,
learning rate, LoRA scope, loss weight, or EXP-024 alignment. ASR is only a
training-corruption filter. It cannot rank naturalness, speaker identity, or
voice quality.

## Admission and stop

- Audit all 87 target references and all 1,044 immutable EXP-035 pseudo sources.
- Stop before training if any target has fewer than six nonempty, non-gross
  candidates, if fewer than ten of twelve donors survive globally, or if the
  selected mean target-relative distance is not at least 25% lower than the
  unfiltered mean.
- If admitted, hold control69, target87, loss, LR, seed, zero condition, and
  1,044 updates fixed. Do not test another keep count.
- Freeze a new clean evaluation before training: all Hadou heldout rows whose
  existing full-utterance audit has CER at most 0.15, alongside the existing
  Common Voice 7 + 12 and ten named conditions. The historical 8.17-second
  tongue twister is not an evaluation gate.

## Command

```bash
.venv/bin/python tools/xvc-source-diversity/audit_training_pairs.py \
  --execute --confirm-gpu-lease gpu0 --device cuda --compute-type float16 \
  --donors experiments/EXP-035-xvc-donor-breadth/donors.json \
  --pair-root artifacts/xvc-human-paired/listen-now/exp026-human87-control69-v1/train-pairs \
  --pseudo-root artifacts/xvc-source-diversity/exp035-cv12-v1/generated-source-pairs \
  --model-root artifacts/shared/stt/faster-whisper-small \
  --output artifacts/xvc-source-diversity/exp059-pseudo-content-audit-v1.json
```
