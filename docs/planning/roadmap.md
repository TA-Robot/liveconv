# Roadmap and phase gates

Status: Active

Progress is gate-driven. Dates may be added later, but no phase advances because
time elapsed or a demo looked promising.

Every gate uses the frozen experiment decision rule and the measurement
definitions in `docs/product/requirements.md`. A gate is not satisfied by a demo,
an average without its distribution, or a result collected before approval.

## Execution overlay

Phase gates constrain evidence claims, but independent engineering work is
scheduled by `docs/planning/critical-path.md`. After every green checkpoint, the
primary recalculates the Ready frontier and delegates all independent nodes that
fit exclusive write scopes and resource leases.

Implementation of the current node, test authoring for the next node, and Sol
review of the previous integrated node run concurrently. Work may prepare a later
phase without claiming its result; no parallel schedule can bypass a prerequisite
gate or external authorization.

Engineering checkpoint (2026-08-09): the deterministic remote-router stack is
implemented and testable end to end with passthrough and gain profiles. Phase 0
and Phase 1 remain evidence-open until authorized recordings, full sample counts,
live TLS, audible continuity, and preregistered measurements are collected.

## Phase 0: Native baseline

Deliver:

- versioned Japanese smoke corpus
- native realtime recordings under authorized storage
- prompt-only Japanese baseline
- deterministic normalization specification
- timing and rating harness skeleton

Gate:

- the smoke manifest contains exactly 40 versioned utterances and meets every
  category minimum in `docs/experiments/evaluation.md`
- the deterministic normalization specification exists, identifies its version,
  covers JP-001 through JP-006, and passes table-driven expected-spoken-text tests
- the timing and rating harness runs one canonical fixture end to end and emits
  schema-valid run metadata with monotonic boundary timestamps and blinded labels
- EXP-001 was approved before collection, contains no material `TBD`, and is
  analyzed with at least three renders per fixture per variant (240 eligible
  renders before exclusions)
- every latency variant has at least 30 eligible post-warmup samples and reports
  P50, P95, environment, and exclusions
- the preregistered numeric preference, correctness, latency, and language-
  stability decision thresholds have an explicit pass, fail, or inconclusive
  outcome
- dominant defect categories are ranked from aggregate results and linked failure
  examples
- the artifact inventory accounts for every produced render; each entry has an
  authorization class, access-controlled locator, retention deadline, checksum,
  and tested deletion owner, and no artifact-policy field remains `TBD`

## Phase 1: Audio router without a model

Deliver:

- Chrome MV3 capture after explicit action
- Offscreen Document and AudioWorklet loopback
- native, loopback, and bypass modes
- sequence, timestamp, and generation tracking
- bounded jitter buffer and cancellation
- no double-playback path
- authenticated remote session gateway and versioned HTTP/WSS PCM contract
- curated profile registry with passthrough and deterministic DSP profiles
- generation-bound model selection and worker adapter contract

Gate:

- zero stale-generation frames play in 100 scripted interruptions
- zero simultaneous native/transformed paths occur in 100 scripted mode changes
- at least 200 eligible loopback turns meet NFR-004, with P50/P95 added latency
  and explicit exclusions reported
- all injected capture and gateway failures return to audible bypass without an
  unbounded queue or unrecoverable session
- passthrough preserves PCM payloads across the remote route, deterministic gain
  is sample-different but rejected as meaningful voice transformation, and both
  retain valid frame sequence and content fixtures
- profile switching succeeds only between generations; 100 illegal or stale
  switching cases produce zero accepted old-pipeline frames
- TLS/auth/ticket/Origin tests satisfy NFR-011 outside loopback, and injected
  worker crashes satisfy NFR-012

## Phase 2: Multi-model VC lab

Deliver:

- at least two isolated real VC profile candidates selected through current
  primary-source and license research
- authorized target-voice preparation
- at least one streaming integration with measured warmup and steady state
- offline frozen-fixture results for every selectable real profile
- native versus VC and cross-model blind evaluation

Gate:

- VC meets NFR-001 and NFR-004 on the frozen set
- interruption-to-audible-stop meets NFR-003 on at least 100 scripted
  interruptions, with no stale-generation playback
- every injected extension, gateway, and VC failure preserves or restores the
  native path as required by NFR-009
- zero stale-generation frames play in 100 scripted interruptions
- blinded Japanese-quality and voice-similarity results are reported separately
  and satisfy the preregistered decision rule
- code, weight, and data licenses are recorded, and every voice artifact satisfies
  GOV-001 through GOV-003
- every real profile independently passes adapter conformance, signal-change,
  content-preservation, speaker-evidence, and integrity lanes; a missing lane is
  `inconclusive`, not a pass
- selecting, warming, evicting, and reselecting each profile leaves the gateway
  healthy and keeps measured VRAM below its preregistered budget

## Phase 3: First external TTS

Deliver:

- response text commit state
- deterministic Japanese normalization and pronunciation dictionary
- one TTS adapter selected through current research
- synthesis queue, played-text accounting, and interruption cancellation
- native versus VC versus TTS blind evaluation

Gate:

- operational formats meet the preregistered exact-reading thresholds for every
  JP-001 through JP-006 slice, with no high-consequence identifier omission
- blinded native-speaker ratings meet the preregistered JP-007 prosody threshold,
  and every JP-008 code-switching slice meets its language-stability threshold
- response start meets NFR-002, interruption meets NFR-003, and integrity meets
  NFR-004 on the frozen set
- zero of 100 scripted interruptions retain unheard text as played conversation
  state or play a stale-generation frame
- all core mode, bypass, start, stop, and interruption controls satisfy NFR-010 in
  automated keyboard and accessible-name checks plus one manual screen-reader pass

## Phase 4: Candidate A/B and architecture decision

Deliver:

- at least one meaningful alternate candidate for the winning path
- long-conversation, noise, and DaaS tests
- cost and deployment profile
- architecture ADR selecting VC, TTS, hybrid, or native-only for the next product

Gate:

- a product-specific winner passes its preregistered blinded quality rule and all
  applicable NFR-001 through NFR-013 guardrails
- the long-session evaluation contains at least 20 sessions of 5-10 minutes and
  reports failures, memory growth, interruption, and quality slices
- residual risks have owners and mitigations

## Phase 5: Supported production integration

Deliver:

- supported realtime API integration
- application-owned conversation and playout state
- authenticated deployment and secrets management
- telemetry, retention, incident response, and rollback
- removal of production DOM dependence

Gate:

- security and privacy review has no unresolved High finding
- load, failover, and rollback tests meet preregistered service objectives
- operational owner accepts runbooks and service objectives
- release accessibility checks demonstrate NFR-010 with keyboard-only operation,
  programmatic labels, focus visibility, and no unresolved critical blocker
