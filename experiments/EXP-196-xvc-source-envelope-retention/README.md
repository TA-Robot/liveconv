# EXP-196: X-VC source activity-envelope retention

Status: Completed listen-now training pilot; mixed/rejected; unselected

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

## Result

The two-row smoke was finite. The one full run completed 170 updates in 129.4
seconds at 6,163,570,688 peak allocated GPU bytes. Total loss moved from
`300.93` to `142.58`; the activity-envelope distance itself moved from `0.253`
to `0.293`, so the auxiliary objective did not decrease over the ordered
trajectory.

EXP-196 published 35 external7 WAVs and EXP-197 published 300 stress60 WAVs.
No arm added a consensus gross corruption row. On the five external7 rows
stable in both control and candidate decodes, source-relative distance moved
`0.256 -> 0.191` and known-text distance `0.371 -> 0.254`, both with W/T/L
`3/1/1`. The broader stress result did not support the timing hypothesis: on
45 common-stable rows source-relative distance moved `0.223 -> 0.233`
(`7/25/13`) and known-text distance `0.599 -> 0.612` (`6/30/9`). Noise20
improved, but tempo1.2 was `0/4/4` on both diagnostics and clean/pitch/silence
were mixed or worse.

Close this objective family. Do not sweep its weight, window, hop, curriculum,
or scope. These machine diagnostics say only that the intended coarse timing
effect was not observed; they do not judge the naturalness, target identity,
or perceptual quality of the 335 unheard WAVs.
