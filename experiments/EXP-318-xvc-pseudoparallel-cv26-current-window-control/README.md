# EXP-318: 170-update Common Voice 26-row current-window control

Status: planned listen-now pilot; implementation commit precedes CUDA

## Milestone

### Goal

Separate source admission from window preprocessing before retrying the
EXP-317 data method.  Keep the existing evaluation-style X-VC source bytes for
the 26 CV32 recordings whose raw Common Voice audio contains at least one
speech-active sample under the EXP-186 policy, and restore the six
below-threshold rows to their original EXP-238 tuples.

### Definition of Done

- Start from EXP-238's ordered 170 rows and replace exactly 26 Common Voice
  positions with the corresponding existing EXP-317 source and frozen
  control69 teacher bytes.
- Preserve 170 updates and the exact Common Voice 48 / JSUT 85 / JVS 3 /
  Hadou 34 composition.
- Preserve every position-specific real Amitaro target ID, WAV, text, and hash.
- Restore the six raw-below-threshold positions byte-for-byte to EXP-238; do
  not normalize, amplify, denoise, or otherwise rescue them in this arm.
- Keep EXP-238's adapter initialization, LoRA69 scope, losses, optimizer, EMA,
  inference path, and external7 coarse screen unchanged.
- Commit the plan and implementation before one sequential gpu0 run, then
  publish its external7 comparison on port 8878.

### Not in this milestone

No speech-active source rerender, new teacher render, row-count or horizon
sweep, loss/scope change, broad rendering, or audible winner claim.  ASR and
decoder stability screen corruption/content only.  The local tongue-twister
is not ChatGPT browser input and is not an optimization target.

## Fixed admission

The retained replacement positions are:

```text
4, 5, 6, 11, 13, 16, 19, 25, 27, 30, 35, 36, 39, 43, 48, 54,
55, 57, 58, 59, 63, 71, 75, 86, 101, 103
```

The restored positions are `14, 31, 52, 78, 80, 91`, corresponding to raw
recordings `cv22959165u`, `cv38987912u`, `cv39076307u`, `cv41934139u`,
`cv42263615u`, and `cv45113065u`.  Their best exact 2.4-second window contains
zero samples above the fixed absolute-amplitude threshold.  This is a CPU
admission fact, not an audible-quality verdict.

## Gate

Stop before CUDA on row/order/composition drift, a non-exact unchanged row,
real-target reassignment, source/teacher hash mismatch, or any retained raw
window with zero active samples.  After external7, stop on a candidate-added
consensus gross row, instability above EXP-238's one row, a newly unstable
EXP-238-stable row, or common-stable source-relative regression.  Known-text
distance is auxiliary only.

EXP-318 is the control for EXP-319.  Its result may show whether excluding the
six below-threshold raw recordings helps; it cannot establish the effect of
speech-active window selection.
