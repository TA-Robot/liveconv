# EXP-152: selective retention on frozen Hadou31

Status: completed; mandatory stop failed

Render base, control69, and unchanged EXP-150 on the exact frozen Hadou31,
which is disjoint from the training-only Hadou windows. The
`RECITATION324_138` numeric repetition is a mandatory stop. Machine ASR cannot
assess naturalness or target voice.

The candidate added one gross row on `RECITATION324_138`, repeating `9` for a
66-character run. Excluding it, source-relative W/T/L was `5/23/2`, mean
improved `0.185 -> 0.170`, and median improved `0.097 -> 0.080`. The local
non-gross gain does not override the added-loop stop.
