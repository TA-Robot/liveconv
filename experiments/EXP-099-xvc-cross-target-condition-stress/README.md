# EXP-099: cross-target conditioning on the 60-row stress matrix

Status: completed; narrow noise/tempo effect, generic method rejected

Render EXP-094 on the exact EXP-086 clean/noise20/leading-silence300/tempo1.2/
pitch+3 matrix. Do not tune the condition reference or stress levels from this
result.

Result against control69:

| Condition | Wins / ties / losses | Control mean | Candidate mean | Candidate loops |
|---|---:|---:|---:|---:|
| clean | 1 / 10 / 1 | `0.260` | `0.277` | 0 |
| noise20 | 5 / 6 / 1 | `0.397` | `0.275` | 0 |
| leading-silence300 | 3 / 5 / 4 | `0.288` | `0.354` | 0 |
| tempo1.2 | 3 / 6 / 3 | `0.374` | `0.339` | 0 |
| pitch+3 | 0 / 5 / 7 | `0.279` | `0.402` | 0 |
| macro | 12 / 32 / 16 | `0.320` | `0.329` | 0 |

The fixed condition text (`クリスはヴァンパイア・ナイトを倒した`) was not
transcribed in any candidate output across EXP-094--099, but broad content and
loop gates still fail. Do not sweep the condition reference or strength.
