# EXP-091: denoising semantic on 33 unused Common Voice speakers

Status: completed; rejected for candidate gross loop

Render `--candidate-kind denoise-semantic-expanded` on the frozen 33-speaker
set. Any gross loop rejects a clean technical pass.

Result: 9 wins / 19 ties / 5 losses row-wise, but mean source-relative distance
regressed from `1.084` to `3.900`. On ASR-empty source `cv41934139u`, the
candidate emitted a repeated-`ぷ` loop with distance `111`. Base and control69
also each looped on another poor source, so this set exposes a broader invalid-
input failure mode; it does not excuse the candidate-specific loop.
