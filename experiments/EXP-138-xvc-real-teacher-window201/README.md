# EXP-138: X-VC near-one-pass real-window teacher breadth

Status: prepared; awaiting bound manifest and one gpu0 lane

## Goal

Test whether the cross-corpus full-output method needs substantially more
distinct real source windows, rather than four to five repetitions of 48
sources, to preserve broad gains without heldout repetition collapse.

## One change

Keep 209 full-output teacher positions, 835 standard positions, 1,044 updates,
objective, target, control69 LoRA, LR, seed, and zero frame condition fixed.
Expand the real teacher pool from 48 to 201: all 48 disjoint Common Voice
teachers, all 150 quality-admitted training-only Hadou utterances exactly once
as balanced start/middle/end 2.4-second windows, and JVS3. The 209 positions
therefore expose all 201 sources once and only eight a second time.

No EXP-135/136 evaluation row or output participates in selection. This is a
data-breadth point, not a threshold fit, teacher-share sweep, or longer horizon.

## Definition of done and stop

Bind and commit the pool, pass one backward smoke, train once, then render the
same external7, frozen fresh48, and frozen Hadou31. Reject on an adapter-added
gross loop or broad common-non-loop regression. Machine ASR cannot select
naturalness, target identity, or a winner.
