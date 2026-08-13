# EXP-111: real-teacher semantic multi-speaker stress matrix

Status: completed; all five condition means improved

Render EXP-106 on the exact EXP-086 matrix: twelve changed Common Voice
utterances crossed with clean, noise20, 300 ms leading silence, tempo 1.2x, and
pitch +3 semitones. Report all 60 rows and per-condition source-relative ASR plus
gross repetition. Do not tune condition levels or select sound quality by ASR.

Across 60 rows the candidate produced 27 wins, 18 ties, and 15 losses. Macro
distance improved `0.320 -> 0.254` with zero gross loops. Candidate/control
means were clean `0.211/0.260`, noise `0.340/0.397`, leading silence
`0.216/0.288`, tempo `0.269/0.374`, and pitch `0.233/0.279`. This is the
strongest broad machine content signal so far, but remains silent about
naturalness and target-voice fit.
