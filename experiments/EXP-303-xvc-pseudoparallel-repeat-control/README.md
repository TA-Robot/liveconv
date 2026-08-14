# EXP-303: exposure-matched pseudoparallel repeat control

Status: planned listen-now control; implementation and commit precede CUDA

## Milestone

### Goal

Separate the effect of 37 additional optimizer updates from the effect of 37
previously unused Common Voice utterances in EXP-304. This is a machine-gated
content/corruption control, not an audible-quality winner.

### Definition of Done

- Materialize and validate one 207-row curriculum whose first 170 rows are the
  exact ordered EXP-238 rows and whose last 37 rows repeat the corresponding
  existing Common Voice training examples.
- Keep the complete EXP-238 model, loss, initialization, optimizer,
  discriminator, EMA, and inference contract.
- Pass CPU identity admission and one real finite-gradient CUDA smoke.
- Complete one sequential 207-update gpu0 lane and publish external7 audio on
  port 8878.
- Record an exact EXP-238 join and an exact EXP-304 join once both exist.

### Required work

Implement only the narrow 207-row policy, dynamic output identity, materializer,
focused tests, and ordinary adapter renderer needed for this comparison. Commit
those inputs before CUDA.

### Not in this milestone

No listening claim, promotion, CTC/GRL head, acoustic representation edit,
loss-weight sweep, extra GPU lane, dirty-tree cleanup, or broad rendering before
EXP-304 clears external7.

## Fixed contract

Start from the same control69 LoRA69 adapter as EXP-238. Retain its standard
semantic, speaker, mel, VQ, and real-Amitaro adversarial losses; `1e-4` learning
rate; norm-5 clipping; zero frame condition; discriminator; EMA; normal
quantized source acoustics; and ordinary inference. The sole control change is
one more exposure to 37 already-used Common Voice rows, for 207 total updates.

The 37 repeated rows are paired by training `client_id_sha256` with EXP-304's
second-utterance rows. They keep their original source, same-content control69
target, and assigned real Amitaro reference. Repeats are explicit in the
manifest and must not be presented as new data.

## Gate

External7 is screened only for gross repetition, decoder instability, and
auxiliary source-relative content. All seven rows are joined by
`(source_id, source_sha256)`. EXP-303 supplies the exposure-matched baseline;
it cannot select naturalness, target identity, a keeper, or a product winner.

