# EXP-105: semantic-token hold on the 60-row stress matrix

Status: completed; balanced robustness rejected

Render EXP-100 on the exact EXP-086 clean/noise20/leading-silence300/tempo1.2/
pitch+3 matrix. Do not tune block size, corruption ratio, or stress levels from
this result.

Across 60 rows the candidate produced 14 wins, 21 ties, and 25 losses, with
macro distance regressing `0.320 -> 0.362`. Per-condition candidate/control
means were clean `0.384/0.260`, noise `0.337/0.397`, leading silence
`0.319/0.288`, tempo `0.304/0.374`, and pitch `0.464/0.279`. Noise and tempo
signals do not outweigh clean, silence, pitch, changed-content, and expanded-set
failures. No candidate stress row looped.
