# Delivery backlog

Status: Active

Only items marked `Ready` may be assigned to a write-capable subagent. The parent
must set an ownership zone before parallel implementation.

| ID | State | Priority | Phase | Deliverable | Evidence / dependency |
|---|---|---:|---:|---|---|
| LV-001 | Ready | P0 | 0 | Define and version the 40-utterance Japanese smoke corpus metadata | Requirements JP-001 through JP-008 |
| LV-002 | Ready | P0 | 0 | Finalize and approve the prompt-only EXP-001 protocol | EXP-001 draft and LV-001 |
| LV-003 | Planned | P0 | 0 | Specify deterministic spoken-text normalization cases | LV-001 |
| LV-004 | Planned | P0 | 0 | Scaffold evaluation package and aggregate report format | Evaluation plan and schema |
| LV-005 | Planned | P0 | 1 | Scaffold Chrome MV3 Extension shell | Phase 0 gate |
| LV-006 | Planned | P0 | 1 | Implement tab capture, Offscreen Document, and native loopback | LV-005 |
| LV-007 | Planned | P0 | 1 | Implement generation-aware bounded playout queue | Protocol contract |
| LV-008 | Planned | P0 | 1 | Add timing trace and loopback experiment | LV-006, LV-007 |
| LV-009 | Research | P1 | 2 | Re-verify streaming VC candidates, licenses, and revisions | Phase 1 evidence |
| LV-010 | Planned | P1 | 2 | Implement common VC adapter and first candidate | LV-009 decision |
| LV-011 | Research | P1 | 3 | Re-verify Japanese streaming TTS candidates and licenses | Phase 1 evidence |
| LV-012 | Planned | P1 | 3 | Implement spoken-text commit and normalization package | LV-003 |
| LV-013 | Planned | P1 | 3 | Implement common TTS adapter and first candidate | LV-011, LV-012 |
| LV-014 | Planned | P1 | 3 | Implement played-text accounting and interruption truncation | Shared state contract |
| LV-015 | Planned | P1 | 4 | Run blinded native / VC / TTS comparison | Phases 2 and 3 gates |
| LV-016 | Planned | P2 | 4 | Run long-session, noise, and DaaS routing tests | LV-015 |
| LV-017 | Planned | P2 | 4 | Record product architecture selection ADR | All Phase 4 evidence |
| LV-018 | Planned | P0 | 0 | Run and analyze EXP-001 without changing its frozen protocol | EXP-001 approved |

## State definitions

- `Research`: evidence is missing before task shape is stable.
- `Planned`: known work with an unmet dependency.
- `Ready`: bounded, accepted, and safe to assign.
- `In progress`: one named owner and ownership zone are active.
- `Review`: implementation complete; independent evidence pending.
- `Done`: Definition of Done is met and linked.
- `Blocked`: blocker, owner, and next unblock action are recorded.

## Next coordinated batch

The recommended first multi-agent batch is read-heavy:

1. `spec_analyst` checks the smoke-corpus categories against requirements.
2. `experiment_designer` drafts the detailed EXP-001 collection protocol.
3. `research_scout` verifies current native realtime prompting and audio capture
   constraints from primary sources.
4. The parent integrates those results and requests any unresolved product
   decision. Approval happens only after all material TBD fields and numeric
   thresholds are resolved. LV-018 becomes Ready after that approval.
