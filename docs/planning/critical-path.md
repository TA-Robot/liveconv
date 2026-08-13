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
  -> MS-3 hear keepers (existing human RVC, then only train if needed)
  -> MS-4 promote a keeper and freeze architecture
  -> MS-5 responsiveness, SSH baseline, and personal recovery
  -> MS-6 personal-use v1 acceptance
```

[`roadmap.md`](roadmap.md) owns milestone outcomes and gates.
[`lab-operating-model.md`](lab-operating-model.md) owns how quality search
spends time. [`listen-queue.md`](listen-queue.md) is the live Ready board.
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
- false authorization, or false evidence promotion used for a model/release
  decision (promote tier; listen-now audio is not a promotion);
- a reproducible expected-path hang, orphan, unbounded resource use, or inability
  to run the milestone's actual acceptance check.

Quality misses, cold-start cost, offline-only candidates, public deployment,
multi-user operation, production-scale sample counts, HA, and SLA work do not
stop basic technical execution. MS-3 now finds an operator-acceptable voice
through the hearing loop. Missing hashes do not stop a listen-now run.
Tuning and the full SSH security baseline start in MS-5.

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
the technical roster. MS-3 is a hearing loop: drain unheard libraries, listen
to existing human-trained RVC on actual input, and only then train or adapt.
Existing RVC profiles are listen-now candidates, not frozen museum pieces.
MS-4 promotes a keeper; it does not begin with a hash cathedral.

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

## MS-3 hearing-loop frontier

The live board is [`listen-queue.md`](listen-queue.md). Quality search uses
listen-now, then promote. EXP-024's failed validation16 DTW gate stays closed.
EXP-025/026 already completed the bounded 87-pair listen-now training path and
its useful renders; its scope, horizon, and learning-rate axes are closed. Qwen
TTS stays a separate fallback and is not mixed into the human VC corpus.

The active-thread provenance correction removes the 8.17-second local
tongue-twister recording from the `actual ChatGPT` role. Earlier browser-domain
claims from that artifact are superseded. The active join is now:

```text
 EXP-033 fixed 10-row method pilot (complete)
        -> EXP-034 external-speaker check (JVS3 gross loop; no generalization claim)
        -> 52-speaker Common Voice source admission
        -> EXP-035 12-donor breadth at fixed 1,044 updates (complete)
        -> seven disjoint speakers + frozen ten conditions (complete)
        -> EXP-036 official 40/20/40 training-role mix (external regression; stop)
        -> EXP-037 content-safe target-context render (external regression; stop)
        -> EXP-038 speaker-conditioned AdaLN-only LoRA (complete)
        -> seven disjoint-speaker screen (mean improved; one empty-output tradeoff)
        -> EXP-039 twelve new utterances / six heldout speakers (speaker7 regressed)
        -> EXP-040 80% standard / 20% same-target reconstruction (complete)
        -> seven disjoint-speaker screen (non-corrupt; mixed small changes)
        -> EXP-041 twelve new utterances / six heldout speakers (non-corrupt; mixed)
        -> EXP-042 ten frozen audio conditions, especially 20 dB noise (gpu0)
        -> operator hearing when available
```

EXP-035 held target text exposure and 1,044 updates fixed while replacing
EXP-033's three donor speakers repeated four times with twelve distinct donor
speakers in one pass. Its external worst case improved, but base remained
competitive and the fixed noise regression survived; no more donor-count point
is admitted. EXP-036 reused those exact generated pairs and changed only role
assignment; the all-standard adapter remained safer on the external screen, so
role mixing is closed. EXP-037 tested X-VC's otherwise-unused frame condition
with a different Amitaro utterance followed by a zeroed current window; its
external content regression closed that route before training. EXP-038 keeps
the zero condition and all-standard data but adapts only the seven AdaLN
linears directly driven by the global speaker embedding, rather than the 69
attention/FFN linears that also carry content. Its first external set improved
the mean but restored one base-like empty output. EXP-039's twelve new
utterances then rejected speaker7 generalization. EXP-040 returns to control69
and tests 20% same-Amitaro reconstruction as content regularization while
removing EXP-036's 40% reversed donor-target dilution. Training donors and
external evaluation speakers remain disjoint. This stays on the method path
without retrying the closed human87 epoch/LR/scope or EXP-024 DTW axes.

```text
 Unheard on 8878: EXP-033/034/035 / stable public RVC-XVC / EXP-023 Qwen
        |
        +--> operator keep / continue / rejected

 Any EXP-020 continue --> larger actual-input RVC listen
 Any keep -------------> promote pass (hashes, route, review) only then
 All stable VC rejected -> revisit the model/training strategy explicitly
```

EXP-020 and EXP-021 are active listen-now items, not historical side lanes. EXP-021
performed one bounded
gross-rejection render each for the already-installed MeanVC2 and OpenVoice V2
families on the same 8.17-second actual input and the same Runrun reference.
It added no training or parameter sweep, used explicit labels, and can only
reject a family or inform a later separately approved actual-input experiment.

EXP-021's two technical renders are complete and await direct operator review
on port 8878. The historical conditional next step would have been one Seed-VC
render after both failed, but that condition was superseded: EXP-022 has already
used and closed its sole attempt. EXP-021 review cannot authorize another
Seed-VC run or re-open the zero-shot sequence.

The sole admitted EXP-022 attempt passed admission and then failed closed during
its discarded full-source warmup. It published no candidate, cleaned up, and
was not retried with changed settings or a smaller model. That exact attempt is
closed as technical failure evidence.

To test a materially different quality path quickly, EXP-023 rendered one
frozen Qwen3-TTS 1.7B CustomVoice / Ono_Anna candidate for 12 fixed Japanese
texts. All 12 explicit-label 24-kHz outputs passed technical and independent
artifact review and are available on the same fixed port 8878. They remain an
offline diagnostic until the operator records one `continue` or `rejected`
action per text. A continue result can only admit later TTS transport and route
work; it does not satisfy `D0`, EXP-020, interruption, played-text, or end-to-end
gates. A rejected result stops this exact profile without a sampling or model
sweep.

`B0` is one content-addressed artifact. The Gateway loads it, the terminal
launcher verifies it after tunnel setup, and the Extension fetches and binds the
same digest. A direct-worker or terminal render is intake/debug evidence only.
Any identity or behavior mismatch marks the variant `route_parity_failed`, hides
it from the chooser, and stops only that variant until repaired. Route
qualification is performed once per frozen profile. The separate quality screen
uses exact source/output-bound authenticated Gateway renders in the local
listening UI; it does not repeat the fallback probe or claim Extension playout
for each quality comparison.

Bundle activation also requires the exact operator-controlled private
authorization-registry revision. Every public authorization digest must resolve
to an approved, nonexpired record with matching variant, family, profile,
source-material, terms, and external-lineage digests; missing, extra, or mutated
records reject the whole bundle before session creation.
Expiry is evaluated against the Gateway's trusted current UTC at every
activation/restart and again before session creation, never against a bundle's
self-declared creation timestamp.

The historical first wave used youthful-feminine reference/style material
across protocol-v1 audio-to-audio VC families. TTS transport remains deferred
until an accepted ADR defines committed spoken text, transport, interruption,
and played-text accounting. EXP-023 is only a direct offline quality diagnostic
and cannot satisfy the active RVC or route path. One GPU lease is active at a
time, and unbounded checkpoint or training sweeps are not admitted.

The exact 90-render historical artifact retains route evidence, but does not
select a quality winner. Stage 0 uses its one 8.17-second actual source capture
only for plain-label gross rejection. All completed listening libraries remain
on the single fixed port `8878`, with explicit model/configuration labels; no
experiment-specific listener port is opened.

The completed acquisition and failed alignment record is EXP-024 in LV-064.
The 87-pair whole-short inventory from EXP-025 was used for the completed
listen-now training path, not as a hash cathedral. The old X-VC adaptation corpus contained only
eight eSpeak texts and 19.2 seconds of effective training audio and remains
rejected. The replacement corpus has 424 human Hadou source utterances and
424 Amitaro runrun target utterances on the same official ITA IDs, display
text, and kana readings. Both sides are 48 kHz mono PCM16.
The content-alignment gate before fixed 2.4-second X-VC windows was attempted
once on the frozen 16 validation IDs. All 16 IDs were attempted, but fewer than
14 retained an admissible window, so Stage A stopped. The exact retained count
and row reasons are unrecoverable because the runner deleted its in-memory
failure evidence; no retry or threshold change is admitted. Existing human
RVC profiles are listen-now candidates on actual input. They are not retrained
to answer the failed X-VC alignment question.
Clipping made all 400 post-clip norms approximately 5 and slightly improved the
step-96 validation median, but it did not prevent the late validation regression.
EXP-017's short, paired prefix-versus-three-window pilot is complete. Its
update-96 six-window median is about 3% lower for the window variant while the
start-window median is about 1.2% higher, so the numerical evidence is mixed and
does not justify further synthetic-data work.
EXP-018 completed the queue
fallback with only the constant AdamW
learning rate changed from `3e-4` to the upstream-native `1e-4`; its best numeric
validation point moved to update 192 and its late worsening was smaller, while
its rendered checkpoint audio remains historical. None of these paths
is an unbounded sweep or route or product evidence. EXP-019's repaired
one-variable rank-capacity trajectory completed 400 finite updates with exact
EXP-014/018 receipt bindings. Its validation median was lowest at update 192
(`522.0286`) and rose to `575.3562` at update 400; this is diagnostic only. The
separate true cross-arm renderer also completed. It is retained as history rather
than a gate for the next run.

LV-064 has frozen the 424 candidate identities, audited audio integrity, prepared
one machine-ASR pronunciation triage, and frozen disjoint train, validation, and
heldout IDs. The 370-row pronunciation UI remains available; it is not a
listen-now blocker. There is no universal 30-minute gate. The sole
validation16 alignment pilot failed the predeclared retained-ID gate, so the
exact EXP-024 Stage B DTW/window trajectory stays blocked. There is no RVC
retraining, blind mapping, parameter sweep, retry of that gate, or automatic
TTS substitution.

EXP-025's CPU inventory found 87 train and 16 heldout complete short
utterances. The bounded stretch+pad training and its EXP-026 follow-ups are
complete. Stable RVC/X-VC heldout, actual-input, and three-row public-validation
comparisons are published on 8878. Their machine screens reject gross content
failure only; no perceptual winner or promote decision exists. The bounded
stable RVC/X-VC cancellation-recovery comparisons are also published: both
families produced zero stale frames after cancel acknowledgment and fully
drained the next generation. Additional cancel variants and RVC state
decomposition are closed; the RVC post-cancel waveform difference remains an
operator hearing question rather than a new machine-selection axis. With no
second retained actual source or active browser capture, the next distinct
system slice published the current exclusive hard native-fallback transition
at 2.0 seconds for both stable families. Further fallback variants now wait for
hearing; sample discontinuity and auxiliary ASR cannot select an alternative.

## MS-2 through MS-6 joins

| Milestone | Serial join | Parallel preparation |
|---|---|---|
| MS-2 | historical: technical routes -> actual Extension listening -> quality rejection -> scope decision | formal EXP-005 receipt was not retained and no pass is claimed |
| MS-3 | drain stable RVC/X-VC and other unheard 8878 libraries -> operator keep | 370-row pronunciation review is optional; Qwen remains a separate fallback only |
| MS-4 | promote a keeper (identities, route, review) then freeze architecture | retain EXP-024 as a closed DTW failure; do not start MS-4 with a hash cathedral |
| MS-5 | frozen primary -> timing/stability tune -> SSH boundary -> runbook/recovery and soak | queue/jitter/cancel tests, failure injection, auth negatives, diagnostics, maintenance checklist |
| MS-6 | frozen server/client bundle -> external audible session -> final audit and release | release notes, known issues, rollback rehearsal, operator acceptance record |

MS-3 is the hearing loop that produces at least one operator `keep`. The
EXP-024 DTW/window trajectory stays unauthorized. The 87-pair whole-short path
is complete and its closed axes are not rerun. MS-5 never retunes multiple
models in parallel.

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
