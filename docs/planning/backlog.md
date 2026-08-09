# Delivery backlog

Status: Active

The target column refers to the personal-use milestones in
[`roadmap.md`](roadmap.md). `Post-v1` work is not allowed to block MS-1 through
MS-6 unless a new user instruction or ADR changes the boundary. Only `Ready`
items may be assigned to a new write-capable agent; an `In progress` item must
name one owner and ownership zone below.

| ID | State | Priority | Target | Deliverable | Evidence / dependency |
|---|---|---:|---|---|---|
| LV-001 | Review | P1 | MS-3 | Define and version the 40-utterance Japanese smoke corpus metadata | Parallel MS-3 preparation; schema-valid corpus has RF-008 intelligibility weakness |
| LV-002 | Planned | P2 | Post-v1 | Finalize and approve prompt-only EXP-001 | Not required for the personal VC path |
| LV-003 | Review | P1 | Post-v1 | Specify deterministic spoken-text normalization cases | TTS/spoken-text work does not block the VC MVP |
| LV-004 | Done | P0 | MS-1 | Implement signal/content/speaker/integrity/streaming evaluation contracts | Forgery/replay/registry fixes passed 109 tests and independent Sol review |
| LV-005 | Done | P0 | MS-1 | Implement Chrome MV3 Extension shell | Loadability, popup, state, permissions, and current-tree Sol review green |
| LV-006 | Done | P0 | MS-1 | Implement tab capture, Offscreen Document, and native loopback | Real topology, bounded credit, native fallback tests, and Sol review green |
| LV-007 | Done | P0 | MS-1 | Implement generation-aware bounded exclusive playout | One playhead, underflow/cancel/replay tests, and Sol review green |
| LV-008 | Planned | P0 | MS-4 | Add timing trace and loopback stability run | Frozen MS-3 architecture |
| LV-009 | Done | P0 | MS-1 | Verify VC candidates, licenses, artifacts, and revisions | Model matrix and adapter records preserve provenance, uncertainty, and nonselectable boundaries; no legal/product approval claim |
| LV-010 | Done | P0 | MS-1 | Implement common worker-v1 VC boundary and real candidates | RVC, Beatrice, and X-VC reached technical M3 worker smoke; OpenVoice reached bounded offline M2 |
| LV-011 | Research | P2 | Post-v1 | Re-verify Japanese streaming TTS candidates | Re-enter only after an MS-3 architecture decision |
| LV-012 | Planned | P2 | Post-v1 | Implement spoken-text commit and normalization package | TTS path only |
| LV-013 | Planned | P2 | Post-v1 | Implement common TTS adapter and first candidate | LV-011 and LV-012 |
| LV-014 | Planned | P2 | Post-v1 | Implement played-text accounting and TTS interruption | TTS path only |
| LV-015 | Planned | P2 | Post-v1 | Run population native/VC/TTS blind comparison | Not the personal-v1 acceptance test |
| LV-016 | Planned | P1 | MS-5 | Run personal soak, restart, reconnect, and recovery checks | Frozen MS-3 route and MS-4 boundary |
| LV-017 | Planned | P0 | MS-3 | Record primary model and Extension architecture ADR | MS-2 trial results plus comparable evidence and operator decision |
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
| LV-030 | Planned | P1 | MS-3 | Calibrate authorized speaker evidence for decision fixtures | Depends on LV-032; prepare in parallel during MS-2 when possible |
| LV-031 | Done | P0 | MS-1 | Implement fake-worker supervisor conformance | Lifecycle, deadline, crash, ordering, cancellation, and backpressure regressions green |
| LV-032 | Ready | P1 | MS-3 | Prepare authorized intelligible Japanese source/target decision fixtures | Parallel preparation only; RF-008 cannot block the first audible MVP |
| LV-033 | Done | P1 | MS-1 | Complete OpenVoice V2 M2 offline technical adapter | Clean-checkout M2 repair reviewed; MS-2 shows it offline-only and does not require Supervisor M3 |
| LV-034 | Planned | P0 | MS-3 | Emit common evidence for shortlisted real candidates | LV-030, LV-032, MS-2 trial roster, and reviewed adapters |
| LV-035 | Planned | P0 | MS-2 | Integrate all four prepared models through Extension and the SSH route | LV-044 through LV-047, LV-049 through LV-051, and LV-053; unlocks LV-048 |
| LV-036 | Done | P0 | MS-1 | Independently review integrated real-model checkpoint | Final Sol audit found no current-scope High/Medium and approved MS-1 closure |
| LV-037 | Done | P0 | MS-1 | Install six-milestone roadmap and review disposition process | Control-check green and independent Sol re-review found no High/Medium |
| LV-038 | Done | P0 | MS-1 | Run the current isolated RVC technical profile through a disposable Gateway | Clean commit 868ae462: EXP-004 passed 28/28 drain, cancel/stale isolation, and teardown; decision remains inconclusive for quality |
| LV-039 | Planned | P0 | MS-3 | Select primary model and freeze Extension architecture | At least two MS-2 candidates plus common authorized evidence |
| LV-040 | Planned | P0 | MS-4 | Tune response, jitter, queue, cancellation, and stability | Frozen LV-039 path |
| LV-041 | Planned | P0 | MS-4 | Verify the real one-client SSH-only security boundary | Frozen MS-3 route and second client shell |
| LV-042 | Planned | P0 | MS-5 | Package personal start/restart/rollback/maintenance operations | MS-4 boundary and release inventory |
| LV-043 | Planned | P0 | MS-6 | Run audible external-client acceptance and freeze personal v1 | LV-035, LV-042, final review |
| LV-044 | Ready | P0 | MS-2 | Define the versioned safe model-roster schema and authenticated API contract | Separate execution/decision axes; keep `/v1/models` v1 routable-only and add a non-sensitive roster surface |
| LV-045 | Planned | P0 | MS-2 | Show all model states in the Extension and permit technical-only invocation | LV-044; accept `pretrained_voice`, reject authorization-required profiles, support live and buffered modes, preserve native-first identity checks |
| LV-046 | Planned | P0 | MS-2 | Integrate a Beatrice 2 technical Gateway profile and route contract | LV-050; existing M3 evidence, technical/nonselectable, one GPU lease |
| LV-047 | Planned | P0 | MS-2 | Integrate X-VC as a technical live Gateway profile | LV-050; a failed route blocks MS-2 unless the user explicitly changes the four-model roster |
| LV-048 | Planned | P0 | MS-2 | Run EXP-005 actual ChatGPT multi-model Extension MVP over SSH | LV-035, LV-051, LV-054; attempt all four, at least two live audible, force native fallback |
| LV-049 | Ready | P0 | MS-2 | Freeze and execute the minimal SSH-loopback MVP preflight | Remote/client loopback, pinned host key, forwarding-only account/permitopen, token, Origin, ticket, max_sessions=1 |
| LV-050 | Planned | P0 | MS-2 | Generalize shared Gateway worker dispatch, profile validation, and technical pack/evidence binding | LV-044 contract first; model-specific adapters then write only disjoint bridge/profile modules |
| LV-051 | Planned | P0 | MS-2 | Freeze the exact four-model deployment roster after route outcomes | LV-044 through LV-047, LV-050, LV-053; no unavailable entry at close |
| LV-053 | Planned | P0 | MS-2 | Add bounded End-triggered OpenVoice buffered preview invocable from the Extension | LV-044/LV-050; same native fallback, no streaming or latency claim |
| LV-054 | Planned | P0 | MS-2 | Implement and review the EXP-005 metadata runner, schema, and frozen prompt/sample plan | LV-044; clean commit/roster identity and per-model attempt/output/fallback fields |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| None | - | - | Dispatch LV-044, LV-049, and parallel MS-3 fixture preparation |

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

MS-1 is closed. MS-2 now builds the fastest hands-on MVP: an actual ChatGPT voice
tab captured by the Extension, routed over SSH, and heard through multiple real
technical models. Quality selection has moved to MS-3 and cannot delay the first
audible trial.

LV-044, LV-049, and LV-032 are the dependency-correct Ready roots. LV-044 freezes
the safe roster/API contract before LV-050, the Extension UI, and EXP-005 runner
start. LV-050 then removes the shared RVC-only Gateway dispatch bottleneck before
Beatrice, X-VC, and OpenVoice work branches into disjoint model modules. LV-049 prepares
the SSH route independently. After the model leaves pass, LV-051 freezes all
four deployment entries and LV-048 joins the registry, UI, runner, SSH preflight,
Chrome profile, and single GPU lease. LV-032 prepares MS-3 evidence in parallel
but is not on the MS-2 close path.

## MS-2 dispatch plan

| Ready item | Intended ownership zone | Stop condition |
|---|---|---|
| LV-044 | parent-owned roster schema/API and consumer fixtures | Contract exposes safe states for all four models without changing `/v1/models` v1 semantics |
| LV-049 | SSH client/server preflight docs and metadata-only operator fixture | Exact isolated-config preflight is ready for the later Chrome/GPU join |
| LV-032 | authorized fixture metadata zone | MS-3 manifest frozen; never blocks MS-2 |

After LV-044 closes, dispatch LV-045, LV-050, and LV-054. After LV-050 closes,
dispatch LV-046, LV-047, and LV-053 in parallel. Their writers must own separate
Extension, model bridge/profile, and experiment-runner zones; the parent alone
integrates the shared registry.
