# Review finding triage

Status: Active process

This record prevents review from turning every possible improvement into an
immediate release blocker. It applies to code review, security review, experiment
review, browser checks, model evidence, documentation review, and package audits.
The target roadmap is the six-milestone personal SSH-use plan in
[`roadmap.md`](roadmap.md).

## Four dispositions

Every High or Medium finding receives exactly one disposition within the same
integration checkpoint:

| Disposition | Meaning | Required record |
|---|---|---|
| `fix-now` | It is necessary to complete or truthfully judge an explicit current-milestone deliverable. | Owner, ownership zone, regression, stop condition, independent re-review |
| `scheduled` | It is real but belongs to a named later milestone. | Target `MS-*`, impact until then, detection/workaround, acceptance evidence |
| `accepted-risk` | The current personal-use boundary makes the risk tolerable through MS-6. | Named operator/owner, reason, exposure boundary, detection and recovery |
| `out-of-scope` | It belongs to post-v1 work or a rejected architecture. | Explicit future scope or rejection reason; no silent deletion |

`TODO`, `later`, and `non-blocking` without one of these records are invalid
dispositions. A reviewer proposes severity and impact. The primary integrator
owns disposition and milestone placement. The implementation author does not
self-approve an accepted risk.

## Stop-the-line conditions

A finding is `fix-now` regardless of estimated effort when it can occur in the
current milestone's intended workflow and does any of the following:

- removes or delays native fallback so the conversation becomes inaudible;
- permits accidental native/transformed double playback or stale-generation
  playback;
- leaks a bearer, ticket, private/reference audio, embedding, checkpoint, or raw
  user content;
- breaks the loopback plus SSH boundary, authentication, exact Origin, or worker
  process containment used by personal v1;
- accepts unbounded input, output, process, memory, disk, or wait behavior from an
  expected client/worker path;
- corrupts or falsely promotes the evidence used to choose a model or release;
- can orphan a worker/session after the documented stop/restart path;
- prevents the current milestone's required real run, package, or rollback from
  being reproduced.

A theoretical issue outside the frozen personal workflow is not automatically a
stop-the-line issue merely because the same code could later become public.
Severity and ease of repair do not determine milestone placement. A High that
cannot affect the active workflow is scheduled or out of scope; a nearby small
cleanup is not `fix-now` unless leaving it open can block or falsify the gate.

## Scheduling defaults

Use these defaults unless a finding's evidence justifies a different decision:

| Finding class | Default disposition |
|---|---|
| Current audio, privacy, authorization, evidence, boundedness, or SSH-boundary invariant | `fix-now` |
| Current milestone correctness defect with a focused fix of at most one owner-day | `fix-now` |
| Model quality after basic execution is proven | `scheduled` to MS-3 |
| Latency or route stability after a model is selected | `scheduled` to MS-4 |
| SSH account, token, Origin, loopback, or artifact hardening | minimum execution boundary in MS-2; full negative/security gate in MS-4 |
| Start/restart/rollback/diagnostic/soak weakness | `scheduled` to MS-5 |
| First audible external-client/multi-model gap | `fix-now` in MS-2; frozen-release acceptance repeats in MS-6 |
| Public TLS, DNS, Internet ingress, multi-user identity, HA, autoscaling, SLA, enterprise observability | `out-of-scope` through MS-6 |
| TTS, population-level blind ratings, publication-quality studies | `out-of-scope` unless MS-3 explicitly selects that path |
| Cosmetic, refactor, theoretical portability, or unsupported-platform Low | issue or note; never a milestone blocker alone |

## Time and review budgets

- A review starts only when a plausible result can change a named decision due in
  the active milestone. Its brief states the decision, possible outcomes, and the
  action taken for each. If every outcome leads to the same current action, the
  review is unnecessary and must not run.
- Reproduction is timeboxed to two hours. If no deterministic reproduction or
  violated contract is established, record the uncertainty and schedule a
  narrower investigation instead of holding the merge queue.
- A `fix-now` implementation is normally bounded to one owner-day. Larger work is
  split into the smallest current-milestone safety fix plus a scheduled follow-up.
- Each checkpoint receives one independent Sol review and one repair/re-review
  cycle. A new High in current scope reopens it. A new Medium or Low after that
  cycle is scheduled or accepted unless it meets a stop-the-line condition.
- No more than two completed implementation checkpoints wait for integration.
  When the queue is full, new capacity goes to review, fixes, tests, or integration.
- GPU, Chrome profile, fixed port, and mutable artifact directories are exclusive
  leases. CPU-only tests, docs, packaging, and read-only reviews remain parallel.
- Passing tests are necessary evidence, not permission to broaden the milestone.
  Reviewers must judge against the current acceptance gate and explicit non-scope.
- A reviewer must name the exact active-milestone deliverable that a proposed
  `fix-now` finding blocks or could falsely pass. Without that link, the primary
  dispositions it later and continues current work.

## Issue record

Use the GitHub `Review finding` issue form or an equivalent private record when
sensitive details cannot be public. Every record contains:

```text
finding_id:
source_review:
severity: high | medium | low
affected_invariant_or_gate:
current_reproduction:
disposition: fix-now | scheduled | accepted-risk | out-of-scope
target: MS-1 | MS-2 | MS-3 | MS-4 | MS-5 | MS-6 | post-v1
owner:
ownership_zone:
impact_until_target:
detection_or_workaround:
acceptance_evidence:
status: open | implementing | review | closed
```

Never attach secrets, private audio, reference voices, model weights, raw
credential-bearing logs, or host-specific access details to a public issue.

## Current ledger

This table records the present integration batch. Update it when a reviewer
returns a concrete result; do not keep completed agents listed as owners.

| ID | Sev. | Finding or gap | Disposition / target | Owner | Interim impact and detection | Status / acceptance evidence |
|---|---|---|---|---|---|---|
| RF-001 | High | Caller-authored or mutable evidence could falsely promote a render | `fix-now` / MS-1 | Foundation owner | No render pass was trusted before exact negative tests passed | Closed: 109 focused tests, adversarial matrix, and Sol re-review found no High/Medium |
| RF-002 | High | Extension restart/underflow/config races broke fallback invariants | `fix-now` / MS-1 | Extension owner | Node harness detects route/state divergence; native remains the operational fallback | Closed: 109/109 and exact Sol reproductions, no High/Medium |
| RF-003 | High | RVC/Beatrice identity omitted or raced installed runtime bytes | `fix-now` / MS-1 | Adapter owners | Technical profiles stay nonselectable; startup hash mismatch fails closed | Closed: Beatrice passed Sol review; RVC content-addressed wheel, runtime, network-isolation, configuration, pack, profile, and route identities matched in EXP-004 |
| RF-004 | Medium | OpenVoice M2 clean-checkout isolation was incomplete | `fix-now` / MS-1 | OpenVoice owner | Offline-only and nonselectable | Closed: 11 pass/1 opt-in skip and Sol found no High/Medium |
| RF-005 | Medium | Public packages lacked one clean offline build/install/resource gate | `fix-now` / MS-1 | Primary | `make package-check` detects archive/resource or code-anchor loss | Closed: all nine archives and isolated installed-resource smokes pass |
| RF-006 | Medium | External Codex pool had cross-state locking and lifecycle races | `scheduled` / MS-5 | Primary | Tooling only; built-in agents/direct tmux are the immediate fallback | Current repair and exact symlink re-review green; cannot block MS-1 |
| RF-007 | Medium | RVC checkpoint fails content preservation and speaker evidence is unassessed | `scheduled` / MS-3 | Model-selection owner | Profile remains technical/nonselectable; failed CER is visible during MS-2 trial | Compare or replace on authorized decision fixtures |
| RF-008 | Medium | Frozen source corpus is weak for STT model ranking | `scheduled` / MS-3 | Fixture owner | Existing results cannot select a model but do not block technical listening | Intelligible authorized subset plus source-STT gate required before selection |
| RF-009 | High | External audible ChatGPT Chrome/SSH multi-model run lacked the frozen receipt | `accepted-risk` / historical MS-2 | Operator | The operator did reach the Extension and rejected the audio, but no EXP-005 pass or detailed technical claim is made | Closed by active user scope decision; all MS-3 counted evidence must use the new bundle-bound receipt |
| RF-010 | Medium | Public Caddy DNS/ACME ingress is unproven | `out-of-scope` / post-v1 | Primary | No public application ingress exists | Re-enter only through a new architecture decision |
| RF-011 | Medium | HA, multi-user auth, scale, and formal SLA are absent | `out-of-scope` / post-v1 | Primary | One trusted user/session with manual restart | Re-enter only if the product boundary changes |
| RF-012 | Medium | Restart/rollback/tunnel recovery need an operator runbook | `scheduled` / MS-5 | Operations owner | Manual restart allowed; native route is recovery | Three cycles, two-hour soak, recovery within ten minutes |
| RF-013 | Medium | External TTS and population comparison are incomplete | `scheduled` / optional MS-3 path; population study post-v1 | TTS ADR owner | TTS is deferred and cannot count toward the protocol-v1 VC gate or inherit VC claims | LV-063 must accept committed spoken-text transport, interruption, played-text, bundle, and shared-consumer contracts before Qwen/Cosy implementation; otherwise defer it |
| RF-014 | High | Gateway 50-frame ingress overflowed the private 25-frame RVC worker | `fix-now` / MS-1 | Gateway owner | Private-25 adversarial regressions are green; real route is the last detection gate | Closed: clean-commit EXP-004 drained 28/28 frames with public credit 50, high-water 28, and no overflow/fallback |
| RF-015 | High | RVC M1 allowed AF_INET/AF_INET6 and retained evidence was stale | `fix-now` / MS-1 | RVC owner | Profile remains technical/nonselectable | Closed: content-addressed v1.4 identity and AF_INET/AF_INET6 denial were rebound before the successful exact-profile route |
| RF-016 | High | Packaged Gateway lacked an explicit production WebSocket transport | `fix-now` / MS-1 | Gateway owner | Explicit pinned backend and packaged tests are green | Closed: the packaged explicit WebSocket backend completed the clean-commit EXP-004 lifecycle |
| RF-017 | High | Selectable profile promotion was not bound to reviewed evidence | `fix-now` / MS-1 | Profile owner | All affected profiles remain nonselectable | Closed: EXP-004 matched the reviewed pack/profile/configuration/pipeline hashes and remains technical/nonselectable |
| RF-018 | High | SSH commands could inherit permissive wildcard client configuration | `fix-now` / MS-1 | SSH docs owner | Do not connect until isolated-config preflight passes | Closed for Linux: exact pin/launcher/autossh checks and Sol re-review found no High/Medium |
| RF-019 | Medium | X-VC shared Gateway trial integration was incomplete | `fix-now` / MS-2 | X-VC route owner | Failed/nonselectable quality remains visible during the trial | Closed: exact clean-commit profile completed 28/28 changed frames with cancel/stale/cleanup green |
| RF-020 | Medium | OpenVoice lacked an Extension-invocable bounded preview route | `fix-now` / MS-2 | OpenVoice preview owner | Keep native audible while buffering and never call the result streaming | Closed: exact clean-commit profile completed 25/25 changed frames only after End, with cancel/stale/cleanup green |
| RF-031 | Medium | OpenVoice MS-2 preview is capped at 500 ms and cannot render an ordinary complete utterance | `scheduled` / MS-3 | Model-selection owner | The Extension labels it a non-live sample preview; it cannot count toward conversational latency or streaming viability | If OpenVoice remains a candidate, test longer authorized utterances with a separately bounded offline route before selection |
| RF-021 | Medium | EXP-003 trace/config evidence is too weak for comparison | `scheduled` / MS-3 | Experiment owner | Draft EXP-003 cannot select a model | Harden or replace with common evidence before selection |
| RF-022 | Medium | Deployment profile parity and secret-file mode need hardening | `scheduled` / MS-4 | Security owner | Loopback/SSH only; preflight failures stop launch | Runtime-parity and exact file-mode negative checks |
| RF-023 | Medium | Public Caddy reproducibility/operations are incomplete | `out-of-scope` / post-v1 | Primary | No public edge in personal v1 | New public-ingress ADR required |
| RF-024 | Medium | Codex runs unsandboxed without command approval | `accepted-risk` / through MS-6 | Repository operator, approved by user in active thread | Trusted dedicated dev container only; secret scan and ignored-artifact rules remain mandatory | Rebuild container after suspected compromise; revisit before shared-host use |
| RF-025 | Medium | Container log rotation and recovery diagnostics are incomplete | `scheduled` / MS-5 | Operations owner | Manual cleanup/restart; disk use is operator-monitored | Bounded retention plus soak/recovery runbook |
| RF-026 | Medium | macOS/Windows SSH preview checks have portability and supervisor-ordering gaps | `scheduled` / MS-5 | Client-docs owner | Linux is the initial supported client; preview platforms are explicitly non-gating | Validate only the operator's actual additional platform before enabling its supervisor |
| RF-027 | Medium | A cancel with one full RVC batch still resident can temporarily deny a new generation's full private credit | `scheduled` / MS-4 | Stability owner | Bounded rejection triggers fallback; ordinary cancel/stale isolation passed EXP-004 | Require an in-flight cancel followed immediately by a full-credit generation with no crash, stale output, or unbounded wait |
| RF-028 | High | The shipped catalog exposed only deterministic profiles and suppressed real/buffered/unavailable model states | `fix-now` / MS-2 | Registry and Extension owners | Operator could not honestly invoke or diagnose the prepared model roster | Closed: exact four-entry roster and chooser expose three live trials plus one buffered preview; all four actual Gateway routes green |
| RF-029 | Medium | ChatGPT generation boundaries have no supported automatic signal | `accepted-risk` / through MS-2 | Operator | Manual End/Interrupt/Next is visible; no DOM scraping; native remains fallback | Revisit in MS-4 only if a supported application/API contract becomes available |
| RF-030 | High | Gateway worker validation and dispatch were hard-coded to RVC | `fix-now` / MS-2 | Gateway contract owner | Beatrice, X-VC, and OpenVoice could not integrate safely or in disjoint leaves | Closed: static registrations bind exact pack/evidence/config/env/capacity, cross-pack attacks fail closed, and all four routes pass |
| RF-032 | High | EXP-005 and Extension lifecycle races could fabricate evidence or let stale controls affect a new generation | `fix-now` / MS-2 | Extension and experiment owners | Runtime receipt is metadata-only; native fallback remains authoritative | Closed: machine receipt/manual judgment split, explicit fifth failure probe, SW persistence, Stop/selection/Next epoch regressions, 148 Extension tests, and Sol review green |
| RF-033 | High | AudioWorklet buffer transfer detached PCM before EXP-005 changed-output observation | `fix-now` / MS-2 | Extension owner | No raw PCM is retained; a bounded scalar is computed before transfer | Closed: real transfer-detach regression passes and independent Sol re-review found no current-scope High/Medium |
| RF-034 | Medium | EXP-003 rejected promoted profiles and expected an obsolete post-close DELETE response | `fix-now` / MS-2 | Experiment owner | Harness drift could false-fail otherwise valid technical routes | Closed: promotion parity and DELETE/GET 404 invalidation regressions pass; clean-commit three-model trace is schema-valid |
| RF-035 | Medium | The one-run OpenVoice Gateway aggregate lacks a committed event schema, reusable runner, and independently replayable transcript | `scheduled` / MS-3 | OpenVoice evidence owner | Treat it only as an operator-observed bounded smoke; it is not comparison evidence | If OpenVoice remains a candidate, add a replayable bundle-bound buffered-route harness before using it in EXP-006 |
| RF-036 | High | Terminal, Gateway, popup defaults, and Extension selection can resolve different deployment settings | `fix-now` / MS-3 | Deployment-bundle owner | Terminal/direct-worker renders are debug-only and cannot make a variant listenable or selectable | One generated bundle hash must be verified by launcher, Gateway, Extension, and every counted receipt; mismatch hides the variant |
| RF-037 | High | A voice variant can be misbound to mutable or unauthorized checkpoint, training data, preset, or reference material | `fix-now` / MS-3 | Variant-profile owner | No raw reference, path, speaker knob, or checkpoint is accepted from the client | Resolve the public digest through the operator-controlled private authorization registry; require approved, nonexpired, exact variant/family/profile/source/terms/lineage binding and reject missing, extra, expired, or mutated records before route eligibility |
| RF-038 | Medium | Current prepared voices are operationally invocable but unacceptable to the operator | `scheduled` / MS-3 | Variant Lab owner | Preserve existing poor results as controls and reject variants quickly rather than recursively repairing them | Screen 9-12 primarily youthful-feminine protocol-v1 VC variants across at least four families through the actual Extension, then shortlist at most four |
| RF-039 | Medium | The current popup persists Gateway configuration including bearer material and has port/delay/roster constants that drift from operator launch settings | `fix-now` / MS-3 | Extension and bundle owners | Personal trusted browser and loopback/SSH remain the boundary; do not log or sync the token | Bundle owns public settings; secrets get an explicit storage decision and never enter the public manifest; parity smoke covers actual installed Extension |
| RF-040 | Medium | JVS/JSUT and some candidate code or weights have research-only, absent, conflicting, or attribution/notice terms | `fix-now` per variant / MS-3 | Candidate research owner | Such variants remain `license-review` or `excluded` and consume no GPU integration lane | Record code, weight, data, and voice authorization independently before material acquisition or training |

## Milestone close query

Before closing a milestone, filter the ledger by its target and ask:

1. Is every `fix-now` item closed with a regression and independent re-review?
2. Does every open High/Medium have an explicit later disposition, owner, and
   bounded impact?
3. Are any accepted risks actually outside the trusted one-client SSH boundary?
4. Did a technical pass get mistaken for quality, authorization, security, or
   production readiness?
5. Can the next milestone start without reopening a frozen contract?

If these answers are satisfactory and the milestone gate passes, advance. Do
not wait for post-v1 polish.
