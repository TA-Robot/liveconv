# EXP-168: upstream-EMA X-VC on frozen expanded33

Status: completed; posthoc technical gate survived

After EXP-163 survived its preregistered gates, render the exact unchanged EMA
adapter on the already-frozen 33 additional Common Voice speakers and
utterances from EXP-055. This set previously exposed ASR-empty and gross-loop
sources that aggregate means hid. It is evaluation-only and was not used to
choose EMA or its checkpoint.

Reject any candidate-added gross corruption. Report raw and common non-gross
W/T/L, means, and medians against control69. This posthoc expansion strengthens
the future listening batch but cannot turn the technical survivor into a keep,
naturalness winner, target-voice winner, route decision, or promotion.

The EMA candidate added no gross row, while base and control69 each gross-looped
on `cv41748688u`. Raw source-relative mean improved `1.084 -> 0.596`, known-text
mean `1.738 -> 1.078`, and maximum source-relative distance `12.33 -> 2.83`.
On the 32 rows where neither control nor candidate was gross, source-relative
W/T/L was `4/21/7`, mean improved `0.732 -> 0.526`, and median
`0.600 -> 0.333`; known-text W/T/L was `3/19/10`, mean regressed
`0.848 -> 0.899`, and median improved slightly `0.833 -> 0.824`.

This mixed posthoc evidence strengthens corruption robustness but does not
override the external7 regression or select perceived quality. Keep the exact
candidate unchanged and do not tune it on expanded33.
