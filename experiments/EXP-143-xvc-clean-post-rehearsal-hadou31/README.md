# EXP-143: clean post-rehearsal on frozen Hadou31

Status: completed; technical stop; hearing deferred

Render base, EXP-035 control69, and EXP-141 on the exact frozen Hadou31. Reject
an adapter-added gross loop, including the recurring `RECITATION324_138`
failure. Auxiliary ASR cannot assess naturalness or target voice.

## Result

All 31 rows and 155 WAV files are on port 8878. Excluding the candidate's one
gross row, candidate versus control was 8/19/3; source-relative mean improved
`0.185 -> 0.148`, median `0.097 -> 0.028`, and known-text mean `0.441 ->
0.420`. Nevertheless `RECITATION324_138` ended by repeating `24` 85 times.
That candidate-added failure triggers the preregistered stop despite the broad
non-loop gain.
