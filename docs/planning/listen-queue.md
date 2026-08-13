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

Provenance correction (2026-08-13): the retained 8.17-second recording saying
`隣の客はよく柿食う客だ` is a local tongue-twister diagnostic, **not** audio
captured from the ChatGPT browser. All earlier `actual ChatGPT` labels for that
artifact and browser-domain conclusions drawn from it are superseded. It stays
available only as historical diagnostics and is not an active optimization
target.

| Item | What to hear | Action | Afterward |
|---|---|---|---|
| EXP-034--038 external speakers | Base and method-level X-VC variants on disjoint Common Voice Japanese speakers | after hearing returns: reject obvious loops first, then judge naturalness and target voice across the set | machine ASR only screens content/corruption; no automatic winner |
| EXP-033 source diversity | Base vs legacy human87 control69-e12 vs JVS3 generated-pair X-VC on ten fixed cross-speaker/constraint rows | after hearing returns: prefer one arm per group or reject all; judge naturalness and target voice by ear | machine ASR may reject corruption only; a consistent audible result admits the next method decision, not promotion |
| EXP-023 | 12 Qwen3-TTS Ono_Anna texts | per text: `continue` or `rejected` | one `rejected` stops this exact TTS profile; all `continue` only admits later TTS transport work, not a VC win |
| EXP-025 whole-short 87 | Frozen base vs human-paired adapted X-VC on three public heldout source-only utterances | `keep` only if adapted is clearly preferable on the set; otherwise `rejected` | `keep` admits a separate promote pass; `rejected` closes this exact 87-pair schedule |
| EXP-026 horizon | The same three X-VC rows at base / epoch 4 / epoch 8 / epoch 12 | nominate one horizon only if it is clearly preferable across the set; otherwise `rejected` | a nomination chooses the next listen-now model state only; it is not a route or product decision |
| EXP-032 stream floor + system path | Historical local tongue-twister diagnostic at epoch 8 with future 100 / 110 / 120 / 125 ms | optional archive only | not browser-domain evidence; no more lookahead points |
| MS-3 stable VC heldout shortlist | The same three public utterances through stable seed-0 RVC Sasayaki clean-bright and stable X-VC Yofukashi Q034 | per row prefer one arm, or reject both; judge clarity, naturalness, and target-voice fit by ear | a consistent preference admits one next listen-now route; it is not promotion or product selection |
| MS-3 stable VC local diagnostic shortlist | The exact 8.17 s local tongue-twister PCM previously consumed by X-VC, through stable seed-0 RVC and stable X-VC Yofukashi Q034 | optional archive only | not ChatGPT-browser or generalization evidence |
| MS-3 stable VC interrupt recovery | Fresh-session output versus the same short utterance immediately after canceling an older generation, once for RVC and X-VC | listen only for a post-cancel clarity/voice change; record `continue` or `rejected` per family | stale-frame safety is machine-closed; hearing may identify a quality issue but does not promote a route |
| MS-3 stable VC native fallback | Continuous remote output versus an exclusive hard switch to aligned native audio at 2.0 s, once for RVC and X-VC | listen at the switch for a click, missing syllable, or disruptive voice jump | identifies a fallback-quality issue only; it does not bind either profile |
| RVC turn-consistency diagnostic | `ms3-rvc-repeat-turn-v1` versus the explicit seed-0/seed-34 repeat collections | compare whether the seeded output removes audible turn-to-turn voice changes; do not choose by auxiliary CER alone | seed 0 is the system integration candidate only; a later audible preference may change it |

Historical X-VC synthetic blinds (EXP-010–019) stay on the listener as
archives. They do not gate the current queue.

Active-thread GPU directive (2026-08-13): operator listening remains the
decision critical path, but it must not leave the GPU idle. While decisions are
pending, admit one bounded, committed, single-variable GPU lane at a time when
it produces new listening audio or directly advances the realtime system.
Publish or record a technical stop before starting the next lane. This does not
authorize promote claims or several speculative sweeps in parallel.

Method reset (2026-08-13): the later `actual-input` statements in this file's
historical narrative refer to the now-corrected local tongue-twister artifact;
they do not establish ChatGPT-browser performance. Exact human87 horizon, LR,
LoRA-scope and EXP-024 DTW retries remain closed. New data construction,
conditioning, loss, and freeze-scope methods are open. EXP-033 completed, but
its JVS-clean improvement did not generalize to the first six Common Voice
rows and one low-quality source produced a gross loop. EXP-035 replaced three
donors repeated four times with twelve distinct admitted donors once while
holding 87 targets, 12 exposures/text, 1,044 updates, control69, LR, loss,
target voice, and zero target conditioning fixed. It avoided gross repetition
on seven disjoint speakers and reduced the adapted worst case, but did not
beat base overall. On the frozen ten-condition set it tied EXP-033's auxiliary
content score and retained the same noise regression. Donor-count expansion is
therefore closed. EXP-036 kept those controls and changed only the upstream
training-role assignment to X-VC's official standard/reconstruction/reversed
mix. It restored an empty external output that EXP-035 had rescued and was
worse on both aggregate content diagnostics, so the role mix is technically
rejected without a fixed-condition expansion. EXP-037 then tested a separate
Amitaro context followed by a masked current window. It did not loop, but
worsened external known-text distance from 0.399 to 0.505, so context-aware
retraining was skipped. EXP-038 kept EXP-035 data, roles, updates, LR, loss,
and zero condition fixed while moving LoRA from 69 content/attention/FFN
linears to only seven global-speaker AdaLN modulators. Its first seven external
rows improved mean source-relative distance from 0.360 to 0.321 without loops,
but lost one empty-output rescue from control69. EXP-039 is the current lane:
twelve new utterances from six of the same external speakers test whether that
scope result survives changed content and 2.184--9.612-second source lengths.
It did not: speaker7 worsened mean source-relative distance from control69's
0.184 to 0.345. Speaker7 is closed. EXP-040 keeps the exact control69 data,
scope, LR, loss, condition, and 1,044 updates, but replaces 209 standard
updates with same-Amitaro reconstruction. It excludes the reversed donor-target
updates implicated in EXP-036, so every target remains the authorized voice.
The seven-row screen had no loops and only mixed small changes. EXP-041 then
replaced speaker7 with reconstruction20 on twelve new utterances. It also had
no loops and retained the same 0.571 maximum source-relative distance as
control69, but its mean moved slightly from 0.184 to 0.198 while the secondary
full-text reference moved from 0.576 to 0.565. This is neither a clear reject
nor a machine-selected win. EXP-042 then produced the exact same auxiliary
result as control69 in all ten clean/tempo/F0/noise/silence rows, including the
unchanged 0.375 noise regression. Target reconstruction is closed. EXP-043
then showed that source-only temporal augmentation made supervision incoherent:
its seven-speaker screen regressed from control69 0.360 to 0.389 and maximum
distance rose from 0.571 to 1.0. EXP-044 keeps the same varied schedule but
applies tempo, F0, and leading silence to both source and target windows so
alignment is preserved; noise remains source-only with a clean target.
Its first seven-speaker screen had no loops and improved control69 on all three
auxiliary summaries: source-relative mean 0.360 to 0.278, known-text mean 0.399
to 0.362, and maximum source-relative distance 0.571 to 0.556. EXP-045 now
tests whether that result survives twelve changed utterances before any frozen
condition render or method claim.

## Next listen-now to render

| Priority | Idea | Owner | Depends on unheard? | Stop |
|---|---|---|---|---|
| 1 | Render EXP-045 base/control69/aligned-condition on the twelve changed utterances | parent | no | 36 candidates and source-relative corruption screen published |
| 2 | If EXP-045 survives, render EXP-044 once on the frozen ten condition rows | parent | no human dependency for machine reject | stress screen published; no automated winner |
| 3 | After hearing returns, hear external/generalization sets before any historical 8.17 s diagnostic | parent | yes | operator keep/continue/rejected recorded |

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

One actual-input preprocessing comparison also completed as
`ms3-stable-rvc-rnnoise-v1`. Raw and stateful-RNNoise input used the same
stable seed-0 RVC profile and Gateway session. Source-relative auxiliary CER
was 0.636 without RNNoise and 0.682 with RNNoise; neither arm gross-looped.
Keep the A/B for optional hearing, but close RNNoise expansion because it did
not improve coarse content retention. It does not displace the stable
cross-family shortlist.

The same bounded comparison on stable X-VC Yofukashi Q034 moved auxiliary CER
from 0.773 raw to 0.659 with RNNoise, with no gross loop. This family-dependent
improvement does not beat stable RVC raw at 0.636 and cannot select perceptual
quality, so retain the A/B for optional hearing and close further denoise
points. During this check, the exact original decoded actual-input float PCM
(`b114ae...`) was recovered in two retained listener collections and matched
byte-for-byte. It differs from the later PCM24 re-decode mainly by amplitude,
despite near-unit correlation. One stable seed-0 RVC render from that recovered
raw is therefore Ready; it replaces the earlier assumption that the raw input
was unavailable and will permit an exact-input RVC/X-VC actual shortlist.

That exact-input actual shortlist is now complete as
`ms3-stable-vc-actual-shortlist-v1`. Stable seed-0 RVC was newly rendered from
the recovered `b114ae...` raw PCM; the existing X-VC Q034 output was reused by
exact source/output hashes. Auxiliary source-relative CER was 0.417 for RVC
and 0.833 for X-VC, with no gross repetition. Keep the stable public heldout
shortlist first and this actual-input pair second for human hearing. Do not
rerender either arm or turn the machine screen into a quality selection.

The recovered raw PCM was exactly 3.0103 dB above the later PCM24 re-decode,
and stable RVC coarse CER improved across that natural pair from 0.636 to
0.417. One bounded extrapolation raised the exact raw input another 3.0103 dB
without clipping. Its CER worsened to 0.472, again without gross repetition.
This brackets the useful level near the recovered original on this input.
Retain `ms3-stable-rvc-input-gain-v1` for optional hearing and close finer gain
search; do not turn a single-input ASR minimum into an automatic normalizer.

One conversation-boundary probe split the same exact input at the center of
its 560 ms silence while preserving byte order and the total 409 frames. Stable
RVC coarse CER worsened from 0.417 for one generation to 0.556 for two. The
first turn was unchanged at 0.577; only the reset second turn worsened from
0.167 to 0.500. No arm gross-looped. This is a generation-boundary quality
defect relevant to realtime conversation, not a model winner. Investigate one
root-cause control before widening voices or inputs; do not rerender the same
split unchanged.

The one latent-noise root-cause control is complete. An isolated direct-backend
standard control reproduced the Gateway baseline transcript and 0.417 CER even
though its waveform correlation was only 0.606. Setting posterior latent noise
from 0.66666 to zero worsened CER to 0.500 without gross repetition. Retain
`ms3-rvc-zero-latent-noise-v3` only as diagnosis and close noise-scale points;
the turn-boundary defect remains a context/state question.

That context/state control is now positive. Gateway reset and direct reset
matched at 0.999 waveform correlation and identical per-turn transcripts. On
the same direct backend, omitting only the reset before turn 2 restored its CER
from 0.500 to 0.167, while turn 1 stayed fixed at 0.577. State carryover is not
a product fix because an interrupted older generation must not contaminate a
new one. Admit one fully reset, silence-only context priming control next; stop
if it does not recover turn 2.

The fully reset 3.5-second zero-PCM prime did not recover turn 2: both reset and
prime stayed at 0.500 turn CER and 0.556 full CER without gross repetition.
Close silence-prime lengths. The positive carryover result therefore depends
on prior-generation state, not merely a warmed zero context. Isolate the prior
input-context buffers once while still clearing RNG, pitch, RMS, and SOLA; any
shipping design must clear all carryover on interruption.

Prior input-context buffers alone also failed: turn 2 stayed at 0.500 and full
CER worsened from 0.556 to 0.667. Close input-context carry. Because the profile
uses RMVPE and pitch cache is the remaining state directly tied to short speech,
isolate pitch/pitchf cache once while resetting input context, RNG, RMS, and
SOLA. Do not test an arbitrary combination or ship state carryover.

Pitch/pitchf cache alone also failed: reset and cache-carry both remained at
0.500 turn-2 CER and 0.556 full CER. Close pitch-cache carry. With threshold
gating disabled at -60 dBFS and SOLA limited to the 90 ms join, the last
high-value state explanation is RNG continuation versus reseeding. Isolate RNG
continuation once with all audio, pitch, RMS, and SOLA buffers reset; then stop
state-decomposition GPU work regardless of outcome.

RNG continuation alone also failed: reset/reseed and reset/continued-RNG both
stayed at 0.500 turn-2 CER and 0.556 full CER. Close RVC state decomposition;
do not test SOLA, state combinations, another seed, or another split point.
Apply the already-fixed natural split once to stable X-VC Q034. That determines
whether the defect is RVC-specific or common to the conversation boundary
without widening model, training, or quality axes.

The stable X-VC Q034 control also degraded across the same natural split. Full
CER stayed 0.833, but per-turn CER moved from 0.577/0.333 in one generation to
0.731/0.500 in two, without gross repetition. The short-generation weakness is
therefore not RVC-only. Close generation-boundary model diagnostics and retain
both A/Bs for hearing. Search retained artifacts for a distinct actual pre-VC
input next; if none exists, use public known-text rows for one bounded
generalization batch rather than another boundary or parameter point.

No second retained actual pre-VC input exists: every collection tagged as the
actual ChatGPT source resolves to the same source hash. The bounded fallback is
complete as `ms3-stable-vc-generalization-v1`. It uses three previously unused
Hadou validation rows spanning 3.0, 4.8, and 7.3 seconds, each in an independent
fresh Gateway session. Stable RVC CER was 0.111/0.000/0.032 and stable X-VC was
0.000/0.100/0.000; all six outputs avoided gross repetition. This establishes
content-intact generalization only, not naturalness or voice identity. Retain
the three RVC/X-VC pairs for hearing and stop adding public rows before an
operator decision.

The bounded realtime fallback requested by the 10:13 progress audit is also
complete. `ms3-stable-xvc-cancel-recovery-v1` and
`ms3-stable-rvc-cancel-recovery-v1` each cancel an older two-second generation,
close the local output gate before cancel, and render the same short recovery
utterance in the next generation. Both families returned zero stale output
frames after the cancel acknowledgment and completed all 151 recovery frames.
X-VC fresh/recovery audio was numerically near-identical and both transcribed
at CER 0. RVC fresh/recovery retained the same transcript and CER 0.111 but had
waveform correlation 0.892, so its perceptual significance remains unheard.
This closes additional cancel variants and RVC state decomposition; do not use
the waveform difference as an automatic quality decision.

The next audit returned `REDIRECT` and requested another actual ChatGPT source,
but no second retained source hash or active Chrome capture existed. Its closure
of cancel/training/state work was adopted; the unavailable source request was
replaced with the distinct audible system slice
`ms3-stable-vc-native-fallback-v1`. It reuses the exact 8.17-second actual
source and stable outputs, then changes only continuous remote playout versus
the current exclusive hard fallback at 2.0 seconds. Remote is muted before
native becomes audible, so there is no overlap. The boundary sample jump is
0.0488 for RVC and 0.1122 for X-VC. A pinned auxiliary ASR found no new gross
loop, but neither that metric nor the sample jump decides whether the
transition is perceptually acceptable. Stop further fallback variants until an
operator hears the switch.

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
