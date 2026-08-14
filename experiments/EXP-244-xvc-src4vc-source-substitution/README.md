# EXP-244: SRC4VC smartphone source substitution

Status: trained; broad listen-now rendering in progress; unheard and unselected

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

## Training result

The private subset contains 115 rows with disjoint 85-train/15-evaluation
speakers. Its manifest SHA-256 is
`b18606f6bfbeed782f26e2e795d739e41dc9dad41f716436d4a9e37bd8ece96c`.
The fixed 170-row curriculum SHA-256 is
`bcef60a8c7157e6da65e9878366441664d6f6e075f110cca5b14fb6505e2ede4`.

Control69 rendered 170 same-content targets in 94.17 seconds at 2,668,426,752
peak allocated GPU bytes. The two-row smoke was finite with 835,584 trainable
parameters. Full retraining completed all 170 optimizer steps in 142.27 seconds
at 6,163,570,688 peak bytes. The EMA adapter SHA-256 is
`1220290f223ad0e2235eeae6b128f2804d06f178f16d8aceec3480b7a621b4f6`.

The initial external7 screen found no gross row. On exact decoder-stable rows,
source-relative distance moved from control69 `0.256410` to candidate
`0.223077`, and known-text distance moved `0.370868 -> 0.270868`. This admits
the prebound broad render only; it does not establish audible quality.
