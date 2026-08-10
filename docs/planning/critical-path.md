# Personal v1 critical path

Status: Active

Current milestone: **MS-3**. MS-1 closed on 2026-08-09. MS-2 closed by explicit
user scope decision on 2026-08-10 after the real Extension path became usable
but the prepared audio was rejected as unacceptable. The missing EXP-005 receipt
means no formal MS-2 evidence pass is claimed.

The user-delivery path is:

```text
MS-1 executable multi-model lab
  -> MS-2 multi-model Extension MVP
  -> MS-3 young-feminine voice Variant Lab
  -> MS-4 shortlist optimization and architecture freeze
  -> MS-5 responsiveness, SSH baseline, and personal recovery
  -> MS-6 personal-use v1 acceptance
```

[`roadmap.md`](roadmap.md) owns milestone outcomes and gates.
[`backlog.md`](backlog.md) owns work state. Findings are classified by
[`review-triage.md`](review-triage.md). This file owns dependency order,
parallel dispatch, and mutable resource leases.

## What can stop the path

Only these classes stop the active milestone:

- native fallback, exclusive playout, generation isolation, or bounded-queue
  invariant failure in the intended personal workflow;
- credential/private-audio/reference/checkpoint leakage;
- broken loopback plus SSH boundary, authentication, Origin, ticket, artifact
  identity, or worker containment used by personal v1;
- false authorization, false evidence promotion, or evidence corruption used for
  a model/release decision;
- a reproducible expected-path hang, orphan, unbounded resource use, or inability
  to run the milestone's actual acceptance check.

Quality misses, cold-start cost, offline-only candidates, public deployment,
multi-user operation, production-scale sample counts, HA, and SLA work do not
stop basic technical execution. Voice discovery starts in MS-3; shortlist
selection starts in MS-4; tuning and the full SSH security baseline start in
MS-5.

## Model gate vocabulary

These per-model gates are independent of the six `MS-*` user milestones:

| Gate | Required evidence |
|---|---|
| M0 provenance | Official source/model revision, license notes, and all downloaded artifact digests |
| M1 runtime | Isolated pinned environment loads exact artifacts with network disabled |
| M2 transform | Authorized PCM produces finite, decodable, nonidentical output through the real engine |
| M3 worker | Worker v1 start/push/end/cancel/timeout/close and identity binding pass through `WorkerSupervisor` |
| M4 evaluation | Signal, content, speaker, integrity, and cold/warm timing are independently recorded; missing lanes remain unassessed |
| M5 route | Real profile passes Gateway selection, generation, cancellation, fallback, and teardown |
| M6 client | Extension completes a real audible or captured-output run through SSH |

MS-1 needs multiple M2 candidates, at least two M3 adapters, and one M5 route.
It does not require every candidate to reach M4-M6. MS-2 exposed and exercised
the technical roster. MS-3 expands this into immutable voice variants and
shortlists them; MS-4 chooses which one continues. Rejected variants release
their implementation and GPU lanes.

## MS-1 dependency graph

```text
 RVC M0..M4 -----\
 Beatrice M0..M3 --+--> C0 count gate: >=3 M2 and >=2 M3 --\
 X-VC M0..M2 ------+                                         \
 OpenVoice M0..M2 -/     F0 safety/evidence closure ----------+--> P0 package/runtime identity
                                                                    |
                                                       R0 one RVC technical registry
                                                                    |
                                                       R1 real Gateway generation route

 E0 Extension current-tree review ------------------------------\
 D0 one-platform SSH setup review -------------------------------+--> Q0 integrated Sol audit + make check -> MS-1
 R1 real Gateway generation route -------------------------------/
```

Only `(F0 + C0) -> P0 -> R0 -> R1 -> Q0` is serial. `E0` and `D0` are
independent leaves that join at `Q0`. Model work, Extension work, package
checks, documentation, and independent review are parallel. A failing candidate
does not block `C0` once the explicit three-M2/two-M3 cardinality is satisfied.

Backlog mapping: `F0` covers LV-004/LV-029; the MS-3 calibration and fixture
items LV-030/LV-032 are deliberately excluded. `C0` covers LV-009/LV-010 and
the candidate items LV-023 through LV-025/LV-033. `P0` covers LV-005 through
LV-007 plus LV-019/LV-020/LV-022/LV-027/LV-031, `R0/R1` are LV-023/LV-038,
`E0` is LV-026, `D0` is the current-client documentation portion of LV-021, and `Q0` is
LV-036/LV-037.

## MS-2 multi-model MVP frontier

| Lane | Current checkpoint | MS-2 gate | Disposition if it fails |
|---|---|---|---|
| RVC v2 | Exact clean-commit 28-frame Gateway route green; quality failed | Actual ChatGPT-tab attempt | Keep technical/nonselectable; failure must fall back native |
| Beatrice 2 | Exact clean-commit 28-frame Gateway route green | Actual ChatGPT-tab attempt | Record operational result; quality selection waits for MS-3 |
| X-VC | Exact clean-commit 28-frame Gateway route green; quality failed | Actual ChatGPT-tab attempt | Do not promote quality; record the audible result honestly |
| OpenVoice V2 | Exact clean-commit 25-frame Gateway preview green, with output only after End | Actual bounded Extension preview | Keep it explicitly non-live and exclude it from latency/streaming claims |
| Extension | Four-model live/buffered chooser, receipt persistence, failure injection, and 148 tests green | Actual audible ChatGPT tab | Native fallback remains the one-action recovery |
| SSH route | Strict Linux preflight implementation and Sol review green | Execute against the actual client/server pair | Full threat/negative matrix remains MS-4 |
| MS-3 evidence | Fixture and speaker work is Ready | Parallel preparation only | Cannot delay first audible technical MVP |

MS-2 dependency graph:

```text
 R0 safe roster schema + authenticated API contract --+--> U0 Extension live/buffered chooser
                                                       +--> X0 EXP-005 runner/schema/prompt freeze
                                                       +--> G0 generic Gateway dispatch/profile/pack contract

 G0 ---------------------------------------------------+--> RVC technical route compatibility
                                                       +--> Beatrice live profile
                                                       +--> X-VC live profile
                                                       +--> OpenVoice buffered-preview profile

 (four model leaves + R0) -> D0 exact deployment roster freeze, no unavailable entry
 SSH loopback preflight + actual client setup ----------------------------> S0

 (D0 + U0 + X0 + S0) -> B0 actual ChatGPT tab capture
                      -> T0 invoke and attempt all four models sequentially
                      -> A0 >=2 live profiles produce audible changed output
                      -> F0 forced remote failure/native fallback
                      -> Q0 metadata record + make check + Sol review -> MS-2

 MS-3 fixtures/speaker calibration prepare in parallel and do not join Q0.
```

R0, U0, X0, G0, the four model leaves, D0, and the deterministic SSH preflight
are green. The operator reached the actual Extension path but rejected the audio
quality and did not retain the frozen receipt. By active user decision the old
serial join is historical and does not claim an EXP-005 pass.

## MS-3 voice-variant frontier

The selectable unit is an immutable variant profile, not a family name or a
client-supplied speaker/checkpoint parameter. The initial target is 9-12
Extension-listenable variants across at least four families, primarily youthful
feminine Japanese voices. Screening admits at most four variants, and at most two
per family, to the full comparison.

```text
 V0 EXP-006 + candidate catalog + bundle schema --------------------------\
                                                                           +--> B0 immutable deployment bundle
 F0 authorized 10/40-utterance fixtures + source-STT eligibility --------/

 B0 --> P0 per-variant profile/compiler + exact pack/config identity ------\
 B0 --> U0 dynamic Extension family/variant chooser -----------------------+--> R0 route-parity receipts
 first-wave runtimes and authorized voices (gpu0 serial) -----------------/

 R0 + F0 -> S0 all 9-12 protocol-v1 VC variants screened through Gateway -> Extension
 S0 -> L0 preregister <=4 shortlist, <=2/family
 L0 + calibrated speaker/content/integrity lanes -> C0 full 40-utterance plan
 C0 -> MS-3 close and MS-4 shortlist optimization
```

`B0` is one content-addressed artifact. The Gateway loads it, the terminal
launcher verifies it after tunnel setup, and the Extension fetches and binds the
same digest. A direct-worker or terminal render is intake/debug evidence only.
Any identity or behavior mismatch marks the variant `route_parity_failed`, hides
it from the chooser, and stops only that variant until repaired.

Bundle activation also requires the exact operator-controlled private
authorization-registry revision. Every public authorization digest must resolve
to an approved, nonexpired record with matching variant, family, profile,
source-material, terms, and external-lineage digests; missing, extra, or mutated
records reject the whole bundle before session creation.
Expiry is evaluated against the Gateway's trusted current UTC at every
activation/restart and again before session creation, never against a bundle's
self-declared creation timestamp.

The counted first wave uses authorized youthful-feminine reference/style
material across protocol-v1 audio-to-audio VC families. Qwen and CosyVoice TTS
remain a parallel deferred path until an accepted ADR defines committed spoken
text, transport, interruption, and played-text accounting; they cannot satisfy
`S0`. One GPU lease is active at a time, and unbounded checkpoint or training
sweeps are not admitted.

## MS-2 through MS-6 joins

| Milestone | Serial join | Parallel preparation |
|---|---|---|
| MS-2 | historical: technical routes -> actual Extension listening -> quality rejection -> scope decision | formal EXP-005 receipt was not retained and no pass is claimed |
| MS-3 | bundle/catalog -> 9-12 route-qualified protocol-v1 VC variants across >=4 families -> 10-utterance screen -> <=4 shortlist | runtimes, authorized youthful-feminine voices, fixtures, dynamic chooser, parity receipts; optional TTS ADR is off the serial path |
| MS-4 | shortlist -> common 40-utterance evidence -> bounded tuning -> primary/fallback or no release -> ADR | blinded listening package, STT/speaker/integrity checks |
| MS-5 | frozen primary -> timing/stability tune -> SSH boundary -> runbook/recovery and soak | queue/jitter/cancel tests, failure injection, auth negatives, diagnostics, maintenance checklist |
| MS-6 | frozen server/client bundle -> external audible session -> final audit and release | release notes, known issues, rollback rehearsal, operator acceptance record |

MS-3 is the broad but bounded discovery point. It narrows 9-12 protocol-v1 VC
variants to four or fewer. MS-4 is the largest scope-reduction point and freezes one primary;
after that, alternate writers stop unless a named issue can change the decision
inside a short timebox. MS-5 never retunes multiple models in parallel.

## Two-tier agent schedule

The built-in subagent API has its own active-thread limit. That is not the
repository development limit. Overflow work runs through
[`scripts/codex-pool.sh`](../development/external-codex-pool.md) in detached tmux
sessions. The pool's supported repository ceiling is 32, and a regression proves
that the shared ownership lock is held only for state transitions rather than a
whole Codex run.

Capacity is filled by independent Ready work, not by a fixed target count:

| Lane | Typical concurrent slots | Admission rule |
|---|---:|---|
| Primary integration | 1 | Owns shared contracts, planning, registries, root lock, merge, and dispositions |
| Disjoint implementation | Up to 6 | One issue, one ownership zone, one stop condition |
| Independent Sol review | Up to 12 | Read-only and pointed at a stable checkpoint or disjoint current zone |
| Test/evidence/reproduction | Up to 6 | No mutable GPU/browser/port/artifact collision |
| Research/docs | Remaining host capacity | Must remove a named milestone blocker or complete a named deliverable |

Rules:

- Luna is suitable for bounded implementation, tests, fixtures, and repeatable
  execution. Sol performs every independent correctness/evidence/security gate.
- More agents do not justify overlapping writers. Read-only review can overlap
  only when the reviewed zone is stable or the review is explicitly provisional.
- The primary keeps at most two completed checkpoints waiting for integration.
  When that queue is full, start reviewers and fixes instead of more writers.
- A subagent reports at each model M-gate or milestone checkpoint; it does not
  hold a slot while waiting for an unrelated external approval.
- All agents preserve unrelated changes and never read the ignored file `key`.

## Resource leases

| Lease | Capacity | Owners |
|---|---:|---|
| `gpu0` | 1 real model load/train/benchmark | one model/evidence runner at a time |
| `chrome-profile` | 1 mutable browser profile/debug port | one Extension smoke at a time |
| `gateway:8765` | 1 long-lived local development Gateway | personal route; disposable tests use alternate ports |
| `gateway:8766+` | 1 per declared port | one disposable real-model route runner |
| model artifact directory | 1 writer | matching adapter owner; all other lanes read-only |
| root manifests/lock/planning | 1 writer | primary integrator |

Agents waiting for a lease continue CPU tests, docs, package checks, or read-only
review. They do not idle while occupying the scarce resource.

## Finding-to-work dispatch

When review returns:

1. Reproduce or reject the finding within two hours.
2. Apply the four-way disposition in `review-triage.md`.
3. For `fix-now`, assign one disjoint owner plus a regression and stop condition.
4. For `scheduled`, create/update the named milestone issue and keep the current
   merge moving.
5. For `accepted-risk`, record the trusted-user exposure, detection, recovery,
   and approver.
6. For `out-of-scope`, link post-v1 or the rejected architecture and stop work.
7. Recompute only dependencies affected by that decision; do not restart every
   review lane.

No current-scope High may cross a milestone. A Medium can cross when its issue
makes the interim risk operationally bounded. Low polish never consumes the
serial critical path by default.

## Checkpoint rhythm

At every green leaf:

1. run focused success/failure tests and diff checks;
2. enqueue one Sol review while the next independent implementation proceeds;
3. integrate in dependency order;
4. run consumer tests for shared-contract changes;
5. run `make check` after two or three leaves and at every milestone;
6. update the ledger and Ready frontier immediately;
7. commit/push a coherent checkpoint instead of accumulating an opaque mega-diff.

MS-2 combines a real browser, one GPU lease, and SSH for the first technical MVP.
MS-6 repeats that combined route with the frozen release and longer personal-use
acceptance. Intermediate milestones use only the real resources their gate needs.
