# EXP-304: Common Voice second-utterance pseudoparallel breadth

Status: planned listen-now pilot; implementation and commit precede CUDA

## Milestone

### Goal

Test whether adding a second, different utterance from 37 already-authorized
Common Voice training speakers improves the broad robustness of EXP-238. The
question is utterance/content breadth, not speaker-count breadth and not an
audible winner.

### Definition of Done

- Materialize a 207-row curriculum with the exact ordered EXP-238 first 170
  rows followed by 37 unused exposure-2 Common Voice rows.
- Prove all 37 additions have distinct source IDs, WAV hashes, and nonempty
  transcripts; are disjoint from the fixed evaluation clients; and have their
  existing same-content control69 teacher outputs and authorized real target
  assignment.
- Keep every model, loss, optimizer, and inference choice fixed against
  EXP-303; pass CPU admission and one real finite-gradient CUDA smoke.
- Complete one 207-update gpu0 lane, publish external7 on port 8878, and join it
  exactly against EXP-238 and EXP-303.
- If the external gate passes, render the unchanged adapter on fresh48,
  Hadou31, stress60, JSUT24, and expanded144 and machine-screen only for
  content/corruption.

### Required work

Reuse the already-rendered 37 control69 same-content teacher WAVs. Implement the
smallest materialization, runner policy, adapter identity, renderer policy, and
focused tests. Commit before CUDA; keep gpu0 sequential.

### Not in this milestone

No new CTC/GRL classifier, ASR pseudo-label, target speaker, acoustic latent,
loss, LR, LoRA scope, rank, EMA, or inference change. Do not generate a large
Hadou/JSUT target corpus until this cheap breadth probe supplies evidence. Do
not infer naturalness or choose a keeper from machine metrics.

## One change

EXP-238 used one utterance from each of 48 Common Voice training speakers. The
authorized EXP-186 pool contains 37 additional exposure-2 utterances from 37 of
those same speakers. All 37 have different source IDs, WAV hashes, and text,
total `88.8` seconds, and zero client overlap with fresh48 or expanded144.
Their same-content control69 outputs already exist 37/37.

EXP-304 appends those 37 examples after the exact EXP-238 order. EXP-303 appends
37 matched repeats instead, so both arms receive 207 sequential updates. Their
model/loss/init/optimizer/EMA/inference contracts are identical. This makes the
new utterance tuples, rather than the additional horizon, the comparison.

## Gate

Run EXP-303 then EXP-304 on the one gpu0 lane. External7 stops EXP-304 on a new
gross row, decoder-instability increase against EXP-238, or common-stable
content regression against both EXP-238 and EXP-303. Exact machine ties are not
an audible tie and may proceed to broad rendering because the diagnostic can be
insensitive to changed audio. Broad rendering stops on added gross corruption,
increased instability, or aggregate common-stable content regression. Audio
remains unheard and unselected until the operator returns.

If this bounded probe fails, close repetition-count and 37-row ordering
neighbors. The next data method may build genuinely larger Hadou or JSUT
same-content targets; it must not optimize the local tongue-twister or claim it
is ChatGPT browser audio.
