# EXP-087: clean-noise denoising semantic consistency

Status: ready method pilot; operator hearing deferred

Alternate exactly 522 clean and 522 deterministic noise20 generated-source
updates. The model receives the current clean/noisy waveform and semantic
tokens, while semantic MSE always targets the corresponding clean generated
source hidden state. Target waveform and target speaker remain Amitaro.
EXP-035 data identities, control69, loss weights, LR `1e-4`, seed, zero target
condition, and 1,044 updates remain fixed.

This is one denoising objective, not an audio-condition level sweep. It follows
EXP-086's broad noise failure and differs from rejected source-only augmentation:
the semantic target explicitly stays clean and no time-warped condition is used.

Done: commit exact tensor binding and schedule; train once; publish seven
external rows plus EXP-088--092. Reject gross loops or broad content regression.
Do not claim naturalness, target voice, or a winner from machine ASR.

Command: `run_role_mix.py --training-policy denoise-semantic --lora-scope control69`
with the EXP-081 paths and `exp087-denoise-semantic-v1` work/listener slug.
