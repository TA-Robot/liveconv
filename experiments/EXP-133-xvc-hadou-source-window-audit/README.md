# EXP-133: X-VC Hadou source-window coverage audit

Status: admitted; read-only GPU audit

## Question

Did EXP-130 select diverse full utterances while leaving the exact 2.4-second
windows consumed by X-VC narrow or repetitive?

## Method

For every training-only Hadou utterance not used by the authorized Amitaro
target set or frozen Hadou31 evaluation, transcribe deterministic start,
middle, and end 2.4-second windows with the already-pinned auxiliary ASR.
Record normalized character coverage, empty windows, and gross repetitions by
position. This changes no model, checkpoint, route, or evaluation decision.

The next pool may use this audit to select actual model windows rather than
official full-utterance text. A later training run must bind its selection and
still pass the frozen fresh48/Hadou31 corruption gate.

## Boundary and stop

This is a training-data coverage diagnostic, not phoneme ground truth and not
a naturalness, speaker-similarity, or winner metric. Stop after one complete
start/middle/end audit; do not tune ASR decoding or fit selection to evaluation
outputs.
