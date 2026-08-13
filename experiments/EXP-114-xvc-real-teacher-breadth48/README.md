# EXP-114: X-VC real-teacher breadth48

Status: completed; rejected by frozen fresh48

## Question

Did EXP-106 fail fresh48 because its 209 semantic-teacher updates repeatedly
covered only the same twelve real Common Voice sources?

## Independent variable

Keep EXP-106's 835 standard target-conversion updates, 209 teacher-semantic
positions, control69 scope, target voice, frozen-base teacher, semantic-only
loss, LR, seed, and 1,044 total updates. Replace only the twelve real teacher
sources with 48 training-only Common Voice speakers, cycling the 209 teacher
positions across them (17 speakers receive five exposures and 31 receive four).

The training pool excludes all original 64 local clips and every speaker in
EXP-112 fresh48. EXP-112 remains evaluation-only. This is one source-diversity
point, not a donor-count sweep; do not add 24/96 variants or tune the 20% share.

## Stop

Train once on gpu0. The built-in external seven-row render is only an early
screen. Next render frozen fresh48; stop on adapter-added gross repetition or a
broad non-loop regression. Only a surviving checkpoint may enter the balanced
stress screen. Machine metrics cannot select naturalness or target voice.

## Frozen input

Commit `07d7a0d` selected and materialized 48 unique training speakers. The
ignored manifest SHA-256 is
`cd093f43c52f79294cd5c5d9d17b8932845cedd03d17530885eff1711c2a8eab`.
Focused tests passed 53 cases. Exact CPU admission confirmed 835 standard plus
209 teacher-semantic roles, 48 teacher sources, 87 target texts, and 1,044
updates without CUDA.

## Result

Commit `23f9d6b` completed 1,044 updates in 304.05 seconds at 4.77 GiB
peak. Standard-role loss moved `144.22 -> 134.83`; teacher-semantic loss moved
`0.0079 -> 1.3302`. The built-in external seven-row mean regressed control69
from `0.360` to `0.430` without gross repetition.

EXP-115 then rendered frozen fresh48. The candidate added two failures beyond
the naturally repetitive source and control69's existing loop, for four gross
repetition rows total. Its raw mean was `1.463`. On the 44 rows where no arm
looped, candidate versus control69 was mean `0.324` versus `0.319`, median
`0.304` versus `0.225`, and W/T/L `10/22/12`.

## Decision

Reject breadth48 as a generic method and stop before the stress screen. The
teacher-source count, share, and weight are closed. The larger source pool did
not solve output instability; the next method must change what is held stable,
not add another count point.
