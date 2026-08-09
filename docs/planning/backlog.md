# Delivery backlog

Status: Active

The target column refers to the personal-use milestones in
[`roadmap.md`](roadmap.md). `Post-v1` work is not allowed to block MS-1 through
MS-6 unless a new user instruction or ADR changes the boundary. Only `Ready`
items may be assigned to a new write-capable agent; an `In progress` item must
name one owner and ownership zone below.

| ID | State | Priority | Target | Deliverable | Evidence / dependency |
|---|---|---:|---|---|---|
| LV-001 | Review | P1 | MS-2 | Define and version the 40-utterance Japanese smoke corpus metadata | Schema-valid corpus; intelligibility weakness is RF-008 |
| LV-002 | Planned | P2 | Post-v1 | Finalize and approve prompt-only EXP-001 | Not required for the personal VC path |
| LV-003 | Review | P1 | MS-2 | Specify deterministic spoken-text normalization cases | Shared normalization revision and table-driven tests |
| LV-004 | Done | P0 | MS-1 | Implement signal/content/speaker/integrity/streaming evaluation contracts | Forgery/replay/registry fixes passed 109 tests and independent Sol review |
| LV-005 | Done | P0 | MS-1 | Implement Chrome MV3 Extension shell | Loadability, popup, state, permissions, and current-tree Sol review green |
| LV-006 | Done | P0 | MS-1 | Implement tab capture, Offscreen Document, and native loopback | Real topology, bounded credit, native fallback tests, and Sol review green |
| LV-007 | Done | P0 | MS-1 | Implement generation-aware bounded exclusive playout | One playhead, underflow/cancel/replay tests, and Sol review green |
| LV-008 | Planned | P0 | MS-3 | Add timing trace and loopback stability run | Frozen MS-2 architecture |
| LV-009 | Review | P0 | MS-1 | Verify VC candidates, licenses, artifacts, and revisions | Primary-source model matrix and per-adapter records |
| LV-010 | Review | P0 | MS-1 | Implement common worker-v1 VC boundary and real candidates | LV-022 plus model adapters |
| LV-011 | Research | P2 | Post-v1 | Re-verify Japanese streaming TTS candidates | Re-enter only after an MS-2 architecture decision |
| LV-012 | Planned | P2 | Post-v1 | Implement spoken-text commit and normalization package | TTS path only |
| LV-013 | Planned | P2 | Post-v1 | Implement common TTS adapter and first candidate | LV-011 and LV-012 |
| LV-014 | Planned | P2 | Post-v1 | Implement played-text accounting and TTS interruption | TTS path only |
| LV-015 | Planned | P2 | Post-v1 | Run population native/VC/TTS blind comparison | Not the personal-v1 acceptance test |
| LV-016 | Planned | P1 | MS-5 | Run personal soak, restart, reconnect, and recovery checks | Frozen MS-3 route and MS-4 boundary |
| LV-017 | Planned | P0 | MS-2 | Record primary model and Extension architecture ADR | Common evidence and operator decision |
| LV-018 | Planned | P2 | Post-v1 | Run and analyze full EXP-001 | Prompt/TTS research path |
| LV-019 | Done | P0 | MS-1 | Implement protocol v1 frame/control contracts and golden tests | Client/frame/server event contracts |
| LV-020 | Review | P0 | MS-1 | Implement authenticated session/generation Gateway | Backpressure/WebSocket/promotion binding tests green; integrated route review pending |
| LV-021 | Review | P1 | MS-4 | Retain loopback/auth/Origin/resource hardening; keep public TLS deployment optional | SSH route is the MS-4 gate; DNS/ACME is RF-010 |
| LV-022 | Review | P0 | MS-1 | Implement isolated worker supervisor and model profile registry | Current supervisor fixes require integrated current-tree review |
| LV-023 | Review | P0 | MS-1 | Integrate RVC v2 isolated technical profile | Content-addressed v1.4 profile/evidence and network denial green; real Gateway route pending |
| LV-024 | Review | P1 | MS-1 | Record X-VC M2 technical transform and failed-quality result | Installed-runtime M3 binding is scheduled to MS-2 only if shortlisted |
| LV-025 | Done | P1 | MS-1 | Complete trainer-based Beatrice technical worker | Full wheel/shared-code/runtime identity and real M3 evidence passed independent Sol review; product gates remain blocked |
| LV-026 | Done | P0 | MS-1 | Implement Extension WSS client, generation controls, and native fallback | Restart, underflow, and config transaction fixes passed 109 tests and independent Sol review |
| LV-027 | Review | P1 | MS-1 | Define machine-readable candidate model packs | Promotion binding and Beatrice trainer graph tests green; integrated review pending |
| LV-028 | Done | P0 | MS-1 | Implement repeatable remote route/fault runner | Route smoke remains explicitly inconclusive for quality |
| LV-029 | Review | P0 | MS-1 | Integrate pinned Japanese STT runner | Current resampling/provenance/rollback repair is under independent re-review |
| LV-030 | Planned | P1 | MS-2 | Calibrate authorized speaker evidence for decision fixtures | Depends on LV-032's intelligible authorized fixtures |
| LV-031 | Review | P0 | MS-1 | Implement fake-worker supervisor conformance | Current lifecycle regressions require integrated current-tree review |
| LV-032 | Ready | P1 | MS-2 | Prepare authorized intelligible Japanese source/target decision fixtures | RF-008 and LV-001; assign after MS-1 route closes |
| LV-033 | Done | P1 | MS-1 | Complete OpenVoice V2 M2 offline technical adapter | Clean-checkout M2 repair independently reviewed; Supervisor M3 is conditional MS-2 work |
| LV-034 | Planned | P0 | MS-2 | Emit common evidence for shortlisted real candidates | LV-030, LV-032, and reviewed adapters |
| LV-035 | Planned | P0 | MS-6 | Prove selected profile through Extension and real SSH tunnel | MS-2 through MS-5 |
| LV-036 | Planned | P0 | MS-1 | Independently review integrated real-model checkpoint | LV-023 through LV-025, LV-033, and LV-038 |
| LV-037 | Done | P0 | MS-1 | Install six-milestone roadmap and review disposition process | Control-check green and independent Sol re-review found no High/Medium |
| LV-038 | In progress | P0 | MS-1 | Run the current isolated RVC technical profile through a disposable Gateway | EXP-004 single 28-frame generation proves Gateway backpressure over private 25-frame worker credit |
| LV-039 | Planned | P0 | MS-2 | Select primary model and freeze Extension architecture | At least two comparable real candidates |
| LV-040 | Planned | P0 | MS-3 | Tune response, jitter, queue, cancellation, and stability | Frozen LV-039 path |
| LV-041 | Planned | P0 | MS-4 | Verify the real one-client SSH-only security boundary | Frozen MS-3 route and second client shell |
| LV-042 | Planned | P0 | MS-5 | Package personal start/restart/rollback/maintenance operations | MS-4 boundary and release inventory |
| LV-043 | Planned | P0 | MS-6 | Run audible external-client acceptance and freeze personal v1 | LV-035, LV-042, final review |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| LV-036/LV-038 integration | Primary | planning docs, root registries/lock, shared integration, ignored RVC route evidence | Real Gateway route and remaining finding dispositions green |

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

The current batch closes MS-1, not the historical public-production roadmap.
Protocol, Gateway, supervisor, Extension, evaluation, STT, model packs, package
checks, SSH instructions, and multiple real model adapters exist. RVC and
Beatrice have isolated real worker evidence. X-VC and OpenVoice repairs are
complete and under independent review. RVC quality currently fails representative
content preservation, so it is a technical route candidate rather than an
approved voice.

The serial MS-1 frontier is:

1. close RF-001 and adapter/Extension/package independent reviews;
2. rebuild the current RVC technical registry and prove one 28-frame generation
   through a disposable loopback Gateway without exceeding its private 25-frame
   worker credit;
3. verify one packaged SSH server/client setup path without public ingress;
4. run integrated checks, disposition every remaining finding, and commit/push.

Work on public Caddy, full EXP-001/EXP-002 sample counts, population ratings,
TTS, HA, and multi-user identity is explicitly excluded from this batch.
