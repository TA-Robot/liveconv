# Product requirements

Status: Draft

## Functional requirements

| ID | Requirement | Initial acceptance evidence |
|---|---|---|
| FR-001 | A user can explicitly start and stop capture of the selected tab or supported realtime session. | Browser integration test and visible session state |
| FR-002 | The system provides an immediate native-audio bypass when transformation is disabled, unavailable, or unhealthy. | Fault-injection test with uninterrupted fallback |
| FR-003 | The evaluation harness can route a frozen input through native, VC, and external-TTS variants. | One command produces comparable run metadata |
| FR-004 | A VC adapter can receive source PCM plus an authorized target-voice identifier and return timestamped PCM. | Contract test and one controlled experiment |
| FR-005 | A TTS adapter can receive committed spoken text plus a voice identifier and stream timestamped PCM. | Contract test and one controlled experiment |
| FR-006 | Every response generation carries a generation ID; stale queued audio is discarded after interruption or cancellation. | Automated stale-generation and queue-clear tests |
| FR-007 | Display text and spoken text are stored separately, with deterministic normalization for configured Japanese operational formats. | Table-driven tests for every supported format |
| FR-008 | The system records capture, transport, buffering, model, synthesis, and playout timing without recording sensitive content by default. | Trace fixture and timing report |
| FR-009 | Model-specific state is isolated behind adapters and does not change the browser-to-service control contract. | Adapter conformance tests |
| FR-010 | Experiment runs record code commit, environment, model revision, configuration, fixtures, metrics, failures, and external artifact locations. | Schema-valid experiment result |
| FR-011 | Original and transformed paths cannot be audible at the same time unless an explicit comparison mode is active. | Audio-routing state test |
| FR-012 | A user can distinguish native, VC, and TTS mode and can return to native mode in one action. | Browser flow test |

## Non-functional requirements

The following values are Phase 1-3 proof-of-concept targets, not claims about an
existing implementation.

| ID | Requirement | Target |
|---|---|---:|
| NFR-001 | VC added latency after warmup | P50 <= 250 ms; P95 <= 400 ms |
| NFR-002 | External-TTS time to first audible output | P50 <= 600 ms; P95 <= 900 ms |
| NFR-003 | Playback stop after user interruption | P95 <= 150 ms |
| NFR-004 | Turns with a click, gap, duplicated segment, or queue stall | < 0.5% in the frozen evaluation run |
| NFR-005 | Timing observability | Monotonic timestamp at every process boundary |
| NFR-006 | Queue safety | Every queue is bounded and has documented overflow behavior |
| NFR-007 | Privacy | No raw user audio retained by default; no secret or private audio in Git |
| NFR-008 | Reproducibility | A second operator can reproduce aggregate results from tracked metadata and authorized artifacts |
| NFR-009 | Browser resilience | Extension failure does not break the native conversation path |
| NFR-010 | Accessibility | Core controls are keyboard reachable and have programmatic labels |

### Measurement definitions

- `VC added latency` is measured on paired fixtures as transformed end-to-end
  capture-to-playout latency minus native loopback capture-to-playout latency in
  the same environment. Report the paired distribution, not the difference of two
  unrelated best runs.
- `External-TTS time to first audible output` begins when the application receives
  the first response-text delta and ends when the first non-silent synthesized
  sample reaches playout. Also report text-commit-to-playout separately.
- `Playback stop` begins at the application's interruption detection timestamp and
  ends at the final audible sample from the canceled generation.
- For NFR-004, the numerator is the number of eligible completed turns with one or
  more verified click, gap, duplicate, stall, or clipping defect. The denominator
  is all eligible completed turns. Report exclusions and count each affected turn
  once for the aggregate rate, with defect categories reported separately.
- Latency thresholds apply after the preregistered warmup. Report P50, P95, sample
  count, environment, and exclusion rules.

## Japanese speech requirements

| ID | Category | Expected behavior |
|---|---|---|
| JP-001 | Telephone numbers | Read digits deterministically and pause at configured groups. |
| JP-002 | Dates and times | Resolve Japanese readings using explicit context and deterministic rules. |
| JP-003 | Money and units | Expand symbols and units to unambiguous spoken forms. |
| JP-004 | Addresses | Apply registered readings for administrative divisions, blocks, and building names. |
| JP-005 | Identifiers | Spell configured Latin letters, digits, and symbols without silent omission. |
| JP-006 | Proper nouns | Use a versioned, domain-scoped pronunciation dictionary. |
| JP-007 | Prosody | Avoid English stress timing and preserve natural Japanese mora and phrase boundaries. |
| JP-008 | Code switching | Do not change the response language because a Japanese sentence contains a name or short foreign term. |

## Governance requirements

- GOV-001: A target voice has an owner, authorization record, permitted purpose,
  retention policy, and deletion path.
- GOV-002: Raw recordings, embeddings, indexes, and checkpoints are classified as
  sensitive artifacts.
- GOV-003: Evaluation reports identify whether fixtures are synthetic,
  redistributable, internal, or restricted.
- GOV-004: User-visible prototypes disclose that transformed or synthesized audio
  is generated.
- GOV-005: Production candidates use authenticated and encrypted transport.

## Requirement change process

Change a requirement only with a linked issue or ADR. When a measured target is
unreachable, record the experiment and tradeoff before revising the target.
