# EXP-136: model-window teacher on frozen Hadou31

Status: completed; adapter-added heldout loop, reject generic keeper

Render base, EXP-035 control69, and EXP-134 once on the exact frozen Hadou31.
All 31 IDs were excluded before EXP-133 source-window audit and selection.
Reject an adapter-added gross loop. Auxiliary ASR does not measure naturalness
or target voice.

`RECITATION324_138` alone produced an adapter-added gross loop: the output
repeated `三・四` 53 times. Across the remaining 30 rows, candidate versus
control was 6/21/3, source-relative mean `0.160` versus `0.185`, median `0.066`
versus `0.097`, and known-text mean `0.421` versus `0.441`. This is useful
non-loop evidence but fails the preregistered safety stop.
