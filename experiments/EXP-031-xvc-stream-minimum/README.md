# EXP-031: X-VC minimum useful streaming lookahead

Status: **runner prepared; GPU listen-now not yet run**.

EXP-030 found gross repetition at 100 ms future context and no gross repetition
at 200, 250, or 300 ms for the epoch-8 human87 adapter on the actual 8.17-second
input. This bounded diagnostic bisects that boundary at 125, 150, 175, and 200
ms. The 200-ms output must reproduce EXP-030 exactly.

All other source, adapter, reference, conditioning, chunk/current/smoothing,
output, and auxiliary Whisper settings remain fixed. Context totals for the
four arms are 265, 290, 315, and 340 ms, all below the product's 400-ms added
latency P95 target before network/playout accounting.

Done means four candidates appear on fixed port 8878 and receive the same
gross-repetition diagnostic. The lowest non-repeating arm becomes the latency
candidate for operator hearing; this does not promote or route-qualify it.

Stop on inherited identity failure, mismatch of the 200-ms control, malformed
audio, CUDA failure, or partial publication. Do not add another point after
seeing the four results.
