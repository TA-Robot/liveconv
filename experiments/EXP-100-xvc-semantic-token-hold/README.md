# EXP-100: X-VC semantic-token hold training

Status: ready method pilot; operator hearing deferred

Alternate exactly 522 clean-token and 522 held-token generated-source updates.
For held rows, each contiguous five-frame block in the 30-frame semantic-token
sequence repeats its first token; the clean source waveform is unchanged. This
forces the existing acoustic path to carry content when the semantic stream is
locally collapsed. Target waveform, speaker and target-hidden semantic losses,
EXP-035 data identities, control69, LR `1e-4`, seed, zero frame condition, and
1,044 updates remain fixed.

Definition of Done: commit the exact token operation, schedule, tests, and all
EXP-101--105 render policies before one GPU run. Publish 7 + 12 + 10 + 31 + 33
+ 60 frozen rows. Reject adapter-added loops or broad content regression. Do
not sweep block size or corruption ratio and do not claim naturalness, target
voice, or a winner from machine ASR.
