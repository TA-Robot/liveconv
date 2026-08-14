# Listen queue

Status: Active board
Updated: 2026-08-14

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
| EXP-163--168 X-VC EMA survivor | Base, control69, and selective real-adversarial EMA across external7, fresh48, Hadou31, stress60, balanced JSUT24, and expanded33 | after hearing returns: judge naturalness, target-voice fit, and stability across corpora/conditions; reject all if gains are not audible | exact checkpoint survived coarse corruption gates with no candidate-added gross loop and rescued the expanded33 shared failure; this is unselected, not a keep or promotion |
| EXP-171--175 X-VC JSUT retention | Base, control69, and the category-balanced JSUT-retention EMA branch across external7, fresh48, Hadou31, stress60, and balanced JSUT24 | after hearing returns: judge naturalness, identity, and its noise/silence versus tempo/ordinary-JSUT tradeoff; do not treat ASR as a winner | v4 retracted the beam-5 false loop; 850 WAVs have no candidate-added consensus gross row and mixed condition/category evidence, so the checkpoint remains unselected |
| EXP-176--180 X-VC paired PCGrad | Base, control69, and hard-repair/retention gradient surgery across external7, fresh48, Hadou31, stress60, and balanced JSUT24 | after hearing returns judge naturalness, identity, and the noise-versus-tempo/silence tradeoff; do not treat ASR as a winner | v4 retracted the beam-5 false loop and the unchanged checkpoint survived every coarse gate with no candidate-added consensus gross row; it improved noise/Hadou but regressed tempo/silence and some JSUT source-relative rows, so remains unselected |
| EXP-181--184 X-VC parameter anchor | Base, control69, and the exact EXP-163 method plus a light control69 L2-SP anchor across external7, fresh48, Hadou31, and stress60 | after hearing returns: optional diagnosis of naturalness/identity versus constrained conversion | 730 WAVs add no consensus gross row, but fresh, pitch, silence, and tempo did not support generic retention; the method family is closed and EXP-185 is deferred |
| EXP-186--190 X-VC Common Voice 48-speaker retention | Base, control69, and the exact EXP-163 method with easy85 replaced by balanced speech-active windows from 48 frozen training-only Common Voice speakers, across external7/fresh48/Hadou31/stress60/JSUT24 | after hearing returns: judge naturalness, identity, ordinary-content retention, and the tempo/pitch tradeoff | 850 WAVs; no candidate-added gross row; fresh/Hadou improve, noise/silence help, but tempo1.2 clearly regresses and JSUT/pitch are mixed; technically completed and unselected |
| EXP-191--193 X-VC conditioned retention | Base, control69, and condition-balanced control69 retention across external7, disjoint-speaker fresh48, and stress60 | after hearing returns: judge naturalness, identity, and the noise-versus-clean/pitch/tempo tradeoff; do not infer a winner from ASR | 575 WAVs; no candidate-added gross row; noise20 improves but clean/pitch regress on source content and tempo1.2 remains worse, so the method family is closed and unselected |
| EXP-194--195 X-VC source36 retention | Base, control69, and the EXP-186 method restricted to 36 source-side LoRA paths across external7 and stress60 | after hearing returns: judge naturalness, identity, and noise versus tempo/silence behavior | 335 WAVs; no candidate-added gross row; noise20 improves but tempo and silence do not, so adjacent scope points are closed and the checkpoint remains unselected |
| EXP-196--197 X-VC source activity-envelope retention | Base, control69, and EXP-186 plus a normalized source/output speech-activity timing loss across external7 and stress60 | after hearing returns: judge naturalness, identity, and whether apparent noise robustness costs tempo/pitch/clean speech | 335 WAVs; no candidate-added gross row; external7 improved but broad stress regressed and tempo1.2 was 0/4/4 on both diagnostics, so the objective family is closed and unselected |
| EXP-198--202 X-VC acoustic-encoder adaptation | Base, control69, and control69 with only the source acoustic encoder retrained, across external7, fresh48, Hadou31, stress60, and balanced JSUT24 | after hearing returns: optionally judge whether the Hadou gain is audible without naturalness, identity, tempo, or broad-content cost | 850 WAVs; no candidate-added gross row; Hadou improves, but disjoint-speaker fresh48, tempo1.2, and balanced JSUT regress on the coarse content screen, so this target family is closed and unselected |
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
to 0.362, and maximum source-relative distance 0.571 to 0.556. EXP-045 showed
that it did not generalize: on twelve changed utterances the mean regressed
from control69 0.184 to 0.289 and maximum distance rose from 0.571 to 1.0.
Aligned augmentation is closed. EXP-046 now replaces exactly one of twelve
synthetic donor exposures per target with its already-authorized aligned human
source, retaining eleven synthetic donors and every optimizer control. Its
seven-row screen regressed from control69 0.360 to 0.430, but the same seven
rows produced EXP-044's false positive. The 14:20 Grok audit therefore changed
the decision gate: EXP-047's twelve changed utterances and EXP-048's ten frozen
conditions must both be screened before another training method is selected.
They confirmed closure: the twelve-row mean was 0.266 versus control69 0.184,
while all ten condition summaries were exactly unchanged, including noise
0.375. EXP-049 is the next loss-method lane. It restores EXP-035's clean
synthetic data and changes only semantic SSL reconstruction weight from 1000
to 2000; waveform, speaker, and VQ losses stay fixed. The combined result
improved the ten-condition macro 0.153 to 0.126, but regressed twelve changed
utterances 0.184 to 0.238 and changed none of the noise/tempo/F0/silence rows.
Loss reweighting is closed. EXP-052 changes learning targets instead: adapt the
36 source/acoustic attention+FFN linears but exclude the 33 frame-condition
linears. Both the campaign trainer and inference route use the same zero-waveform
condition; the test asks whether adapting its input-invariant path is unnecessary
or overfits, while source-path adaptation is retained. The complete bundle
closed it: source36 regressed twelve changed utterances from 0.184 to 0.278
source-relative distance and maximum 0.571 to 1.0, despite improving the frozen
ten-condition macro from 0.153 to 0.113. No arm gross-looped. EXP-055 therefore
changed data coverage, not another scope point: it redistributed the fixed 1,044
updates from 87 to 275 authorized target texts and froze 33 additional unused
Common Voice utterances as a sentence-diversity evaluation. The full bundle did
not establish robust content improvement. Seven external rows regressed, twelve
changed utterances were source-relative identical, and all ten condition rows
were identical. The apparent 33-row mean improvement disappeared after removing
one shared gross-loop outlier: the remaining rows were six wins, nineteen ties,
seven losses with equal medians. Target275 stays unheard on 8878, but target-text
count and exposure-ratio sweeps are closed.

EXP-059 then screened all 1,044 generated training sources and admitted exactly
one best-six-per-target filtered schedule. EXP-060--063 completed a substantially
broader gate: seven external rows, twelve changed utterances, ten named audio
conditions, and 31 unseen Hadou sentences. Filtered6x2 tied control69 on the
seven-row and condition sets, regressed the changed-utterance source-relative
mean from 0.184 to 0.222, and changed Hadou by 3 wins / 25 ties / 3 losses while
introducing one gross loop. The method and keep-count sweep are closed. The
next distinct method restores X-VC's pretrained waveform discriminator and its
alternating adversarial/feature-matching loss, which the local LoRA runner has
so far omitted. Machine screens may reject corruption only; the intended
naturalness effect remains an unheard hypothesis. EXP-064--067 completed that
one method point with no gross loop across 60 varied rows. Seven external rows
and all ten conditions tied control69, twelve changed utterances moved from
0.184 to 0.204, and Hadou31 improved by 5 wins / 24 ties / 2 losses with mean
0.210 to 0.186. Retain the adapter as unheard naturalness-motivated audio, but
do not sweep the objective or call it better. The next separate hypothesis is
decoder-interface placement: adapt only final speaker-conditioned normalization
and `proj_out` while all EXP-035 data and optimizer controls remain fixed.
EXP-068--071 rejected that scope: twelve changed utterances regressed from
`0.184` to `0.375`, and one gross repeated-number loop appeared on Hadou even
though two condition rows and the Hadou aggregate improved. Do not sweep output
layers or rank. The next distinct data hypothesis retains control69 and replaces
exactly 209 target-conversion updates with self-reconstruction rehearsal of the
twelve real Common Voice training-donor windows. That rehearsal regressed the
changed-utterance screen and added one Hadou loop, so its ratio is closed. A
separate final-waveform-decoder point then regressed every aggregate screen:
changed utterances moved from `0.184` to `0.394` and Hadou from `0.210` to
`0.305`. Decoder depth and LR are closed. The next distinct learning-target
hypothesis keeps target waveform and target speaker objectives but supervises
the semantic decoder with the generated source's frozen Whisper hidden states
instead of the target-voice hidden states. It will also reuse the 33-speaker
expanded set; no tongue-twister optimization is involved. EXP-081--085 then
improved the seven-row, condition, Hadou, and 33-row aggregate means, but
regressed the twelve changed utterances and gross-looped one ASR-empty expanded
input. Retain it unheard without a blend sweep. The largest positive signal was
the ten-condition set, but noise and leading silence each had only one row.
The next evaluation therefore crosses those named limitations with all twelve
changed Common Voice utterances before another retraining method is admitted.
EXP-086 rejected the apparent robustness: across 60 rows source-semantic
regressed macro distance from `0.320` to `0.484`, noise20 from `0.397` to
`1.247`, and added one noise loop. Tempo improved, but noise, pitch, and leading
silence did not. Direct source-hidden replacement and blend weights are closed.
EXP-087--092 completed denoising semantic consistency. The balanced 60-row
matrix improved noise20 from `0.397` to `0.258`, tempo from `0.374` to `0.287`,
and macro from `0.320` to `0.311`, but pitch regressed from `0.279` to `0.512`.
The twelve changed utterances also regressed from `0.184` to `0.232`, and an
ASR-empty expanded source triggered a distance-111 repeated-`ぷ` loop. Retain
the unheard audio but reject the method as a generic keeper. Noise ratio, SNR,
condition level, and semantic blend sweeps are closed. The next shortest step
is to test whether source semantic-token or acoustic statistics identify the
low-information inputs that trigger different adapter loops before admitting
another retraining objective. EXP-093 found no universal separator: covering
all three loop-prone sources required flagging at least eight of thirty non-loop
rows. Low semantic-token diversity did isolate both adapter-added loop sources,
but also flagged three non-loop sources and missed the base/control loop source.
It remains a disjoint-validation safety hypothesis, not a fitted runtime gate.
The next distinct training method addresses the still-open conditioning
contract: supply each training row with a deterministic same-Amitaro,
different-utterance frame condition instead of the always-zero waveform.
EXP-094--099 then rejected that contract as a generic method: changed
utterances regressed `0.184` to `0.306`, expanded33 regressed `1.084` to
`1.247` and added a loop, and the balanced stress macro regressed `0.320` to
`0.329`. Noise20 improved `0.397` to `0.275`, but silence and pitch worsened.
No fixed-condition text copy was detected. Close condition reference, strength,
and ratio sweeps. EXP-100--105 then tried to make the redundant acoustic path
tolerate semantic-token collapse by holding each five-frame token block on half
the training rows. The broad gate rejected it: external and changed-utterance
means regressed, stress60 moved `0.320` to `0.362`, and expanded33 produced
seven candidate gross loops. Noise and tempo improved only locally. Close block
size and corruption-ratio sweeps; all audio remains unheard and unselected.
EXP-106--111 then replaced EXP-072's donor-voice reconstruction with 209
semantic-only frozen-base teacher rows under Amitaro speaker context. This is
the first method to improve all five balanced stress means: macro `0.320 ->
0.254`, changed utterances `0.184 -> 0.146`, with no stress or expanded-set
candidate loop. It still added one gross repeated-number loop on pathological
Hadou input `RECITATION324_138`, and expanded33's raw mean gain was driven by
three known failure sources. Retain it as the strongest unheard technical
candidate, not a winner. Do not sweep share or loss weight; validate this exact
checkpoint on genuinely fresh speakers and sentences.
EXP-112 completed that check on 48 previously unmaterialized speakers. The raw
mean favored EXP-106 over control69 only because the two arms catastrophically
looped on different rows. On the 45 rows where no arm looped, EXP-106 regressed
mean `0.326 -> 0.357`, median `0.250 -> 0.308`, and had W/T/L `10/19/16`.
Close the generic teacher method without share or weight tuning. Its earlier
stress signal remains unheard audio, not a machine-selected keeper; fresh48 is
evaluation-only and may not be fitted or moved into training.
EXP-113 then tested the previously retained waveform-adversarial adapter on the
same fresh48 set. It was a `6/33/6` tie against control69 on the common 45
non-loop rows but added a separate catastrophic repetition. Reject it as a
generic keeper and close adversarial-weight tuning. The next training point
keeps EXP-106's exact 209 semantic-teacher slots but cycles them across 48 new
training-only speakers disjoint from fresh48; this tests real-source diversity,
not another teacher share or weight.
EXP-114/115 completed that point. Increasing the real teacher pool from 12 to
48 did not solve instability: the candidate added two fresh48 gross failures,
and on the common 44 non-loop rows it regressed median `0.225 -> 0.304` with
W/T/L `10/22/12`. Close source count, teacher share, and semantic weight.
The increasing teacher-semantic loss (`0.0079 -> 1.3302`) indicates that
semantic-only rehearsal is not holding the waveform decoder near frozen-base
behavior. A materially different next method may distill the frozen base's
complete converted waveform on the same train48 pool; fresh48 remains frozen.
EXP-116/117 completed that full-output point. It removed control69's catastrophic
fresh48 loop, reduced raw mean `1.001 -> 0.334`, reduced maximum distance
`32.4 -> 1.25`, and improved common-non-loop median `0.250 -> 0.154` and
known-text mean `0.610 -> 0.586`. It also added one shorter repeated-`ぷ`
failure on a different low-quality source. Retain this as the strongest unheard
technical signal, but honor the no-added-loop stop and do not run stress60 yet.
The next one-axis method keeps the successful full-output objective and freezes
all 47 attention LoRA targets, adapting only the 22 converter feed-forward
linears. Do not open adjacent scope points.
EXP-118/119 rejected that hypothesis. FFN-only retained control69's catastrophic
repeated-family failure and added a separate 110-character repeated-`ぃ` run.
Its common 45 non-loop rows nearly tied control, so the failure is not a broad
content collapse; it is specifically unsafe output stability. Attention updates
were necessary for EXP-116 to remove the control failure, but not sufficient to
avoid its own short loop. Close the scope branch. The next one-axis point returns
to EXP-116's control69 topology and changes only PEFT parameterization from
standard LoRA to DoRA. Do not open LoRA+, rsLoRA, rank, or DoRA-parameter sweeps
beside it.
EXP-120/121 also failed the no-added-loop gate. DoRA gave the strongest
external7 and common-non-loop content numbers, but retained control69's
catastrophic loop and reproduced EXP-116's short repeated-`ぷ` failure. This
closes PEFT parameterization as the next lever. The next one-axis method returns
to EXP-116 standard LoRA and adds aligned waveform first-difference matching on
only the existing 209 full-output teacher rows. Unlike the earlier pretrained
waveform discriminator, this directly penalizes local temporal collapse against
the exact frozen teacher output. Use one preregistered weight; do not sweep it.
EXP-122/123 rejected that loss too. It retained control69's catastrophic row
and reproduced the same short repeated-`ぷ` failure, while common non-loop rows
were essentially tied. Close temporal-loss weights. The next method responds
directly to the operator's broader-data request: keep 48 teacher sources and
209 slots fixed, but replace the Common Voice-only pool with 24 disjoint Common
Voice speakers, 21 training-only Hadou utterances excluded from target/evaluation
IDs, and three official JVS speaker samples. This changes corpus/domain
composition, not count or share. Do not sweep the 24/21/3 ratio.

## Next listen-now to render

| Priority | Idea | Owner | Depends on unheard? | Stop |
|---|---|---|---|---|
| 1 | Materialize and commit-admit one 48-source cross-corpus teacher pool: CV24 + Hadou21 + JVS3 | parent | no | exact domain counts, target/evaluation exclusions, and 209-slot balance |
| 2 | Train EXP-124 with EXP-116's objective/control69/settings and render EXP-125 on frozen fresh48 | parent | no | one lane; stop on added loop or broad common-non-loop regression |
| 3 | On survival only, cross recording domains rather than adding more Common Voice: frozen stress60 plus existing JVS/Hadou sources | parent | no | separate speaker/content/condition/domain summaries; no combined automatic winner |
| 4 | After hearing returns, hear external/generalization sets before any historical 8.17 s diagnostic | parent | yes | operator keep/continue/rejected recorded |

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
existing 8.17-second legacy diagnostic input. That input is not established as
ChatGPT browser audio. It is published beside the
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
