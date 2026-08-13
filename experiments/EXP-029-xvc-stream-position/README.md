# EXP-029: X-VC e8 streaming-position diagnostic

Status: **completed; superseded by EXP-032**.

Future 0/100 ms repeated in the auxiliary transcript, while 300/500 ms did not.
This supported the streaming-position hypothesis and justified a bounded lower
lookahead bracket, not shipping the high-lookahead arms.

EXP-027's epoch-8 adapter repeated phrases under upstream streaming, while the
same adapter did not repeat under EXP-028 full-utterance inference. The human87
training windows place complete aligned speech at sample zero and right-pad the
remainder. Upstream streaming emits the 120-ms current region near the end of a
2.4-second window. Longer adaptation may therefore have learned a position
bias that is harmless offline and destructive at the streaming extraction
position.

This diagnostic holds the actual source, epoch-8 adapter, reference, zero frame
condition, 2400-ms window, 120-ms current, and 20-ms smoothing fixed. It changes
only future context: 0, 100, 300, or 500 ms. That moves the current-region start
from 2260 to 1760 ms. The 100-ms output must reproduce EXP-027 exactly before
publication.

Done means four explicit e8 future-context candidates appear on
`http://127.0.0.1:8878/`, with CUDA-synchronized chunk timing and the same
auxiliary Whisper diagnostic. A reduction in repetition as the current region
moves earlier supports position augmentation as the next training variable. A
flat failure redirects away from that hypothesis. Operator hearing remains the
quality decision.

This sweep is diagnostic only: 300/500-ms lookahead is not assumed to meet the
product latency target. Do not promote a high-lookahead arm.
