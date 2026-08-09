# Personal SSH-use roadmap

Status: Active

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

## MS-2: Candidate and architecture freeze

Outcome: choose one primary personal-use conversion path and stop spending equal
effort on every model.

Deliver:

- a same-input comparison of at least two real candidates using an authorized,
  intelligible Japanese fixture subset plus integrity, STT, speaker, cold/warm
  timing, and operator listening notes;
- one primary streaming candidate, one explicit native fallback, and optionally
  one offline comparator; all other candidates are archived or assigned a
  bounded follow-up issue;
- a short ADR freezing the Extension topology: tab capture, always-hot native
  path, one source playhead, generation isolation, exclusive final playout, and
  server-returned candidate PCM;
- frozen model revision, runtime, profile configuration, reference/target
  authorization, sample rate, frame size, batching, and selection policy.

Gate:

- the primary is intelligible on the selected personal-use fixtures, has no
  clipping/repetition/gap failure that makes normal use impractical, and is
  compared honestly even if it misses a product NFR;
- the decision records why each alternate is selected, deferred, or rejected;
- no unassessed lane is represented as a pass and no failed quality result is
  hidden by a technical route pass;
- the chosen worker and Extension contract have no unresolved current-scope High.

Allowed known issues: a documented product-threshold miss, synthetic-reference
limitations, manual model warmup, and a single selected voice. The chosen
candidate must still be useful enough for the operator's listening test; a
clearly unintelligible result cannot be accepted merely to close the milestone.

## MS-3: Responsiveness and route stability

Outcome: tune only the frozen MS-2 path until ordinary conversation feels usable
and the core audio invariants remain stable.

Deliver:

- capture-to-playout, worker, jitter-buffer, and cancellation timing with warmup,
  P50, P95, sample count, environment, and exclusions;
- measured and tuned batching/context/crossfade/jitter settings;
- bounded backpressure and overflow behavior at every queue;
- retry, disconnect, stale-output, worker-crash, and cancel-during-drain tests;
- a 30-minute continuous route run and at least 30 post-warmup turns, including
  25 scripted interruptions and 25 native/remote mode changes.

Gate:

- zero accepted stale-generation frames and zero accidental double playback in
  the scripted cases;
- every injected route/worker failure reaches audible native fallback without an
  unbounded queue or Gateway-process crash;
- interruption stop targets NFR-003; any measured miss has a recorded personal-
  use budget and mitigation rather than an invented pass;
- warm response latency is measured against NFR-001 and reduced to the best
  stable configuration selected by the operator;
- the 30-minute run has no unrecoverable state, monotonic memory/queue growth, or
  required repository change.

Allowed known issues: a cold start around one minute, manual first warmup, and a
documented conversational delay above the product target when the operator
accepts it for personal use.

## MS-4: SSH-only security baseline

Outcome: make the intended one-user network boundary explicit and fail closed
without building an Internet service.

Deliver:

- Gateway bound to remote loopback with `max_sessions=1` and technical-profile
  opt-in explicit;
- forwarding-only SSH account/key, `permitopen`, disabled shell/session features,
  host-key pinning, client-local bind, and firewall verification;
- exact Extension Origin, visible-ASCII bearer policy, short-lived one-use WSS
  ticket, request/frame/body caps, worker process containment, and redacted logs;
- authenticated readiness and negative auth/origin/ticket-replay checks through
  the real SSH tunnel;
- a concise threat record scoped to one trusted client and one controlled host.

Gate:

- port 8765 is unreachable from the network and reachable only through the local
  forward;
- an invalid token, Origin, ticket, profile identity, artifact digest, or worker
  startup fails closed to native fallback;
- no raw audio, secret, reference voice, model weight, or credential is committed
  or emitted in normal logs/traces;
- the SSH and Gateway setup is reproduced from a second client shell using the
  documented commands.

Allowed known issues: one manually distributed bearer, no automatic rotation,
no SSO, no public TLS endpoint, and no defense against the trusted server
administrator. Public Caddy deployment work is post-v1 unless independently
useful and must not block this gate.

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
