# EXP-110: real-teacher semantic on 33 unused Common Voice speakers

Status: completed; loop resilience improved but raw mean is outlier-driven

Render EXP-106 on the frozen 33-speaker Common Voice set. Explicitly inspect the
known low-token-diversity rows and reject adapter-added gross loops; do not fit a
runtime threshold to this evaluation set.

The candidate produced twelve wins, eight ties, and thirteen losses with zero
gross loops versus one control loop. Raw mean improved `1.084 -> 0.620` and
maximum `12.33 -> 2.33`. Diagnostic exclusion of the three already-known loop
sources reverses the mean to `0.514 -> 0.607` and gives 9/8/13, so do not claim
general content improvement from this set. The no-loop result is still useful.
