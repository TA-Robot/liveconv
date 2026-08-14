# EXP-147: hard-negative curriculum on frozen fresh48

Status: completed; candidate rejected

Render base, control69, and EXP-146 on the exact 48 disjoint Common Voice
speakers. Reject candidate-added gross repetition and report common-non-gross
W/T/L, mean, median, and known-text distance. Audio remains unheard and
unselected.

The candidate and control69 shared the natural repeated source and the same
`cv30615849f` catastrophic family loop; no new fresh48 gross row was added. On
the 46 common non-gross rows, source-relative W/T/L was `10/20/16`, mean
regressed `0.341 -> 0.402`, and median regressed `0.275 -> 0.326`. Known-text
mean slightly regressed `0.618 -> 0.625`. This is broad content-regression
evidence, not a perceptual judgment.
