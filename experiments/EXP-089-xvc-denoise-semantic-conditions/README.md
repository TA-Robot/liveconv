# EXP-089: denoising semantic on the original condition set

Status: completed; positive but underpowered continuity diagnostic

Render `--candidate-kind denoise-semantic` on EXP-033's ten frozen condition
rows. This preserves continuity with earlier methods; EXP-092 is the stronger
multi-speaker limitation test.

Result: 3 wins / 7 ties / 0 losses and mean source-relative distance improved
from `0.153` to `0.075`, with no gross loop. Noise and leading silence contain
only one row each here, so this result does not authorize a robustness claim;
the balanced EXP-092 matrix is the relevant limitation screen.
