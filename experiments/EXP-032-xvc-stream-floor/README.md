# EXP-032: X-VC streaming lookahead floor

Status: **runner prepared; final diagnostic GPU lane not yet run**.

EXP-031 found no gross auxiliary-ASR repetition at 125, 150, 175, or 200 ms,
while EXP-030 reproduced the gross repetition at 100 ms. This final bounded
diagnostic tests 100, 110, 120, and 125 ms. The endpoint controls must reproduce
their earlier WAV hashes exactly.

All arms are below 265 ms of model context (`120 current + 20 smoothing +
future`) before compute/network/playout. Done means four candidates appear on
fixed port 8878, receive the same auxiliary Whisper screen, and the streaming
lookahead sweep stops. The lowest non-repeating arm is only a candidate for
operator hearing; it is not automatically selected or route-qualified.

Stop on any inherited identity or control mismatch, malformed audio, CUDA
failure, or partial publication. Do not open another lookahead experiment after
this result.
