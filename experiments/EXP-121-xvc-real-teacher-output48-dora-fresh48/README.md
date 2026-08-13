# EXP-121: DoRA full-output teacher on frozen fresh48

Status: completed; rejected on two model-specific gross loops

Render base, EXP-035 control69, and EXP-120 once on the exact EXP-112 manifest.
Fresh48 remains evaluation-only. Reject on an adapter-added gross loop or broad
regression on common non-loop rows. Only a survivor may enter cross-condition
and cross-recording-domain screens. Auxiliary ASR is a corruption/content
screen, not a naturalness, target-voice, or winner metric.

Commit `effa73d` produced 144 outputs on port 8878. Besides the naturally
repetitive source shared by all arms, DoRA retained control69's `32.4` repeated
family failure and added the same 12-character repeated-`ぷ` failure seen in
EXP-116. Stop before stress60. Audio remains unheard and unselected.
