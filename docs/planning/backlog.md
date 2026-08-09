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
| LV-035 | Review | P0 | MS-2 | Integrate all four prepared models through Extension and the SSH route | Four exact technical routes and the Extension integration are green; the actual client SSH/ChatGPT join remains LV-048 |
| LV-036 | Done | P0 | MS-1 | Independently review integrated real-model checkpoint | Final Sol audit found no current-scope High/Medium and approved MS-1 closure |
| LV-037 | Done | P0 | MS-1 | Install six-milestone roadmap and review disposition process | Control-check green and independent Sol re-review found no High/Medium |
| LV-038 | Done | P0 | MS-1 | Run the current isolated RVC technical profile through a disposable Gateway | Clean commit 868ae462: EXP-004 passed 28/28 drain, cancel/stale isolation, and teardown; decision remains inconclusive for quality |
| LV-039 | Planned | P0 | MS-3 | Select primary model and freeze Extension architecture | At least two MS-2 candidates plus common authorized evidence |
| LV-040 | Planned | P0 | MS-4 | Tune response, jitter, queue, cancellation, and stability | Frozen LV-039 path |
| LV-041 | Planned | P0 | MS-4 | Verify the real one-client SSH-only security boundary | Frozen MS-3 route and second client shell |
| LV-042 | Planned | P0 | MS-5 | Package personal start/restart/rollback/maintenance operations | MS-4 boundary and release inventory |
| LV-043 | Planned | P0 | MS-6 | Run audible external-client acceptance and freeze personal v1 | LV-035, LV-042, final review |
| LV-044 | Done | P0 | MS-2 | Define the versioned safe model-roster schema and authenticated API contract | Exact-four schema/API, pack identity binding, package resources, and Sol review green |
| LV-045 | Done | P0 | MS-2 | Show all model states in the Extension and permit technical-only invocation | Four-model chooser, live/buffered modes, native-first operation, race regressions, and 148 Extension tests green |
| LV-046 | Done | P0 | MS-2 | Integrate a Beatrice 2 technical Gateway profile and route contract | Exact technical profile completed a clean-commit 28-frame Gateway route; no quality claim |
| LV-047 | Done | P0 | MS-2 | Integrate X-VC as a technical live Gateway profile | Exact technical profile completed a clean-commit 28-frame Gateway route; quality-failed status remains visible |
| LV-048 | Ready | P0 | MS-2 | Run EXP-005 actual ChatGPT multi-model Extension MVP over SSH | Sole MS-2 serial gate: operator client, audible authenticated tab, four attempts, two live audible results, and forced native fallback |
| LV-049 | Review | P0 | MS-2 | Freeze and execute the minimal SSH-loopback MVP preflight | Script, 47 deterministic checks, and Sol review are green; execute it against the operator's actual client/server pair in LV-048 |
| LV-050 | Done | P0 | MS-2 | Generalize shared Gateway worker dispatch, profile validation, and technical pack/evidence binding | Static exact-pack registrations, capacity invariants, injection negatives, and Sol review green |
| LV-051 | Done | P0 | MS-2 | Freeze the exact four-model deployment roster after route outcomes | Generated registry is byte-stable and exposes three live trials plus one buffered preview with exact identities |
| LV-053 | Done | P0 | MS-2 | Add bounded End-triggered OpenVoice buffered preview invocable from the Extension | Actual 25-frame Gateway route emitted no output before End and passed cancel/stale/cleanup; no streaming claim |
| LV-054 | Done | P0 | MS-2 | Implement and review the EXP-005 metadata runner, schema, and frozen prompt/sample plan | Runtime receipt, separate manual judgments, fifth failure probe, persistence, strict identity checks, and Sol review green |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| None | - | - | LV-048 is Ready and begins when the operator supplies the external Chrome/SSH session |

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

MS-1 is closed. MS-2 implementation and server-side execution are complete: the
exact four-model registry, Extension chooser, receipt producer, SSH preflight,
and static adapter dispatch passed the full repository checks and independent
review. On clean commit `365e2a4`, RVC, Beatrice 2, and X-VC each completed a
28-frame live technical Gateway route; OpenVoice completed a 25-frame bounded
preview with no output before End. All four passed cancellation, stale-output,
and cleanup checks. These are execution results, not quality selections.

LV-048 is now the only MS-2 Ready item and the only serial close gate. It must run
on the operator's actual client because this workspace has neither their
authenticated audible ChatGPT tab nor their SSH client identity. LV-032 may
prepare MS-3 evidence in parallel but cannot delay this hands-on trial.

## MS-2 dispatch plan

| Ready item | Intended ownership zone | Stop condition |
|---|---|---|
| LV-048 | operator client plus parent-owned evidence join | Actual audible ChatGPT tab, exact SSH preflight, four attempts, two live audible changes, OpenVoice preview, and forced native fallback are recorded |
| LV-032 | authorized fixture metadata zone | MS-3 manifest frozen; never blocks MS-2 |

Do not reopen completed model or shared-contract work for quality tuning during
LV-048. Record poor audio or an honest model failure in EXP-005 and defer model
selection and comparison to MS-3.
