# Delivery backlog

Status: Active

Only items marked `Ready` may be assigned to a write-capable subagent. The parent
must set an ownership zone before parallel implementation.

| ID | State | Priority | Phase | Deliverable | Evidence / dependency |
|---|---|---:|---:|---|---|
| LV-001 | Review | P0 | 0 | Define and version the 40-utterance Japanese smoke corpus metadata | 40-entry schema-valid corpus; native-speaker review remains |
| LV-002 | Ready | P0 | 0 | Finalize and approve the prompt-only EXP-001 protocol | EXP-001 draft and LV-001 |
| LV-003 | Review | P0 | 0 | Specify deterministic spoken-text normalization cases | Frozen normalization revision is shared by evaluation and STT tests |
| LV-004 | Done | P0 | 0 | Scaffold signal/STT/integrity evaluation package and report contracts | Independent evidence-gate review closed; workspace suite green |
| LV-005 | Review | P0 | 1 | Scaffold Chrome MV3 Extension shell | MV3 shell and Chrome load smoke implemented |
| LV-006 | Review | P0 | 1 | Implement tab capture, Offscreen Document, and native loopback | Real browser topology and bounded capture credits implemented |
| LV-007 | Review | P0 | 1 | Implement generation-aware bounded playout queue | Single playhead, 200 ms native shadow, jitter and cancellation tests pass |
| LV-008 | Planned | P0 | 1 | Add timing trace and loopback experiment | LV-006, LV-007 |
| LV-009 | Review | P1 | 2 | Re-verify streaming VC candidates, licenses, and revisions | Primary-source matrix is review-ready; legal decisions remain explicit |
| LV-010 | Planned | P1 | 2 | Implement common VC adapter and first candidate | LV-009 decision |
| LV-011 | Research | P1 | 3 | Re-verify Japanese streaming TTS candidates and licenses | Phase 1 evidence |
| LV-012 | Planned | P1 | 3 | Implement spoken-text commit and normalization package | LV-003 |
| LV-013 | Planned | P1 | 3 | Implement common TTS adapter and first candidate | LV-011, LV-012 |
| LV-014 | Planned | P1 | 3 | Implement played-text accounting and interruption truncation | Shared state contract |
| LV-015 | Planned | P1 | 4 | Run blinded native / VC / TTS comparison | Phases 2 and 3 gates |
| LV-016 | Planned | P2 | 4 | Run long-session, noise, and DaaS routing tests | LV-015 |
| LV-017 | Planned | P2 | 4 | Record product architecture selection ADR | All Phase 4 evidence |
| LV-018 | Planned | P0 | 0 | Run and analyze EXP-001 without changing its frozen protocol | EXP-001 approved |
| LV-019 | Done | P0 | 1 | Implement protocol v1 frame/control contracts and golden tests under `packages/protocol` | Golden client/frame/server-event contracts pass in the workspace suite |
| LV-020 | Done | P0 | 1 | Implement authenticated gateway, session/generation router, and deterministic profiles under `services/audio` | Independent lifecycle/security review has no open finding |
| LV-021 | Review | P0 | 1 | Configure TLS ingress, one-use tickets, Origin policy, resource limits, and redacted observability | Hardened Caddy/Compose deployment validates; live DNS/ACME check remains external |
| LV-022 | Done | P0 | 1 | Implement isolated worker supervisor, profile registry, warmup/readiness, and GPU budget | 54 worker lifecycle/conformance tests and independent review pass |
| LV-023 | Blocked | P1 | 2 | Integrate RVC v2 as the first isolated real VC profile | Requires approved immutable weights, license record, and authorized target corpus |
| LV-024 | Planned | P1 | 2 | Run X-VC Japanese offline eligibility evaluation before streaming work | LV-004, LV-009, frozen Japanese fixtures |
| LV-025 | Research | P1 | 2 | Resolve Beatrice server-use and dependent-data licensing before integration | Written permission/license record |
| LV-026 | Review | P0 | 1 | Implement Extension WSS client, local exclusive selector, and generation gate | 90 deterministic Extension tests and Chrome load smoke pass |
| LV-027 | Done | P1 | 2 | Define machine-readable candidate model packs and onboarding gates | Four blocked packs enforce license and per-artifact immutability gates |
| LV-028 | Done | P0 | 1 | Implement the EXP-002 remote runner, trace schema, and fault-injection schedule | Eight-case route smoke passes and is explicitly inconclusive for full EXP-002 |
| LV-029 | Done | P0 | 1 | Integrate a revision-pinned Japanese STT runner with provenance and exact-entity output | Full hash-locked runtime closure, provenance, rollback, packaging, and independent review pass; approved Japanese model remains an experiment input |
| LV-030 | Research | P1 | 2 | Select and calibrate an authorized source/target speaker-embedding evaluator | Authorized pilot voices and FR-015 |
| LV-031 | Done | P0 | 1 | Implement deterministic fake-worker adapter conformance under `workers/conformance/` | Crash, stall, timeout, cancel, ordering, restart, and cleanup paths pass |

## Active ownership

| Item | Owner | Exclusive write scope | Stop condition |
|---|---|---|---|
| None | - | - | Integration validation and read-only review are active |

## State definitions

- `Research`: evidence is missing before task shape is stable.
- `Planned`: known work with an unmet dependency.
- `Ready`: bounded, accepted, and safe to assign.
- `In progress`: one named owner and ownership zone are active.
- `Review`: implementation complete; independent evidence pending.
- `Done`: Definition of Done is met and linked.
- `Blocked`: blocker, owner, and next unblock action are recorded.

## Current coordinated batch

The remote-router engineering checkpoint is integrated: protocol, Gateway,
subprocess worker supervision, Extension routing, route smoke, evaluation, STT,
and remote deployment configuration exist and are covered by the root checks.
This is not a Phase 1 evidence pass: the live TLS deployment, audible-tab route,
and scripted turn-count gates have not been collected.

Current reproducible engineering evidence is 320 passing Python tests, 90
passing Extension tests, six buildable Python wheels with packaged schemas and
defaults, and eight passing local route-smoke cases. The route trace remains
explicitly `inconclusive` for EXP-002 because nine required evidence lanes are
uncollected.

The next critical frontier is external-input constrained:

| Frontier | Next work | Blocker or input |
|---|---|---|
| Live route | Deploy `deploy/remote`, load the Extension, and run audible continuity/TLS checks | DNS, Docker host, public certificate |
| First real VC | Promote the RVC pack into an implemented profile | approved weight digest, license record, authorized target corpus |
| Model comparison | Add a second eligible isolated VC worker | candidate-specific Japanese/license gate |
| Full evidence | Render the frozen corpus, run pinned STT and speaker lanes, then execute EXP-002 | authorized audio, approved STT and speaker artifacts |

Implementation, test authoring, and independent Sol review continue in parallel
for distinct scopes, but no agent may convert a missing external approval or
uncollected experiment lane into a software pass.
