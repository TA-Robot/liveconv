# Delivery backlog

Status: Active

The target column refers to the personal-use milestones in
[`roadmap.md`](roadmap.md). `Post-v1` work is not allowed to block MS-1 through
MS-6 unless a new user instruction or ADR changes the boundary. Only `Ready`
items may be assigned to a new write-capable agent; an `In progress` item must
name one owner and ownership zone below.

| ID | State | Priority | Target | Deliverable | Evidence / dependency |
|---|---|---:|---|---|---|
| LV-001 | Review | P1 | MS-4 | Define and version the 40-utterance Japanese comparison corpus metadata | Prepare during MS-3; full shortlist comparison is MS-4 and RF-008 remains open |
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
| LV-015 | Planned | P2 | Post-v1 | Run population native/VC/TTS blind comparison | Not the personal-v1 acceptance test |
| LV-016 | Planned | P1 | MS-5 | Run personal soak, restart, reconnect, and recovery checks | Frozen MS-4 route and MS-5 boundary |
| LV-017 | Planned | P0 | MS-4 | Record primary variant and Extension architecture ADR | EXP-006 shortlist plus full common evidence and operator decision |
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
| LV-030 | Planned | P1 | MS-4 | Calibrate authorized speaker evidence for decision fixtures | Depends on LV-032; prepare during MS-3, required for the full comparison |
| LV-031 | Done | P0 | MS-1 | Implement fake-worker supervisor conformance | Lifecycle, deadline, crash, ordering, cancellation, and backpressure regressions green |
| LV-032 | Ready | P1 | MS-3 | Prepare authorized intelligible Japanese source/target decision fixtures | Parallel preparation only; RF-008 cannot block the first audible MVP |
| LV-033 | Done | P1 | MS-1 | Complete OpenVoice V2 M2 offline technical adapter | Clean-checkout M2 repair reviewed; MS-2 shows it offline-only and does not require Supervisor M3 |
| LV-034 | Planned | P0 | MS-4 | Emit common route-qualified evidence for shortlisted variants | LV-030, LV-032, LV-057, and the shortlist frozen by LV-061 |
| LV-035 | Review | P0 | MS-2 | Integrate all four prepared models through Extension and the SSH route | Four exact technical routes and the Extension integration are green; the actual client SSH/ChatGPT join remains LV-048 |
| LV-036 | Done | P0 | MS-1 | Independently review integrated real-model checkpoint | Final Sol audit found no current-scope High/Medium and approved MS-1 closure |
| LV-037 | Done | P0 | MS-1 | Install six-milestone roadmap and review disposition process | Control-check green and independent Sol re-review found no High/Medium |
| LV-038 | Done | P0 | MS-1 | Run the current isolated RVC technical profile through a disposable Gateway | Clean commit 868ae462: EXP-004 passed 28/28 drain, cancel/stale isolation, and teardown; decision remains inconclusive for quality |
| LV-039 | Planned | P0 | MS-4 | Select the primary variant and freeze Extension architecture | EXP-006 shortlist plus full common authorized evidence |
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
| LV-057 | Ready | P0 | MS-3 | Implement per-variant route-parity receipt and fail-closed eligibility | Resolve every public authorization digest against the exact operator-controlled private registry, require approved/nonexpired status at session creation and exact variant/family/profile/lineage binding, and reject missing/extra/mutated records |
| LV-058 | Done | P0 | MS-3 | Replace the fixed model chooser with a dynamic family/variant chooser | The chooser renders the authenticated deployment manifest and preserves exact profile/config/pack binding, native-first playout, and generation isolation |
| LV-059 | Review | P0 | MS-3 | Prepare first-wave youthful-feminine VC runtimes and authorized voice variants | Nine selectable profiles across RVC, MeanVC2, X-VC, and OpenVoice are active; the MeanVC2 Runrun Gateway route passed bounded PCM/cancel/cleanup checks, while all nine still require Extension listening and EXP-006 screening |
| LV-060 | Planned | P0 | MS-3 | Run the 10-utterance EXP-006 Extension screening pass | LV-032, LV-057 through LV-059; target 9-12 protocol-v1 VC variants across at least four families |
| LV-061 | Planned | P0 | MS-3 | Freeze a four-or-fewer shortlist and common 40-utterance comparison plan | LV-030 and LV-060; maximum two variants per family; this unblocks LV-034 without depending on it |
| LV-062 | Planned | P0 | MS-4 | Run shortlist tuning/comparison and record the selection ADR | LV-034 and LV-061; select one exact primary and fallback or record no release |
| LV-063 | Planned | P1 | MS-3 optional | Decide whether to accept a committed-text TTS transport ADR and protocol revision | Define spoken-text commit, profile identity, interruption, played-text accounting, and shared consumer tests, or explicitly defer TTS; never blocks the VC first wave |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| None | - | - | LV-055 is done; LV-056 and LV-032 are the next disjoint Ready nodes |

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

MS-1 is closed. MS-2 implementation and server-side execution are complete, and
the operator subsequently reached the real Extension route. The audio was not
acceptable. Because the formal EXP-005 receipt was not retained, this observation
does not become a technical evidence pass; the active user instruction instead
closes MS-2 by scope decision and starts the quality-discovery milestone.

## MS-3 dispatch plan

| Ready item | Intended ownership zone | Stop condition |
|---|---|---|
| LV-057 | evaluation receipt plus Gateway/Extension consumers | Each selectable variant receives an exact bundle/profile/config/authorization-bound route receipt or is hidden |
| LV-032 | authorized fixture metadata zone | Ten-utterance screen and 40-utterance comparison fixtures are frozen without raw audio in Git |

LV-055, LV-056, and LV-058 are complete. LV-057 and LV-032 may run in parallel;
LV-059 is at review with nine Gateway-selectable variants across four families.
Model runtime work is serialized by the single GPU lease. A poor voice is
retained as rejection evidence and removed from the next wave; it does not
trigger an open-ended repair cycle. No terminal WAV or direct-worker render can
make a variant decision-eligible without LV-057 route parity.
