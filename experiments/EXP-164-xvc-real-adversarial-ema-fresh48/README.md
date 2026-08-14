# EXP-164: upstream-EMA X-VC on frozen fresh48

Status: completed; technical gate survived

Render base, control69, and unchanged EXP-163 EMA on the same 48 disjoint
Common Voice speakers that rejected the online checkpoint. Reject any new
gross repetition and report common non-gross W/T/L, means, medians, and
known-text distance. Audio remains unheard and unselected.

The EMA candidate added no gross row. On 46 common non-gross rows,
source-relative W/T/L was `12/25/9`, mean improved `0.341 -> 0.328`, and median
improved `0.300 -> 0.235`. Known-text mean improved `0.618 -> 0.607`. This
admits the unchanged Hadou31 gate but does not select perceived quality.
