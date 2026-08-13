# EXP-078: final decoder on changed utterances

Status: completed; technically rejected; operator hearing deferred

Render `--candidate-kind decoder-final` on EXP-039's twelve changed Common
Voice utterances against EXP-035. Machine screen is corruption/content only.

The candidate produced zero wins, three ties, and nine losses against
control69. Mean source-relative distance regressed from `0.184` to `0.394` and
the maximum from `0.571` to `1.000`; no gross repetition was detected.
