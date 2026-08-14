# EXP-319: 170-update Common Voice 26-row speech-active window treatment

Status: broad corruption/content gate failed; unheard and unselected

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

## External7 result

The CPU materializer produced 26/26 nonzero-active windows; all source hashes
differ from EXP-318 while the same 26 positions and all real-target assignments
remain fixed.  Frozen control69 rendered 26 fresh teachers in 99.39 seconds at
2,668,426,752 peak GPU bytes.  The resulting 170-row curriculum passed the
real-artifact admission gate.  Its source-pool manifest SHA-256 is
`1196f32129e970442dbdd763f5ec7f3ebf5563d3b84e246132ae7b4d256e93e3`.

Training completed 170 updates in 157.44 seconds at 6,163,570,688 peak bytes
and published 35 external7 WAVs.  The EMA adapter SHA-256 is
`9692d107e5e92cc8aa2b79d54c80390b27a8348eaa9f681efef3988757596670`.
All seven outputs changed versus EXP-238 and EXP-318.  No consensus gross row
was added, and all three arms have the same sole unstable row, `cv39005101`.

On the six jointly stable rows, EXP-319 versus EXP-318 source-relative distance
was `1W/5T/0L`, mean `0.351496 -> 0.323718`; secondary known-text distance was
`2W/4T/0L`, `0.382470 -> 0.315009`.  Against EXP-238, source-relative distance
was `1W/4T/1L`, mean `0.338675 -> 0.323718`, while known-text was `2W/4T/0L`,
`0.422152 -> 0.315009`.  The predefined external gate passes, so only the five
already-frozen broad surfaces are admitted next.  These auxiliary diagnostics
do not establish naturalness, target identity, a keeper, or a winner.

## Broad result and decision

EXP-320--324 rendered all 307 frozen inputs and published 1,535 WAVs on port
8878. Exact EXP-238 joins below use rows where both candidates are decoder
stable. W/T/L is EXP-319 versus EXP-238 on source-relative auxiliary ASR
distance; lower is better.

| Surface | Common rows | EXP-238 -> EXP-319 | W/T/L | Unstable |
| --- | ---: | ---: | ---: | ---: |
| fresh48 | 40 | `1.033891 -> 1.030058` | 5/33/2 | `6 -> 8` |
| Hadou31 | 26 | `0.127328 -> 0.129427` | 4/21/1 | `5 -> 5` |
| stress60 | 46 | `0.212649 -> 0.215318` | 2/42/2 | `13 -> 12` |
| JSUT24 | 22 | `0.123253 -> 0.102246` | 3/19/0 | `2 -> 2` |
| expanded144 | 108 | `0.315745 -> 0.510056` | 9/92/7 | `33 -> 34` |
| all | 242 | `0.377108 -> 0.462015` | 23/207/12 | `59 -> 61` |

Fresh48 gained two newly decoder-unstable rows. Stress60 resolved two unstable
rows but added one different unstable row. Expanded144 added one consensus
gross repetition on `cv39028774f-silence600`, three newly unstable rows while
resolving two, and a large common-stable mean regression. Hadou was essentially
flat and JSUT improved, so the effect is distribution-dependent rather than a
generic content gain.

The predefined broad stop fires. Close first-window/activity-threshold/gain/
filter/row-count neighbors and do not nominate EXP-319. The audio remains
useful for later human diagnosis of naturalness and target voice; the machine
screen cannot reject or keep it perceptually.
