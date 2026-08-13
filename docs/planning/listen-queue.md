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
| MS-3 stable VC heldout shortlist | The same three public utterances through stable seed-0 RVC Sasayaki clean-bright and stable X-VC Yofukashi Q034 | per row prefer one arm, or reject both; judge clarity, naturalness, and target-voice fit by ear | a consistent preference admits one next listen-now route; it is not promotion or product selection |
| RVC turn-consistency diagnostic | `ms3-rvc-repeat-turn-v1` versus the explicit seed-0/seed-34 repeat collections | compare whether the seeded output removes audible turn-to-turn voice changes; do not choose by auxiliary CER alone | seed 0 is the system integration candidate only; a later audible preference may change it |

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
| 2 | Keep `ms3-stable-vc-heldout-shortlist-v1` as the only active cross-family hearing surface; the unseeded predecessor is historical | parent | no: the exact six candidates are already published | one operator preference set or both arms rejected |
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

Base future-200 improved source-relative ASR distance to 0.463 without gross
repetition, but still trailed offline base at 0.317. Publish it for hearing and
close X-VC horizon/LR/scope/lookahead machine search. The next single GPU lane
uses the already-deployed RVC Runrun standard plus four presets on the same
actual source, with the existing Sasayaki standard as a cross-style reference.
It adds no RVC training and cannot select a perceptual winner.

That live-Gateway Runrun comparison is complete. Sasayaki standard had the
lowest auxiliary content error at 0.512; Runrun standard was 0.610, the other
non-looping Runrun presets were 0.683--0.829, and girl-bright produced gross
repetition. Because the comparison already used realtime 20 ms Gateway pacing,
do not duplicate Runrun standard as another system-path render. The historical
32-profile screen placed Sasayaki clean-bright at 0.488 on the same source.
Test only standard versus clean-bright on the three existing public heldout
source rows next, then stop this RVC preset axis. Human hearing is still needed
for any quality decision.

The separate Qwen natural-conversation instruction probe also completed. Its
known-text macro CER worsened from 0.0876 for default to 0.1175 and exact rows
fell from 6/12 to 5/12. Keep the new audio for hearing, but close further TTS
style/profile expansion during this machine-only window.

The Sasayaki heldout run is complete. Standard versus clean-bright known-text
macro CER was 0.477 versus 0.184, and clean-bright was lower on all three rows.
The bounded RMVPE/PM check did not improve on that live result, so preset, block
size, and F0 expansion are closed. A same-source live-Gateway X-VC Yofukashi
Q034 control also completed at 0.166 without gross repetition. Machine evidence
cannot distinguish perceptual quality between 0.166 and 0.184. Both surviving
routes are therefore collected, still unselected, in
`ms3-vc-heldout-shortlist-v1`; do not widen this comparison before hearing.

The persistent-session diagnostic found a separate conversation-system issue:
unseeded RVC repeated the exact same input with correlation -0.283/-0.083 on
turns 2/3, while X-VC was numerically stable. Explicit RVC generation seeds 34
and 0 raised repeat correlation above 0.999997 and removed turn-dependent
auxiliary-ASR changes. Seed 0 had lower coarse CER than seed 34 on the single
diagnostic sentence (0.333 versus 0.444), so it is the sole integration
candidate. This is not a perceptual selection. Do not add another seed point;
the bounded worker/Gateway verification is now complete. Its turn 2/3
correlation was 0.9999967/0.9999976 and all three auxiliary-ASR transcripts
were identical. Keep the three new WAVs for hearing and close further seed,
bit-exactness, runtime-identity, and route-receipt work.

The same frozen seed-0 profile also completed one bounded render on the
existing 8.17-second actual ChatGPT input. It is published beside the
historical unseeded clean-bright control as `ms3-rvc-seed0-actual-input-v5`.
Auxiliary source-relative CER was 0.636 for seed 0 and 0.727 for the historical
control, with no gross repetition in either. The historical raw float input is
no longer retained, so use this as a hearing comparison rather than a strict
seed-only causal estimate. Do not rerender this input or add another seed.

The deployable heldout shortlist is now complete as
`ms3-stable-vc-heldout-shortlist-v1`. Two missing seed-0 RVC rows were rendered
in one persistent Gateway session; the third stable RVC row and all three X-VC
rows were reused by exact hash. Stable RVC auxiliary macro CER was 0.277 and
X-VC was 0.166, with no gross repetition. Machine evidence does not select
perceptual quality. The predecessor `ms3-vc-heldout-shortlist-v1` remains an
archive because its RVC arm predates the generation-stability fix.

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
