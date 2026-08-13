# EXP-139: near-one-pass teacher breadth on frozen fresh48

Status: completed; rejected on one candidate-only gross loop

Render base, EXP-035 control69, and EXP-138 on the exact frozen fresh48. Reject
an adapter-added gross loop and report common-non-loop W/T/L, mean, median, and
known-text distance. All rows remain unheard and unselected.

The candidate added a 109-character repeated-`ぃ` failure on `cv39028774f`,
retained control69's repeated-`家族` collapse, and matched the naturally
repetitive input shared by all arms. On the 45 common non-loop rows it improved
control69 W/T/L `15/24/6`, source-relative mean `0.326 -> 0.289`, median
`0.250 -> 0.200`, and known-text mean `0.610 -> 0.594`. The broad signal does
not compensate for a new gross failure.
