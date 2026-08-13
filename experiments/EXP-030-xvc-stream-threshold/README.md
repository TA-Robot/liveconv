# EXP-030: X-VC minimum-lookahead threshold

Status: **v1 technical stop; corrected v2 completed and superseded by EXP-032**.

After a fixed discarded warmup separated the one-time cold path, both endpoint
controls reproduced exactly. Future 100 ms repeated; 200/250/300 ms did not in
the auxiliary screen.

EXP-029 removed the epoch-8 actual-input repetition when future context moved
from 100 ms to 300 or 500 ms. This follow-up brackets the smallest useful
lookahead with 100, 200, 250, and 300 ms while preserving every other input,
model, and streaming parameter. The 100- and 300-ms outputs must reproduce
EXP-029 exactly before publication.

The important boundary is 250 ms: current 120 + smoothing 20 + future 250 is
390 ms of model-induced context, below the product P95 target of 400 ms before
network/playout accounting. The 300-ms arm totals 440 ms and is diagnostic only.

Done means four explicit candidates appear on fixed port 8878 and receive the
same auxiliary Whisper gross-repetition screen. If 250 ms removes repetition,
it becomes the lowest bounded route candidate for operator hearing. If only
300 ms works, retraining with position-aware windows is preferred over shipping
excess lookahead. Whisper remains diagnostic, not a quality verdict.

Stop on inherited identity failure, mismatch of either control output,
malformed audio, CUDA failure, or partial publication. Do not add another
lookahead value after seeing output.

Repair note: `v1` stopped before listener publication because its first arm was
future 100 ms and therefore took the model's one-time cold CUDA path, while the
EXP-029 future-100 control was the second inference. The later future-300 arm
still reproduced EXP-029 exactly. `v2` adds one fixed, discarded future-100
warmup before every measured arm; it changes no published comparison value.
