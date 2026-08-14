# EXP-196: X-VC source activity-envelope retention

Status: Prepared listen-now training pilot; unselected

## Goal

Test one retraining mechanism that directly expresses the product rule: X-VC
may change timbre, but it should preserve where speech begins, pauses, and ends
inside the fixed 2.4-second route window.

## Definition of Done

- Commit the loss, focused tests, distinct EXP-196 identity, and both frozen
  evaluation bindings before CUDA work begins.
- Run a finite hard/easy smoke, then exactly one 170-update training pilot.
- Publish external7 and stress60 comparisons to port 8878 from the unchanged
  checkpoint, record the coarse corruption/content screen, and close the lane.
- Keep all outputs unselected until an operator can record `keep`, `continue`,
  or `rejected`.

## One method change

EXP-196 adds a fixed weight-10 L1 loss between per-utterance-normalized absolute
amplitude envelopes of source and converted audio. The envelope uses a 20 ms
window and 10 ms hop at 16 kHz. This is intentionally gain-insensitive and does
not ask the converter to reproduce source timbre.

Everything else is EXP-186: its frozen hard85/easy85 Common Voice 48-speaker
curriculum, control69 LoRA69 initialization, real-reference adversarial
objective, 170 sequential updates, learning rate, AdamW, gradient clipping,
zero condition, and upstream EMA schedule.

## Frozen evaluation contract

- External7: the same seven external evaluation utterances.
- Stress60: the same clean/noise20/pitch+3/silence300/tempo1.2 matrix.
- Gate: candidate-added gross corruption and broad common-stable diagnostic
  movement. Auxiliary ASR/CER is only a content/corruption screen; it cannot
  select naturalness, identity, voice quality, or a winner.

## Not in this experiment

No loss-weight, envelope-window, hop, scope, LR, epoch, or data sweep. No
fresh48, Hadou, JSUT, EXP-024 DTW retry, adjacent source-path scope, product
promotion, or optimization of the obsolete 8.17-second tongue-twister sample.
