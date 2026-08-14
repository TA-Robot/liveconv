# EXP-319: 170-update Common Voice 26-row speech-active window treatment

Status: planned listen-now pilot; implementation commit precedes CUDA

## Milestone

### Goal

Test the one preprocessing difference left by EXP-317: use EXP-186's exact
speech-active 2.4-second window policy instead of the historical
evaluation-style first-window/right-pad plus X-VC normalization path, while
holding the admitted 26 recordings, schedule, target assignment, model, and
optimizer fixed against EXP-318.

### Definition of Done

- Use exactly EXP-318's 170 rows and 26 replacement positions.
- For those 26 rows only, decode the frozen raw MP3 to 16 kHz mono PCM16 and
  select the 38,400-sample window that maximizes samples with
  `abs(int16) > 328`, then squared energy, then earliest start, on a 1,600
  sample hop.
- Apply no gain normalization, high-pass filter, denoise, or post-selection
  content filter.  Require a nonzero active fraction for all 26 rows.
- Render fresh same-content teachers with the frozen control69 adapter from
  those exact new source bytes.  Do not reuse EXP-306 teachers.
- Preserve EXP-318's position-specific real Amitaro targets and every other
  EXP-238 row exactly; train the same LoRA69 path for exactly 170 updates.
- Commit all bindings before teacher CUDA or training CUDA, then publish the
  external7 comparison on port 8878.

### Not in this milestone

No recovery of the six below-threshold raw recordings, gain/filter sweep,
row-count/horizon/loss/scope change, broad render before external7, or machine
naturalness/winner claim.  EXP-318 versus EXP-319 is the primary causal
comparison; EXP-238 remains the corruption/content safety reference.

## Gate

Stop before teacher CUDA if any raw input/hash/metadata differs, any selected
window has zero active samples, any active source is byte-identical to its
EXP-318 source, any schedule or real target moves, or the output contract is
not exactly 170 rows.  The ordinary one-row backward smoke and LoRA69 trainable
count remain required, but no new training wrapper is admitted.

After external7, stop on a candidate-added consensus gross row, instability
above EXP-238's one row, a newly unstable EXP-238-stable row, or common-stable
source-relative regression.  Record EXP-318 versus EXP-319 changed-audio and
coarse content/corruption evidence, but leave naturalness, identity, keep, and
winner judgments open for the operator.
