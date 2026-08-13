# EXP-028: X-VC actual-input offline control

Status: **completed; diagnostic archived**.

The same epoch-8/12 states did not show gross auxiliary-ASR repetition in
full-utterance offline inference. Longer training alone is therefore not a
global-collapse explanation; the failure interacts with streaming position or
windowing.

EXP-027 showed gross repeated phrases in auxiliary Whisper transcripts for the
8- and 12-epoch upstream-stream outputs. This bounded follow-up asks whether the
same base/epoch4/epoch8/epoch12 model states also repeat on the same actual
8.17-second input under full-utterance offline inference.

Exactly one variable changes from EXP-027: inference mode, upstream streaming
window versus full-utterance offline. Source, target reference, zero frame
condition, model/adapters, output duration, and four labels remain fixed.

Done means one four-way offline control appears on
`http://127.0.0.1:8878/`. After publication, run the same pinned auxiliary
Whisper-small diagnostic. Repetition in both modes redirects away from longer
human87 training; repetition only in streaming redirects to window/condition
diagnostics. Whisper is not a naturalness or selection oracle; the operator
still hears the audio.

Stop before publication on any inherited EXP-027 identity failure, malformed
or nonfinite output, output-length drift, CUDA failure, or a partial arm set.
Do not change training or the actual input.

Not in scope: new training, another window, automatic winner selection, route
qualification, Extension playback, or product readiness.
