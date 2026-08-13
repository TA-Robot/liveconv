# Orchestration Execution Log

This lightweight log records project-progress audits and the resulting changes
to orchestration. It is not a substitute for experiment receipts or the durable
job queue.

## 2026-08-11T14:48:00Z - EXP-009 prequeue audit

- Agent: `progress_audit_20260811_1448`
- Task: Judge whether the current EXP-009 review and admission strategy remains
  the highest-value path to the seven-job run.
- Dependencies: Parent focused checks, accepted-runtime CPU79 probe, final
  time-boxed EXP-009 review, and queue required-artifact review.
- Result: `SIMPLIFY`.
- Adopted: Yes.
- Problems: Repeated correctness reviews found real launch blockers, but the GPU
  remained idle and further general review had lower expected value than running
  the frozen experiment.
- Changed action: Fix only the two final decision-critical High findings, bound
  the clean X-VC source state operationally, then stop general review and proceed
  directly through snapshots, revision 23 admission, and queue execution.
- Rework avoided: No additional seed, rank, learning-rate, model-quality, or
  broad source-hardening work is admitted before the seven-job result.

## 2026-08-11T15:24:00Z - EXP-009 closure audit

- Agent: `progress_audit_20260811_1524`
- Task: Decide whether more EXP-009 review or computation could still improve
  the milestone decision after the queue and independent result review closed.
- Dependencies: Queue revision 24 through event 1332, the successful aggregate
  repair job, independent raw-metric and event-chain recomputation, focused
  tests, control-check, and the decided experiment record.
- Result: `STOP` for EXP-009 only.
- Adopted: Yes.
- Problems: Review had become the dominant lead-time cost while no remaining
  approved EXP-009 branch could change the `no-select` decision.
- Changed action: Close EXP-009 immediately, admit no rerun, third seed,
  heldout evaluation, or parameter change, and recompute the MS-3 Ready frontier.
- Rework avoided: At least one further review cycle and all unauthorized
  EXP-009 GPU work. The next work starts as a separately bounded milestone node.

## 2026-08-11T15:54:00Z - EXP-006 screening-path audit

- Agent: `progress_audit_20260811_1554`
- Task: Decide whether the counted nine-variant screen needs a new nine-only
  deployment or should safely select the frozen baseline from the current
  32-profile bundle.
- Dependencies: Frozen LV-032 fixture, in-progress LV-057 route receipts, the
  green screen runner, current bundle identities, and an idle GPU.
- Result: `SIMPLIFY`.
- Adopted: Yes.
- Problems: Requiring the whole bundle to contain only nine profiles exceeded
  the experiment DoD and would churn the bundle revision and route receipts
  without adding scientific information.
- Changed action: Keep the current immutable bundle, require every frozen
  baseline profile and valid receipt, derive the execution plan only from those
  exact nine catalog entries, and ignore rather than execute extra diagnostics.
- Rework avoided: A new deployment activation and nine route-receipt repeats,
  estimated at 30 to 90 minutes plus one operational cycle.

## 2026-08-11T16:24:00Z - EXP-006 evidence-path audit

- Agent: `progress_audit_20260811_1624`
- Task: Decide whether closing the LV-057 forgery path and adding per-render
  identity is necessary progress or another low-value strictness cycle.
- Dependencies: Green LV-032 fixtures, focused-green LV-057 producer, the
  independent direct-sealer forgery finding, the stdin-free screen runner, and
  the frozen ten-utterance decision rule.
- Result: `SIMPLIFY`.
- Adopted: Yes.
- Problems: One LV-057 observation can currently be hand-authored and sealed,
  while repeating the full fallback probe for all 99 attempts still does not
  bind the ten planned source files to the audio actually heard.
- Changed action: Close the direct-sealer path with one-time Gateway evidence;
  collect one route qualification per baseline profile; bind each of the 90
  scored renders to its exact source, output, session/playout, and operator
  judgment; remove per-render fault-probe repetition.
- Rework avoided: Ninety redundant fallback cycles, a new bundle, and another
  broad review round, estimated at 60 to 180 minutes plus one operator cycle.

## 2026-08-11T16:54:00Z - EXP-006 execution audit

- Agent: `progress_audit_20260811_1654`
- Task: Judge whether the route-qualification and single-render path remains the
  shortest route to the operator listening screen.
- Dependencies: Completed LV-057 attestation gate, focused-green 9 x 10
  renderer, live listener and qualification Gateway, sealed qualification plan,
  and a successful Xvfb/XTEST invocation of the unmodified Extension.
- Result: `CONTINUE`.
- Adopted: Yes.
- Problems: No remaining design or review work can improve the next decision;
  extra review, bundle churn, or partial render batches would only idle the
  execution path.
- Changed action: Collect and seal exactly one route qualification for each of
  the nine baseline profiles, then admit one exact 90-render job and move
  directly to the listening UI.
- Rework avoided: Further Sol review, `make check`, redeployment, repeated fault
  probes, partial screen batches, and any tuning before the first operator
  shortlist.

## 2026-08-11T17:36:00Z - EXP-006 live-route pivot audit

- Agent: `progress_audit_20260811_1736`
- Task: Reassess whether completing nine Extension route qualifications still
  remained the highest-value path after real browser and GPU execution.
- Dependencies: Four sealed RVC qualifications, the buffered OpenVoice drain
  fix, and real X-VC and MeanVC2 Extension attempts.
- Result: `PIVOT`.
- Adopted: Yes.
- Problems: X-VC and MeanVC2 initialized correctly but hit the bounded live
  ingress `QUEUE_OVERFLOW`; follow-up OpenVoice attempts hit the same live-route
  limit. Expanding queues or redesigning backpressure now would delay the
  listening decision and could disguise route ineligibility.
- Changed action: Preserve the four route-qualified RVC profiles. Classify the
  other five frozen profiles as `offline_only_queue_overflow`, retain the exact
  nine-by-ten listening comparison, and label every render and exported choice
  with its route status. Offline-only quality interest cannot enable an
  Extension profile without a later successful route qualification.
- Rework avoided: Streaming queue redesign, protocol changes, additional route
  retries, fake parity receipts, and another broad correctness review before the
  first complete listening screen.

## 2026-08-11T18:04:00Z - EXP-006 mixed-render audit

- Agent: `progress_audit_20260811_1804`
- Task: Reassess whether the mixed four-qualified/five-offline renderer remained
  the shortest path to the operator listening screen before GPU admission.
- Dependencies: Frozen mixed-lane experiment contract, focused-green renderer,
  route-status listener projection, four sealed route receipts, and ten frozen
  source utterances.
- Result: `CONTINUE` with two bounded contract corrections.
- Adopted: Yes.
- Problems: The runner initially emitted `qualified` instead of the frozen
  `route_qualified` status, and the experiment prose circularly described the
  future checkbox export as a pre-render receipt prerequisite.
- Changed action: Use exact `route_qualified` output vocabulary and bind the
  later selection export to immutable render receipts in one direction. Run one
  CPU preflight, then one 90-render GPU job; expose only that completed run on
  port 8878.
- Rework avoided: Additional route qualification, a separate GPU canary,
  `make check`, another independent review, and ninety placeholder unchecked
  judgments before listening.

## 2026-08-11T18:34:00Z - EXP-006 Gateway boundary audit

- Agent: `progress_audit_20260811_1834`
- Task: Decide whether focused OpenVoice/Gateway diagnosis still beats exposing
  partial RVC output, splitting the offline lane, or changing render paths.
- Dependencies: Retained v2 failure after 40 RVC renders, green exact OpenVoice
  engine and raw-worker probes, an idle GPU, and the bounded Gateway canary.
- Result: `CONTINUE` with a time-boxed redirect condition.
- Adopted: Yes.
- Problems: OpenVoice failed only at the Gateway boundary with a sanitized
  `WORKER_CRASH`; the retained partial run has no aggregate/index and cannot be
  presented as the preregistered comparison.
- Changed action: Run the exact Gateway canary and one shortened RVC4-to-
  OpenVoice sequence. If the boundary is green, submit one fresh 90-render job;
  if it is red twice or expands beyond one boundary by 18:50 UTC, re-audit a
  transparent 70-candidate missing-data screen.
- Rework avoided: Resume implementation, receipt merging, offline job splitting,
  direct-worker evidence substitution, another broad review, and blind full-run
  retries.

## 2026-08-11T19:12:00Z - EXP-006 listening handoff audit

- Agent: `progress_audit_20260811_1912`
- Task: Decide whether more technical validation was worth delaying the now-live
  operator listening screen.
- Dependencies: Successful v3 queue result, 90 WAV and receipt pairs, complete
  nine-by-ten identity checks, HTTP checks, and the single-run listener on port
  8878.
- Result: `STOP`.
- Adopted: Yes.
- Problems: None blocking; further review had low marginal value after the
  counted render and listener checks were green.
- Changed action: Hand the 90-candidate sequential listener to the user now and
  wait for the operator's `良かった` selections before any new experiment,
  render, or promotion work.
- Rework avoided: Additional review, another render, unrelated model work, and
  several minutes of avoidable handoff delay.

## 2026-08-11T23:49:00Z - X-VC adaptation preview audit

- Agent: `progress_audit_20260811_2349`
- Task: Decide whether rendering already-trained X-VC adapters for immediate
  listening was higher value than another training sweep or more evidence-gate
  implementation.
- Dependencies: EXP-009's two-seed directional validation improvement, retained
  base/control69/expanded79 adapters, shared validation items 011 and 014, and
  an idle exclusive GPU.
- Result: `CONTINUE` with a deliberately minimal preview.
- Adopted: Yes.
- Problems: The prior no-select decisions were preregistered technical gates,
  not perceptual-quality conclusions; no adapted output had been listened to.
- Changed action: Render only validation 011/014 for base, control69 seed
  20260814, and expanded79 seed 20260814 in one GPU job, then expose the six
  research-only outputs through a separate listener run.
- Rework avoided: A new UI, Gateway or Extension integration, held-out access,
  extra seeds, additional training, new metric design, and a broad review before
  the first adapted-audio listen.

## 2026-08-12T01:05:00Z - X-VC improvement campaign audit

- Agent: `progress_audit_20260811_2349`
- Task: Check whether immediately starting the long-horizon X-VC campaign is a
  better use of the idle GPU than further contracts, reviews, or UI work.
- Dependencies: Completed six-output base/control69/expanded79 preview, live
  listener on port 8880, the approved EXP-008 cache, EXP-009 expanded79 evidence,
  and an idle exclusive GPU.
- Result: `PIVOT` in ordering only: render the listening preview first, then
  continue the long-horizon run.
- Adopted: Already satisfied. The preview job and listener had completed before
  this audit returned, so no additional work or delay was introduced.
- Problems: The new 400-update run changes breadth and horizon together and is
  therefore an exploratory trajectory, not a clean causal comparison.
- Changed action: Proceed directly with one broad-eight, expanded79, 400-update
  trajectory with checkpoints at 48, 96, 192, and 400; prepare LoRA+ and DoRA
  while it runs.
- Rework avoided: New ADRs, large schemas, full-repository checks, independent
  reviews at every checkpoint, extra seeds, new UI, and arbitrary loss gates.

## 2026-08-12T01:34:52Z - EXP-010 result and next-GPU audit

- Agent: `progress_audit_20260812_0135`
- Task: Decide whether checkpoint listening, rank-16 feasibility, and the full
  converter probe remain the shortest path to audible X-VC improvement.
- Dependencies: The completed 400-update EXP-010 trajectory, five retained
  checkpoints, zero held-out access, and an idle exclusive GPU.
- Result: `CONTINUE`.
- Adopted: Yes.
- Problems: Validation improved through update 96, then worsened at 192 and 400;
  the final checkpoint cannot be presumed best from training loss alone.
- Changed action: Render all five checkpoints for blinded listening now, then
  run exactly one rank-16 feasibility batch and one full-converter feasibility
  batch. Start a full-converter trajectory only if its bounded probe passes.
- Rework avoided: Another broad receipt review, extra seeds, arbitrary loss
  thresholds, and LoRA+/DoRA GPU runs before the listening binding exists.
## 2026-08-12T02:04:00Z - X-VC conditioning-first progress audit

- Agent: `progress_audit_20260812_0204`
- Verdict: `PIVOT`
- Accepted: keep the EXP-013 full-converter trajectory implementation running
  on CPU, but do not leave `gpu0` idle waiting for it. Run a small blinded
  render-only comparison first at EXP-010 checkpoint 96, changing only the
  frame-level target conditioning from the campaign's all-zero tensor to an
  authorized synthetic reference tensor.
- Reason: EXP-010 validation improved through update 96 and regressed after it,
  while upstream X-VC inference normally supplies a real target-derived frame
  condition. This A/B render is faster and more directly informative about
  audible quality than starting another 400-update run before listening.
- Next actions: freeze and run the conditioning A/B; serve its blinded output;
  then either correct conditioning if it clearly wins or admit the already
  planned EXP-013 trajectory if it is neutral or worse.
- Explicitly skipped: additional one-batch proofs, multi-seed training, formal
  MOS/statistical work, exhaustive checkpoint grids, and LoRA+/DoRA GPU runs
  before the current listening evidence is bound.

### Outcome by 2026-08-12T02:34:00Z

- EXP-015 completed the four-WAV conditioning A/B and is listening-ready at
  `http://127.0.0.1:8882/`.
- The CPU-prepared EXP-013 full-converter runner then used the freed GPU lease,
  completed 400 updates and five converter snapshots, and produced its blinded
  ten-WAV listener at `http://127.0.0.1:8883/`.
- The pivot therefore avoided idle GPU time without cancelling the already
  useful training implementation. The next one-variable preparation is
  EXP-016's native gradient clip; no additional review gate was inserted.

## 2026-08-12T02:35:00Z - EXP-016 immediate-run progress audit

- Agent: `exp005_integrity_review` (independent read-only progress auditor)
- Verdict: `CONTINUE`.
- Accepted: Admit EXP-016 immediately. It preserves the EXP-010 trajectory and
  changes only the upstream-native `clip_grad_norm_=5` behavior; its source,
  configuration, cache, and no-CUDA admission checks are green and `gpu0` is
  idle.
- Reason: Both EXP-010 LoRA and EXP-013 full-converter trajectories improve near
  updates 48/96 and worsen later. Testing the omitted native clipping setting is
  a higher-information use of the GPU than waiting for operator listening or
  adding another proof layer.
- Next actions: run the single 400-update trajectory; prepare its blinded
  checkpoint renderer concurrently; compare 48/96 first, and move to EXP-017
  full-utterance windows without an extra seed if clipping is not audibly better.
- Explicitly skipped: another static review, CUDA preflight repetition, multiple
  seeds, formal MOS/statistics, exhaustive checkpoint listening, LoRA+/DoRA GPU
  runs, and schema/report redesign.
- High blocker: none.

### Outcome by 2026-08-12T03:22:22Z

- EXP-017 materialization succeeded with 30 sealed start/middle/end payloads.
  Its first two control launches stopped before model updates on, respectively,
  a relative-versus-absolute containment comparison and inherited EXP-009 seed
  allowlisting. Both failures remain in append-only history; neither contributes
  training evidence.
- The audit pivot launched EXP-018 while the EXP-017-local fixes were prepared.
  EXP-018 completed 400 updates in 91.93 seconds at peak allocated GPU memory
  3,567,258,624 bytes, exported all five adapters, and retained zero held-out
  payload access.
- EXP-018 validation medians at `0,48,96,192,400` were
  `840.1133,627.7845,542.9402,521.6521,556.8834`. This substantially reduced
  EXP-010's late numeric worsening, but it is not an audible selection.
- EXP-017 v3 now owns its fixed seed controls locally and has entered the real
  96-update control run. The EXP-018 blinded renderer is frozen and queues after
  the current paired pilot jobs.

### Outcome by 2026-08-12T02:49:30Z

- EXP-016 v1 stopped before model import because the parent queue invocation
  omitted the three approved offline environment values. The append-only v1
  failure remains recorded; no training evidence is attributed to it.
- The condition-identical v2 completed 400 updates in 116.46 seconds with peak
  GPU memory 3,567,258,624 bytes. All 400 updates were clipped to approximately
  norm 5 and held-out payload access remained zero.
- Validation medians were `840.1133, 528.6850, 514.3716, 563.6107, 709.5266`
  at steps `0,48,96,192,400`. Clipping slightly improved the early numeric
  result but did not remove late regression, weakening clipping as the primary
  explanation.
- The ten-WAV blinded five-checkpoint demo completed and is listening-ready at
  `http://127.0.0.1:8884/`; no audible selection is inferred from loss.
- EXP-017 was explicitly shortened from the draft 432-update/numeric-threshold
  design to a paired 96-update pilot with evaluations at `0,48,96` and no
  arbitrary numeric auto-winner. This applies the audit's time-cost guidance.

## 2026-08-12T03:05:00Z - EXP-017 immediate-run progress audit

- Agent: `exp005_integrity_review` (independent read-only progress auditor)
- Verdict: `CONTINUE`.
- Accepted: Launch the serial EXP-017 materialization, control-96, variant-96,
  and blinded-render chain as soon as the frozen tool hashes are available.
- Reason: EXP-017 tests a distinct and plausible limitation of the current
  prefix-only 2.4-second cache, EXP-016 is already complete through listening
  artifacts, and `gpu0` is idle. EXP-018 and the best-of listener can finish on
  CPU in parallel.
- Pivot trigger: If EXP-017 cannot enter the queue within 5-10 minutes or its
  materializer hard-fails, launch the queue-ready EXP-018 learning-rate-only
  trajectory instead. Stop only the affected branch on nonfinite values, OOM,
  or identity drift.
- Explicitly skipped: extra seeds, a 400-update window expansion, exhaustive
  checkpoint rendering, MOS/statistical work, expanded CER/speaker evaluation,
  route integration, additional independent review, and schema/report growth.
- High blocker: none.

## 2026-08-12T04:05:00Z - X-VC research-series progress audit

- Agent: `xvc_research_progress_audit` (independent read-only progress auditor)
- Verdict: `SIMPLIFY`.
- Partially accepted: avoid repeating the X-VC paper/code contract analysis and
  compress evidence already established by Inquiry 01 and 02.
- Not accepted: the proposed narrowing to one product-boundary question and an
  immediate synthesis. The active user instruction explicitly asks for broader
  searches across LoRA/PEFT research, modern VC models, data/objective methods,
  and architectures, with later inquiries chosen from discoveries rather than
  fixed in advance.
- Changed action: Inquiry 03 became one integrated broad method-map research
  trail fed by five read-only primary-source scouts. Inquiry 04 is selected only
  from its strongest emergent connection: adaptation placement may matter more
  than rank alone. No GPU job, queue admission, or audio selection runs during
  this research milestone.

## 2026-08-12T04:41:21Z - X-VC open-inquiry milestone complete

- Completed five sequential research artifacts under
  `docs/research/xvc-improvement-inquiry/`. Each next inquiry was selected from
  the preceding findings rather than assigned a fixed topic in advance.
- What worked: parallel primary-source scouting broadened Inquiry 03 across
  PEFT, speech adaptation, VC data/objectives, model families, and realtime;
  sequential integration then returned those findings to the local X-VC
  function graph instead of leaving a literature catalog.
- Main knowledge update: condition contract, data identifiability, functional
  adapter placement, generator/representation family, and realtime lifecycle
  are separate levers. The final-block `to_q_c` zero-reachability is a direct
  local static result; EXP-009's `157/158` changed count is only consistent
  aggregate evidence and does not identify the unchanged tensor.
- Rework: the initial exploration was too narrowly centered on the local
  condition contract. The active user correction moved broad LoRA/VC/model
  research earlier; one draft branch was discarded before publication. The
  independent Sol review then narrowed four overstated maturity/objective
  claims. Its final verdict has no remaining High or Medium finding.
- Deliberately not run: GPU training, queue admission, audio listening or
  selection, and product/model promotion. Existing blind artifacts remain
  unselected, and numeric loss thresholds remain diagnostic or experiment-local
  rules rather than audible-quality adoption criteria.

## 2026-08-12T04:52:00Z - rolling experiment cycle resumed and replanned

- Active instruction: resume bounded experiments and periodically replan from
  their results rather than following a fixed sweep.
- Current evidence audit found EXP-017 control and three-window variant both
  completed. At update 96 the six-window variant/control median ratio is
  `0.9695792829`, while the start-window ratio is `1.0121180288`; this is mixed
  diagnostic evidence and creates a render/listening checkpoint, not a winner.
- EXP-018 training and its blinded five-checkpoint renderer are complete and
  unselected. `gpu0` is idle and the queue has no active job.
- Independent review redirected EXP-019 before GPU admission: its plan requires
  exact EXP-014/018 receipt bindings, but the sealed runner did not verify them;
  its prepared renderer compared only rank-16 checkpoints and could not answer
  the registered rank8-versus-rank16 question. No proposal was extended or run.
- First replan actions: synchronize EXP-017 registry status to `analyzed`, close
  its terminal blind-render contract, add EXP-019 receipt admission and a true
  cross-arm renderer, then recalculate the Ready frontier. `make control-check`
  returned green after the registry repair.
- Cadence: replan after every completed GPU job, completed blind batch, or
  branch-changing failure, with the 30-minute audit as a backstop. Admit no more
  than one new one-variable GPU question between replans.

## 2026-08-12T07:09:57Z - EXP-017 terminal window render complete

- The post-training contract was narrowed before execution to six independent
  blinded `q=0/0.5/1` window comparisons. A stitched output was removed because
  independently normalized, substantially overlapping source/target crops do
  not constitute an original-utterance reconstruction.
- Independent pre-run review found and closed false-green paths for arbitrary
  output length, silent clipping, unsealed indexes, partial publication, and a
  dirty X-VC source tree. The final renderer was admitted only after its exact
  file hash, queue revision, inputs, and clean source were rechecked.
- Queue job `exp017-xvc-window-terminal-ab-render-v2-sealed-output` succeeded.
  Independent output verification recomputed the receipt, index, WAV, and
  queue artifact bindings: exactly 12 mono PCM16 16-kHz/38,400-sample WAVs, six
  blind indexes, and one receipt; no clipping, held-out access, stitch, mapping
  leak, extra artifact, or residual process was found.
- Receipt file SHA-256 is
  `b7eb2d012e5aa3a80cbb851d2fc06deee8838140b4c36bfc86c8bedbbe958b36`;
  its canonical internal receipt SHA-256 is
  `f6f605e4fbbfddd85f260b7214e9203fe2f9f8c1a2c42c950b71af6770ea908f`.
  The unselected listener is available at `http://127.0.0.1:8887/`.

## 2026-08-12T07:14:00Z - rolling experiment progress audit

- Agent: `progress_audit_0714` (independent read-only progress auditor).
- Verdict: `CONTINUE`.
- Accepted: run exactly one repaired EXP-019 rank-16 trajectory while the
  operator can listen to the already-served blind libraries. The two activities
  do not compete, the GPU question changes only rank/alpha capacity, and the
  expected job is short and bounded.
- Next checkpoint: immediately after EXP-019 completion or branch-changing
  failure. Do not admit another training experiment after it until the matching
  r8/r16 renderer is available and blind evidence can be collected.
- Explicitly deferred: additional seeds, MOS/statistics, LoRA+/DoRA, another
  conditioning sweep, architecture migration, route/product claims, and another
  broad review pass.
- High blocker: none after EXP-019 predecessor binding and true cross-arm
  comparator received independent approval.

## 2026-08-12T07:17:28Z - EXP-019 v1 pre-model operational stop

- Queue job `exp019-xvc-expanded79-broad400-rank16-native-lr-v1` exited `2`
  before model import with `real training requires the pinned offline
  environment`. The job allowlisted the three offline variable names, but the
  parent `run-next` invocation did not supply their values.
- No output directory, checkpoint, model update, or GPU training evidence was
  produced. This is an orchestration failure, not a rank-16 scientific result.
- Replan: append one condition-identical v2 job and invoke its queue controller
  with `HF_DATASETS_OFFLINE=1`, `HF_HUB_OFFLINE=1`, and
  `TRANSFORMERS_OFFLINE=1`. Preserve the runner, config, seed, data, schedule,
  receipt inputs, resource caps, and no-retry scientific contract unchanged.

## 2026-08-12T07:32:16Z - EXP-019 trajectory and matched blind render complete

- The condition-identical v2 trajectory ran with the three pinned offline
  environment values and completed 400 finite rank-16 updates in 88.25 seconds.
  Peak allocated GPU memory was 3,581,809,664 bytes under the 4-GiB cap; all
  five held-out payload counters remained zero, the immutable base remained
  exact, and five adapter checkpoints were exported with a terminal fresh-base
  reload.
- Validation medians at updates `0,48,96,192,400` were
  `840.1133,585.2890,528.5224,522.0286,575.3562`. Rank 16 descends faster than
  the rank-8 control at early checkpoints but does not improve its recorded
  step-192 minimum. This is technical trajectory evidence, not an audible
  winner.
- The separately sealed cross-arm renderer then succeeded with two validation
  IDs and four blinded candidates per ID: rank 8 and rank 16 at updates 96 and
  192. The mappings remain outside the listening indexes, and operator
  selection is pending.
- Replan: admit no further training run until the matched rank comparison and
  existing conditioning/window comparisons receive operator judgments. A
  capacity preference leads to one function-group placement question; a tie or
  rank-8 preference redirects to the frame-conditioning diagnostic.

## 2026-08-12T07:34:00Z - one-port listening interface adopted

- The operator requested one persistent SSH tunnel instead of a new listener
  port for every experiment. All individual listener processes were stopped.
- `tools/ms3-listening/serve.py` now defaults to the completed queue attempts,
  the listening artifact root, and the best-of root on port `8878`. The UI
  exposes `All` plus one tab per experiment collection, keeps selections across
  tabs, and exports one combined selection record. Future completed indexes
  appear after reload; no per-experiment listener server or port is started.
- Focused validation passed 13 Python tests, seven Node tests, Ruff, and the
  live projection check. The current projection contains 18 collections,
  32 runs, and 232 candidates without exposing repository paths.

## 2026-08-12T22:01:34Z - EXP-024 validation alignment pilot stopped

- Exact human same-text acquisition is complete: 424 Hadou source and 424
  Amitaro runrun target utterances are bound to official ITA IDs, display text,
  kana, audio hashes, and disjoint `334 / 36 / 54` roles. Existing RVC models
  were not retrained, and Qwen TTS was not mixed into the corpus.
- The sole admitted alignment pilot used runner SHA-256
  `9539e90b771a7f07e4407d489f7e97e0c1a0ef331ad997647c9fcf9309ab9a24`,
  started at `21:42:50Z`, attempted all 16 frozen validation IDs, and exited `2`
  at `21:44:20Z` with `fewer than 14 fixed validation IDs retained`.
- No aligned output or staging tree remained, the GPU was clean, and no retry,
  threshold change, full alignment, training, or render followed. The gate
  proves retained IDs were in `0..13`, but a runner cleanup defect destroyed the
  exact count and per-row rejection reasons.
- Replan: Stage B is blocked. Only CPU-only durable attempt/failure evidence
  hardening and the already-published 370-row pronunciation review on fixed port
  `8878` are Ready. A later model run requires a separate accepted replan; this
  failed attempt cannot be recreated under a diagnostic label.

## 2026-08-12T22:30:00Z - EXP-025 whole-short CPU replan opened

- EXP-025 is a new experiment, not a retry or threshold relaxation of the
  failed EXP-024 validation16 alignment attempt. It keeps the same 424 exact
  Hadou-to-Amitaro runrun ITA identities and does not train RVC or mix Qwen.
- A CPU-only PCM inventory uses non-overlapping 20 ms RMS frames at -45 dBFS,
  one 20 ms edge guard, complete source/target intervals, target duration
  1.8--2.4 seconds, and target/source duration factor 0.5--2.0. It found 108
  rows: train 87, validation 5, heldout 16. Validation is excluded from training
  and final evaluation. The train-plus-heldout stream SHA-256 is
  `faa542d67073038118dae0f3dc34b1fc8f056b639993f9f73815bf4a75f7d6bd`.
- The new materialization contract permits exactly one source-only,
  pitch-preserving complete-utterance stretch to the target clock, followed by
  common right padding to 2.4 seconds. It forbids DTW, tiling, truncation,
  internal-silence deletion, candidate substitution, and retry.
- Current state is CPU preparation only. Named candidate pronunciation review,
  source/target authorization receipts, the exact candidate lock, materializer
  tests, and independent admission review must pass before any model import or
  GPU training. The fixed port remains `8878`.

## 2026-08-13T12:00:00Z - hearing-loop process reset

- Agent: `primary-integrator` (this session).
- Task: Stop the hash/receipt factory and make voice-quality search the default
  agent completion function.
- Dependencies: operator diagnosis that agents optimized evidence ceremony
  instead of audible candidates; unheard libraries already on port 8878.
- Result: adopted `docs/planning/lab-operating-model.md` and
  `docs/planning/listen-queue.md` above experiment drafts for process.
- Changed action: listen-now then promote. Unheard-first. Dirty-tree digest is
  not an identity. Independent review waits for a `keep`. EXP-025 87-pair
  inventory is a listen-now train, not a plumbing cathedral. EXP-024 DTW gate
  stays closed.
- Rework avoided: another admission-receipt cycle before the next audible
  candidate.
- Adopted: Yes.

## 2026-08-13T01:12:50Z - Grok hearing-loop progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only snapshot; no tools or subagents).
- Task: Judge whether the current work is the shortest path to better Japanese
  voice quality and a personally usable realtime conversation system.
- Dependencies: fixed listener on `8878`, 17 unheard EXP-020/021/023
  candidates, idle RTX 5090, the accepted hearing-loop process, and the dirty
  shared worktree.
- Result: `REDIRECT`; no new audio or operator decision in the prior 30
  minutes.
- Adopted: Partially. Return immediately to the unheard queue and do not grow
  UI, identity, receipt, or review work. Keep the bounded listener-note change
  because the live page opened the optional 370-row pronunciation review and
  displayed a superseded GPU gate. Reject the suggested EXP-023-first order;
  the source-of-truth board requires EXP-020, then EXP-021, then EXP-023.
- Changed action: Make EXP-020 the initial listener tab with the three Ready
  collections ordered and plainly briefed. In parallel, isolate only the
  already-named 87-pair X-VC listen-now runner/note for a commit and render.
- Rework avoided: broad dirty-tree cleanup, another experiment schema,
  EXP-024 retry, pre-keep promote evidence, and further listener features.
- Cadence: tmux repeats the same read-only Grok audit every 1,800 seconds and
  appends its raw verdict to
  `/tmp/liveconv-grok-progress-auditor-v2.log`.
