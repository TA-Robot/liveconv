# EXP-116: X-VC full-output teacher on train48

Status: admitted for one gpu0 training run

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
