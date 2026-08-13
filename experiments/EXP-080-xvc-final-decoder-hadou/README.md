# EXP-080: final decoder on 31 Hadou sentences

Status: completed; technically rejected; operator hearing deferred

Render `--candidate-kind decoder-final-hadou` on the frozen 31 Hadou windows.
They are evaluation-only and are not ChatGPT browser audio.

The candidate produced three wins, eleven ties, and seventeen losses against
control69. Mean source-relative distance regressed from `0.210` to `0.305`.
No gross repetition was detected. These 2.4-second windows are a broad
content/corruption screen, not full-sentence CER or a naturalness judgment.
