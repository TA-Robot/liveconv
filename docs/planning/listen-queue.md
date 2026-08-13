# Listen queue

Status: Active board
Updated: 2026-08-13

This is the MS-3 Ready board for quality search. Agents read it before opening
an experiment or sealing a hash. The process is
[`lab-operating-model.md`](lab-operating-model.md).

Listener: `http://127.0.0.1:8878/`

## Unheard now

Operator work. Agents do not start a new quality experiment until they have
made this list shorter or the next render is independent and would otherwise
leave the GPU idle.

Active instruction update (2026-08-13): the operator cannot listen during the
current work window. Do not block GPU quality search on this queue. Run one
committed, single-variable job at a time, publish its comparison on 8878, apply
only coarse machine rejection for corruption/content failure, and replan after
each result. Accumulated candidates remain unselected until human hearing.

| Item | What to hear | Action | Afterward |
|---|---|---|---|
| EXP-020 Stage 0 | Native vs existing human RVC `hakihaki` / `runrun` / `yofukashi` on the 8.17 s actual ChatGPT input | per profile: `rejected` if grossly dead, else `continue` | all rejected → skip more RVC-on-actual and go to the 87-pair X-VC listen-now; any `continue` → that profile may enter a larger actual-input listen |
| EXP-021 | MeanVC2 and OpenVoice V2 on the same 8.17 s input | per family: `continue` or `rejected` | `rejected` kills that family for this input; `continue` only admits a later larger actual-input listen |
| EXP-023 | 12 Qwen3-TTS Ono_Anna texts | per text: `continue` or `rejected` | one `rejected` stops this exact TTS profile; all `continue` only admits later TTS transport work, not a VC win |
| EXP-025 whole-short 87 | Frozen base vs human-paired adapted X-VC on three public heldout source-only utterances | `keep` only if adapted is clearly preferable on the set; otherwise `rejected` | `keep` admits a separate promote pass; `rejected` closes this exact 87-pair schedule |
| EXP-026 horizon | The same three X-VC rows at base / epoch 4 / epoch 8 / epoch 12 | nominate one horizon only if it is clearly preferable across the set; otherwise `rejected` | a nomination chooses the next listen-now model state only; it is not a route or product decision |
| EXP-032 stream floor + system path | Actual 8.17 s input at epoch 8 with future 100 / 110 / 120 / 125 ms, followed by the future-120 candidate through the bounded worker/cancellation path | hear 120 and 125 ms, then compare the source/system pair; record the lowest acceptable arm, or `rejected` | 100/110 have auxiliary-ASR repetition; the worker probe completed with zero stale frames but is not Gateway-, Extension-, or route-qualified |

Historical X-VC synthetic blinds (EXP-010–019) stay on the listener as
archives. They do not gate the current queue.

Active-thread GPU directive (2026-08-13): operator listening remains the
decision critical path, but it must not leave the GPU idle. While decisions are
pending, admit one bounded, committed, single-variable GPU lane at a time when
it produces new listening audio or directly advances the realtime system.
Publish or record a technical stop before starting the next lane. This does not
authorize promote claims or several speculative sweeps in parallel.

## Next listen-now to render

| Priority | Idea | Owner | Depends on unheard? | Stop |
|---|---|---|---|---|
| 1 | Help the operator finish the six rows above; EXP-027--031 are superseded diagnostics and do not need separate draining | parent | n/a | decisions recorded |
| 2 | Reuse the established future-200 endpoint with unadapted base to test whether more context restores actual-input content | parent | no: base future-120 isolated LoRA repetition but still lost content | one future-200 base system WAV and coarse content screen, then close this stream search |
| 3 | If EXP-032 receives a `keep`, bind that exact candidate to the formal Gateway profile and exercise native fallback/Extension playout | parent | yes: EXP-032 `keep` | one route-qualified system listen or a recorded integration blocker |
| 4 | Existing human RVC on more actual pre-VC ChatGPT input (EXP-020 beyond the 8 s smoke) | audio worker | yes: drop any Stage 0 `rejected` profile | published `dev` set or a recorded reason that source capture is the blocker |

The EXP-026 horizon and EXP-027--032 actual-input diagnostics are complete.
EXP-032 closes the lookahead sweep at a 120-ms auxiliary-ASR floor; do not open
another lookahead point. Its bounded worker/cancellation probe also completed
and published one actual-input system WAV. While hearing is unavailable, GPU
work returns to bounded quality-candidate generation. Expanded79 degraded at
epochs 18/24. Narrowing LoRA scope to control69 improved epoch-12 auxiliary
content error from 0.568 to 0.198, but control69 also degraded at epochs 18/24.
Longer 1e-4 training is closed; the next one-axis run halves learning rate while
holding control69 fixed. That run also closed: half-LR content error worsened
from 0.255 to 0.348/0.441 and did not beat standard-LR control69 epoch 12 at
0.198. Do not add another human87 horizon or learning-rate point. Compare the
existing exact epoch-12 adapters on the actual input next; only a candidate
that passes coarse content/repetition screening may enter one bounded worker
system-path run. A recorded `keep` is still required before formal
Gateway/Extension binding or any quality claim.

The actual-input offline screen is complete. Source-relative auxiliary ASR
distance was 0.317 for base, 0.463 for expanded79 epoch 12, and 0.439 for
control69 epoch 12. Control69 did not beat base, but preserved its small
relative advantage over expanded79 and showed no gross loop. Admit only the
single control69 epoch-12/future-120 system-path probe now; do not interpret
its admission as a model selection.

That system probe preserved all queue/cancellation invariants but failed its
audio stop: auxiliary ASR ended with a long repeated `な`. Close control69 for
additional machine-only work. Admit one unadapted-base system control with the
same actual input, target, future-120 geometry, and worker; this is fault
isolation, not another tuning sweep.

The base future-120 control completed without gross repetition and improved
source-relative ASR distance over the old expanded79 system output from 0.561
to 0.512, but remained worse than offline base at 0.317. Reuse only the
already-established future-200 endpoint with base to test whether additional
context recovers content. Do not add intermediate points after the result.

## Keepers

None yet. A `keep` here is the only ticket into a promote pass.

## Killed or closed

| Item | Status | Do not do |
|---|---|---|
| eSpeak 8-text / 19.2 s X-VC corpus | rejected | more synthetic micro-tuning |
| EXP-024 validation16 DTW/window gate | failed closed | retry, relax the 14/16 rule, or backfill a formal receipt |
| EXP-022 Seed-VC | failed closed in warmup | retry or tiny-model substitute |
| EXP-025 as hash/plumbing cathedral | superseded as the Ready path | seal abbreviated identities before a listen-now render |

## Do not start

- new EXP schema whose first deliverable is hashes
- independent review of a listen-now plan
- LoRA+ / DoRA / another synthetic X-VC trajectory
- RVC retraining
- TTS mixed into the human VC corpus
- SSH/MS-5 hardening
- listener ports other than `8878`
