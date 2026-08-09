# Personal v1 critical path

Status: Active

The user-delivery path is:

```text
MS-1 executable multi-model lab
  -> MS-2 candidate and Extension architecture freeze
  -> MS-3 responsiveness and route stability
  -> MS-4 SSH-only security baseline
  -> MS-5 personal operations and recovery
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
stop MS-1. They are scheduled to MS-2/MS-3 or post-v1.

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
It does not require every candidate to reach M4-M6. MS-2 chooses which one
continues; rejected candidates release their implementation and GPU lanes.

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

Backlog mapping: `F0` covers LV-004/LV-029; the MS-2 calibration and fixture
items LV-030/LV-032 are deliberately excluded. `C0` covers LV-009/LV-010 and
the candidate items LV-023 through LV-025/LV-033. `P0` covers LV-005 through
LV-007 plus LV-019/LV-020/LV-022/LV-027/LV-031, `R0/R1` are LV-023/LV-038,
`E0` is LV-026, `D0` is the current-client documentation portion of LV-021, and `Q0` is
LV-036/LV-037.

## Current MS-1 frontier

| Lane | Current checkpoint | Next gate | Disposition if it fails |
|---|---|---|---|
| Foundation | False-promotion, cross-render replay, schema, STT, and authorization repairs Sol-green | F0 closed | Reopen only for a new current-scope High |
| RVC v2 | Content-addressed M3/M4 technical worker, network denial, and profile load green; content CER fails | R1 | Keep technical/nonselectable; run one exact route, then compare in MS-2 |
| Beatrice 2 | Real isolated worker and full installed/runtime identity independently reviewed | M3 closed | Keep technical/nonselectable; product gates remain blocked |
| X-VC | Real transform and failed-quality evidence exist; full installed-runtime M3 identity remains incomplete | M2 technical failure; revisit only if shortlisted in MS-2 | Preserve failed/nonselectable result; do not block RVC route |
| OpenVoice V2 | Real Japanese whole-file transform and offline runtime identity are green; no Supervisor evidence | M2 offline comparator; revisit M3 only if shortlisted in MS-2 | Retain offline/nonselectable; never put on streaming route v1 |
| Extension | MV3 capture/playout/control and restart/underflow/config repairs Sol-green | E0 closed | Audible real-tab run remains MS-6 |
| Packaging | Nine workspace wheels/sdists, anchored resources, and isolated imports green | P0 closed | Reopen only for a reproducibility blocker |
| External pool | Concurrent runner and exact symlink repair re-reviewed | not an MS-1 product gate | Fall back to built-in agents or direct tmux immediately |

The immediate serial work is:

1. close F0 and current adapter reviews;
2. rebuild and validate the isolated RVC technical registry against the current
   worker wheel, runtime, network isolation, artifacts, pack, and evidence
   digests;
3. run a disposable loopback Gateway with technical profiles enabled and
   `max_sessions=1` through one paced 28-frame generation, private 25-frame
   Supervisor backpressure, partial-batch drain, cancel, fallback/teardown, and
   readiness checks;
4. record the SSH server/profile setup without publishing artifacts or secrets;
5. run the integrated gate and close or schedule review findings.

Public Caddy DNS/ACME, full blinded experiments, TTS, all-model Gateway switching,
and an audible external Chrome tab are not in this MS-1 serial list.

## MS-2 through MS-6 joins

| Milestone | Serial join | Parallel preparation |
|---|---|---|
| MS-2 | intelligible authorized decision fixtures -> common evidence -> model/Extension ADR | candidate offline renders, operator listening setup, STT/speaker/integrity checks |
| MS-3 | frozen primary profile -> measured bottleneck -> one tuned configuration -> stability gate | queue tests, jitter/cancel tests, latency tracing, failure injection, soak harness |
| MS-4 | frozen route -> SSH threat boundary -> real second-shell tunnel check | docs validation, auth/origin/ticket negatives, firewall/account checks, secret/log scan |
| MS-5 | release inventory -> start/restart/rollback runbook -> recovery and soak gate | actual client-platform docs, diagnostics, cleanup, maintenance checklist; other OS notes are best-effort |
| MS-6 | frozen server/client bundle -> external audible session -> final audit and release | release notes, known issues, rollback rehearsal, operator acceptance record |

MS-2 is the largest scope-reduction point. Once a primary is selected, alternate
model writers stop unless their named issue can change the decision inside a
short timebox. MS-3 never retunes multiple models in parallel.

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

At MS-1 through MS-5, real browser/GPU/SSH evidence is scoped to that milestone.
Only MS-6 combines all three into the final personal-use acceptance.
