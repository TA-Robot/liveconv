# EXP-090: denoising semantic on 31 Hadou windows

Status: completed; mixed positive content diagnostic; hearing deferred

Render `--candidate-kind denoise-semantic-hadou` on 31 evaluation-only Hadou
windows. They are not ChatGPT browser audio and consume only the frozen 2.4
second window.

Result: 7 wins / 22 ties / 2 losses against control69. Mean source-relative
distance improved from `0.210` to `0.185`; neither arm gross-looped. This is an
auxiliary content/corruption result, not a naturalness or voice-quality win.
