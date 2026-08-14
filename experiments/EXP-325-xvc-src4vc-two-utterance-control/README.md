# EXP-325/326: two-utterance SRC4VC source-speaker adversary

Status: EXP-325/326 matched external7 and six broad surfaces complete;
generic GRL content-improvement claim rejected, audio remains unheard

## Milestone

### Goal

Test whether explicitly removing source-speaker information from X-VC's
post-converter latent improves broadly robust Amitaro conversion. The causal
comparison is a matched pair on a new 85-speaker, two-utterance-per-speaker
SRC4VC substrate: EXP-325 is ordinary source-aligned pseudoparallel training;
EXP-326 changes only the source-speaker adversarial objective.

This does not reopen EXP-244's rejected claim that substituting SRC4VC for
JSUT is generically better data. EXP-238 remains a safety reference, but only
EXP-325 versus EXP-326 isolates the adversary.

### Definition of Done

- Reuse EXP-244's exact 85 training speakers and exclude its fixed 15 heldout
  speakers. Deterministically select RECITATION utterances zero and one for
  each training speaker, producing exactly 170 distinct WAVs, transcripts,
  source hashes, and explicit `source_speaker_id` values with 85 classes of
  exactly two rows each.
- Keep the private SRC4VC archive members, audio, metadata, and manifests below
  ignored `artifacts/`; commit only the acquisition recipe and aggregate facts.
- Bind the exact EXP-238 ordered real Amitaro discriminator references to both
  arms and freshly render the same frozen-control69, same-content teacher for
  every source. Both arms start from control69, use LoRA69, LR `1e-4`, the
  ordinary composite and real-adversarial losses, 170 updates, EMA, zero frame
  condition, and normal quantized inference.
- Capture the differentiable acoustic-converter output `x [B,1024,T]` during
  training only. Mean/std pool it to 2,048 values and classify the 85 explicit
  source speakers with one linear head. Update that head on detached `x`; on
  the generator step freeze the head and reverse only its CE gradient into
  LoRA69. The head is never exported or used at inference.
- Before full training, prove that source-speaker signal exists: use frozen
  control69 features from utterance zero as the 85 reference centroids and
  identify utterance one by cosine similarity. Record top-1 and top-5; stop if
  they do not materially exceed chance. Then run a two-speaker CUDA backward
  smoke proving finite nonzero classifier and LoRA gradients, disjoint
  optimizers, and unchanged inference output shape.
- Commit the exact fetcher, materializer, trainer, renderer, focused tests, and
  this plan before teacher CUDA or either training lane.
- Phase 1 runs the teacher render and ordinary EXP-325 control only, then
  publishes its external7 comparison on port 8878. Replan from that
  content/corruption screen before authorizing EXP-326 CUDA. Phase 2 may run
  EXP-326 only on the identical committed manifest, teachers, target order,
  initialization, and optimizer contract, so the adversary is its sole change.

### Not in this milestone

No SRC4VC speaker/utterance/ratio sweep, class-count neighbor, GRL weight or
head architecture sweep, loss/LR/rank/scope/horizon change, Common Voice
window retry, CTC, output-speaker objective, or final-WAV content cycle. No
comparison may declare naturalness, target-voice fit, a keeper, or a winner.

## Gates

Stop before teacher CUDA on archive/terms drift, heldout-speaker leakage,
anything other than 85 classes x 2 distinct utterances, invalid audio, target
order drift, or weak cross-utterance source-speaker signal. Stop before full
training on nonfinite or zero GRL-to-LoRA gradient, classifier parameters in
the LoRA optimizer, inference-hook leakage, or memory-envelope failure.

Phase 1 stops before EXP-326 if the new control substrate is invalid, nonfinite,
adds gross corruption, or is materially less stable than EXP-238 on external7.
If admitted, Phase 2 must run the matched GRL arm through external7 before any
broad render. Broad work requires EXP-326 to add no gross corruption, add no
decoder instability, and avoid common-stable source-relative regression versus
EXP-325. Passing only authorizes the fixed fresh48, Hadou31, stress60, JSUT24,
expanded144, and SRC4VC-heldout30 surfaces. Machine ASR remains a corruption
and content diagnostic, not perceptual selection.

## Phase-1 data admission

Commit `9b36ab2` added deterministic train-utterance selection without
weakening the frozen ten-RECITATION-entries-per-speaker archive check. The
private index-1 subset then materialized 85 train rows and the unchanged 30-row
heldout set. Its manifest SHA-256 is
`ab356bb10cf620ba13243c9da1152a2b775ef620d147cb684991c6a75f8a6e83`.

The 85 train speakers exactly match EXP-244, every selected WAV hash, text, and
ID differs from that speaker's index-0 row, and the two train sets share zero
WAV hashes. The new rows contain 444.15 seconds of mono PCM16 speech at the
published 24, 44.1, or 48 kHz rates. The heldout 15 speakers remain disjoint
and their exact 30 identities, hashes, and texts are unchanged.

## Phase-1 result and phase-2 admission

The committed binder produced 170 rows with 85 explicit speakers and exactly
two distinct utterances per speaker. Frozen control69 rendered all 170
same-content teachers. The first renderer invocation finished every WAV but
failed while assembling the final manifest because it discarded the validated
EXP-238 target-order object. Commits `e79d9e6` and `28661c5` added an
exact-inventory crash-recovery path and restored the required
`source_relative_distance: 0.0`; no teacher WAV was rerendered. The final
curriculum SHA-256 is
`a524272f31c94fa0c32cc434e1a02fedf3ac16204272247e1056a67b35bb66e1`.

EXP-325 then completed 170 ordinary pseudoparallel real-adversarial updates in
190.20 seconds at 6,163,570,688 peak allocated GPU bytes. It published 35
external7 WAVs on port 8878. Against the exact EXP-238 candidate on the same
seven rows, source-relative distance was `0W/6T/1L`, mean
`0.433150 -> 0.444139`. Both arms had one decoder-unstable row, neither had a
gross repetition, and EXP-325 added neither a new unstable row nor a new gross
row. Auxiliary known-text distance moved `0.504702 -> 0.480892`; it is not a
naturalness or winner signal.

The phase-1 improvement hypothesis is unsupported, but its predefined safety
gate passes: the new substrate is finite, complete, and no less stable on
external7. Phase 2 may therefore change only the training-only source-speaker
GRL objective on the exact same curriculum, teachers, target order,
initialization, LoRA69 scope, LR, 170-update horizon, EMA, and inference path.
Run the bounded signal/gradient/inference admission before the full EXP-326
lane. Human hearing remains unavailable, so EXP-325 stays unheard and
unselected.

## Phase-2 external7 result

The first two bounded GRL smokes exposed integration defects before any
optimizer update. The first incorrectly resolved SRC4VC target IDs through an
unrelated target inventory; commit `342f287` binds pseudoparallel realism to
each row's ordered real Amitaro file and hash. The second found stale one-arg
generator calls and, during that repair, a deeper matched-contract error: the
GRL helper used the control69 teacher rather than real Amitaro for the waveform
discriminator. Commit `32c8ba1` keeps the teacher as the X-VC generator target,
passes no speaker-target override, and supplies row-specific real Amitaro only
to the discriminator/adversarial path, exactly matching EXP-325.

The corrected two-row smoke produced finite nonzero classifier gradients on
174,165 elements and GRL-to-LoRA gradients on 827,376 elements. It proved
disjoint optimizers, removed the training hook before inference, and retained
output shape `[1, 1, 38400]` at 5,222,119,424 peak allocated GPU bytes.

Before full training, frozen-control69 acoustic-converter latents identified
utterance one from utterance-zero centroids at top-1 `0.152941` and top-5
`0.352941`, respectively 13x and 6x chance. EXP-326 then completed 170 updates
in 226.87 seconds at 6,163,124,736 peak allocated GPU bytes. The 2,048-to-85
head was not exported, the hook recorded zero inference calls and was removed,
and ordinary adapter inference published 35 external7 WAVs on port 8878.

All seven EXP-326 candidate hashes differ from EXP-325. The exact coarse screen
was `0W/7T/0L` on source-relative distance; gross remained `0 -> 0`, decoder
instability remained `1 -> 1`, and no new unstable row appeared. This supports
neither a perceptual improvement nor a winner. It does satisfy the predefined
external gate, so only the frozen fresh48, Hadou31, stress60, balanced JSUT24,
expanded144, and SRC4VC-heldout30 surfaces are admitted next. Do not sweep GRL
weight, classifier shape, data, horizon, loss, or scope.

## Phase-2 broad result

Both matched arms completed all six frozen surfaces: fresh48, Hadou31,
stress60, balanced JSUT24, expanded144, and SRC4VC-heldout30. They published
3,370 broad comparison WAVs on port 8878. All 337 candidate hashes differ
between EXP-325 and EXP-326.

The exact aggregate source-relative ASR join is `15W/303T/19L`, mean
`0.609039 -> 0.628134`. Auxiliary known-text distance is `17W/305T/15L`, mean
`0.691933 -> 0.688295`. Decoder instability improves in aggregate `70 -> 67`,
but with seven newly unstable rows and ten recovered rows. Gross repetition
stays `2 -> 2`, with no added gross row.

The surface pattern is mixed. Hadou31 is `3W/28T/0L`; fresh48 is
`4W/43T/1L`; stress60 is `3W/55T/2L`; JSUT24 is `0W/23T/1L`;
SRC4VC-heldout30 is `1W/28T/1L`. The largest expanded144 surface is
`4W/126T/14L` and drives the aggregate content regression despite a small
aggregate decoder-stability gain.

Therefore the fixed source-speaker GRL is not a generic broad-content
improvement over EXP-325, and weight/head/loss/scope/LR/horizon neighbors stay
closed. Its changed audio remains available for later human naturalness and
target-voice comparison; ASR does not select or reject it perceptually.
