# EXP-142: clean post-rehearsal on frozen fresh48

Status: completed; technical regression; hearing deferred

Render base, EXP-035 control69, and EXP-141 on the exact frozen fresh48. Reject
an adapter-added gross loop and report common-non-loop W/T/L, mean, median, and
known-text distance. All audio remains unheard and unselected.

## Result

All 48 rows and 240 WAV files are on port 8878. The candidate had the same two
gross rows as control69: one naturally repeated source row shared by every arm
and the `cv30615849f` 32.4-distance collapse. Unlike EXP-138, it did not add the
109-character vowel failure. Excluding every gross row, candidate versus
control was 9/22/15; source-relative mean regressed `0.341 -> 0.352`, median
`0.275 -> 0.321`, while known-text mean was essentially tied (`0.618 ->
0.617`). This is not a keeper or promotion decision.
