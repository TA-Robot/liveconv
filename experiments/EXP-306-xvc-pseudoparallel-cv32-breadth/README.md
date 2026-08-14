# EXP-306: genuine Common Voice 32-speaker pseudoparallel breadth

Status: planned listen-now pilot; implementation commit precedes CUDA

## Milestone

### Goal

Test whether adding genuinely new Japanese speakers and source content improves
the broad robustness of the retained EXP-238 X-VC retraining method. Compare
against EXP-305 at the same 202 updates and with the same ordered real Amitaro
references.

### Definition of Done

- Preserve the exact ordered first 170 EXP-238 rows, then append exactly 32
  Common Voice rows with new source IDs, audio hashes, text, and client IDs.
- Prove all 32 clients are absent from EXP-238's training Common Voice clients
  and from external7, fresh48, stress60, and expanded144.
- Pair the 32 appended rows with the same ordered real Amitaro references used
  by EXP-305's appended repeats. Render only their frozen-control69
  same-content teacher WAVs.
- Keep every model, loss, initialization, optimizer, discriminator, EMA, and
  inference setting identical to EXP-305; pass CPU admission and one real
  finite-gradient CUDA smoke.
- Train one 202-update gpu0 lane and publish external7 on port 8878. If it
  clears both EXP-238 and EXP-305 machine gates, render both 202-update arms on
  fresh48, Hadou31, stress60, JSUT24, and expanded144.

### Not in this milestone

No CTC/GRL head, pseudo-label, speaker loss, acoustic edit, target model, LR,
scope, rank, EMA, or inference change. Do not optimize the local tongue-twister
or describe it as ChatGPT browser audio. Do not infer naturalness, target
identity, a keeper, or a product winner from machine metrics.

## One data change

The source is the historical EXP-055 `commonvoice-local-unused` set. Its raw
Common Voice MP3 hashes remain available, and EXP-168 already materialized the
same items as deterministic 16 kHz, mono, 2.4-second WAVs. One row,
`cv27706775u`, is excluded because its client also owns external7
`cv27706769` and a stress60 base row. The remaining set is exactly 32 rows,
32 clients, and 116.46 seconds of original audio. It has zero client overlap
with the current fixed Common Voice evaluation surfaces or EXP-238 training.

These 32 rows were formerly used by the historical expanded33 evaluation.
They are explicitly retired from future evaluation of EXP-306 and descendants;
historical audio and decisions remain historical evidence. The current broad
evaluation uses the disjoint expanded144 surface instead.

EXP-305 and EXP-306 both append 32 positions after EXP-238. At each appended
position, the real Amitaro target assignment is identical between arms. The
sole comparison variable is repeating an old Common Voice source/teacher tuple
versus supplying the matched-position new source and its newly rendered
same-content control69 teacher.

## Gate

External7 stops EXP-306 on a new gross row, increased decoder instability, or
common-stable source-relative content regression against either EXP-238 or
EXP-305. Exact auxiliary ties may proceed because content diagnostics can be
insensitive to changed audio. Broad rendering stops on added gross corruption,
increased instability, or aggregate common-stable content regression. All
audio remains unheard and unselected until the operator returns.
