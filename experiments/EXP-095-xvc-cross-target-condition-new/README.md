# EXP-095: cross-target conditioning on changed utterances

Status: completed; content regression; hearing deferred

Render EXP-094 on the twelve EXP-039 changed Common Voice utterances with fixed
`EMOTION100_009` frame condition. Machine screening is content/corruption only.

Result: 1 win / 5 ties / 6 losses against control69; mean distance regressed
from `0.184` to `0.306`, maximum from `0.571` to `1.000`, with no gross loop.
