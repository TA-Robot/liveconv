# EXP-148: hard-negative curriculum on frozen Hadou31

Status: completed; mandatory stop failed

Render base, control69, and EXP-146 on the exact frozen Hadou31. These rows are
disjoint from the Hadou training-only windows used to construct EXP-146. The
`RECITATION324_138` numeric repetition remains a mandatory stop. Machine ASR
cannot assess naturalness or target voice.

The candidate added one gross row: `RECITATION324_138` repeated `24` through a
long numeric tail. Excluding that row, it improved source-relative mean
`0.185 -> 0.153`, median `0.097 -> 0.066`, and scored `9/18/3` against
control69. The local gain does not override the predeclared added-loop stop.
