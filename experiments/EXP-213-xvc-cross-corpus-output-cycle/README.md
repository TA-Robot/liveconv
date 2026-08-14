# EXP-213: X-VC cross-corpus unpaired output cycle

Status: Completed listen-now training pilot; technical survivor, not selected

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

The real two-row backward smoke matched the detached Whisper path with maximum
hidden-state difference `0.00014424` under the fixed `0.001` tolerance. Both
updates were finite, with 835,584 trainable parameters and 5,366,944,768 peak
allocated GPU bytes.

## Result

Commit `2830fc3` completed 170 updates in 152.44 seconds at 5,875,919,872
peak allocated bytes. The EMA adapter SHA-256 is
`006e369c270fc00eab4f15115935332c90bb138e231799547e97685f6b9597f5`.
The unchanged checkpoint produced 35 external7, 240 fresh48, 155 Hadou31, 300
stress60, and 120 balanced-JSUT24 WAVs on port 8878: 850 total.

On rows stable and non-gross in both control69 and the candidate,
source-relative distance moved external7 `0.256 -> 0.254` (`1/2/2`), fresh48
`0.208 -> 0.214` (`5/25/6`), Hadou31 `0.133 -> 0.091` (`7/16/2`), stress60
`0.221 -> 0.185` (`11/27/7`), and JSUT24 `0.115 -> 0.134` (`2/18/2`).
Noise20 improved `0.271 -> 0.163`; tempo1.2 remained worse at
`0.262 -> 0.280`, and ordinary JSUT basic rows regressed.

Fresh48's two consensus gross rows are the same control69 failures
`cv30615849f` and `cv39087839f`; this candidate added none and removed none.
No other fixed surface contained a consensus gross row. The source-diversity
hypothesis therefore removes EXP-208's candidate-added low-information loop and
retains substantial Hadou/noise signal, but does not solve tempo or broad JSUT
retention. Keep this checkpoint as an unheard technical survivor. It is not a
machine-selected winner and no naturalness, voice-identity, or emotion claim is
made.
