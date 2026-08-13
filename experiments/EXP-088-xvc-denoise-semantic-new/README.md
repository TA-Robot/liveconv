# EXP-088: denoising semantic on changed utterances

Status: completed; content regression; hearing deferred

Render `--candidate-kind denoise-semantic` on EXP-039's twelve changed Common
Voice utterances. Machine screen is content/corruption only.

Result: 1 win / 6 ties / 5 losses against control69. Mean source-relative
distance regressed from `0.184` to `0.232` and maximum distance from `0.571` to
`1.000`; no gross loop was detected.
