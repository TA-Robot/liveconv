# EXP-325/326: two-utterance SRC4VC source-speaker adversary

Status: planned; no private data acquisition or CUDA authorized yet

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
- Run teacher render, EXP-325, and EXP-326 sequentially on gpu0. Publish both
  external7 comparisons on port 8878 and apply content/corruption screening.

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

Run both matched arms through external7 even if the new substrate differs from
EXP-238; otherwise the adversary cannot be isolated. Stop before broad render
unless EXP-326 adds no gross corruption, adds no decoder instability, and does
not regress common-stable source-relative content versus EXP-325. A broad
render is additionally ineligible if both arms are materially less stable than
EXP-238. Passing only authorizes the fixed fresh48, Hadou31, stress60, JSUT24,
expanded144, and SRC4VC-heldout30 surfaces. Machine ASR remains a corruption
and content diagnostic, not perceptual selection.
