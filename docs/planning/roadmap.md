# Personal SSH-use roadmap

Status: Active

Current milestone: **MS-3**. MS-1 closed on 2026-08-09 as an executability
checkpoint. MS-2 closed by explicit user direction on 2026-08-10 after the
actual Extension route became usable and the first hands-on listening result
was clearly unacceptable. That observation is a product-quality rejection, not
a formal EXP-005 evidence pass: the operator did not retain the complete frozen
receipt required to make the earlier four-model technical claim.

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

Status: **Closed by scope decision 2026-08-10.** This milestone put hands-on use
before model selection.

Automation checkpoint (2026-08-09): the exact four-model registry, Gateway
dispatch, Extension UI/receipt path, and SSH preflight are implemented, fully
checked, and independently reviewed. On clean commit `365e2a4`, all four real
technical profiles completed the intended one-run Gateway smoke: RVC, Beatrice
2, and X-VC returned 28 ordered changed frames in a schema-valid replayable
trace; the operator-observed OpenVoice aggregate reports 25 ordered changed
frames only after End. Cancellation, stale-output rejection, teardown, and GPU
cleanup were observed. A final isolated Chrome 151 load smoke also passed with no popup or
Service Worker error. The remaining close gate is the operator's actual SSH-forwarded,
authenticated audible ChatGPT session; server-side route output is not a
substitute for that audible acceptance.

The metadata-only raw route records remain outside Git at
`/tmp/exp003-ms2-live-three-365e2a4.json` (SHA-256
`4a72fbf6ebaf35f4ce94fd25bfe569f4819146b77023bcd3fd2e135414c9c49e`) and
`/tmp/openvoice-ms2-gateway-buffered-365e2a4.json` (SHA-256
`b11133b79a6ae05238c00a8071671689a1223f322c9485d9a5d27f7640ae15e8`).
The OpenVoice record is an internally consistent aggregate without a committed
event transcript or reusable runner, so it is not treated as general stability
evidence. The operator subsequently reached the actual Extension path and heard
the prepared choices, but reported that the audio was not usable. EXP-005 was
not completed with its machine receipt and therefore remains a historical draft,
not an MS-2 pass record. The active user instruction advances to MS-3 instead of
spending more time certifying choices already rejected by listening.

Outcome: use the actual liveconv Extension on an audible `chatgpt.com` voice tab
through the SSH-loopback route, hear multiple real conversion models, and learn
their operational shape without making a quality or production claim.

Deliver:

- one versioned deployment roster containing RVC, Beatrice 2, X-VC, and
  OpenVoice V2 with two independent labels: execution state (`live-trial`,
  `buffered-preview`, or `unavailable`) and decision state (`technical-only`, `quality-failed`,
  `unassessed`, or later `selected`);
- a remote-loopback technical Gateway registry for RVC, Beatrice 2, and X-VC,
  plus a bounded 60-500 ms manual-generation buffered sample preview for
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

## MS-3: Young-feminine voice Variant Lab

Status: **Active.** The preferred direction is a youthful feminine Japanese
voice. Model family alone is not the comparison unit: checkpoint, training data,
speaker/style preset, authorized reference voice, and inference configuration
form one immutable variant.

Outcome: make enough materially different voice choices available through the
actual Extension to discover a useful direction quickly. This milestone creates
a shortlist; it does not prematurely freeze one model.

Deliver:

- one generated, immutable deployment bundle containing profiles, model
  families, public-safe variant metadata, exact configuration identities, and a
  canonical bundle digest;
- one dynamic Extension chooser sourced from that bundle, with clear model,
  voice/style, execution-mode, readiness, and authorization labels;
- 9 to 12 protocol-v1 voice-conversion variants listenable through the
  Extension across at least four model families,
  with a majority targeting youthful feminine Japanese voices and including
  checkpoint/training-data and authorized-reference differences where useful;
- a fast first wave using authorized existing youthful-feminine voice/style
  artifacts across RVC, MeanVC2, X-VC, and OpenVoice, followed by new
  trained/adapted variants only when the first wave cannot answer the listening
  question;
- EXP-006: a 10-utterance screening pass for every runnable variant, then a
  preregistered shortlist of at most four variants and at most two per family;
- honest separation of audio-to-audio VC/accent conversion from text-to-speech.
  Qwen/CosyVoice TTS candidates stay off the counted path until an accepted ADR
  and shared protocol define committed spoken text, interruption, and played-text
  accounting; they never inherit a VC or captured-audio claim.

Gate:

- the same content-addressed deployment bundle is loaded by the Gateway,
  verified by the terminal launcher, fetched by the Extension, and bound into
  every counted receipt; copied popup constants or terminal-only configuration
  cannot satisfy the gate;
- at least nine protocol-v1 VC variants from at least four families are
  actually selectable and heard through the Extension on the same frozen
  10-utterance screen;
- every target preset/reference/training set has a license and authorization
  disposition before it becomes runnable; its public digest resolves to an
  approved, nonexpired exact record in the operator-controlled private registry,
  checked against trusted current UTC at activation/restart and session creation,
  while raw references and model weights stay outside Git;
- each variant receives operator ratings for Japanese intelligibility,
  naturalness, youthful-feminine fit, artifacts, conversational usefulness, and
  keep/reject, while route failures remain distinct from quality failures;
- no terminal-only render counts as an Extension result, no unassessed lane is
  represented as a pass, and the current poor RVC/X-VC observations remain
  visible as controls rather than being overwritten;
- a shortlist of no more than four variants is frozen for MS-4, or one bounded
  second wave is explicitly approved when fewer than two variants are worth
  continuing;
- `make check`, an installed-Chrome bundle-parity smoke, the real listening
  screen, and an independent Sol review are green with no current-scope High.

Allowed known issues: cold starts, manual End/Next boundaries, technical-only
profiles, a worker restart between variants, missing population-level evidence,
and variants that fail or are rejected quickly. MS-3 optimizes learning rate,
not universal coverage or production readiness.

## MS-4: Shortlist optimization and architecture freeze

Precondition: MS-3 produced a shortlist of no more than four variants.

Outcome: compare and tune only the shortlist, then select one primary route and
one fallback choice or record an explicit no-release decision.

Deliver:

- a frozen 40-utterance authorized Japanese comparison for the shortlist and a
  native control, with operator listening notes plus integrity, STT, speaker,
  cold/warm timing, and failure cases;
- bounded tuning of at most two configurations per shortlisted variant;
- one selected primary, one explicit fallback choice, and a disposition for
  every alternate, or a recorded `no release` decision;
- an ADR freezing the audio/VC-or-TTS path, Extension capture and playout,
  generation isolation, manual-boundary policy, model/runtime/profile/voice
  identities, and selection policy.

Gate:

- the selected primary is intelligible and subjectively useful on the personal
  fixtures, with no clipping, repetition, gaps, or delay that makes normal use
  impractical; misses are recorded rather than promoted;
- all compared evidence binds the same deployment bundle and exact variant
  identities, and route failures are not scored as voice-quality judgments;
- no unassessed lane is represented as a pass and no current-scope High remains
  in the selected worker or Extension architecture.

Allowed known issues: a cold start around one minute, manual first warmup,
documented NFR misses, and one selected voice. A `no release` decision closes the
roadmap before MS-5 unless the user starts another bounded candidate wave.

## MS-5: Responsiveness, SSH baseline, and personal recovery

Outcome: tune the frozen primary, verify the one-user SSH security boundary, and
make the system recoverable without remembering repository internals.

Deliver:

- capture-to-playout, worker, jitter, interruption, cold/warm P50/P95, bounded
  queue, retry, disconnect, worker-crash, and 30-minute route evidence;
- forwarding-only SSH, `permitopen`, host-key pinning, loopback-only reachability,
  exact Origin, bearer, one-use ticket, caps, and negative auth checks;
- preflight, start, readiness, stop, restart, update, rollback, tunnel reconnect,
  Extension reload, and log-inspection procedures driven by the same bundle;
- a pinned release inventory for code, profile, model artifacts, runtime, and
  client Extension ID;
- three clean cold-start/restart cycles, three tunnel-loss recoveries, worker
  crash recovery, and a two-hour personal soak;
- a known-issues list with detection, workaround, target milestone, and artifact
  retention/cleanup instructions;
- a monthly maintenance checklist and a ten-minute manual recovery objective.

Gate:

- zero accepted stale frames or accidental double playback, and every injected
  route failure reaches native fallback without an unbounded queue;
- a fresh operator shell can restore the route from stopped processes within ten
  minutes using the runbook and reproduce the exact deployed bundle digest;
- a failure during the soak may require one documented manual restart, but it
  must not corrupt the profile, retain raw audio, require code editing, or remove
  native playback;
- rollback to the previous code/profile/runtime inventory is tested once;
- all current MS-5 findings are fixed or explicitly accepted in the ledger.

Allowed known issues: no automatic failover, no background pager, monthly manual
maintenance, and an occasional restart when a clear runbook restores service.

## MS-6: Personal-use v1 acceptance

Precondition: MS-4 selected a primary variant and MS-5 closed on that route. The
`no release` branch does not enter MS-6.

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
multi-user operation, stronger population quality studies, additional TTS
expansion, automatic recovery, and service-level objectives begin only in a
separately approved post-v1 roadmap.
