# EXP-112: X-VC real-teacher on 48 fresh Common Voice speakers

Status: completed; EXP-106 generic improvement not reproduced

## Question

Does the exact EXP-106 checkpoint retain its changed-content and stress signal
on a genuinely fresh set of speakers and sentences, rather than the 64 Common
Voice clips repeatedly reused by earlier method screens?

## Boundary

Select 48 unique client IDs from the already-pinned Common Voice 25.0 Japanese
`test-ja00` metadata, excluding every client represented by the 64 locally
materialized clips. Require at least two up-votes, zero down-votes, and 10--80
normalized text characters. Download from revision
`365b7654cd582e20e8000921ef7b0e32caa1906a`, freeze hashes and durations, then
render base, EXP-035 control69, and EXP-106 once.

This is new evaluation data, not X-VC training data and not ChatGPT browser
audio. Auxiliary ASR may reject loops, empty output, or broad content drift. It
cannot select naturalness, target voice, or a winner. Do not tune the selection
filter or teacher method from individual rows.

## Result

Commit `6c1caa8` rendered 48 fresh speakers once, producing 144 model outputs
on port 8878. The manifest SHA-256 is
`e75f719460e6228535bce31af4226394da70651c0f09fc1f8e5843cf7cfbfa0b`.

| Arm | Source-relative mean | Median | Gross repetition |
|---|---:|---:|---:|
| base | 0.414 | 0.283 | 1 |
| control69 | 1.001 | 0.275 | 2 |
| EXP-106 teacher | 0.666 | 0.308 | 2 |

The one base repetition is already present in the naturally repetitive source
sentence. Control69 and EXP-106 each added one separate catastrophic loop.
Across the 45 rows where no arm looped, EXP-106 regressed control69 on both
mean (`0.357` versus `0.326`) and median (`0.308` versus `0.250`), with
win/tie/loss `10/19/16`. Its raw-mean advantage over control69 is therefore an
outlier effect, not broad generalization.

## Decision

Close EXP-106 as a generic retraining method without share or weight sweeps.
Keep its audio as an unheard technical candidate because it previously improved
the balanced stress matrix, but do not call it a winner or a base improvement.
The fresh48 set stays evaluation-only and must not become the next training or
row-selection set.
