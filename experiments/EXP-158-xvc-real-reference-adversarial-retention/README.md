# EXP-158: selective retention with real-reference waveform adversarial loss

Status: rejected after frozen fresh48

## Goal

Test whether X-VC's pretrained waveform discriminator and feature-matching
objective suppress gross repetition while EXP-150's selective generative
targets retain control69's normal content behavior. The local tongue-twister is
excluded from training and every gate.

## One method change

Keep EXP-150's exact 170-row order, 85 base-teacher repair targets, 85 control69
retention targets, control69 LoRA69 initialization and trainable scope, LR
`1e-4`, norm-5 clip, target identities, and zero frame condition. Change only
the objective by adding the pretrained upstream waveform discriminator and its
adversarial plus feature-matching loss.

The two target roles are deliberately separate:

- X-VC's composite generative loss still sees each committed repair or
  retention waveform, preserving the causal comparison with EXP-150.
- The discriminator's real side sees the authorized original Amitaro target
  recording for that row. Generated teacher audio is never labeled real.

EXP-064 previously produced no new gross loop across 60 condition rows and
slightly improved Hadou content diagnostics, but did not establish audible
quality. This experiment tests that objective once under the later selective
retention policy; it is not an adversarial weight or schedule sweep.

## Definition of done and stop

Train once and publish external7. An unchanged survivor proceeds through frozen
fresh48, Hadou31, and stress60 (clean, noise, leading silence, tempo, and F0).
Only survival of all four opens untouched balanced JSUT24. Reject a
candidate-added gross corruption or broad common-row regression. Auxiliary ASR
cannot select naturalness, voice identity, a keeper, or promotion.

Do not tune discriminator weights, update ratio, LR, loss weights, curriculum
ratio, retention blend, threshold, LoRA scope, or update count.

## Result

Commit `ca91011` completed 170 updates in 149.25 seconds at 5.47 GiB peak.
Total loss moved `298.40 -> 102.46`; generator, adversarial, feature-matching,
and discriminator components were finite. External7 added no gross repetition,
with source-relative mean `0.360 -> 0.356` and known-text mean
`0.399 -> 0.423`.

Frozen fresh48 added one gross failure beyond control69. On `cv39042955f`, the
source transcription `あ、すいません。エレ、ネクザー` became a phrase ending
in nineteen consecutive `フ` characters. The candidate is rejected even though
the 45 common non-gross rows improved source-relative W/T/L `12/24/9`, mean
`0.319 -> 0.301`, and median `0.250 -> 0.200`. This objective improved ordinary
content diagnostics but did not provide a collapse safety mechanism. Do not
tune adversarial weights or run Hadou31, stress60, or JSUT24 for this checkpoint.
