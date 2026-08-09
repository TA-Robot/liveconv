# Personal SSH-use roadmap

Status: Active

Current milestone: **MS-2**. MS-1 closed on 2026-08-09 with a clean-commit
technical RVC Gateway route, green integrated checks, and an independent Sol
audit. This is an executability checkpoint, not a voice-quality approval.

This roadmap targets one person's usable voice-conversion system, not a public
service. The final MS-6 system uses one trusted Chrome client, one managed remote
GPU host, and an SSH local forward to a loopback-only Gateway. Manual maintenance
and an occasional restart are acceptable. Public Internet ingress, multi-user
identity, high availability, an uptime SLA, and unattended fleet operations are
outside these six milestones.

The product requirements remain measurement targets and safety invariants. A
milestone may record a measured deviation for this personal-use checkpoint; it
must not claim that an unmet NFR or experiment gate passed. Model-adapter gates
`M0` through `M6` in
[`critical-path.md`](critical-path.md) are separate from the user-delivery
milestones `MS-1` through `MS-6` below.

## MS-6 target envelope

The completed personal v1 has this boundary:

```text
one trusted Chrome Extension
        |
        | http://127.0.0.1:8765 + ws://127.0.0.1:8765/v1/ws
        v
OpenSSH local forward (-L, host key pinned, forwarding-only account)
        |
        v
remote 127.0.0.1:8765 Gateway -> one selected supervised model worker
```

Required qualities:

- native audio remains immediately available when conversion is unhealthy;
- native and transformed audio do not play together accidentally;
- interruption retires the old generation and its queued output;
- the Gateway stays on loopback and requires its bearer, one-use ticket, and
  exact Extension Origin in addition to SSH;
- raw user audio is not retained by default and secrets, voices, weights, and
  generated audio remain outside Git;
- one operator can install, start, stop, diagnose, restart, roll back, and
  reconnect the system from written instructions;
- a model or process failure may require a manual restart, but the native route
  remains usable and the documented recovery completes within ten minutes.

Explicitly not required for MS-6:

- public DNS, Caddy/ACME, an Internet-facing application port, or public clients;
- multi-user accounts, per-user authorization, SSO, billing, audit retention, or
  enterprise secrets management;
- automatic failover, zero-downtime deployment, an uptime percentage, on-call
  rotation, autoscaling, or more than one active session;
- production approval for every researched model, a TTS path, or completion of
  every historical experiment;
- native-speaker publication-quality evidence when a result is clearly labelled
  technical, personal, failed, or unassessed.

## Milestone rules

1. Work advances on observable gates, not on a reviewer's desire for general
   perfection.
2. Every finding is disposed through
   [`review-triage.md`](review-triage.md) as `fix-now`, `scheduled`,
   `accepted-risk`, or `out-of-scope`.
3. Only a current-milestone invariant, sensitive-data exposure, evidence
   corruption, unbounded expected-path resource leak, or inability to execute the
   gate stops the line.
4. A current-scope High finding must close before the milestone. A Medium may be
   scheduled or accepted when it has an owner, target milestone, bounded impact,
   and a concrete detection or recovery procedure. Low findings never block a
   milestone by themselves.
5. Each checkpoint gets one independent Sol review and one bounded repair and
   re-review cycle. A newly discovered non-blocking issue goes to its milestone
   instead of recursively reopening the checkpoint.
6. `make check` must pass at every milestone. Focused checks run continuously;
   expensive real-model and browser checks use explicit GPU, Chrome-profile, and
   port leases.

## MS-1: Executable multi-model lab

Status: **Closed 2026-08-09.** The retained RVC profile passed EXP-004 through
the disposable Gateway at commit `868ae46215335f7d9e900894f2c8158ed603eb3f`.
The experiment decision remains `inconclusive`, and all candidates remain
labelled according to their actual technical and quality evidence.

Outcome: prove what actually runs on this host and establish one real routed VC
path without making a quality or production claim.

Deliver:

- immutable provenance, isolated runtime, and a real transform attempt for RVC
  v2, Beatrice 2, X-VC, and OpenVoice V2;
- at least three successful real PCM-to-PCM transforms and at least two adapters
  exercised through worker protocol v1;
- one rolling or streaming candidate selected through the real Gateway with
  generation start/end/cancel and native fallback intact;
- loadable MV3 Extension, bounded capture/playout queues, deterministic
  passthrough and gain routes, packaged Python distributions, and the SSH client
  setup documents;
- every candidate labelled `technical`, `failed`, `offline-only`, `unassessed`,
  or `nonselectable` exactly as its evidence supports.

Gate:

- real artifacts, source, adapter code, runtime lock, worker wheel, and effective
  configuration identities are bound and independently checked for every model
  used in a claim;
- all successful transforms return finite normalized audio and preserve worker
  generation/sequence/timestamp identity;
- malformed authorization or evidence cannot promote a profile;
- at least one real profile passes a disposable local Gateway route smoke;
- package builds, focused suites, `make check`, and an independent Sol review are
  green with no open current-scope High.

Allowed known issues: poor voice quality, failed STT or speaker lanes, slow cold
start, whole-file-only inference, no external audible-tab run, and candidates
that remain nonselectable. These become MS-2 inputs rather than MS-1 blockers.

## MS-2: Multi-model Extension MVP

Status: **Active.** This milestone puts hands-on use before model selection.

Outcome: use the actual liveconv Extension on an audible `chatgpt.com` voice tab
through the SSH-loopback route, hear multiple real conversion models, and learn
their operational shape without making a quality or production claim.

Deliver:

- one versioned deployment roster containing RVC, Beatrice 2, X-VC, and
  OpenVoice V2 with two independent labels: execution state (`live-trial`,
  `buffered-preview`, or `unavailable`) and decision state (`technical-only`, `quality-failed`,
  `unassessed`, or later `selected`);
- a remote-loopback technical Gateway registry for RVC, Beatrice 2, and X-VC,
  plus a bounded manual-generation buffered preview for whole-utterance
  OpenVoice V2, all invocable from the Extension;
- an Extension chooser that shows all roster entries, disables unavailable or
  unauthorized entries with a safe reason during development, switches a live
  model only at an idle generation boundary, and invokes buffered preview only
  after an explicit End;
- one real Chrome client connected through the pinned OpenSSH local forward,
  capturing an audible ChatGPT voice tab with explicit Start, End, Interrupt,
  Next, model selection, and Stop controls;
- a metadata-only trial record for all four prepared models. Raw audio is not
  retained.

Gate:

- all four roster models are operator-invocable from the Extension and attempted;
  an `unavailable` entry is useful during development but blocks MS-2 closure
  unless the user explicitly removes that model from the prepared roster;
- at least two distinct live model profiles produce audible, finite, changed PCM
  through the same Extension/Gateway contract on the actual ChatGPT tab;
- RVC, Beatrice 2, and X-VC each receive a live attempt; OpenVoice receives a
  bounded, manual End-triggered buffered preview through the same Extension,
  clearly labelled non-live and excluded from latency/streaming claims;
- native audio is available before remote readiness and immediately on forced
  tunnel, worker, or profile failure; native and converted output never play
  together accidentally, and canceled/stale output is not accepted;
- the Gateway remains bound to remote loopback with `max_sessions=1`; the client
  uses a pinned-host-key, forwarding-only SSH local forward plus bearer, exact
  Extension Origin, and one-use ticket;
- `make check`, the installed-Chrome smoke, the real audible multi-model trial,
  and one independent Sol review are green with no current-scope High.

Allowed known issues: poor or unintelligible conversion, failed quality lanes,
slow cold start, manual End/Next boundaries, technical-profile opt-in, Linux-only
operator instructions, a Gateway or worker restart between model attempts, and
an honestly failed attempt after the model was actually invocable. Automatic
ChatGPT turn detection, quality selection, tuning, and a release claim are not
MS-2 gates.

## MS-3: Candidate and architecture freeze

Outcome: use the MS-2 hands-on results plus comparable authorized evidence to
choose one personal-use path, or explicitly choose native-only when no candidate
is useful enough.

Deliver:

- a same-input comparison of at least two real MS-2 candidates using an
  authorized, intelligible Japanese fixture subset plus integrity, STT, speaker,
  cold/warm timing, and operator listening notes;
- one primary streaming candidate and one explicit native fallback, or a
  recorded `no VC selected` decision; all alternates are archived or assigned a
  bounded follow-up;
- an ADR freezing tab capture, always-hot native playout, one source playhead,
  generation isolation, exclusive final playout, server-returned PCM, and the
  manual-boundary policy;
- frozen model, runtime, profile, target authorization, sample rate, frame size,
  batching, and selection policy.

Gate:

- if a primary is selected, it is intelligible on the personal-use fixtures and
  has no clipping, repetition, or gap failure that makes ordinary use
  impractical; if no VC is selected, the recorded no-release decision satisfies
  this branch and terminates the roadmap before MS-4;
- no unassessed lane is represented as a pass and no failed quality result is
  hidden by the MS-2 technical route;
- the decision states why every alternate is selected, deferred, rejected, or
  retained offline;
- no current-scope High remains in the chosen worker or Extension architecture.

Allowed known issues: documented NFR misses, synthetic-reference limitations,
manual warmup, and one selected voice. If MS-3 records `no VC selected`, it
closes as a no-release decision and the VC path stops; MS-4 through MS-6 do not
start without a new user decision.

## MS-4: Responsiveness, stability, and SSH baseline

Precondition: MS-3 selected one primary VC profile. A `no VC selected` decision
terminates this roadmap before MS-4.

Outcome: tune only the MS-3-selected path, keep it stable in ordinary use, and
verify the minimum one-user SSH security boundary.

Deliver:

- capture-to-playout, worker, jitter, and cancellation timing with warmup, P50,
  P95, sample count, environment, and exclusions;
- tuned batching/context/crossfade/jitter plus bounded backpressure and overflow
  behavior at every queue;
- retry, disconnect, stale-output, worker-crash, cancel-during-drain, and one
  30-minute route run with scripted interruptions and native/remote changes;
- forwarding-only SSH account/key, `permitopen`, disabled shell/session features,
  host-key pinning, client-local bind, firewall/external-unreachability checks,
  exact Origin, bearer, one-use ticket, caps, containment, and redacted logs;
- authenticated readiness and negative auth/Origin/ticket/profile/artifact cases
  reproduced from a second client shell.

Gate:

- zero accepted stale frames and accidental double playback; every injected
  route/worker failure reaches native fallback without an unbounded queue or
  Gateway crash;
- warm latency and interruption are measured against NFR-001/NFR-003 and tuned
  to the best stable configuration; any miss is recorded rather than promoted;
- port 8765 is unreachable from the network and reachable only through the local
  forward; invalid credentials, identity, artifacts, or startup fail closed;
- the 30-minute run has no unrecoverable state or monotonic resource growth, and
  no sensitive material is committed or emitted in ordinary logs.

Allowed known issues: a cold start around one minute, manual first warmup, one
manually distributed bearer, no automatic rotation or SSO, and a documented
delay above product targets when the operator accepts it. Public Caddy ingress
remains post-v1.

## MS-5: Personal operations and recovery

Outcome: one person can keep the system usable without remembering repository
internals.

Deliver:

- preflight, start, readiness, stop, restart, update, rollback, tunnel reconnect,
  Extension reload, and log-inspection procedures;
- a pinned release inventory for code, profile, model artifacts, runtime, and
  client Extension ID;
- three clean cold-start/restart cycles, three tunnel-loss recoveries, worker
  crash recovery, and a two-hour personal soak;
- a known-issues list with detection, workaround, target milestone, and artifact
  retention/cleanup instructions;
- a monthly maintenance checklist and a ten-minute manual recovery objective.

Gate:

- a fresh operator shell can restore the route from stopped processes within ten
  minutes using the runbook;
- a failure during the soak may require one documented manual restart, but it
  must not corrupt the profile, retain raw audio, require code editing, or remove
  native playback;
- rollback to the previous code/profile/runtime inventory is tested once;
- all current MS-5 findings are fixed or explicitly accepted in the ledger.

Allowed known issues: no automatic failover, no background pager, monthly manual
maintenance, and an occasional restart when a clear runbook restores service.

## MS-6: Personal-use v1 acceptance

Precondition: MS-3 selected a primary VC profile and MS-4/MS-5 closed on that
route. The `no VC selected` branch does not enter MS-6.

Outcome: the actual external client and remote server complete a normal audible
conversation over the SSH-only route, and the result is frozen as personal v1.

Deliver and gate:

- one Chrome client loads the release Extension on a normal audible tab, opens
  the SSH tunnel, selects the frozen primary profile, and completes at least a
  30-minute session with 20 generations and five interruptions;
- forced tunnel loss and worker failure both return to native audio, after which
  the documented reconnect/restart restores conversion;
- output is intelligible and subjectively useful to the named operator; this is a
  personal acceptance record, not a population-level quality claim;
- release notes state the exact model/profile/runtime revisions, measured
  latency, failed/unassessed evidence lanes, security boundary, known issues,
  manual recovery, and rollback;
- `make check`, package checks, Extension checks, the real SSH route smoke, secret
  scan, and final independent Sol review are green;
- every remaining High/Medium has one of the four explicit dispositions and no
  current-scope High remains.

After MS-6, normal operation is intentionally modest: use the system personally,
inspect it monthly, restart it when a documented failure occurs, and open a
targeted issue when repair requires more than the runbook. Public access,
multi-user operation, stronger quality studies, TTS, automatic recovery, and
service-level objectives begin only in a separately approved post-v1 roadmap.
