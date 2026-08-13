# EXP-094: X-VC cross-utterance target-frame conditioning

Status: completed; rejected as generic conditioning; hearing deferred

## Question

Does replacing the always-zero X-VC frame-condition waveform with a
same-Amitaro, different-utterance reference improve stability or later audible
quality without copying unrelated reference content?

## Method

For each of the 87 target utterances, bind `target_wav_cond` to the next target
utterance in the frozen inventory, wrapping at the end. The condition therefore
has the desired speaker but never the supervised target content. At inference,
use fixed `EMOTION100_009` as the frame condition and `EMOTION100_003` as the
speaker/target reference. Keep the EXP-035 generated sources and targets,
target-hidden semantic supervision, control69 LoRA scope, standard loss
weights, LR `1e-4`, seed, clean inputs, and 1,044 updates fixed.

## Definition of Done

- Commit the exact 87-row rotation, conditioned inference helper, and all
  frozen render policies before GPU admission.
- Train exactly once and publish EXP-094--099 on port 8878.
- Reject gross loops, empty output, broad content regression, or evidence that
  the unrelated condition text is copied. Machine ASR cannot decide
  naturalness, target voice, or a winner.

## Not in this experiment

No zero/nonzero ratio, reference-ID, condition-strength, LR, rank, scope, or
data sweep. No retry of human87 horizon or EXP-024 DTW.

## Result

Training completed 1,044 updates in 262.04 seconds at 5.13 GB peak; loss moved
from `141.10` to `123.42`. The seven external rows were 2 wins / 4 ties / 1
loss, but mean source-relative auxiliary ASR distance regressed from `0.360` to
`0.410`. No gross loop appeared there. EXP-095--099 found condition-specific
benefit but broad regressions and one expanded-speaker loop, so the method and
all adjacent condition reference/strength/ratio sweeps are closed.
