# EXP-098: cross-target conditioning on 33 unused speakers

Status: completed; rejected for candidate loop

Render EXP-094 on the frozen 33-speaker Common Voice set. Any candidate gross
loop rejects a clean technical pass.

Result: 9 wins / 15 ties / 9 losses, while mean distance regressed from `1.084`
to `1.247`. `cv39045104u` emitted a repeated-`ヘイ` loop with distance `16.667`.
Base/control69 also retain their known loop on another source, but that does not
excuse the candidate-specific failure.
