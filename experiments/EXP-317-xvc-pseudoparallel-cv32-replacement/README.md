# EXP-317: 170-update Common Voice 32-row replacement

Status: planned listen-now pilot; implementation commit precedes CUDA

## Milestone

### Goal

Test whether EXP-306's genuinely new Common Voice data helps the retained
EXP-238 X-VC retraining method when the total curriculum and optimizer horizon
remain exactly 170 rows and updates. This removes the extra-update failure seen
in both 202-update EXP-305/306 arms.

### Definition of Done

- Start with EXP-238's ordered 170-row curriculum and replace exactly its first
  32 Common Voice positions with the already-admitted disjoint CV32 rows.
- Preserve 170 total rows and the exact corpus composition: Common Voice 48,
  JSUT 85, JVS 3, and Hadou 34.
- At every replaced position, preserve EXP-238's real Amitaro target ID, WAV,
  text, and SHA-256; change only the Common Voice source and its frozen
  control69 same-content teacher.
- Reuse the exact EXP-306 source and teacher bytes. Do not rerender, filter, or
  select rows using the EXP-305/306 auxiliary screen.
- Keep EXP-238's control69 initialization, LoRA69 scope, complete model and
  losses, LR, AdamW, clip, discriminator, EMA, inference, and 170 updates.
- Commit the materializer, ordinary trainer/renderer bindings, tests, and this
  plan before one gpu0 pilot. Publish external7 on port 8878 and run only the
  coarse content/corruption screen before deciding whether broad rendering is
  justified.

### Not in this milestone

No 202-update retry, adjacent horizon, loss, scope, condition, target voice,
teacher, corpus ratio, row filtering, CTC/GRL, or broad EXP-307--316 render.
Do not optimize the local tongue-twister or call it ChatGPT browser audio. Do
not infer naturalness, target identity, a keeper, or a winner from machine
metrics.

## One data change

EXP-238 contains 48 one-row Common Voice speakers among 170 total rows. In its
ordered manifest, replace the first 32 Common Voice positions with CV32 rows
`00` through `31` in order. The positions are:

```text
4, 5, 6, 11, 13, 14, 16, 19, 25, 27, 30, 31, 35, 36, 39, 43,
48, 52, 54, 55, 57, 58, 59, 63, 71, 75, 78, 80, 86, 91, 101, 103
```

The other 138 rows, including the remaining 16 Common Voice rows, remain
byte-identical in manifest identity to EXP-238. The new sources differ from
the replaced rows in speaker, text, and capture/window provenance, so the
claim is data-tuple replacement, not a pure speaker-count effect.

Primary comparison is EXP-317 versus EXP-238. EXP-305/306 only motivate
removing the 202-update horizon; their known-text movement is not a selection
rule.

## Gate

Stop before CUDA on row-count, order, corpus-composition, source/teacher, real
target, disjointness, path, WAV, or hash drift. A shared real backward smoke is
already green for the identical ordinary training path; do not repeat it unless
the path changes.

After external7, stop on a candidate-added consensus gross row, decoder
instability above EXP-238's one row, a newly unstable EXP-238-stable row, or
common-stable source-relative mean regression. Known-text distance is auxiliary
only. If the arm clears the external gate, admit the existing disjoint broad
surfaces in a later committed slice; otherwise record the stop and replan.

## Result

Plan commit `7813612` and implementation commit `c1108f4` bound exactly 170
rows with the declared 32 replacement positions and 138 unchanged rows. The
real artifact preflight verified every source, control69 teacher, and real
Amitaro WAV hash. It also found that EXP-306's appended rows carried incorrect
`real_target_text` metadata despite correct target IDs, WAV paths, and hashes;
EXP-317 restores the text from each position's EXP-238 source of truth. The
training audio contract was unaffected.

The pilot completed 170 updates in 163.30 seconds at 6,163,570,688 peak
allocated bytes and published 35 external7 WAVs. The EMA adapter SHA-256 is
`5623f7c9434dbd45ef1af35a1ed549fc3aebdc06f78786306b6b9c9d4f276b5f`.
All seven candidates changed and no consensus gross row was added.

Decoder instability increased from one row in EXP-238 to two: existing
`cv39005101` plus newly unstable `cv45195640`. On the five jointly stable rows,
source-relative distance tied exactly (`0W/5T/0L`, mean `0.344872`), while
secondary known-text distance was `1W/4T/0L` (`0.435154 -> 0.401821`). The
predefined instability stop fired, so no broad render is admitted. The result
does not select an audible winner. The next method must address the CV32 window
construction difference rather than sweep row count or horizon.
