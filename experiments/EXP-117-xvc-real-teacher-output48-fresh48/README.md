# EXP-117: X-VC full-output teacher on frozen fresh48

Status: completed; retained but not a clean technical pass

Render base, EXP-035 control69, and EXP-116 once on the exact EXP-112 manifest.
Fresh48 remains evaluation-only. Reject on an adapter-added gross loop or broad
regression across common non-loop rows. Only a survivor may enter stress60;
auxiliary ASR cannot select naturalness or target voice.

Commit `28ddbd0` produced 144 outputs. EXP-116 broadly improved raw mean and
maximum distance and beat base on 17 of 45 common non-loop rows, but added one
short repeated-`ぷ` failure. Stop before stress60. Audio remains unheard and
unselected on port 8878.
