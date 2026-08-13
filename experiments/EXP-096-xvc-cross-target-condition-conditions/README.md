# EXP-096: cross-target conditioning on original conditions

Status: completed; one-row improvement only

Render EXP-094 on the ten EXP-033 condition rows with fixed
`EMOTION100_009` frame condition. This continuity set is secondary to the
balanced EXP-099 stress matrix.

Result: 1 win / 9 ties / 0 losses, moving macro mean `0.153` to `0.146`. The
only changed row was leading silence (`0.400` to `0.333`); the other nine rows
matched control69. This does not establish robustness.
