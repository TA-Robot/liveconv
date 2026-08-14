# EXP-159: real-reference adversarial retention on frozen fresh48

Status: completed; technical reject

Render base, control69, and unchanged EXP-158 on 48 disjoint Common Voice
speakers. Reject candidate-added gross repetition and report common non-gross
W/T/L, mean, median, and known-text distance. Audio remains unheard and
unselected.

The candidate added gross repetition on `cv39042955f`, ending in nineteen
consecutive `フ` characters. On 45 common non-gross rows it improved
source-relative W/T/L `12/24/9`, mean `0.319 -> 0.301`, and median
`0.250 -> 0.200`; known-text mean improved `0.610 -> 0.603`. These ordinary-row
gains cannot override the new corruption or establish perceived quality.
