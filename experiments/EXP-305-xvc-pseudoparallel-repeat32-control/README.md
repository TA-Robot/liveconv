# EXP-305: exposure-matched pseudoparallel repeat32 control

Status: planned listen-now control; implementation commit precedes CUDA

## Milestone

### Goal

Measure the effect of 32 extra optimizer updates without adding source data, so
EXP-306 can isolate the value of genuinely new Common Voice speakers and
content. This is a machine-gated control, not an audible-quality winner.

### Definition of Done

- Preserve the exact ordered 170-row EXP-238 curriculum, then append repeats
  of its first 32 Common Voice rows in their original relative order.
- Run exactly 202 sequential updates with EXP-238's complete model, loss,
  control69 initialization, optimizer, discriminator, EMA, and inference
  contract.
- Use each repeated row's existing same-content control69 teacher and real
  Amitaro discriminator reference without rerendering or reassignment.
- Pass CPU identity admission and one finite-gradient CUDA smoke, then train on
  the single gpu0 lane and publish external7 on port 8878.
- Join external7 exactly against EXP-238 and EXP-306. If EXP-306 passes, render
  this control on the same five broad surfaces as EXP-306.

### Not in this milestone

No loss, condition, target voice, LoRA scope, rank, LR, acoustic
representation, inference, or evaluation-text change. No naturalness, target
identity, keeper, or promotion claim. Do not use auxiliary ASR as a winner.

## One control change

The first 170 rows are byte-identical in ordered identity to EXP-238. The last
32 rows repeat the first 32 `commonvoice-unpaired` rows selected from that
order. Source WAV, same-content teacher WAV, real Amitaro target, and all
training settings are unchanged. Only the sequential horizon grows from 170 to
202 updates.

## Gate

Stop on identity drift, nonfinite loss or gradient, OOM, malformed adapter, a
new external7 gross row, increased decoder instability, or common-stable
content regression against EXP-238. Exact auxiliary ties are not audible ties.
The checkpoint remains unheard and unselected until human listening returns.

## Result

Commit `bd4b3dc` plus output-directory fix `5f4b2ea` materialized the matched
202-row curriculum. The shared real two-row CUDA smoke proved finite losses
and gradients for 835,584 trainable LoRA69 parameters at 4,636,175,872 peak
allocated bytes. Training completed 202 updates in 199.22 seconds at
6,163,570,688 peak bytes and published 35 external7 WAVs. The EMA adapter
SHA-256 is `e71dd1f439cdda03bac6b8cf1422e7d755825700d6dafb29884cf6536c44f503`.

All seven candidate WAVs changed and no consensus gross row was added. Decoder
instability increased from EXP-238's one row to three. On the four rows stable
in EXP-238, EXP-305, and EXP-306, both source-relative and known-text distances
were exact ties (`0W/4T/0L`). The predefined external stop fired. Do not render
EXP-312--316 or infer an audible result from the auxiliary screen.
