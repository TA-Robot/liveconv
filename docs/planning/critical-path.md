# Critical path and parallel delivery

Status: Active

This plan controls execution order. The roadmap controls evidence gates, while
the backlog records issue state. The primary integrator recalculates the Ready
frontier after every green checkpoint and delegates every independent bounded
node that fits the current runtime and resource limits.

## Product critical path

The shortest path to a remotely transformed, measurable Japanese voice is:

```text
F0 foundation checkpoint
  -> F1 gateway-worker SPI freeze
  -> F2 supervisor + fake-worker conformance
  -> F3 Extension/gateway/worker remote-route join
  -> F4 RVC profile integration
  -> F5 frozen multi-model evaluation
```

The evidence path runs in parallel and must join before F5:

```text
E0 40-utterance corpus
  -> E1 normalization + STT provenance + speaker evaluator
  -> E2 trace/fault runner + aggregate report
  -> F5 frozen multi-model evaluation
```

External approval for target voices, weights, licenses, and model revisions is a
separate blocker. It must be pursued in parallel because it can become the real
critical path even when the software path is green.

## Dependency graph

| Node | Backlog work | Depends on | Unlocks |
|---|---|---|---|
| F0 | LV-004, LV-019, LV-020, LV-027 foundation checkpoint | current QA closure | all implementation worktrees from one SHA |
| F1 | Freeze private gateway-worker SPI inside LV-022 | F0 | supervisor and conformance work |
| F2a | LV-022 worker supervisor | F1 | gateway-worker bridge |
| F2b | LV-031 fake-worker conformance | F1 | crash, stall, cancel, and unload proof |
| F3a | LV-005, LV-006, LV-007, LV-026 Extension route | LV-019; shell can start after F0 | remote-route join |
| F3b | LV-021 authenticated TLS ingress | LV-020 and threat brief | remote-route join |
| F3c | LV-028 trace and fault runner | LV-004, LV-019, LV-020 | repeatable route evidence |
| F3 | Extension + gateway + worker route join | F2a, F2b, F3a, F3b, F3c | real model integration |
| E0 | LV-001 smoke corpus | JP-001 through JP-008 | normalization and frozen evaluation |
| E1a | LV-003 deterministic normalization | E0 | content-preservation evaluation |
| E1b | LV-029 pinned Japanese STT | LV-004 and engine approval | content/integrity evidence |
| E1c | LV-030 authorized speaker evaluator | authorized pilot voices | speaker evidence |
| E2 | EXP-002 aggregate route evidence | E0, E1a, E1b, F3c | model comparison |
| F4 | LV-023 RVC integration | F2, F3, approved revision and target | first real VC result |
| F5 | LV-024 plus second eligible model comparison | E2, F4, model-specific gates | Phase 2 decision |

Nodes on the F path receive the first available implementation and test slots.
Evidence and external-approval nodes receive the remaining slots because delaying
their join would only move the bottleneck downstream.

## Three-stage pipeline

Parallelism is demand-driven, not a fixed department chart. For different nodes,
run these stages at the same time:

1. **Test N+1:** a Luna `test_author` writes accepted failing tests and synthetic
   fixtures for the next Ready candidate. It edits tests only.
2. **Implement N:** a Luna implementation worker consumes already accepted tests
   for the current Ready node in an exclusive worktree.
3. **Review N-1:** a Sol `qa_reviewer` at `max` reviews the previous integrated
   checkpoint. Luna output never satisfies independent review.

The primary, running Sol, freezes interfaces, accepts test intent, integrates
commits, triages findings, and advances backlog state. The same agent must not be
the implementation author and independent reviewer for one node.

## Dynamic dispatch

After every merge or blocker change, the primary performs this loop:

1. Mark dependencies satisfied by the new integration SHA.
2. Sort Ready nodes by critical-path position, then by downstream fan-out.
3. Spawn implementation for every independent Ready node with a distinct write
   scope, up to six simultaneous writers.
4. Spawn test authors for the highest-priority Planned nodes whose interfaces are
   accepted and whose tests do not overlap active writers.
5. Spawn Sol reviewers for every checkpoint awaiting review, up to three reviews.
6. Use remaining slots on research or threat work that removes a named blocker.
7. Stop adding writers when two checkpoints are waiting in the merge queue; use
   new capacity for review, repair, or integration instead.

One Codex session requests up to 12 child threads. If the active client exposes a
lower cap, start additional chats in dedicated Git worktrees from the same green
checkpoint SHA. Runtime capacity never changes the dependency order.

## Worktree and merge rules

- One issue, branch, base SHA, and allowed path set per write-capable agent.
- Root manifests, lockfiles, protocol, ADRs, registries, and this plan are owned by
  the primary and merged serially.
- Test-author branches land before the matching implementation branch starts, or
  are explicitly cherry-picked as the implementation base.
- Reviewers inspect the integrated SHA, not an unpublished writer worktree.
- Integrate in dependency order and run focused consumer checks after every leaf.
- Run `make check` after two or three leaves, every shared-contract change, and at
  each checkpoint used as a new worktree base.
- GPU, browser, ports, and mutable model caches use explicit exclusive leases.

## Current dispatch

F0, F1, F2, F3a, F3c, E0, and the software portion of E1b are implemented. The
F3b deployment configuration and fail-closed preflight are implemented; its
remaining join is a live DNS/ACME/WSS deployment plus the audible-tab browser
check. The real model path cannot advance to F4 until an approved RVC revision,
every artifact digest, its license record, and an authorized target corpus are
supplied.

| Pipeline stage | Work that may run now |
|---|---|
| Deploy N | Validate `deploy/remote` on the DNS-owning Docker host and run WSS/Origin smoke |
| Test N+1 | Run user-gesture tab capture, audible no-replay, and 100-interruption scripts |
| Review N-1 | Sol reviews Extension, STT, and deployment checkpoints independently |
| Unblock | Resolve RVC artifacts/voice authorization and LV-030 speaker evaluator approval |

The next green deployment checkpoint unlocks a real F3 route, but it still does
not satisfy Phase 1 sample-count or latency gates. Those remain experiment work,
not implementation assertions.
