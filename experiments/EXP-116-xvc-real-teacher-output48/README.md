# EXP-116: X-VC full-output teacher on train48

Status: completed; strongest technical signal, not a clean pass

## Question

Can frozen-base full converted-output distillation prevent the waveform loops
left by semantic-only teacher rehearsal?

## Independent variable

Reuse EXP-114's exact train48 pool, 835 standard rows, 209 teacher positions,
1,044 updates, control69 scope, LR, seed, zero frame condition, and Amitaro
target voice. Change only each teacher row's target:

- EXP-114: frozen-base semantic prediction only;
- EXP-116: frozen base converts the real source under the current Amitaro
  reference; that complete waveform becomes the paired target, with standard
  semantic, speaker, mel, and VQ losses.

This teaches the adapter to preserve the base model's complete stable behavior
on varied real speech while the other 835 rows retain target adaptation. It is
not a teacher share, loss-weight, source-count, LR, or scope sweep.

## Stop

Commit the objective and one-row runtime smoke before gpu0. Train once, render
built-in external7 and then frozen fresh48. Stop before stress60 on any added
gross loop or broad common-non-loop regression. Machine metrics cannot select
naturalness, target voice, or a winner.

## Runtime smoke

Commit `2fe309a` passed a one-row real-model LoRA backward smoke: the frozen
teacher target contained 38,400 samples, full composite loss was `161.0455`,
gradient norm was `24.3294`, and peak GPU allocation was 3.30 GiB. Exit status
was zero. No smoke adapter was retained.

## Result

Commit `28ddbd0` completed 1,044 updates in 329.15 seconds at 4.77 GiB peak.
Standard loss moved `144.22 -> 131.10`; full-output teacher loss moved
`161.02 -> 72.94`. External7 had no gross loop and improved control69 from
`0.360` to `0.320` source-relative and `0.399` to `0.359` known-text distance.

EXP-117 then rendered frozen fresh48. Raw mean improved to `0.334`, versus base
`0.414` and control69 `1.001`; maximum distance was `1.25`, versus control's
catastrophic `32.4`. On the 45 rows where no arm tripped repetition, candidate
versus control69 was 10/25/10, mean `0.329` versus `0.319`, median `0.154`
versus `0.250`, and known-text mean `0.586` versus `0.610`. Versus base it was
17/18/10.

One low-quality source added a 12-character repeated-`ぷ` output, so the exact
method does not pass the precommitted no-added-loop stop and stress60 was not
run. Retain it as the strongest unheard technical candidate. The next bounded
method freezes all 47 attention LoRA targets and retains only the 22 converter
feed-forward targets under the same full-output training.
