# EXP-092: denoising semantic on the 60-row stress matrix

Status: completed; narrow denoising effect, generic method rejected

Render `--candidate-kind denoise-semantic-stress` on EXP-086's exact clean,
noise20, leading-silence300, tempo1.2, and pitch+3 matrix. Compare twelve rows
per condition. Do not tune condition levels from this result.

Result against control69:

| Condition | Wins / ties / losses | Control mean | Candidate mean | Candidate loops |
|---|---:|---:|---:|---:|
| clean | 4 / 4 / 4 | `0.260` | `0.226` | 0 |
| noise20 | 6 / 3 / 3 | `0.397` | `0.258` | 0 |
| leading-silence300 | 4 / 6 / 2 | `0.288` | `0.272` | 0 |
| tempo1.2 | 6 / 3 / 3 | `0.374` | `0.287` | 0 |
| pitch+3 | 2 / 4 / 6 | `0.279` | `0.512` | 0 |
| macro | 22 / 20 / 18 | `0.320` | `0.311` | 0 |

The noise hypothesis worked on this fixed matrix, but pitch regressed and
EXP-091 found a severe candidate loop. Do not sweep condition levels, noise
ratio, or SNR. Retain all audio for later hearing without a quality claim.
