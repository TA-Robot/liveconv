# EXP-166: upstream-EMA X-VC on frozen stress60

Status: completed; technical gate survived

Render unchanged EXP-163 EMA across twelve utterances under clean, noise20,
300 ms leading silence, tempo 1.2, and pitch +3 semitones. Report each
condition and macro; this is a corruption/content gate, not automatic voice
quality selection.

The candidate added no gross row. Macro source-relative mean tied control69
`0.31959 -> 0.32000`; known-text improved `0.6726 -> 0.6588`. Source-relative
means improved for noise20 (`0.397 -> 0.377`) and leading silence
(`0.288 -> 0.251`), while clean (`0.260 -> 0.298`), pitch
(`0.279 -> 0.288`), and tempo (`0.374 -> 0.385`) worsened. Preserve every
condition for hearing; none is a machine quality winner.
