# EXP-158: selective retention with real-reference waveform adversarial loss

Status: ready for one bounded gpu0 lane

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
