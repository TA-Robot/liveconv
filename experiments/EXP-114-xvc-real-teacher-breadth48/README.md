# EXP-114: X-VC real-teacher breadth48

Status: method preparation

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
