# EXP-082: source-semantic on changed utterances

Status: completed; regression observed; operator hearing deferred

Render `--candidate-kind source-semantic` on EXP-039's twelve changed Common
Voice utterances against EXP-035. Machine screen is corruption/content only.

The candidate produced one win, eight ties, and three losses. Mean
source-relative distance regressed from `0.184` to `0.303`, and the maximum
from `0.571` to `1.571`; no gross repetition was detected.
