# EXP-112: X-VC real-teacher on 48 fresh Common Voice speakers

Status: ready data-generalization screen; no training

## Question

Does the exact EXP-106 checkpoint retain its changed-content and stress signal
on a genuinely fresh set of speakers and sentences, rather than the 64 Common
Voice clips repeatedly reused by earlier method screens?

## Boundary

Select 48 unique client IDs from the already-pinned Common Voice 25.0 Japanese
`test-ja00` metadata, excluding every client represented by the 64 locally
materialized clips. Require at least two up-votes, zero down-votes, and 10--80
normalized text characters. Download from revision
`365b7654cd582e20e8000921ef7b0e32caa1906a`, freeze hashes and durations, then
render base, EXP-035 control69, and EXP-106 once.

This is new evaluation data, not X-VC training data and not ChatGPT browser
audio. Auxiliary ASR may reject loops, empty output, or broad content drift. It
cannot select naturalness, target voice, or a winner. Do not tune the selection
filter or teacher method from individual rows.
