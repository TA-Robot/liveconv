# EXP-032: X-VC streaming lookahead floor

Status: **completed; operator hearing pending; lookahead sweep closed**.

The 100- and 125-ms endpoint controls reproduced exactly. Auxiliary Whisper
showed gross repetition at 100 ms, shorter repetition at 110 ms, and no gross
repetition at 120/125 ms. The lowest diagnostic candidate is therefore future
120 ms: 260 ms of model context plus measured CUDA compute P50 26.19 ms and P95
32.84 ms across 69 failure-free chunks. Network, playout, conversational
latency, naturalness, route qualification, and product selection remain open.

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
