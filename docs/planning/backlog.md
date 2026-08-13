# Delivery backlog

Status: Active

The target column refers to the personal-use milestones in
[`roadmap.md`](roadmap.md). `Post-v1` work is not allowed to block MS-1 through
MS-6 unless a new user instruction or ADR changes the boundary. Only `Ready`
items may be assigned to a new write-capable agent; an `In progress` item must
name one owner and ownership zone below.

| ID | State | Priority | Target | Deliverable | Evidence / dependency |
|---|---|---:|---|---|---|
| LV-001 | Deferred | P2 | Historical | Hear existing human RVC on the local 8 s tongue-twister diagnostic | The artifact is not ChatGPT browser audio; retain as a historical gross screen, not a domain gate |
| LV-002 | Planned | P2 | Post-v1 | Finalize and approve prompt-only EXP-001 | Not required for the personal VC path |
| LV-003 | Review | P1 | MS-3 | Specify deterministic Japanese spoken-text normalization cases | Required only for TTS variants; keep text and captured-audio products separate |
| LV-004 | Done | P0 | MS-1 | Implement signal/content/speaker/integrity/streaming evaluation contracts | Forgery/replay/registry fixes passed 109 tests and independent Sol review |
| LV-005 | Done | P0 | MS-1 | Implement Chrome MV3 Extension shell | Loadability, popup, state, permissions, and current-tree Sol review green |
| LV-006 | Done | P0 | MS-1 | Implement tab capture, Offscreen Document, and native loopback | Real topology, bounded credit, native fallback tests, and Sol review green |
| LV-007 | Done | P0 | MS-1 | Implement generation-aware bounded exclusive playout | One playhead, underflow/cancel/replay tests, and Sol review green |
| LV-008 | Planned | P0 | MS-5 | Add timing trace and loopback stability run | Frozen MS-4 architecture |
| LV-009 | Done | P0 | MS-1 | Verify VC candidates, licenses, artifacts, and revisions | Model matrix and adapter records preserve provenance, uncertainty, and nonselectable boundaries; no legal/product approval claim |
| LV-010 | Done | P0 | MS-1 | Implement common worker-v1 VC boundary and real candidates | RVC, Beatrice, and X-VC reached technical M3 worker smoke; OpenVoice reached bounded offline M2 |
| LV-011 | Done | P0 | MS-3 | Re-verify Japanese streaming TTS candidates | Official-source review prioritizes Qwen3-TTS 0.6B and CosyVoice3, with license blockers retained for later candidates |
| LV-012 | Planned | P1 | MS-3 optional | Implement spoken-text commit and normalization package | LV-063 must first accept the TTS transport decision; never infer spoken text from captured audio |
| LV-013 | Planned | P1 | MS-3 optional | Implement common TTS adapter and the Qwen3-TTS `Ono_Anna` candidate | LV-012 plus LV-056; not part of the counted VC gate |
| LV-014 | Planned | P1 | MS-3 optional | Implement played-text accounting and TTS interruption | LV-013; preserve generation isolation and native fallback |
| LV-015 | Deferred | P2 | Post-v1 | Run a population native/VC/TTS comparison only after basic audio quality is usable | Not part of the current personal-v1 quality search; current evaluations use explicit model labels |
| LV-016 | Planned | P1 | MS-5 | Run personal soak, restart, reconnect, and recovery checks | Frozen MS-4 route and MS-5 boundary |
| LV-017 | Planned | P0 | MS-4 | Record primary variant and Extension architecture ADR | EXP-020 confirmation evidence for a surviving named profile plus route-qualified common evidence and operator decision |
| LV-018 | Planned | P2 | Post-v1 | Run and analyze full EXP-001 | Prompt/TTS research path |
| LV-019 | Done | P0 | MS-1 | Implement protocol v1 frame/control contracts and golden tests | Client/frame/server event contracts |
| LV-020 | Done | P0 | MS-1 | Implement authenticated session/generation Gateway | Backpressure, explicit WebSocket transport, promotion binding, and clean-commit EXP-004 route green |
| LV-021 | Review | P1 | MS-4 | Retain loopback/auth/Origin/resource hardening; keep public TLS deployment optional | SSH route is the MS-4 gate; DNS/ACME is RF-010 |
| LV-022 | Done | P0 | MS-1 | Implement isolated worker supervisor and model profile registry | Lifecycle, identity, bounded-credit, packaging, and real-route gates green |
| LV-023 | Done | P0 | MS-1 | Integrate RVC v2 isolated technical profile | Content-addressed v1.4 identity, network denial, and clean-commit Gateway route green; quality remains failed/nonselectable |
| LV-024 | Done | P1 | MS-1 | Record X-VC technical worker smoke and failed-quality result | M3 worker behavior is technical-only; failed quality and nonselectable decision remain controlling |
| LV-025 | Done | P1 | MS-1 | Complete trainer-based Beatrice technical worker | Full wheel/shared-code/runtime identity and real M3 evidence passed independent Sol review; product gates remain blocked |
| LV-026 | Done | P0 | MS-1 | Implement Extension WSS client, generation controls, and native fallback | Restart, underflow, and config transaction fixes passed 109 tests and independent Sol review |
| LV-027 | Done | P1 | MS-1 | Define machine-readable candidate model packs | Promotion/evidence binding, package resources, and exact-profile route identity green |
| LV-028 | Done | P0 | MS-1 | Implement repeatable remote route/fault runner | Route smoke remains explicitly inconclusive for quality |
| LV-029 | Done | P0 | MS-1 | Integrate pinned Japanese STT runner | Provenance, 24/48 kHz resampling, collision prevention, and publication rollback gates green |
| LV-030 | Planned | P1 | MS-4 | Calibrate authorized speaker evidence for decision fixtures | Depends on LV-032; prepare during MS-3, required for the surviving named-profile confirmation |
| LV-031 | Done | P0 | MS-1 | Implement fake-worker supervisor conformance | Lifecycle, deadline, crash, ordering, cancellation, and backpressure regressions green |
| LV-032 | Done | P1 | MS-3 | Prepare authorized intelligible Japanese source/target decision fixtures | Frozen 10-screen/40-comparison metadata binds exact synthetic source digests and route-receipt requirements without raw/private audio in Git; checker and mutation tests are green |
| LV-033 | Done | P1 | MS-1 | Complete OpenVoice V2 M2 offline technical adapter | Clean-checkout M2 repair reviewed; MS-2 shows it offline-only and does not require Supervisor M3 |
| LV-034 | Planned | P0 | MS-4 | Emit common route-qualified evidence for the surviving named profile | LV-030, LV-032, LV-057, and EXP-020 `confirmation24`; does not depend on the retired family shortlist |
| LV-035 | Review | P0 | MS-2 | Integrate all four prepared models through Extension and the SSH route | Four exact technical routes and the Extension integration are green; the actual client SSH/ChatGPT join remains LV-048 |
| LV-036 | Done | P0 | MS-1 | Independently review integrated real-model checkpoint | Final Sol audit found no current-scope High/Medium and approved MS-1 closure |
| LV-037 | Done | P0 | MS-1 | Install six-milestone roadmap and review disposition process | Control-check green and independent Sol re-review found no High/Medium |
| LV-038 | Done | P0 | MS-1 | Run the current isolated RVC technical profile through a disposable Gateway | Clean commit 868ae462: EXP-004 passed 28/28 drain, cancel/stale isolation, and teardown; decision remains inconclusive for quality |
| LV-039 | Planned | P0 | MS-4 | Select the primary variant and freeze Extension architecture | EXP-020 confirmation of a surviving named profile plus full common authorized evidence |
| LV-040 | Planned | P0 | MS-5 | Tune response, jitter, queue, cancellation, and stability | Frozen LV-039 path |
| LV-041 | Planned | P0 | MS-5 | Verify the real one-client SSH-only security boundary | Frozen MS-4 route and second client shell |
| LV-042 | Planned | P0 | MS-5 | Package personal start/restart/rollback/maintenance operations | MS-4 boundary and release inventory |
| LV-043 | Planned | P0 | MS-6 | Run audible external-client acceptance and freeze personal v1 | LV-035, LV-042, final review |
| LV-044 | Done | P0 | MS-2 | Define the versioned safe model-roster schema and authenticated API contract | Exact-four schema/API, pack identity binding, package resources, and Sol review green |
| LV-045 | Done | P0 | MS-2 | Show all model states in the Extension and permit technical-only invocation | Four-model chooser, live/buffered modes, native-first operation, race regressions, and 148 Extension tests green |
| LV-046 | Done | P0 | MS-2 | Integrate a Beatrice 2 technical Gateway profile and route contract | Exact technical profile completed a clean-commit 28-frame Gateway route; no quality claim |
| LV-047 | Done | P0 | MS-2 | Integrate X-VC as a technical live Gateway profile | Exact technical profile completed a clean-commit 28-frame Gateway route; quality-failed status remains visible |
| LV-048 | Review | P0 | MS-2 | Run EXP-005 actual ChatGPT multi-model Extension MVP over SSH | Operator reached the actual Extension path and rejected the audio quality, but did not retain the formal EXP-005 receipt; historical technical pass remains unclaimed |
| LV-049 | Review | P0 | MS-2 | Freeze and execute the minimal SSH-loopback MVP preflight | Script, 47 deterministic checks, and Sol review are green; execute it against the operator's actual client/server pair in LV-048 |
| LV-050 | Done | P0 | MS-2 | Generalize shared Gateway worker dispatch, profile validation, and technical pack/evidence binding | Static exact-pack registrations, capacity invariants, injection negatives, and Sol review green |
| LV-051 | Done | P0 | MS-2 | Freeze the exact four-model deployment roster after route outcomes | Generated registry is byte-stable and exposes three live trials plus one buffered preview with exact identities |
| LV-053 | Done | P0 | MS-2 | Add bounded End-triggered OpenVoice buffered preview invocable from the Extension | Actual 25-frame Gateway route emitted no output before End and passed cancel/stale/cleanup; no streaming claim |
| LV-054 | Done | P0 | MS-2 | Implement and review the EXP-005 metadata runner, schema, and frozen prompt/sample plan | Runtime receipt, separate manual judgments, fifth failure probe, persistence, strict identity checks, and Sol review green |
| LV-055 | Done | P0 | MS-3 | Define EXP-006, the young-feminine candidate catalog, and the deployment-bundle contract | Protocol-v1 VC first wave, public/private identity and authorization schemas, trusted-clock validation, 24 focused tests, and independent Sol review are green with no High/Medium |
| LV-056 | Done | P0 | MS-3 | Implement one immutable deployment-bundle compiler and authenticated manifest | Gateway, Extension, and one-command terminal activation resolve sealed bundle `sha256:468babb589f31d3a48a4bd07ca8a939da5ef9fefef89488bc78be7db4fb32df4`; activation fails closed on bundle, identity, artifact, or trusted-clock mismatch |
| LV-057 | Done | P0 | MS-3 | Implement per-variant route-parity receipt and fail-closed eligibility | Gateway-issued one-time attestation now binds a real evidence session, WS attach, generation start, and exact route identity; hand-authored and replayed observations fail closed |
| LV-058 | Done | P0 | MS-3 | Replace the fixed model chooser with a dynamic family/variant chooser | The chooser renders the authenticated deployment manifest and preserves exact profile/config/pack binding, native-first playout, and generation isolation |
| LV-059 | Deferred | P0 | Historical | Retire the nine-family youthful-feminine VC screening lane | Nine selectable RVC, MeanVC2, X-VC, and OpenVoice profiles remain historical technical inventory; they do not gate EXP-020 or its named human-trained RVC comparison |
| LV-060 | Review | P0 | MS-3 | Run the 10-utterance EXP-006 Extension-qualified screening pass | Exact 90 source/profile renders and receipts are complete. Selection is superseded by LV-064 because the source fixtures do not replace the actual pre-VC ChatGPT input set |
| LV-061 | Deferred | P0 | Historical | Retire the four-or-fewer cross-family shortlist and 40-utterance plan | Historical EXP-006 dependency only; it does not unblock LV-034 or participate in the actual-input RVC path |
| LV-062 | Deferred | P0 | Historical | Retire the cross-family shortlist tuning/comparison selection lane | Historical EXP-006/X-VC-era dependency only; EXP-020 decides only among surviving named human-trained RVC profiles |
| LV-063 | Planned | P1 | MS-3 optional | Decide whether to accept a committed-text TTS transport ADR and protocol revision | Define spoken-text commit, profile identity, interruption, played-text accounting, and shared consumer tests, or explicitly defer TTS; never blocks the VC first wave |
| LV-064 | Blocked | P1 | Historical | Exact human same-text X-VC via 2.4 s DTW windows | Failed closed at validation16; do not retry or relax the 14/16 gate; 370-row pronunciation UI is optional, not a listen-now blocker |
| LV-065 | Review | P0 | MS-3 | Gross-screen installed zero-shot VC families on the same actual input | EXP-021 technical renders are complete and plainly labelled on port 8878; operator `continue`/`rejected` is the remaining listen-now work |
| LV-066 | Done | P0 | MS-3 | Run one Seed-VC v1 full offline gross screen | The sole admitted EXP-022 attempt failed closed during the discarded warmup, published no candidate, cleaned up, and was not retried or replaced by a tiny model or parameter sweep |
| LV-067 | Review | P1 | MS-3 optional | Gross-screen one Qwen3-TTS Ono_Anna Japanese candidate | EXP-023 12 texts are on port 8878; operator `continue`/`rejected` only; this cannot win the VC path |
| LV-068 | Done | P0 | MS-3 | Listen-now train the 87 whole-short human pairs through X-VC | EXP-025/026 stretch+pad training and heldout renders completed; scope, horizon, and learning-rate follow-ups are closed, with stable comparisons published on 8878 and no quality winner claimed |
| LV-069 | Done | P0 | MS-3 | Retrain X-VC with generated same-content source-speaker diversity and a fixed diverse evaluation | EXP-033 published 30 candidates; JVS-clean content improved, but external Common Voice exposed one gross loop and no generalization claim survives |
| LV-070 | Done | P0 | MS-3 | Expand generated-source donor breadth at fixed exposure and evaluate on disjoint external speakers | EXP-035 published 21 disjoint-speaker and 30 fixed-condition candidates; CV12 removed the JVS3 gross external failure but did not beat base overall and retained the noise weakness, so donor-count expansion is closed |
| LV-071 | Done | P0 | MS-3 | Restore X-VC's upstream training-role mixture at fixed EXP-035 exposure | EXP-036 completed 1,044 updates and 21 external candidates; it restored one empty output and worsened aggregate auxiliary content versus all-standard, so no fixed-condition expansion is admitted |
| LV-072 | Done | P0 | MS-3 | Test content-safe target frame context before context-aware X-VC retraining | EXP-037 published 14 candidates; context did not loop but worsened external known-text distance from 0.399 to 0.505, so retraining was skipped |
| LV-073 | Done | P0 | MS-3 | Restrict X-VC adaptation to global-speaker modulation at fixed EXP-035 exposure | EXP-038 improved the first seven-row mean, but EXP-039's twelve new utterances regressed from control69 0.184 to speaker7 0.345 source-relative distance; speaker7 is closed |
| LV-074 | Done | P0 | MS-3 | Add target-preserving reconstruction without reversed donor-target dilution | EXP-042 matched control69 exactly across all ten frozen conditions and did not repair noise; reconstruction20 is retained as unheard audio only and the training method is closed |
| LV-075 | Done | P0 | MS-3 | Train X-VC against varied source-side audio limitations | EXP-043 completed but source-only temporal changes caused incoherent target supervision and regressed the seven-speaker screen; the method is closed without more renders |
| LV-076 | Done | P0 | MS-3 | Preserve target alignment while training X-VC on varied audio limitations | EXP-044 improved seven external rows, but EXP-045 regressed on twelve changed utterances; aligned augmentation is closed without a fixed-condition render |
| LV-077 | Done | P0 | MS-3 | Anchor synthetic X-VC diversity with authentic aligned sources | EXP-047 regressed on twelve changed utterances and EXP-048 changed none of ten stress summaries; the authentic-anchor method is closed |
| LV-078 | Done | P0 | MS-3 | Strengthen X-VC semantic content preservation without weakening acoustic losses | EXP-049 improved the ten-condition clean subset but regressed twelve changed utterances and no constrained row; semantic loss reweighting is closed |
| LV-079 | Done | P0 | MS-3 | Exclude input-invariant frame-condition modules from X-VC adaptation | EXP-052 improved the frozen condition subset but regressed twelve changed utterances; source36 is closed without an adjacent scope point |
| LV-080 | Done | P0 | MS-3 | Expand X-VC target-text coverage at fixed updates and strengthen sentence-diverse evaluation | EXP-055 completed the 7 + 12 + 10 + 33 bundle; the apparent 33-row mean gain was outlier-driven, so target breadth is closed without a count sweep and remains unheard audio only |
| LV-081 | Done | P0 | MS-3 | Improve X-VC retraining data quality without another breadth or horizon sweep | EXP-059 admitted one filtered6x2 run; EXP-060--063 tied the original external set and frozen conditions, regressed changed utterances, and added one Hadou loop, so the method and keep-count sweep are closed |
| LV-082 | Done | P0 | MS-3 | Restore X-VC's omitted pretrained waveform-adversarial objective in one bounded adapter run | EXP-064--067 completed with no loops across 60 rows; external and condition sets tied control69, changed utterances slightly regressed, and Hadou improved 5/24/2, so retain it unheard without a naturalness claim and prohibit objective sweeps |
| LV-083 | Done | P0 | MS-3 | Test decoder-interface X-VC adaptation as one function-aware scope | EXP-068--071 regressed twelve changed utterances from 0.184 to 0.375 and added one Hadou gross loop; reject output2 and prohibit adjacent scope/rank/LR sweeps |
| LV-084 | Done | P0 | MS-3 | Rehearse real donor speech during target-voice X-VC retraining | EXP-072--075 regressed changed utterances and added one Hadou gross loop; reject rehearsal and prohibit ratio sweeps |
| LV-085 | Done | P0 | MS-3 | Adapt one bounded final waveform-decoder stage | EXP-077--080 regressed every aggregate content screen, including changed utterances from 0.184 to 0.394 and Hadou from 0.210 to 0.305; reject the method and prohibit decoder-depth/LR sweeps |
| LV-086 | In progress | P0 | MS-3 | Change X-VC's semantic learning target from target-voice hidden states to source hidden states | Keep EXP-035 data/scope/LR/weights/updates fixed, train one source-semantic point, then apply the frozen 7 + 12 + 10 + 31 + 33 bundle |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| LV-086 | `primary-integrator` | `tools/xvc-source-diversity/`, EXP-081--085 notes, and their ignored artifacts | Commit one source-semantic learning-target point or reject it before GPU admission |

Read-only Sol reviewers are not owners and do not block writers in disjoint
zones. Completed writers are removed from this table immediately.

## State definitions

- `Research`: evidence is missing before task shape is stable.
- `Planned`: known work with an unmet dependency or a later target milestone.
- `Ready`: bounded, accepted, and safe to assign now.
- `In progress`: one named owner and ownership zone are active.
- `Review`: implementation is complete; independent current-tree evidence is pending.
- `Done`: the applicable milestone Definition of Done is met and linked.
- `Blocked`: a real external dependency prevents meaningful progress and the next
  unblock action is recorded.

## Current coordinated batch

MS-1 is closed. MS-2 closed by scope decision after the operator rejected the
prepared audio. Human hearing is temporarily unavailable. MS-3 therefore runs
one committed method-level GPU pilot at a time, publishes its audio on 8878,
and uses machine metrics only to reject corruption. EXP-035 closed donor-count
expansion after improving external stability without repairing the shared
noise weakness. EXP-036 role mixing and EXP-037 target context then regressed
the external screen. EXP-038 speaker-only scope failed EXP-039's new-utterance
generalization. EXP-040 retains control69 and tests only target-preserving
reconstruction, omitting reversed donor-target updates; exact human87 epoch/LR/
scope and EXP-024 DTW retries remain closed. Do not spend this batch on hashes
or receipts.

## MS-3 dispatch plan

The live board is [`listen-queue.md`](listen-queue.md). Process is
[`lab-operating-model.md`](lab-operating-model.md).

| Ready item | Intended ownership zone | Stop condition |
|---|---|---|
| LV-079 EXP-052 | `tools/xvc-source-diversity/` and fixed-port 8878 | one 1,044-update source36 train plus seven external rows, followed by the combined gate |
| Unheard drain | Fixed-port 8878: EXP-033/034/035, stable public sets, EXP-023 | Operator `continue`/`rejected` when hearing returns |

LV-032, LV-055, LV-056, LV-057, LV-058, and LV-068 are complete. LV-059,
LV-061, LV-062, and LV-064 Stage B are historical or blocked. The prior nine-family
screening does not gate the hearing loop. The rejected eSpeak corpus remains
stopped. The failed EXP-024 DTW gate is not retried. Existing human RVC
checkpoints are listen-now candidates. No RVC model is being retrained to
answer the failed X-VC alignment question.
