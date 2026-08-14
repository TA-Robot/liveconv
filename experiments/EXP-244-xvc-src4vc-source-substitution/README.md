# EXP-244: SRC4VC smartphone source substitution

Status: prepared; private research subset acquisition pending

## Goal

Test whether broader real recording domains and speaker variation improve the
source-aligned pseudoparallel X-VC retraining contract. EXP-243 found no gross
failure and no single condition or speaker that explains the remaining mixed
rows. This lane changes one 85-row source-corpus block, not the loss or
optimization schedule.

## One training change

Replace the existing 85 single-speaker JSUT training sources with one
RECITATION utterance from each of 85 distinct SRC4VC version 1 speakers recorded
on smartphones. Retain Common Voice 48, JVS 3, and Hadou 34 sources for an
unchanged total of 170 rows. Retain the exact ordered Amitaro target assignment,
frozen-control69 same-content pseudoparallel target construction, complete
generative loss, LoRA scope, learning rate, one 170-update pass, and EMA.

Fifteen evenly spread SRC4VC speakers are excluded from training and contribute
two RECITATION utterances each to a frozen 30-row evaluation. There is no
speaker overlap between the 85-row train block and this heldout surface.

## Data boundary

SRC4VC version 1 is published for research use and prohibits redistribution.
The bounded fetcher pins the archive byte count, ETag, central-directory range,
and central-directory SHA-256, then retrieves only the selected ZIP members by
HTTP range. Raw audio, metadata, and derived manifests remain ignored below
`artifacts/`; repository history contains only the acquisition recipe and
aggregate evidence.

Official page:
`https://y-saito.sakura.ne.jp/sython/Corpus/SRC4VC/index.html`

## Definition of Done

- Commit the pinned byte-range fetcher, deterministic 85-train/15-heldout
  speaker split, focused tests, and this plan before materializing audio.
- Fetch and validate exactly 85 train and 30 evaluation WAVs as mono PCM16 at
  their published native 24, 44.1, or 48 kHz rate, with transcripts and speaker
  metadata. The active-window path preserves native rate.
- Materialize exactly 170 fixed curriculum rows by replacing only JSUT85 and
  preserve the original target sequence and all non-JSUT sources byte-for-byte.
- Render 170 source-aligned control69 targets, pass a two-row smoke, and run one
  gpu0 170-update training lane.
- Publish comparisons across the established five surfaces, EXP-243, and the
  disjoint 30-row SRC4VC surface. Use ASR only for corruption/content screening.

## Not in this lane

No SRC4VC ratio, utterance, speaker, device, dialect, loss, LR, horizon, rank,
scope, teacher, target, or EMA sweep. No product selection, promotion, corpus
redistribution, TTS comparison, or claim about naturalness or target identity.

## Stop conditions

Stop on archive or terms drift, invalid audio, speaker leakage, curriculum
identity drift outside the intended JSUT85 substitution, nonfinite training,
candidate-added gross corruption, or broad content regression. A passing
machine screen produces another unheard technical candidate, not a winner.
