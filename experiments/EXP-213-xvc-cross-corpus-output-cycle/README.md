# EXP-213: X-VC cross-corpus unpaired output cycle

Status: Admitted listen-now training pilot; not selected

## Goal

Test the generalization explanation left by EXP-208--212. The final-waveform
content cycle improved Hadou and broad stress rows, but Hadou-only source
training still added a low-information collapse on an unknown Common Voice
speaker. Replace that narrow source distribution with one fixed, training-only
cross-corpus curriculum before designing another loss.

The invalidated 8.17-second `隣の客はよく柿食う客だ` recording is neither a
training target nor an evaluation priority. It is not actual ChatGPT browser
audio. Success means more stable behavior over disjoint speakers, ordinary
Japanese categories, and controlled acoustic conditions, not recovery of that
single phrase.

## One method change

Change only EXP-208's 170-row source-side distribution:

- all 48 frozen training-only Common Voice speakers from EXP-186;
- all 85 JSUT training sentences from EXP-169, which already exclude the
  frozen JSUT24 evaluation IDs and span basic, counters, loanwords,
  onomatopoeia, and travel;
- all three frozen JVS training speakers from EXP-138;
- 34 Hadou rows spread over the complete EXP-203 predecessor to fill 170.

Order the fixed rows by `sha256(domain:teacher_id)` so sequential SGD sees a
mixed schedule rather than four corpus blocks. Keep the exact ordered multiset
of 170 unrelated Amitaro target windows, final-WAV weight-1000 frozen-Whisper
content cycle, target-speaker loss, real-wave adversarial/feature objective,
control69 LoRA69 initialization, 170 updates, LR, optimizer, clip, zero frame
condition, and upstream EMA.

This is one fixed data/generalization architecture, not a source-count, ratio,
weight, frontend, scope, LR, or horizon sweep.

## Definition of Done

- Bind every source to its frozen manifest and materialized WAV identity, prove
  the `48 + 85 + 3 + 34 = 170` composition, and admit all rows without CUDA.
- Commit the materializer, runner policy, tests, plan, and
  external7/fresh48/Hadou31/stress60/JSUT24 identities before the GPU run.
- Run one real two-row finite backward smoke, then one 170-update CUDA pilot.
- Publish the unchanged EMA checkpoint on all five surfaces to port 8878.
- Record candidate-added consensus corruption and cross-arm common-stable
  auxiliary content movement only. Do not infer naturalness, voice identity,
  emotion, or a perceptual winner.

## Stop conditions

Stop on source/evaluation overlap, missing or changed source identity, frontend
mismatch, nonfinite loss/gradient, OOM, malformed adapter, candidate-added gross
corruption, or broad common-stable content regression. Do not tune corpus
ratios, counts, schedule, target pairing, loss weight, frontend, scope, LR,
horizon, or EMA after this point.

If this still collapses on low-information speech, close data mixing as the
primary explanation and move to an explicit anti-collapse mechanism. If it
retains broad stability without added corruption, leave it unheard and ready
for operator comparison; machine ASR is not a quality selector.

## Admission

The materialized curriculum SHA-256 is
`44d2ba9c03d44437711c7b7d359f519672dca32696ba73b3fcd178b07024b931`.
It contains 48 Common Voice, 85 JSUT, three JVS, and 34 Hadou source windows,
paired with the unchanged 170-target Amitaro multiset. Focused policy,
materializer, runner, and render tests passed `97/97`; exact CPU admission
reported 170 training rows and seven external evaluation rows.
