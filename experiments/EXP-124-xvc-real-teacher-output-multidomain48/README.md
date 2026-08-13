# EXP-124: X-VC full-output teacher with cross-corpus sources

Status: admitted; one bounded gpu0 lane

## Question

Can cross-corpus teacher-source composition improve robust generalization while
holding teacher count and share fixed?

## Independent variable

Keep EXP-116's 48 teacher sources, 209 teacher positions, 835 standard rows,
full-output objective, 1,044 updates, control69 standard LoRA, LR, rank, seed,
zero frame condition, and Amitaro target fixed. Change only the teacher pool:

- EXP-116: 48 unique Common Voice speakers;
- EXP-124: 24 of those frozen training-only Common Voice speakers, 21 Hadou
  training utterances excluded from all 87 target IDs and frozen Hadou31, and
  three official clean JVS speaker samples.

The fixed ratio is 24/21/3. Do not sweep it or change teacher share.

## Bound input

- Manifest: `artifacts/xvc-source-diversity/exp124-multidomain-teacher48-inputs-v1/training.json`
- SHA-256: `eb7d506a70e644829223cbbfe244c6ad4dffa23c5005280f96a61d391b66cc0b`
- Materialized rows: Common Voice 24, Hadou 21, JVS 3
- Hadou exclusions: every Amitaro target ID and every frozen Hadou31
- Method commit: `d47a464`

## Stop

Commit the preparer, training policy, and focused tests before materialization.
Bind exact files and exclusions before gpu0. Pass one real-model output-teacher
smoke, then train once. Render external7, frozen fresh48, the frozen ten-row
JVS/Hadou condition matrix, and 31 disjoint clean Hadou utterances. Stop on any
added gross loop or broad non-loop regression. Machine metrics cannot select
naturalness, target voice, or a winner.
