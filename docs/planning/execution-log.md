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

## 2026-08-13T01:38:42Z - EXP-025 whole-short listen-now published

- Agent: `primary-integrator`.
- Task: Produce the independent Ready-board X-VC render without waiting for
  operator decisions on EXP-020/021/023.
- Start: after the 01:12 Grok audit; end: 01:38 UTC.
- Dependencies: committed runner/note, the inventoried 87 eligible train pairs,
  pinned X-VC base/runtime, authorized Amitaro runrun target archive, fixed
  listener on `8878`, and idle `gpu0`.
- Result: the first launch stopped before model load or any update because of
  one incorrect upstream import. Commit `db03907` repaired only that boundary.
  The condition-identical `v2` launch then completed 348 updates in 124.49
  seconds and published three plain-label base/adapted comparisons. Six
  candidate hashes match their indexes, audio formats are valid, and the
  heldout-target access counter is zero.
- Problems: one Repair-tier import failure; no scientific retry and no partial
  listener publication. The unused `v1` work directory is retained as failure
  evidence.
- Rework: one import-line repair, one regression assertion, and a fresh output
  locator. No corpus, schedule, rank, learning rate, or render-source change.
- Changed action: move EXP-025 from `Next listen-now to render` to `Unheard
  now`. Start no further X-VC trajectory until the operator records `keep` or
  `rejected` for this set.

## 2026-08-13T01:43:55Z - Grok hearing-loop progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only snapshot; no tools or subagents).
- Result: `REDIRECT`. The audit observed the new EXP-025 WAVs at 01:35 and no
  observable operator decision. It identified operator listening, rather than
  another render or evidence pass, as the critical path.
- Adopted: Yes for the decision. Stop new X-VC trajectories and hand the four
  Ready rows to the operator on `8878`. The listener and Ready board already
  include EXP-025 as three runs and six candidates.
- Rejected as stale input: the audit described the parent as still editing the
  old banner and treated EXP-025 publication as unknown. Both were already
  complete. The static auditor prompt caused that discrepancy.
- Changed action: replaced the tmux loop with a dynamic snapshot of the Ready
  board, execution-log tail, recent commits and WAVs, listener collections,
  running jobs, and GPU state. The next audit starts 1,800 seconds after the
  prior start; subsequent starts use the same 1,800-second cadence rather than
  adding Grok response time to the interval. Raw first/second audits remain in
  `/tmp/liveconv-grok-progress-auditor-v2.log`; the corrected loop writes
  `/tmp/liveconv-grok-progress-auditor-v3.log`.

## 2026-08-13T02:43:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `REDIRECT`. It recognized new EXP-026/027 audio but judged the Ready
  board stale and warned that more X-VC diagnostics before hearing could become
  a detour.
- Adopted: Partially. Update the live board immediately, collapse intermediate
  diagnostics, close the sweep at the already-committed final floor, and move
  to system integration. Do not stop all useful GPU work: the active user
  instruction explicitly requires productive GPU use while hearing is pending.
- Changed action: EXP-032 is the terminal lookahead diagnostic; the next lane
  must advance the realtime system rather than add another sweep point.
- Expected saving: avoids four redundant operator collections and an unbounded
  series of adjacent lookahead experiments.

## 2026-08-13T02:50:45Z - bounded GPU lane closed at X-VC stream floor

- Agent: `primary-integrator`.
- Task: Keep one useful GPU lane active while operator hearing was pending,
  then stop at a system-relevant boundary.
- Dependencies: committed runners, EXP-025 human87 model boundary, the actual
  8.17-second input, fixed listener `8878`, and exclusive `gpu0` use.
- Result: EXP-026 completed base/epoch4/8/12 on three heldout source rows.
  EXP-027 exposed epoch8/12 repetition at future 100 ms; EXP-028 showed it was
  absent offline; EXP-029--032 isolated the streaming-window interaction and
  closed the sweep. The lowest arm without gross auxiliary-ASR repetition was
  future 120 ms, with 260 ms total model context and CUDA chunk compute P50
  26.19 ms/P95 32.84 ms across 69 failures. All audio is on `8878`; operator
  hearing remains required.
- Problems: EXP-027 v1 stopped before model load on a padded-length assumption.
  EXP-030 v1 stopped before publication because its first inference used a
  one-time cold CUDA path and could not match a warm control hash.
- Rework: one explicit padded-length binding and one fixed discarded warmup;
  neither repair changed a published comparison arm. Intermediate EXP-027--031
  collections are diagnostic archives so the operator only drains EXP-032.
- Changed action: no more training-horizon or lookahead sweeps. Move to the
  experimental X-VC system path while preserving bypass and cancellation.

## 2026-08-13T03:11:37Z - EXP-032 candidate worker path published

- Agent: `primary-integrator`.
- Task: Put the existing epoch-8/future-120-ms candidate through the bounded
  X-VC worker state machine without activating the retained Gateway profile.
- Start: after the 02:43 Grok audit; end: 03:11 UTC.
- Dependencies: committed system-path probe, EXP-032 candidate identities,
  actual 8.17-second source, existing `XvcWorker`, fixed listener `8878`, and
  exclusive `gpu0` use.
- Result: `v4` published one source/system pair. The canceled generation
  produced zero stale frames; the retained generation completed contiguous
  409/409 input/output frames while respecting the 25-frame credit. Auxiliary
  faster-whisper-small found no gross loop. Gateway routing, Extension playout,
  route qualification, naturalness, and selection remain unclaimed.
- Problems: `v1` stopped before model load because CUDA device selection followed
  peak-memory reset. `v2` stopped before inference because deterministic cuBLAS
  configuration was absent. `v3` overflowed the direct worker queue because the
  probe omitted the Gateway bridge's output-backed credit; no failed attempt
  published audio, and the stuck `v3` exception-exit process was terminated.
- Rework: repaired only device ordering, deterministic runtime configuration,
  and credit accounting. The model, adapter, source, target reference, stream
  geometry, and cancellation question stayed fixed.
- GPU: peak allocation 2,701,843,456 bytes; 70 model calls; zero failures;
  compute P50 43.34 ms, P95 54.93 ms, cold max 1,573.58 ms. GPU returned idle.

## 2026-08-13T03:13:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `SIMPLIFY`. It recognized the new system-path audio as direct MS-3/MS-4
  progress and judged the focused worker/render stop condition satisfied.
- Adopted: Yes. Do not start another GPU lane merely to avoid idle hardware;
  after the bounded integration render, the highest-value next information is
  the operator's `keep | continue | rejected` on the already-published queue.
- Corrected stale audit input: the live library contains EXP-026, EXP-032, and
  `exp032-system-path-v4`; the auditor's compact `ready` extraction omitted
  them even though all are served on 8878. Add a concise system-path collection
  note so the operator sees the intended order and claim boundary.
- Changed action: stop worker polish, lookahead/training sweeps, and pre-keep
  route claims. Formal Gateway/Extension binding becomes eligible only after an
  EXP-032 `keep`.
- Expected saving: avoids at least one additional diagnostic/GPU cycle and
  moves directly to the decision that can kill or admit the candidate.

## 2026-08-13T04:13:55Z - Grok audit superseded by operator availability

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `SIMPLIFY`. Its snapshot correctly observed no new audio, commit, or
  operator decision in the preceding 30 minutes and repeated the hearing-first
  recommendation.
- Adopted: No after the audit started. The operator then explicitly stated that
  human hearing is unavailable during the current work window and directed the
  project to keep stacking bounded validation comparisons so the GPU is not
  wasted. The audit did not have that new premise; active user instruction
  therefore supersedes its stop recommendation.
- Changed action: keep listen-now/promote boundaries and one GPU lane, but make
  machine-screened candidate generation the temporary critical path. Start with
  the exact human87 trajectory at epochs 12/18/24 because loss was still
  decreasing through epoch 12. Require the completed epoch-12 WAVs as exact
  controls before publishing the extension.
- Not admitted: concurrent GPU sweeps, another lookahead point, RVC retraining,
  TTS-to-VC corpus mixing, EXP-024 retry, or any model/route selection claim.

## 2026-08-13T04:23:20Z - human87 extended horizon machine-screened

- Agent: `primary-integrator`.
- Task: Extend only the completed human87 training duration from epoch 12 to
  epochs 18/24 while operator hearing is unavailable.
- Dependencies: commit `8c40f26`, exact EXP-026 inputs, idle exclusive `gpu0`,
  the three public source-only rows, and fixed listener `8878`.
- Result: 2,088 updates completed in 262.54 seconds. Epoch-12 and base WAVs
  reproduced exactly; heldout-target access remained zero; 12 candidates were
  published. Loss at 12/18/24 was 367.1953/356.9258/310.8828.
- Machine screen: frozen base preserved the three texts closely. Expanded79
  adaptation degraded all three by epoch 12; epoch 24 produced a nonsensical
  second row and `ああああああ` for the third. This is a coarse content screen,
  not a naturalness or speaker-quality judgment.
- Changed action: stop horizon extension despite falling train loss. The next
  job changes only LoRA scope from expanded79 to the established control69
  attention/FFN modules at epochs 4/8/12. The hypothesis is that the extra ten
  projections damage content preservation on human pairs.
- GPU: peak allocation 3,568,677,888 bytes; returned idle after publication and
  the auxiliary ASR batch.

## 2026-08-13T04:31:26Z - human87 control69 scope comparison published

- Agent: `primary-integrator`.
- Task: Change only human87 LoRA scope from expanded79 to the established
  attention/FFN control69 modules at epochs 4/8/12.
- Dependencies: commit `af022dc`, the same 87-pair order and three public
  source rows, the same seed/rank/LR/clip/reference/conditioning, and `gpu0`.
- Result: 1,044 updates completed in 172.95 seconds and 12 candidates published
  on 8878. Loss at 4/8/12 was 441.6620/410.2230/396.1591. Base controls
  reproduced and heldout-target access remained zero.
- Machine screen: mean normalized transcript distance at control69 epochs
  4/8/12 was 0.329/0.346/0.198, versus 0.568 at expanded79 epoch 12. The short
  third sentence recovered from `あ、ありがとう。` to `あっ、ヘルが鳴ってる`.
- Changed action: control69 epoch 12 is a stronger content-preserving listening
  candidate, not an audible winner. Admit one 12/18/24 control69 horizon run;
  require exact control69 epoch-12 WAV reproduction and stop if longer training
  repeats the expanded79 degeneration.
- GPU: peak allocation 3,552,147,968 bytes; returned idle after publication and
  the auxiliary ASR batch.

## 2026-08-13T04:37:08Z - human87 control69 horizon closed

- Agent: `primary-integrator`.
- Task: Extend only the content-preserving control69 trajectory from epoch 12
  through epochs 18/24.
- Dependencies: commit `5536538`, exact control69 epoch-12 WAV controls, the
  same human87 inputs, and exclusive `gpu0`.
- Result: 2,088 updates completed in 244.85 seconds; loss at 12/18/24 was
  396.1591/373.4965/365.7220; controls reproduced; 12 candidates published.
- Machine screen: mean normalized content error worsened from 0.198 at epoch 12
  to 0.531/0.496 at epochs 18/24. The short sentence degraded to
  `あ!いらない!` and `ああああああ`.
- Changed action: stop all 1e-4 horizon extension. An independent ECAPA speaker
  metric exists, but the exact human reference is not in that evaluator's
  reviewed-target registry; do not block GPU work on authorization plumbing.
  Instead, keep control69 and halve only LR to 5e-5 at epochs 12/18/24.
- GPU: peak allocation 3,552,147,968 bytes; returned idle after publication and
  auxiliary ASR.

## 2026-08-13T04:45:09Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. The preceding 30 minutes produced two committed,
  single-variable control69 audio collections and the active half-LR job was
  using `gpu0`; Grok found that this followed the temporary machine-screened
  quality-search path without claiming a winner.
- Adopted: yes. Finish and screen the one active job before admitting another;
  keep a single GPU lane, skip ceremony and premature Gateway/Extension work,
  and do not convert auxiliary ASR into a naturalness or speaker-quality win.
- Changed action: because Grok also identified repeated use of the same three
  heldout rows as the main risk, the next gate is the existing 8.17-second
  actual ChatGPT input, not another horizon point.
- Cadence: the corrected tmux loop remains on an exact 1,800-second schedule;
  raw output is `/tmp/liveconv-grok-progress-auditor-v3.log`.

## 2026-08-13T04:50:00Z - human87 control69 half-LR closed

- Agent: `primary-integrator`.
- Task: Hold human87 data and control69 scope fixed, halve only AdamW learning
  rate to `5e-5`, and compare epochs 12/18/24.
- Dependencies: commit `06c164e`, the same 87-pair order, seed, rank, clip,
  reference, conditioning, and exclusive `gpu0`.
- Result: 2,088 updates completed in 247.54 seconds; loss at 12/18/24 was
  420.1410/403.3412/390.5418; heldout-target access remained zero; 12
  candidates were published on 8878.
- Machine screen: mean normalized content error was 0.255/0.348/0.441. The
  half-LR epoch 12 did not beat standard-LR control69 epoch 12 at 0.198, and
  longer training again degraded content. This is not an audible verdict.
- Changed action: close further human87 horizon/LR points. Reuse the exact base,
  expanded79 epoch-12, and control69 epoch-12 states on the actual 8.17-second
  input. Admit a system-path run only if that coarse screen generalizes.
- GPU: peak allocation 3,552,147,968 bytes; returned idle after publication and
  auxiliary ASR.

## 2026-08-13T04:56:00Z - EXP-026 scopes screened on actual input

- Agent: `primary-integrator`.
- Task: Reuse the exact base, expanded79 epoch-12, and control69 epoch-12
  states on the existing 8.17-second actual ChatGPT input.
- Dependencies: commit `fefbc4f`, fixed source/target/adapter hashes, no new
  training, and exclusive `gpu0`.
- Result: three outputs completed in 80.11 seconds and published as
  `exp026-actual-scope-offline-v1`; peak allocation was 2,845,547,520 bytes.
- Machine screen: source-relative auxiliary ASR character distance was 0.317
  for base, 0.463 for expanded79 epoch 12, and 0.439 for control69 epoch 12.
  Control69 retained a small relative content advantage over expanded79 and
  showed no gross loop, but neither adaptation beat base. No audible quality,
  naturalness, or speaker-identity claim is made.
- Problems: the evidence STT wrapper rejected X-VC float WAV input; the same
  pinned local faster-whisper model accepted the files directly. No audio was
  regenerated and the failed wrapper attempt did not publish evidence.
- Changed action: admit one control69 epoch-12/future-120 worker/cancellation
  probe. A stale frame, queue failure, gross repetition, or content collapse
  closes this branch; do not add another training point.

## 2026-08-13T05:01:00Z - control69 system-path branch closed

- Agent: `primary-integrator`.
- Task: Run the exact control69 epoch-12 adapter on the actual input through
  the established future-120 `XvcWorker` queue and cancellation path.
- Dependencies: commit `547b132`, fixed source/target/adapter hashes, and
  exclusive `gpu0`.
- Result: generation cancellation acknowledged in 0.016 ms with zero stale
  frames. The retained generation completed contiguous 409/409 input/output
  frames in 9.575 seconds, max in-flight 25, with 70 model calls and zero
  failures. Compute P50/P95 was 42.59/49.35 ms; peak GPU allocation was
  2,701,059,072 bytes. The WAV was published as
  `exp026-control69-e12-system-path-v1`.
- Machine screen: the output transcript ended in a long repeated `な`, unlike
  its offline control. This is a gross corruption stop, not a naturalness or
  speaker-quality judgment.
- Changed action: close control69 from further machine-only tuning. Run the
  unadapted base through exactly the same future-120 worker path once to
  distinguish an adapter/stream interaction from base streaming failure.

## 2026-08-13T05:05:00Z - base future-120 system control completed

- Agent: `primary-integrator`.
- Task: Remove LoRA entirely while holding actual input, target reference,
  future-120 geometry, worker queue, cancellation, and pacing fixed.
- Dependencies: commit `e60a071`, exact base checkpoint, and exclusive `gpu0`.
- Result: cancel acknowledgement was 0.015 ms with zero stale frames. The
  retained generation completed contiguous 409/409 frames in 9.489 seconds,
  max in-flight 25, with 70 calls and zero failures. Compute P50/P95 was
  35.36/37.54 ms; peak allocation was 2,697,716,736 bytes. The WAV was
  published as `exp026-base-system-path-v1`.
- Machine screen: no gross repetition. Source-relative ASR distance was 0.512,
  better than the old expanded79 epoch-8 system output at 0.561, but worse than
  offline base at 0.317.
- Changed action: the long control69 repetition is an adapter/stream
  interaction, while base streaming still loses content. Reuse the previously
  established 200-ms lookahead endpoint once with base. Do not add a new
  intermediate point; improvement admits hearing only, and failure closes the
  X-VC machine-screened streaming search.

## 2026-08-13T05:09:00Z - base future-200 endpoint completed

- Agent: `primary-integrator`.
- Task: Reuse the already-established future-200 endpoint with unadapted X-VC
  base, holding actual input, target, worker, cancellation, and pacing fixed.
- Dependencies: commit `e47cf25`, exact base checkpoint, and exclusive `gpu0`.
- Result: cancel acknowledgement was 0.029 ms with zero stale frames. The
  retained generation completed contiguous 409/409 frames in 9.668 seconds,
  max in-flight 25, with 70 calls and zero failures. Compute P50/P95 was
  36.83/44.39 ms; peak allocation was 2,697,716,736 bytes. The WAV was
  published as `exp026-base-future200-system-path-v1`.
- Machine screen: no gross repetition; normalized source-relative ASR distance
  improved from 0.512 at future 120 to 0.463 at future 200, but remained worse
  than offline base at 0.317. This is hearing-only, not a quality selection.
- Changed action: close X-VC horizon, LR, scope, and lookahead machine search.
  Do not spend the 400-ms latency budget on a larger endpoint.

## 2026-08-13T05:15:18Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok confirmed that the preceding 30 minutes produced
  several committed, sequential, single-variable audio collections and that
  future-200 was the board's explicit final X-VC stream endpoint.
- Adopted: yes. Screen future-200, close the X-VC stream search regardless of
  perceptual outcome, and replan exactly one quality lane independent of human
  hearing. Reject more lookahead/LR/horizon/control69 work, parallel sweeps,
  route binding, and promote ceremony.
- Changed action: the next lane is the already-deployed RVC Runrun preset set
  on the same actual input. It is a bounded comparison, not retraining and not
  a quality winner declaration.
- Expected saving: avoid at least one further X-VC diagnostic cycle and keep
  the next GPU lane ready immediately after closure.

## 2026-08-13T05:16:00Z - existing Sasayaki presets machine-screened

- Agent: `primary-integrator`.
- Task: Reuse the six already-rendered Sasayaki parameter outputs on the exact
  actual-input source for a common auxiliary-ASR corruption/content screen.
- Result: normalized source-relative distances were 0.537 for the anchor,
  0.561/0.780/0.561/0.659 for index 0.00/0.10/0.20/0.30 at RMS 0.25, and 0.537
  for index 0.20/RMS 0.00. No new audio or perceptual selection was claimed.
- Changed action: presets materially change content behavior, so compare the
  five existing Runrun presets through the actual Gateway next rather than
  training RVC or extrapolating from the standard profile alone.

## 2026-08-13T05:28:00Z - Runrun presets rendered through the live Gateway

- Agent: `primary-integrator`.
- Task: Compare Runrun standard plus four deployed presets, with Sasayaki
  standard as a cross-style reference, on the exact 8.17-second actual input.
- Dependencies: commit `1db055b`, sealed deployment
  `9b7e2090039f3ed89511307573f98882d8fa692029e2dddda2b662ebdba7b11d`,
  exact source hash, live Gateway `8877`, realtime 20 ms pacing, and `gpu0`.
- Result: all six profiles completed without fallback or dropped frames and
  were published as `exp020-runrun-presets-actual-v1`. Per-profile wall time
  was 85.89--97.94 seconds, dominated by worker/model startup.
- Machine screen: source-relative transcript distance was 0.512 for Sasayaki
  standard and 0.610 for Runrun standard. Runrun soft/high/clean-bright were
  0.829/0.707/0.683; girl-bright produced a gross repeated phrase and is closed
  for further machine-only work. No perceptual winner is selected.
- Changed action: a second Runrun standard "system-path" render would be
  duplicate work because this run already used the live Gateway and realtime
  frame pacing. Use cross-input evidence before another RVC preset decision.

## 2026-08-13T05:32:00Z - existing VC families cross-screened

- Agent: `primary-integrator`.
- Task: Apply the same pinned auxiliary-ASR corruption/content screen to the
  existing 32-variant actual-input library; generate no duplicate audio.
- Result: best normalized source-relative distances were 0.488 for RVC
  Sasayaki clean-bright and X-VC Yofukashi q34, 0.561 for X-VC Runrun, and
  0.585 for several RVC/X-VC standard arms. OpenVoice Runrun/Yofukashi and
  MeanVC2 q34 contained severe transcript-length/repetition explosions. The
  later X-VC base future-200 output was 0.463, lower than all 32 historical
  candidates on this content metric only.
- Changed action: close OpenVoice and MeanVC2 parameter/reference-length
  expansion for machine-only work. Keep RVC Sasayaki clean-bright and X-VC
  base future-200 as hearing candidates; neither is an audible selection.

## 2026-08-13T05:45:26Z - Qwen natural-style axis closed

- Agent: `primary-integrator`.
- Task: Hold Qwen3-TTS 1.7B, Ono_Anna, Japanese, 12 texts, sampling, and seeds
  fixed; change only empty `instruct` to one natural-conversation instruction.
- Dependencies: commits `1d4efa4` and cleanup fix `b543eca`, the existing
  EXP-023 runtime/model/fixture, fixed listener `8878`, and exclusive `gpu0`.
- Result: 12 new style outputs plus the 12 exact default controls were
  published as `exp023-qwen3-tts-ono-anna-natural-style-v1`; all 12 new files
  completed the pinned CUDA faster-whisper screen.
- Machine screen: default macro text CER was 0.0876 with 6/12 exact rows;
  natural-style was 0.1175 with 5/12 exact rows. TTS007 improved, but TTS006
  and TTS012 regressed. This is content evidence only, not a naturalness score.
- Problems: the first wrapper run generated all 12 WAVs but failed before
  publication because it used non-recursive removal for Qwen's temporary HOME
  cache. Fail-closed cleanup removed staging; no partial collection appeared.
- Rework: changed only cache cleanup to recursive removal, added a regression
  test, committed the fix, and reran identical model settings. Do not add a
  second instruction wording or another TTS profile in this machine-only lane.

## 2026-08-13T05:43:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. The preceding 30 minutes produced committed Runrun and
  Qwen comparisons on 8878 while X-VC search, RVC retraining, promote work, and
  parallel GPU sweeps stayed closed. Grok warned that another TTS lane would
  become a detour from realtime VC.
- Adopted: yes. Close TTS style expansion and return to the RVC path with one
  machine-screened lane. Continue one GPU job at a time and keep all audio
  unselected until human hearing.
- Not adopted literally: Grok proposed another Runrun standard bounded
  system-path render, but the just-completed six-profile run already exercised
  the exact profile through live Gateway/WebSocket with realtime 20 ms pacing.
  Rerendering it would add no quality information.
- Changed action: test whether the best historical RVC content candidate,
  Sasayaki clean-bright, generalizes against Sasayaki standard across three
  public heldout source utterances. This avoids single-input overfitting while
  producing six new hearing files.
- Expected saving: skip one redundant 85--98 second worker render and all
  further TTS/X-VC tuning cycles.

## 2026-08-13T05:53:28Z - Sasayaki heldout generalization started

- Agent: `primary-integrator`.
- Task: Render deployed Sasayaki standard and clean-bright on public heldout
  `EMOTION100_002`, `EMOTION100_004`, and `EMOTION100_017` through live Gateway
  `8877`, then content-screen the six outputs.
- Dependencies: commit `78a3551`, the exact sealed deployment and public
  source hashes, realtime 20 ms pacing, fixed listener `8878`, and `gpu0`.
- Stop: publish exactly six unselected outputs, close any arm with gross
  corruption, and do not convert auxiliary ASR into a perceptual winner.
- Status: in progress; profiles are ordered outermost so all three rows for one
  worker identity run consecutively before the second profile is loaded.

## 2026-08-13T06:03:00Z - Sasayaki heldout generalization completed

- Agent: `primary-integrator`.
- Result: Sasayaki standard and clean-bright both completed all three public
  rows through live Gateway `8877` with realtime 20 ms pacing. Six new WAVs
  were published as `exp020-sasayaki-heldout-generalization-v1`; every
  generation was finite, contiguous, changed from input, and invalidated on
  session close.
- Machine screen: known-text macro CER was 0.477 for standard and 0.184 for
  clean-bright. Clean-bright was lower on all three rows, so its coarse content
  advantage generalized beyond the single actual input. This does not rank
  naturalness, voice identity, or perceptual quality.
- Problems: the evidence wrapper rejected the PCM24 outputs. The same pinned
  local faster-whisper model screened the unchanged WAVs directly; no audio
  was regenerated.
- Changed action: close Sasayaki standard for further machine-only preset work
  and retain clean-bright for hearing. Do not add another RVC preset point.

## 2026-08-13T06:07:00Z - full-utterance and F0 boundaries screened

- Agent: `primary-integrator`.
- Task: Separate the live block boundary and pitch extractor from the retained
  Sasayaki clean-bright profile without opening a broad sweep.
- Existing full-utterance result: source-relative CER was 0.682 for the live
  Gateway anchor and 0.636 for the already-rendered upstream full-utterance
  control. The small 0.046 change left both poor, so frame batching is not the
  sole content failure and block-size search is closed.
- New F0 result: six full-utterance WAVs were published as
  `exp020-sasayaki-f0-offline-v1`. Known-text macro CER was 0.327 for RMVPE and
  0.292 for PM; PM changed only one row materially and both trailed the live
  clean-bright result at 0.184. F0 extractor expansion is closed pending human
  hearing.
- Problems/rework: the first F0 attempt used relative input paths while the
  upstream runtime changes working directory. It stopped before GPU inference;
  the exact failed directory was moved to
  `/tmp/liveconv-exp020-sasayaki-f0-offline-v1-failed-relative-path`. Commit
  `0212cd4` resolved all paths before the successful rerun.

## 2026-08-13T06:15:56Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `SIMPLIFY`. Grok correctly required the six heldout WAVs to be
  content-screened, warned against more RVC knobs, and redirected the next
  useful work toward a surviving real system route.
- Adopted: yes for closing parameter expansion and returning to a system-path
  comparison. The literal recommendation to render clean-bright on the actual
  ChatGPT input was not repeated because that exact profile/input output
  already exists in the 32-variant collection and was screened at 0.488.
- Snapshot lag: by audit completion the heldout screen was already available
  and the bounded F0 run had already completed. Its result was screened and
  closed rather than used to justify another F0 point.
- Changed action: compare the two surviving VC families on the same three
  texts, then publish only a compact cross-family hearing shortlist.

## 2026-08-13T06:40:00Z - two-family live-route shortlist published

- Agent: `primary-integrator`.
- Task: Put the surviving RVC and X-VC families on the same three source texts
  and the same live Gateway/realtime frame boundary before shortening the
  hearing queue.
- Dependencies: commits `d28cc9c`, `2082a31`, and `f3af234`; sealed deployment;
  fixed public source hashes; live Gateway `8877`; listener `8878`; one GPU
  lane.
- Baseline screen: the existing offline X-VC base files had macro CER 0.163,
  versus 0.184 for live RVC clean-bright. Because route conditions differed,
  those files were not used as the final comparison.
- New audio: deployed X-VC Yofukashi Q034 completed all three sources through
  the live Gateway. Three new PCM24 WAVs were finite, contiguous, changed from
  input, and published as `exp026-xvc-yofukashi-q34-heldout-route-v1`.
  Direct pinned faster-whisper macro CER was 0.166, with no gross loop.
- Problems/rework: the first route attempt stopped before audio with
  `MODEL_UNAVAILABLE`. X-VC's source-identity gate treated 11 ignored
  `__pycache__` directories as a dirty checkout. They were moved recoverably to
  `/tmp/liveconv-xvc-source-pycache-recovery.MmtxBr`; the failed work directory
  was retained at
  `/tmp/liveconv-exp026-xvc-yofukashi-q34-heldout-route-v1-failed-model-unavailable`.
  An isolated backend warmup then passed before the exact route rerun.
- Decision: 0.166 versus 0.184 is too small and row-dependent for machine
  selection. Both arms remain unselected. The exact three rows by two live
  routes were copied into `ms3-vc-heldout-shortlist-v1` so later hearing does
  not require navigating the full archive.
- GPU: X-VC route generation and both fixed STT screens completed; `gpu0` is
  idle pending the next audited system-path job.

## 2026-08-13T06:43:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `REDIRECT`. Grok accepted the new X-VC live-route audio and compact
  shortlist, closed the exhausted model axes, and asked for one missing live
  X-VC Q034 render on the existing 8.17-second ChatGPT input.
- Adopted: yes for moving from model tuning to a conversation-system boundary.
- Not adopted literally: the requested exact source/profile/render already
  exists in `20260811-114251-32-variants`; its source hash, live Gateway
  profile, configuration hash, and output were verified. A rerender would have
  been a duplicate.
- Changed action: compare fresh versus persistent Gateway sessions for the two
  surviving RVC/X-VC profiles, using the same three public heldout inputs.

## 2026-08-13T06:54:00Z - persistent VC session comparison completed

- Agent: `primary-integrator`.
- Task: Send three sequential generations through one live Gateway session for
  RVC Sasayaki clean-bright and X-VC Yofukashi Q034, then compare each output
  with its existing fresh-session control.
- Dependencies: commit `c5a883c`, sealed deployment, live Gateway `8877`,
  fixed listener `8878`, and one profile/worker at a time on `gpu0`.
- Result: twelve unselected comparison WAVs were published as
  `ms3-vc-session-reuse-v1`. Once loaded, both workers completed a generation
  in about 2.4 seconds; the old fresh RVC path had paid roughly 82 seconds of
  startup per source.
- Signal screen: X-VC fresh/persistent correlation was at least 0.999999988.
  RVC was 0.601, 0.680, and -0.134, with the third row at -3.55 dB SNR. Fixed
  Whisper content CER changed from 0.184 fresh to 0.314 persistent for RVC;
  X-VC stayed at 0.166.
- Changed action: keep persistent workers for latency, but diagnose RVC's
  generation-boundary variability before treating its conversation output as
  stable.

## 2026-08-13T06:59:41Z - RVC same-input drift reproduced

- Agent: `primary-integrator`.
- Task: Repeat exact public input `EMOTION100_017` three times within one RVC
  clean-bright Gateway session.
- Dependencies: commit `c6c7b5b`; identical source bytes and profile settings;
  only generation position changed.
- Result: three new unselected WAVs were published as
  `ms3-rvc-repeat-turn-v1`. Generation 2/3 correlation to generation 1 was
  -0.283/-0.083, maximum difference was 0.502/0.429, and fixed Whisper CER
  changed from 0.222 to 0.444/0.444. This is reproducible turn-to-turn output
  drift, not an input-row effect.
- Root cause: the pinned RVC synthesizer samples its latent representation with
  `torch.randn_like()` on every block. The existing generation reset cleared
  audio, pitch, RMS, and SOLA buffers but did not reset the model RNG.

## 2026-08-13T07:13:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `SIMPLIFY`. Grok required the new session diagnostics to be visible
  on `8878`, rejected further seed/runtime ceremony and broad model-knob work,
  and requested immediate publish, coarse screen, and replan.
- Adopted: yes. The session-reuse and repeat-turn collections were confirmed
  in the live listener; no new hash, receipt, review, or model-family lane was
  opened. Seed/runtime repairs stopped once audio was produced.
- Not adopted literally: the audit snapshot preceded the first seeded audio.
  Because one explicit seed could make output consistently bad, one standard
  seed-0 control was admitted after seed 34; no further seed points are
  allowed before hearing.

## 2026-08-13T07:22:35Z - RVC generation seed control closed

- Agent: `primary-integrator`.
- Task: Bind an explicit inference seed at generation reset and compare three
  repeats of exact public input `EMOTION100_017`; change CUDA Graph once only to
  locate any residual numeric difference, then compare seed 34 with seed 0.
- Dependencies: commits `c9a52ba`, `4d4ada5`, `f6067ac`, `f1114c3`, and
  `3d6d4c7`; retained isolated RVC runtime and public source; listener `8878`.
- Result: seed 34 with CUDA Graph improved repeat correlations from
  -0.283/-0.083 to 0.999997/0.999998 and reduced maximum difference from about
  0.5 to at most 0.00138. Disabling CUDA Graph left the same tiny residual, so
  graph-specific work is closed. Seed 0 reproduced the same stability at
  0.999998 correlation and at most 0.00134 maximum difference.
- Content screen: all seed-34 files transcribed as `ヴェルがなってる` (CER
  0.444); all seed-0 files transcribed as `いや、ベルがなってる` (CER
  0.333). Both passed gross corruption/repetition screening. Seed 0 is the
  lower-content-error integration candidate, not a perceptual winner; seed 34
  remains a hearing control. No further seed search is admitted.
- Problems/rework: three attempts stopped before useful publication on sealed
  environment, installed-runtime, OS-isolation, and upstream-cwd safety gates.
  Each was repaired narrowly and retained recoverably under `/tmp`; no partial
  listener collection appeared. The fourth attempt generated the first audio.
- Validation: 25 focused RVC/Gateway/runner tests and focused Ruff checks pass.
  `make check` completed its repository/control checks, then the lint phase
  failed on 272 pre-existing errors in unrelated dirty/untracked EXP-007 and
  X-VC files. Those files were not changed as part of this slice.
- Changed action: integrate seed 0 through the bounded worker/Gateway profile
  and rerun the three-turn conversation comparison; do not widen training,
  model, F0, lookahead, or seed axes.

## 2026-08-13T07:41:00Z - seeded RVC conversation route verified

- Agent: `primary-integrator`.
- Task: Run the seed-0 RVC profile through the sealed worker and live Gateway,
  repeating exact public input `EMOTION100_017` for three generations in one
  session.
- Dependencies: commits `078f8b0` and `2533927`; isolated seeded runtime;
  evaluation-only Gateway `8881`; fixed listener `8878`.
- Result: three new unselected WAVs were published as
  `ms3-rvc-seed0-gateway-repeat-v2`. Generation 2/3 correlation to generation
  1 was 0.9999967/0.9999976, maximum difference was 0.00125/0.00118, and SNR
  was 51.82/53.13 dB. The pre-fix route had correlation -0.283/-0.083 and
  maximum differences above 0.42.
- Machine screen: all three outputs transcribed as
  `いや、ベルがなってる` (CER 0.333). This rejects gross turn-dependent
  content corruption but does not select perceptual quality.
- Problems/rework: the first route attempt stopped before GPU inference with
  HTTP 404 because a listen-now profile has no promote-tier route receipt.
  Commit `2533927` selected the existing evaluation-only session endpoint;
  no receipt, hash ceremony, or formal route claim was added.
- Changed action: the RVC generation-boundary fix is verified through the
  actual Gateway/worker path. Close seed and bit-exactness work; retain seed 0
  as the sole stable integration candidate pending hearing.

## 2026-08-13T07:45:56Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `REDIRECT`. Grok accepted the turn-stability fix as relevant to
  realtime conversation, required the closed seed/bit-exact axis to stay
  closed, and redirected the idle GPU to one frozen-converter actual-input
  quality render.
- Adopted: yes. No further seed, CUDA Graph, receipt, formal bind, training,
  F0, lookahead, or model-family point was opened. The next lane used the
  frozen seed-0 profile once on the existing 8.17-second actual input.
- Expected time saved: Grok estimated 20--40 minutes by stopping stability
  confirmation work and moving directly to new listening audio.

## 2026-08-13T07:54:00Z - stable RVC actual-input comparison published

- Agent: `primary-integrator`.
- Task: Render the frozen seed-0 RVC clean-bright profile once on the existing
  8.17-second ChatGPT-tab input and publish it beside the historical unseeded
  clean-bright output.
- Dependencies: commits `93adf7e`, `20e2842`, and `689dd14`; evaluation-only
  Gateway `8881`; fixed PCM24 source and historical-control hashes; listener
  `8878`.
- Result: `ms3-rvc-seed0-actual-input-v5` contains the exact listening source,
  the historical unseeded control, and one new stable seed-0 Gateway output.
  The new route completed 409 contiguous frames in 8.193 seconds with finite,
  changed PCM and no timestamp drift. Output SHA-256 is `244733423790ef297348c0acb1c45b89770c2d4d35248d8f19448ba7d84509a0`.
- Machine screen: fixed faster-whisper source-relative CER was 0.727 for the
  historical control and 0.636 for seed 0; neither transcript gross-looped.
  This does not rank naturalness, voice identity, or perceptual quality.
- Evidence limit: both arms use the same frozen PCM24 listening source. The
  historical arm predates retention of its raw float32 input, while the new
  arm deterministically decodes that PCM24 source. Treat this as a hearing
  comparison, not a strict seed-only causal estimate.
- Problems/rework: four attempts stopped before GPU inference on PCM16-only
  ingestion, a stale historical raw-float hash, and an 8,000 ms ingress budget
  that advertised 400 frames for a 409-frame source. The successful isolated
  Gateway used a 10,000 ms evaluation budget; no model setting changed.
- Changed action: close this actual-input job after publication and gross
  screen. The stable converter remains unselected pending hearing.

## 2026-08-13T08:02:00Z - stable two-family heldout shortlist published

- Agent: `primary-integrator`.
- Task: Replace the hearing shortlist's turn-unstable RVC arm with the frozen
  seed-0 profile without opening another model or seed point.
- Dependencies: commit `08d63a2`; evaluation Gateway `8881`; exact three
  public source hashes; retained X-VC Q034 route outputs; existing stable RVC
  row `EMOTION100_017`; listener `8878`.
- Result: seed-0 RVC generated the two missing public rows in one persistent
  session. After worker load, both 120-frame generations completed in
  2.403/2.402 seconds with finite changed PCM, contiguous sequences, and echoed
  timestamps. The existing third seed-0 row and all three X-VC rows were reused
  by exact hash. Six comparison WAVs are published as
  `ms3-stable-vc-heldout-shortlist-v1`.
- Machine screen: stable RVC known-text CER by row was 0.444/0.053/0.333,
  macro 0.277. Retained X-VC was 0.222/0.053/0.222, macro 0.166. Neither arm
  gross-looped. These values reject corruption only and do not select voice
  quality.
- Changed action: make the stable shortlist the only active cross-family
  hearing surface. The prior `ms3-vc-heldout-shortlist-v1` remains historical
  because its RVC arm predates the generation-boundary fix. Do not add another
  seed or model knob before hearing.

## 2026-08-13T08:15:38Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok accepted the stable shortlist and actual-input
  output as new listening audio, classified RNNoise as a valid one-variable
  actual-input comparison rather than a closed training-axis retry, and told
  the parent to start the committed job immediately.
- Adopted: yes. Commit `b6a5eac` was already CPU-admitted; the parent launched
  exactly one raw-versus-RNNoise stable-RVC job. No second GPU lane, training,
  seed, F0, lookahead, receipt, or formal route-bind work was opened.
- Expected time saved: 10--20 minutes versus continued idle/planning and
  30--60 minutes versus reopening a closed training axis.

## 2026-08-13T08:22:00Z - stable RVC RNNoise comparison closed

- Agent: `primary-integrator`.
- Task: Hold the 8.17-second actual input, stable seed-0 RVC profile, Gateway,
  and persistent session fixed; change only stateful RNNoise preprocessing.
- Dependencies: commits `b6a5eac` and `40fdf7b`; fixed source, RNNoise helper,
  RNNoise manifest, and seeded deployment identities; evaluation Gateway
  `8881`; listener `8878`; exclusive `gpu0`.
- Result: raw and RNNoise arms both completed 409 contiguous finite frames in
  8.192/8.194 seconds with echoed timestamps. They are published as
  `ms3-stable-rvc-rnnoise-v1`; output SHA-256 values are `bc6bbe26fea62bd605a91089d80a6b706a5593c7b8937fc1134bc36d151e2128`
  and `12745c7fd4eeaffbe0e12608377f643ea5043d46efbbd092b10ecec324726828`.
- Machine screen: source-relative faster-whisper CER was 0.636 for raw and
  0.682 for RNNoise. Neither gross-looped. This closes RNNoise expansion on
  the stable RVC arm; it does not rank perceptual quality.
- Problems/rework: model inference completed, but publication first failed on
  a cross-filesystem atomic rename from `/tmp` into the repository. Generated
  audio was retained. Commit `40fdf7b` moved future staging beside the final
  listener directory. The completed files were copied to same-filesystem
  hidden staging, hash-verified, and atomically published without rerunning
  GPU inference.
- Changed action: keep the stable cross-family shortlist at highest hearing
  priority and do not add another RVC denoise point.

## 2026-08-13T08:34:00Z - stable X-VC RNNoise comparison closed

- Agent: `primary-integrator`.
- Task: Reuse the same single-variable raw-versus-RNNoise plan on stable X-VC
  Yofukashi Q034, whose persistent-session output was already numerically
  stable; do not infer the RVC preprocessing result across model families.
- Dependencies: commit `0f6eeb9`; sealed deployment revision `9b7e209...`;
  evaluation Gateway `8882` with 10,000 ms ingress credit; exact source and
  RNNoise identities; listener `8878`; exclusive `gpu0`.
- Result: both arms completed 409 contiguous finite frames in 8.272/8.238
  seconds in one loaded session and published as `ms3-stable-xvc-rnnoise-v1`.
  Raw/RNNoise output SHA-256 values are `dafd2f84f170ef9c5f1557b43d13aff4be7ee64e75126c969ea3fbef4c3c33d1`
  and `645e7f1fe0a6bfc39d0ddc9166200e7bd9daa7531421a463e0be5a6794f8cb7a`.
- Machine screen: source-relative CER improved from 0.773 raw to 0.659 with
  RNNoise; neither gross-looped. The effect is opposite to RVC, but the X-VC
  denoised arm did not beat stable RVC raw at 0.636. This is coarse content
  evidence only, not a perceptual or cross-family winner.
- Problems/rework: the first isolated-Gateway activation stopped before model
  execution because the historical deployment lacked the now-required empty
  route-parity registry. A private `/tmp` deployment copy filled only that
  derived empty registry; bundle, profiles, manifest, authorization, runtime
  identities, and settings remained unchanged. Gateway preflight passed.
- Discovery: two retained listener collections contain byte-identical original
  decoded actual-input PCM at SHA-256 `b114aed49c79291b10caf30f9828e6efb0e191773aa2fe8ab77d786f7a83b5f2`.
  This corrects the earlier working assumption that the raw float input was
  unavailable. It correlates almost exactly with the later PCM24 re-decode but
  differs in amplitude (maximum sample difference 0.0672), enough to confound
  a VC comparison.
- Changed action: close RNNoise expansion. Render stable seed-0 RVC once from
  the recovered exact raw PCM, then compose an exact-input actual RVC/X-VC
  shortlist without regenerating the existing X-VC control.

## 2026-08-13T08:42:00Z - exact-input stable VC actual shortlist published

- Agent: `primary-integrator`.
- Task: Hold the exact original decoded actual-input float PCM fixed, render
  stable seed-0 RVC once, and compare it with the retained X-VC Yofukashi Q034
  output that consumed byte-identical input.
- Dependencies: commit `cf693d9`; raw source SHA-256 `b114aed...`; evaluation
  Gateway `8881`; retained X-VC output SHA-256 `bbcc638...`; listener `8878`;
  exclusive `gpu0`.
- Result: one new RVC output completed 409 contiguous finite frames in 8.196
  seconds with echoed timestamps. It was atomically published with the reused
  X-VC control as `ms3-stable-vc-actual-shortlist-v1`. RVC output SHA-256 is
  `e00b7f6ec53e838ee3b7cd77d1c6af3035ff3a8e49b724c674631f53cc56e13f`.
- Machine screen: source-relative faster-whisper CER was 0.417 for stable RVC
  and 0.833 for stable X-VC. Neither gross-looped. This admits both for hearing
  but does not rank naturalness, voice identity, or perceptual quality.
- Rework: the first screen invocation completed all three transcriptions but
  used the wrong metrics attribute name while formatting the report. The
  corrected invocation reused the cached model and changed no audio.
- Changed action: the earlier actual-input comparison confound is removed.
  Keep the public heldout shortlist first and this exact actual-input shortlist
  second for operator hearing; do not rerender either arm.

## 2026-08-13T08:45:51Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok accepted the three new comparisons and exact-input
  repair as direct MS-3 progress, required the idle GPU to take one next
  committed single-variable lane, and kept RNNoise, training, horizon, LR,
  lookahead, rerenders, promote work, and machine quality selection closed.
- Adopted: yes. The suggested additional pre-VC capture was not available.
  Instead, the parent used the newly measured exact 3.0103 dB source-level
  difference and its correlated RVC content change to admit one safe +3.0103 dB
  point. The runner was CPU-admitted and committed before taking `gpu0`.
- Expected time saved: the next 30-minute window produces a bounded result
  instead of waiting for hearing or reopening a closed model/training axis.

## 2026-08-13T08:51:00Z - stable RVC input-gain probe closed

- Agent: `primary-integrator`.
- Task: Hold the exact actual waveform, stable seed-0 RVC profile, and Gateway
  fixed; increase input gain exactly 3.0103 dB once, derived from the recovered
  raw-versus-PCM24 level difference.
- Dependencies: commit `e78a818`; raw source SHA-256 `b114aed...`; retained
  exact-level RVC output SHA-256 `e00b7f6...`; evaluation Gateway `8881`;
  listener `8878`; exclusive `gpu0`.
- Result: input peak rose from 0.229 to 0.324 without clipping. The new arm
  completed 409 contiguous finite frames in 8.192 seconds with echoed
  timestamps and published as `ms3-stable-rvc-input-gain-v1`. Output SHA-256
  is `3c690e0b08720caa830873bbab4b37593ce08953704e93da092e9c812a0c550e`.
- Machine screen: source-relative faster-whisper CER was 0.417 at the recovered
  original level and 0.472 at +3.0103 dB. Neither gross-looped. Combined with
  the earlier -3.0103 dB result at 0.636, the coarse minimum is bracketed near
  the recovered original level on this input; no perceptual winner is claimed.
- Changed action: close finer gain search and retain the A/B for optional
  hearing. Do not infer a production normalizer from one actual input.

## 2026-08-13T09:01:00Z - stable RVC natural turn-boundary defect reproduced

- Agent: `primary-integrator`.
- Task: Hold exact input bytes, order, total frames, stable seed-0 RVC profile,
  and Gateway fixed; split only the generation at 4.24 seconds, the center of
  an existing 560 ms sub--50 dBFS silence.
- Dependencies: commit `5587fc8`; exact raw source and one-generation output;
  evaluation Gateway `8881`; listener `8878`; exclusive `gpu0`.
- Result: both generations completed in one Gateway session and concatenated
  to the same 409-frame length as the one-generation control. The new output
  published as `ms3-stable-rvc-turn-split-v1` with SHA-256
  `e79cc12e00f9a2fa95a8c32bdab8f649aea9d7dbd1e7268a9e876c928c000598`.
- Machine screen: full-input CER worsened from 0.417 to 0.556 without gross
  repetition. Per-turn decoding localized the change: turn 1 was identical at
  0.577, while the reset turn 2 worsened from 0.167 to 0.500.
- Interpretation limit: this identifies a generation-boundary quality defect,
  not whether naturalness or voice identity is worse. It does not by itself
  distinguish latent-noise restart, cold context, or overlap state.
- Changed action: prioritize one root-cause control at the RVC generation
  boundary before another voice, gain, denoise, input, or training lane.

## 2026-08-13T09:13:00Z - zero-latent-noise RVC control rejected

- Agent: `primary-integrator`.
- Task: Compare the pinned RVC posterior latent-noise scale 0.66666 with zero
  on exact actual input, holding checkpoint, index, seed, settings, and direct
  backend path fixed; retain the stable Gateway output as a path control.
- Dependencies: commits `92e8950`, `5a5d98e`, and `8ff8275`; isolated upstream
  revision `9b61903`; sealed seed-0 worker runtime; listener `8878`;
  exclusive `gpu0`.
- Result: standard and zero-noise direct runs completed in 90.745/88.640
  seconds and published as `ms3-rvc-zero-latent-noise-v3`. Direct output
  SHA-256 values are `9f03703b8fe88c02bde39c5527179931bab8f88f7a825e654ce82fd5f0280a10`
  and `d2d36ee13afe63c3762cafb91a377e4b5c841ff3ca7f10df7641d48a46122f15`.
- Machine screen: Gateway standard and direct standard had only 0.606 waveform
  correlation but identical fixed transcripts and 0.417 CER. Zero latent noise
  worsened CER to 0.500. No arm gross-looped. The direct A/B is valid for the
  changed source line, but it is not a Gateway qualification.
- Problems/rework: two attempts stopped before GPU execution. The first used
  the repository venv instead of the retained worker wheel; the second resolved
  the worker venv symlink to system Python and lost its site-packages. The final
  runner preserves the sealed launcher path. No partial listener collection
  was published.
- Changed action: reject zero latent noise and close noise-scale expansion.
  Keep the generation-boundary defect open as context/state behavior rather
  than another seed or stochastic-latent sweep.

## 2026-08-13T09:16:06Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok judged the natural turn-split defect directly
  relevant to realtime conversation, accepted the zero-latent rejection, and
  directed one committed context/state variable before any new voice or sweep.
- Adopted: yes. The parent changed only whether the backend reset runs before
  turn 2, retained a Gateway reset baseline, and kept the diagnostic off any
  product route.
- Expected time saved: one root-cause lane within 30 minutes versus reopening
  seed, gain, latent-noise, training, or promote work.

## 2026-08-13T09:24:00Z - RVC turn-state cause localized

- Agent: `primary-integrator`.
- Task: Hold the exact two-turn input, split, standard latent behavior,
  checkpoint, seed, and direct backend fixed; change only whether `reset()` is
  called before turn 2.
- Dependencies: commit `6b5916d`; sealed seed-0 runtime; existing Gateway
  reset output; listener `8878`; exclusive `gpu0`.
- Result: reset and preserve-state direct arms completed in 88.267/86.504
  seconds and published as `ms3-rvc-turn-state-v1`. Their output SHA-256 values
  are `4e1f08c38b4e367004e10c7b12627ff99533b2b527c7cb4fd7c79cc9a76b426f`
  and `32f157015bb55e1204dd472d20fb0f0d677d55a1295df3ee90556208b0b55610`.
- Machine screen: Gateway and direct reset had 0.9993 waveform correlation and
  identical transcripts. Turn 1 stayed at CER 0.577. Omitting only the turn-2
  reset restored turn-2 CER from 0.500 to 0.167. No arm gross-looped.
- Safety limit: state carryover is diagnostic only. It violates the invariant
  that interrupted older-generation audio/state must not contaminate a new
  generation, so it cannot be bound or shipped.
- Changed action: run one fully reset, silence-only context prime before turn 2.
  If that fails to recover content, stop priming and inspect individual reset
  buffers without broad GPU expansion.

## 2026-08-13T09:30:00Z - RVC silence-only prime rejected

- Agent: `primary-integrator`.
- Task: After a full safe generation reset, process and discard 3.5 seconds of
  zero PCM, reapply seed 0, then process exact turn 2; use no audio or state
  from the prior generation.
- Dependencies: commit `89ae5ce`; exact direct-reset baseline; sealed seed-0
  runtime; listener `8878`; exclusive `gpu0`.
- Result: the one new direct arm completed in 92.423 seconds and published as
  `ms3-rvc-silence-prime-v1` with SHA-256
  `5c9551d267155ea80b8696f16a16fa097b2b6a7eb541aa04e655a5142dffe55a`.
- Machine screen: reset and prime retained identical full CER 0.556 and turn-2
  CER 0.500, with no gross repetition. Waveform correlation was 0.983.
- Changed action: reject silence priming and close prime-length search. Test
  one prior-input-context carryover control while clearing RNG, pitch, RMS, and
  SOLA; preserve-on-clean-completion is diagnostic and must still clear on
  interruption.

## 2026-08-13T09:35:00Z - RVC prior-input context carry rejected

- Agent: `primary-integrator`.
- Task: After processing turn 1, fully reset generation state, restore only the
  48 kHz input and 16 kHz HuBERT context buffers, and process exact turn 2.
- Dependencies: commit `6ea8723`; exact direct-reset baseline; sealed seed-0
  runtime; listener `8878`; exclusive `gpu0`.
- Result: the input-context arm completed in 93.538 seconds and published as
  `ms3-rvc-input-context-v1` with SHA-256
  `420b1c14c5a9ae0fa2d6696b53f7251bd36b9975189efc03735dbe3bc0923add`.
- Machine screen: turn-2 CER remained 0.500 and full CER worsened from 0.556 to
  0.667, without gross repetition. Input context alone is not the recovery
  state observed in the full preserve-state control.
- Changed action: close input-context carry. Isolate RMVPE pitch/pitchf cache
  once while resetting RNG, input context, RMS, and SOLA; do not combine more
  state classes or bind a diagnostic route.

## 2026-08-13T09:39:00Z - RVC pitch-cache carry rejected

- Agent: `primary-integrator`.
- Task: After turn 1, fully reset generation state, restore only RMVPE
  pitch/pitchf caches, and process exact turn 2.
- Dependencies: commit `0c34c2a`; exact direct-reset baseline; sealed seed-0
  runtime; listener `8878`; exclusive `gpu0`.
- Result: the pitch-cache arm completed in 84.944 seconds and published as
  `ms3-rvc-pitch-cache-v1` with SHA-256
  `b28ac146ce1f9c99138500d4dd5ec7c6dc7b95bd4eef15437762406d3cc6c0ea`.
- Machine screen: reset and pitch-cache arms both retained turn-2 CER 0.500 and
  full CER 0.556, without gross repetition.
- Changed action: close pitch-cache carry. Run one final state-decomposition
  control that resets all audio/pitch/RMS/SOLA buffers but restores the RNG
  continuation point after turn 1; stop this GPU diagnosis after its result.

## 2026-08-13T09:43:00Z - RVC RNG continuation rejected; state split closed

- Agent: `primary-integrator`.
- Task: After turn 1, fully reset audio, pitch, RMS, and SOLA state, then
  restore only CPU/CUDA RNG continuation state before exact turn 2.
- Dependencies: commit `88d5c1e`; exact direct-reset baseline; sealed seed-0
  runtime; listener `8878`; exclusive `gpu0`.
- Result: the RNG-state arm completed in 92.687 seconds and published as
  `ms3-rvc-rng-state-v1` with SHA-256
  `4d15577482849a5632b6466c19e59d7175f66a4cf9ca19b629ef8537c114c47e`.
- Machine screen: reset and RNG-continuation arms both retained turn-2 CER
  0.500 and full CER 0.556, without gross repetition.
- Changed action: close RVC state decomposition. Do not test SOLA, state
  combinations, another seed, or another split. Apply the fixed natural split
  once to stable X-VC Q034 to distinguish RVC-specific from system-common
  generation-boundary behavior.

## 2026-08-13T09:46:00Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok accepted the bounded RVC state rejections and their
  closure, explicitly selected committed X-VC split commit `d648145` as the
  last model-boundary diagnostic, and prohibited more RVC state, seed, split,
  training, promote, or multi-lane work.
- Adopted: yes. The X-VC job was already running in parallel with the audit;
  no additional diagnostic lane was opened.
- Expected time saved: about 15--20 minutes versus continuing RVC internals.

## 2026-08-13T09:49:00Z - X-VC confirms short-generation quality weakness

- Agent: `primary-integrator`.
- Task: Reuse the exact actual input and 4.24-second natural split on stable
  X-VC Yofukashi Q034, changing only one versus two Gateway generations.
- Dependencies: commit `d648145`; exact retained one-generation X-VC output;
  evaluation Gateway `8882`; listener `8878`; exclusive `gpu0`.
- Result: both generations completed and published as
  `ms3-stable-xvc-turn-split-v1`; the two-generation SHA-256 is
  `c6b704cceb38fba6faec9297d86e3e88555432ed629882b6717bae3d3fb3231f`.
- Machine screen: full CER remained 0.833, while per-turn CER worsened from
  0.577/0.333 for one generation to 0.731/0.500 for two. Neither arm
  gross-looped. The effect is not RVC-only and is not a perceptual comparison.
- Changed action: close generation-boundary model diagnostics. Find a distinct
  retained actual pre-VC input by source identity; otherwise return to one
  bounded public known-text generalization batch.

## 2026-08-13T10:10:00Z - stable VC public-validation generalization published

- Agent: `primary-integrator`.
- Task: After proving that all retained actual-input collections share one
  source hash, render the two stable VC families on three unused, authorized
  Hadou validation rows of 3.0, 4.8, and 7.3 seconds.
- Dependencies: commits `ad17c4e` and `f935022`; frozen source-manifest SHA-256
  `12e334f...`; evaluation Gateways `8881`/`8882`; listener `8878`; exclusive
  sequential `gpu0` lease.
- Result: six fresh-session outputs completed with contiguous finite frames and
  atomically published as `ms3-stable-vc-generalization-v1`. RVC output hashes
  are `fe59f8e...`, `8814223...`, and `1b8fa4d...`; X-VC hashes are
  `a9e98fa...`, `2861e06...`, and `39470f5...`.
- Machine screen: the frozen source audit had zero CER on all three inputs.
  Output CER for RVC was 0.111/0.000/0.032 and for X-VC was
  0.000/0.100/0.000. No output triggered the gross-repeat screen. This admits
  all six for hearing but does not rank naturalness, identity, or voice quality.
- Problems/rework: the first execution stopped before GPU inference because an
  older single-render helper called the non-qualification session endpoint and
  received HTTP 404. The runner moved to the already-qualified current session
  path and the partial hidden staging tree was isolated under `/tmp`. The first
  STT invocation then rejected PCM24 at the strict PCM16 package ingress; the
  same pinned local engine and decode configuration successfully screened the
  WAVs directly without changing audio.
- Changed action: stop adding public rows before hearing. Keep this collection
  after the original stable heldout shortlist and before the exact actual-input
  pair; ask the next scheduled progress audit for the shortest system-side or
  quality-candidate slice that does not reopen closed training or diagnostics.

## 2026-08-13T10:13:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok accepted the new generalization audio and kept
  public-row expansion, human87/horizon/LR, RVC state/training, EXP-024,
  promote ceremony, and machine quality selection closed.
- Adopted: yes, with the audit's explicit fallback. A second distinct retained
  actual pre-VC source hash does not exist, so the parent selected one audible
  realtime interrupt/cancel recovery slice using the already-stable profiles.
- Expected time saved: about 20--30 minutes versus reopening a closed model or
  training axis while operator hearing is unavailable.

## 2026-08-13T10:24:19Z - stable X-VC cancel recovery published

- Agent: `primary-integrator`.
- Task: Send two seconds of an older X-VC generation, close the local output
  gate, cancel it, then render a known short utterance as the next generation
  on the same Gateway connection.
- Dependencies: commits `5dfdea6` and `b3c14c6`; stable X-VC Q034 Gateway
  `8882`; listener `8878`; exclusive `gpu0`.
- Result: 84 old-generation output frames already in the socket before the
  1.482 ms cancel acknowledgment were excluded; zero stale frames arrived
  after acknowledgment. The new generation completed 151/151 frames and was
  published as `ms3-stable-xvc-cancel-recovery-v1` with SHA-256
  `e460626...` beside fresh control `a9e98fa...`.
- Machine screen: both arms transcribed the exact reference at CER 0. Waveform
  correlation was 0.9999999998, MAE `1.74e-7`, and maximum difference
  `2.48e-5`; this is corruption evidence, not a perceptual winner.
- Problems/rework: the first execution stopped after sending the old audio but
  before cancel because the reused renderer helper did not export protocol
  cancel classes. No listener collection was published; the partial output was
  isolated under `/tmp`, explicit protocol imports were committed, and the
  clean retry completed.
- Changed action: close further X-VC cancel variants. Apply the same system
  slice once to stable RVC because that family has known generation-state
  sensitivity.

## 2026-08-13T10:28:05Z - listener refresh latency unblocked

- Agent: `primary-integrator`.
- Task: Make newly published collections visible on port 8878 without forcing
  every library API request to rebuild the full 498-run index.
- Dependencies: listener cache commit `687d922`; listener `8878`.
- Result: the server now keys its cached library by a cheap artifact-root
  fingerprint. The first changed-root scan remains about 14 seconds, while a
  cached request fell to 21--39 ms. A focused test proves reuse and invalidation
  when a new top-level collection appears; 25 Python listener tests and Ruff
  passed. After the RVC publish, the API reported 499 runs / 838 candidates and
  both cancel-recovery collections with two candidates each.
- Problems/rework: the first five-second probe after publishing hit the
  expected changed-root rebuild and timed out; the ongoing server scan warmed
  the cache, and subsequent calls completed in tens of milliseconds.
- Changed action: keep the listener cache; do not optimize the full cold scan
  unless it again blocks the hearing loop.

## 2026-08-13T10:33:46Z - stable RVC cancel recovery published

- Agent: `primary-integrator`.
- Task: Reuse the exact X-VC cancellation sequence on stable seed-0 RVC, with
  profile family as the only changed system variable.
- Dependencies: commit `ece00d6`; stable seed-0 RVC Gateway `8881`; listener
  `8878`; exclusive `gpu0`.
- Result: 75 old-generation output frames already in the socket before the
  1.610 ms cancel acknowledgment were excluded; zero stale frames arrived
  after acknowledgment. The recovery generation completed 151/151 frames and
  published as `ms3-stable-rvc-cancel-recovery-v1` with SHA-256 `aff86ec...`
  beside frozen fresh control `fe59f8e...`.
- Machine screen: both arms retained the same transcript, “社長カルの指示です”,
  at CER 0.111 without gross repetition. Unlike X-VC, their waveform
  correlation was 0.892 (MAE 0.00418, maximum difference 0.14769); that
  difference remains a human-listening question and is not an automatic fail.
- Changed action: stale-frame safety is closed for both stable families. Do not
  reopen state decomposition or add cancel variants; keep the RVC A/B audible
  for later hearing and ask the next scheduled audit whether a distinct
  system slice now has more value than another GPU render.

## 2026-08-13T10:43:55Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `REDIRECT`. Grok accepted both cancel-recovery collections, the
  listener-cache unblock, and their commits as direct progress, then closed
  further cancel/state, human87 horizon/LR, losing adapted-system paths, and
  premature binding. It requested one additional actual ChatGPT input through
  the two stable profiles as the next distinct quality lane.
- Adopted: partially. The closure and single committed-lane rule were adopted.
  The exact proposed input cannot run: all retained actual inputs have the same
  hash and no Chrome capture process is active. The parent therefore selected
  a distinct audible system behavior from the prior audit's allowed fallback:
  current exclusive native fallback on the retained exact actual input.
- Expected time saved: one immediately reproducible fallback collection instead
  of waiting indefinitely for a browser capture or rerunning a closed axis.

## 2026-08-13T10:49:00Z - stable VC native-fallback audio published

- Agent: `primary-integrator`.
- Task: Reuse the exact 8.17-second actual source and frozen stable outputs;
  change only continuous remote playout versus the current Extension semantics
  of muting remote and enabling aligned native audio at exactly 2.0 seconds.
- Dependencies: commit `0605c56`; source SHA-256 `78b15cd...`; frozen RVC/X-VC
  remote hashes `e00b7f6...` / `bbcc638...`; listener `8878`.
- Result: two runs / four candidates published as
  `ms3-stable-vc-native-fallback-v1`, raising the listener to 501 runs / 842
  candidates. RVC/X-VC fallback hashes are `7fc83a6...` / `b70c968...`.
  Both transitions are exclusive with zero route overlap.
- Machine screen: the single-sample discontinuity at the switch was 0.0488 for
  RVC and 0.1122 for X-VC. Pinned faster-whisper-small CER for continuous versus
  fallback was 0.917/0.778 for RVC and 1.000/1.000 for X-VC, with no new gross
  loop. These measurements do not determine click audibility, naturalness, or
  route acceptability.
- Changed action: retain both switch points for later hearing. Do not add a
  crossfade, gap length, alternate switch time, or profile binding until the
  operator reports whether the current hard switch is actually disruptive.

## 2026-08-13T11:21:44Z - corrected-premise Grok audit redirected to method work

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, exact 1,800-second cadence).
- Task: Re-audit the project after the operator corrected the 8.17-second
  recording's provenance and requested stronger evaluation plus X-VC methods.
- Result: `REDIRECT`. No new audio was produced in the preceding 30 minutes and
  `gpu0` was idle. Grok requested a small diverse fixed evaluation followed by
  one method-level X-VC pilot, and rejected another system/fallback/cancel or
  human87 epoch/LR/scope variant.
- Adopted: yes. The 8.17-second tongue-twister is demoted to historical local
  diagnostics. EXP-033 changes source construction only, using three official
  JVS sample donor voices to create generated same-content pairs while holding
  target exposure and 1,044 optimizer updates fixed.
- Expected time saved: 30--60 minutes versus another invalid single-clip or
  closed-axis run.

## 2026-08-13T11:40:00Z - EXP-033 method pilot prepared

- Agent: `primary-integrator`.
- Task: Freeze a ten-row cross-speaker/tempo/pitch/noise/silence evaluation and
  implement a generated-source-diversity X-VC training runner.
- Dependencies: official JVS sample WAVs; immutable X-VC base; completed 87
  Amitaro target windows and legacy control69-e12 adapter; exclusive `gpu0`.
- Result: CPU admission confirms 87 targets, 261 generated pairs, 12 exposures
  per target, 1,044 updates, and ten evaluation rows. Four focused tests pass.
- Problems: the full JVS Google Drive archive was quota-blocked and SpeechBSD
  was gated; the bounded pilot uses only the three official public JVS samples
  and records that limitation instead of substituting untracked data.
- Changed action: commit the plan and runner, start exactly one GPU run, then
  machine-screen corruption by evaluation group and publish all arms on 8878.

## 2026-08-13T11:44:27Z - EXP-033 source-diversity audio published

- Agent: `primary-integrator`.
- Task: Generate three JVS-donor pseudo sources per Amitaro target, train the
  fixed control69 trajectory, and publish base/legacy/new comparisons.
- Dependencies: commit `e6558ca`; exclusive `gpu0`; fixed ten-row evaluation.
- Result: 261 generated pairs, 1,044 updates, and 30 candidates across ten rows
  completed in 194.24 seconds. Loss moved from 145.4782 to 115.6919; peak GPU
  allocation was 5.13 GB. Port 8878 now exposes 511 runs / 872 candidates.
- Machine screen: no gross repetition in any arm. Mean source-relative distance
  was 0.153 new, 0.170 base, and 0.280 legacy. On six clean cross-speaker rows it
  was 0.084/0.123/0.325. The new arm also improved tempo and leading-silence
  versus base, tied pitch, but regressed the sole 20 dB-noise row to 0.375 from
  base/legacy 0.0. These are content diagnostics, not audible quality ranks.
- Changed action: retain EXP-033 for later hearing. Before another training
  method, run one six-speaker Common Voice external evaluation to test whether
  the clean result merely follows the three JVS donors.

## 2026-08-13T11:52:17Z - Grok progress audit accepted EXP-033 direction

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok confirmed new audio within 30 minutes, the fixed
  diverse evaluation, one-variable source-diversity hypothesis, and valid GPU
  method pilot. It explicitly rejected rerunning EXP-033, closed-axis work,
  system diagnostics, or automatic quality selection.
- Adopted: yes, with one short strengthening check. The audit flagged the three
  JVS samples as thin evidence. Six distinct Common Voice speakers are therefore
  added as evaluation-only data before selecting the next training method.
- Expected time saved: this sub-two-minute external render can detect donor
  overfit before spending another 3--5 minutes on a method-level train.

## 2026-08-13T12:03:08Z - EXP-034 rejected an EXP-033 generalization claim

- Agent: `primary-integrator`.
- Task: Render base, legacy human87, and EXP-033 on six Common Voice Japanese
  speakers excluded from training and the three JVS donor references.
- Dependencies: commits `8bf11d9`, `daf34c2`, and `4525be7`; exclusive
  `gpu0`; exact Common Voice 25.0 mirror revision.
- Result: 18 candidates were published in 83.68 seconds. The first attempt
  stopped before publication because a 2.196-second real turn did not fill the
  fixed 2.4-second X-VC window; the committed retry right-padded short turns.
- Machine screen: mean source-relative distance was 0.422 base, 0.689 legacy,
  and 3.190 EXP-033. EXP-033 produced one gross loop on the row whose source
  ASR was itself invalid. Two of six sources had unusable source ASR, so the
  six-row mean is not treated as a clean generalization benchmark. It is still
  sufficient to reject any automatic claim that JVS3 generalized.
- Changed action: screen a wider deterministic Common Voice pool against its
  known text before model comparison. Do not promote EXP-033 or optimize the
  old tongue-twister.

## 2026-08-13T12:08:22Z - Common Voice source pool expanded before next train

- Agent: `primary-integrator`.
- Task: Test whether a larger external evaluation and donor pool can be built
  without admitting obviously undecodable source clips.
- Result: 52 distinct Common Voice speakers were screened on only the first
  2.4 seconds, matching X-VC's model window. Nineteen had known-text distance
  at or below 0.375; five were exact and eleven were at or below 0.25.
- Decision: use twelve distinct admissible speakers as training donor
  references and reserve seven disjoint speakers for external evaluation.
  Keep 87 target texts, twelve exposures per text, 1,044 updates, control69,
  LR, loss, target voice, and zero target conditioning fixed. The sole method
  change from EXP-033 is donor-pool construction: twelve unique speakers in
  one pass instead of three speakers repeated four times.
- Next: commit EXP-035 runner and manifests, run the single GPU lane, then
  screen seven disjoint Common Voice rows. Re-render the original ten
  conditions only if the external screen avoids a clear regression.

## 2026-08-13T12:20:35Z - EXP-035 donor-breadth audio published

- Agent: `primary-integrator`.
- Task: Replace three donors repeated four times with twelve disjoint admitted
  Common Voice donor speakers in one pass at fixed target exposure and update
  count.
- Dependencies: commit `01b2b24`; exclusive `gpu0`; twelve training donors and
  seven disjoint evaluation speakers from the exact Common Voice revision.
- Result: 1,044 pseudo-source pairs, 1,044 updates, and 21 external evaluation
  candidates completed in 255.30 seconds. Loss moved from 144.2214 to 126.6413;
  peak GPU allocation was 5.13 GB.
- Machine screen: no gross repetition in any arm. Mean source-relative distance
  was 0.296 base, 0.384 JVS3, and 0.360 CV12. Known-text distance was 0.414,
  0.441, and 0.399 respectively. CV12 reduced the adapted maximum from 1.0 to
  0.571 and rescued one row that base/JVS3 rendered as empty, but worsened two
  other rows. This supports better external stability than JVS3, not a quality
  winner or a claim that adaptation beats base.
- Changed action: retain CV12 for hearing and render it once on the already
  frozen ten condition rows. Do not add another donor-count point.

## 2026-08-13T12:22:23Z - Grok progress audit continued the method path

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, no tools or delegation).
- Result: `CONTINUE`. Grok accepted the disjoint evaluation, donor-overfit
  explanation, and fixed-exposure single-variable EXP-035 hypothesis. It said
  to run EXP-035, screen seven rows, avoid another donor point, and move next
  to conditioning or upstream role assignment if corruption remained.
- Adopted: yes. The audit snapshot landed immediately after EXP-035 released
  the GPU and before its new collection was visible, so its `GPU idle/job not
  started` inference was stale; the requested run and screen had completed.
- Changed action: fix the listener refresh race, publish the completed seven
  rows, then finish the frozen tempo/F0/noise/silence check before choosing the
  next training method.

## 2026-08-13T12:25:10Z - listener atomic-publication race fixed

- Agent: `primary-integrator`.
- Task: Make an atomically renamed collection visible when publication lands
  during the listener's root scan.
- Result: the cache now stores the root fingerprint observed before scanning,
  rather than a post-scan fingerprint that could describe files absent from
  the cached index. A publication-during-scan regression test and all 26
  listener tests pass; EXP-035 became visible after the server restart.
- Changed action: retain atomic publication and the cheap cache. New collections
  should appear on the request after a concurrent scan instead of requiring a
  listener restart.

## 2026-08-13T12:29:00Z - EXP-035 fixed-condition comparison published

- Agent: `primary-integrator`.
- Task: Render CV12 once on EXP-033's frozen six clean, tempo, pitch, noise,
  and leading-silence rows without another training run.
- Dependencies: commit `1f0ecdd`; EXP-033 and EXP-035 adapters; exclusive
  `gpu0`; listener `8878`.
- Result: 30 candidates across ten rows completed in 90.16 seconds with 5.13
  GB peak GPU allocation. No arm gross-looped. Mean source-relative distance
  was 0.170 base and 0.153 for both JVS3 and CV12. Both adapted arms improved
  clean, tempo, and silence content retention, tied pitch, and regressed the
  single noise row from 0.0 to 0.375.
- Interpretation: JVS3 and CV12 had identical auxiliary transcripts on these
  ten rows, but their WAVs were not identical and had only low-to-moderate
  waveform correlation. The metric therefore cannot select perceptual quality.
  Combined with the disjoint-speaker result, CV12 supports external stability
  over JVS3 but not superiority to base.
- Changed action: close donor-count expansion. Reuse the exact EXP-035 pairs for
  one official training-role mixture; do not add donor speakers or another
  horizon/LR/scope point.

## 2026-08-13T12:39:43Z - EXP-036 role-mix pilot prepared

- Agent: `primary-integrator`.
- Task: Restore the pinned X-VC 40% standard / 20% reconstruction / 40%
  reversed training roles while fixing EXP-035 data, update count, scope, LR,
  loss, target voice, and zero target conditioning.
- Result: the exact 1,044-update allocation is frozen as 418/208/418. The
  runner regenerates all pseudo sources with the original seeds and requires
  every PCM hash plus the aggregate inventory to match EXP-035 before
  training. Twenty focused tests, Ruff, CPU admission over all 1,044 artifacts,
  `make control-check`, and `git diff --check` pass.
- Changed action: commit the runner before execution, then start the sole GPU
  lane and publish the same seven-speaker base/CV12-standard/role-mix screen.

## 2026-08-13T12:46:25Z - EXP-036 role mix technically rejected

- Agent: `primary-integrator`.
- Task: Reproduce all EXP-035 generated pairs, train the official 40/20/40 role
  mixture for 1,044 updates, and screen the same seven external speakers.
- Dependencies: commit `2c0f14e`; exclusive `gpu0`; EXP-035 generated inventory
  `e909e465...`; listener `8878`.
- Result: all 1,044 regenerated PCM hashes matched. Training completed in
  255.62 seconds with 5.13 GB peak allocation and published 21 candidates.
  No arm gross-looped. Role mix worsened mean source-relative distance from
  0.360 to 0.400 and known-text distance from 0.399 to 0.423 versus EXP-035
  all-standard. Its maximum returned from 0.571 to 1.0 by producing an empty
  transcript on the row EXP-035 had rescued.
- Changed action: technical reject; do not spend a fixed-condition render on
  role mix. Test target frame context cheaply at inference before admitting
  one matching context-aware retrain. No naturalness or voice winner is claimed.

## 2026-08-13T12:51:40Z - EXP-037 target-context admission prepared

- Agent: `primary-integrator`.
- Task: Exercise X-VC's upstream masked target-context geometry without leaking
  the current text or paying for training before corruption is known.
- Result: the render holds the EXP-035 adapter, seven external speakers,
  target reference, and seeds fixed. Its only change replaces all-zero frame
  conditioning with separate Amitaro utterance `EMOTION100_009` followed by a
  zeroed 2.4-second current window. Twenty-two focused tests, Ruff, CPU
  admission, and `git diff --check` pass.
- Changed action: commit and render the two arms on `gpu0`. Admit one matching
  1,044-update retrain only if the contextual arm avoids gross corruption.

## 2026-08-13T12:52:36Z - Grok progress audit continued conditioning admission

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, exact 1,800-second cadence).
- Result: `CONTINUE`. Grok accepted the new audio, disjoint seven-speaker and
  frozen ten-condition evaluation, closure of donor count and role mixing, and
  the cheap target-context admission before retraining. It explicitly rejected
  EXP-036 fixed-condition rendering, closed-axis retries, evaluation redesign,
  and machine quality selection.
- Adopted: yes. EXP-037 had already been committed as `3ee987a` and launched
  while the auditor evaluated its earlier snapshot; the reported idle GPU was
  stale by audit completion.
- Expected time saved: the 88.65-second inference admission avoided a full
  context-aware training run after detecting its content regression.

## 2026-08-13T12:55:01Z - EXP-037 context-aware retraining rejected at admission

- Agent: `primary-integrator`.
- Task: Compare all-zero frame conditioning with a separate Amitaro utterance
  followed by a zeroed current 2.4-second window on seven external speakers.
- Dependencies: commit `3ee987a`; EXP-035 adapter; exclusive `gpu0`; listener
  `8878`.
- Result: 14 candidates completed in 88.65 seconds with 2.67 GB peak GPU
  allocation. Neither arm gross-looped. Context worsened mean source-relative
  distance from 0.360 to 0.370, known-text distance from 0.399 to 0.505, and
  maximum source-relative distance from 0.571 to 0.714.
- Listener: the refreshed library exposes EXP-035/036/037 at 548 runs / 976
  candidates, resolving the auditor's snapshot uncertainty.
- Changed action: do not train the contextual variant. Move adaptation off the
  content attention/FFN linears and onto the seven global-speaker AdaLN linears
  while restoring all-standard roles and zero condition.

## 2026-08-13T13:00:00Z - EXP-038 speaker7 pilot prepared

- Agent: `primary-integrator`.
- Task: Hold EXP-035's exact data and schedule fixed while moving LoRA from 69
  content attention/FFN linears to seven global-speaker AdaLN modulators.
- Result: the derived scope contains exactly six block
  `attn_norm_x.linear` modules plus `norm_out.linear`, or 166,400 trainable
  rank-8 parameters versus control69's 835,584. Twenty-four focused tests,
  Ruff, all-1,044-artifact CPU admission, and `git diff --check` pass.
- Changed action: commit before execution, run the sole `gpu0` lane, and screen
  the same seven external rows before any fixed-condition expansion.

## 2026-08-13T13:06:18Z - EXP-038 speaker7 audio published

- Agent: `primary-integrator`.
- Task: Train only seven global-speaker AdaLN linears on EXP-035's exactly
  reproduced 1,044 all-standard pairs and compare against base/control69.
- Dependencies: commit `6b1f41a`; exclusive `gpu0`; generated inventory
  `e909e465...`; listener `8878`.
- Result: all 1,044 generated hashes matched. Training completed in 276.84
  seconds with 5.13 GB peak allocation and published 21 candidates. No arm
  gross-looped. Speaker7 improved mean source-relative distance from 0.360 to
  0.321 and known-text distance from 0.399 to 0.393 versus control69, including
  large recoveries on two rows. It returned one control69-rescued row to the
  base-like empty transcript, making maximum distance 1.0.
- Changed action: do not tune the seven-row set. Add different utterances from
  the same heldout speakers and evaluate the existing adapters before another
  training decision.

## 2026-08-13T13:13:00Z - EXP-039 new-utterance evaluation prepared

- Agent: `primary-integrator`.
- Task: Strengthen external evaluation beyond one utterance per speaker without
  changing an adapter.
- Result: thirteen additional clips from the exact Common Voice revision were
  downloaded and screened. Twelve from six prior external speakers have
  non-empty first-window ASR of at least seven normalized characters and are
  frozen for rendering; one three-character window was excluded. Durations
  span 2.184--9.612 seconds. Twenty-six focused tests, Ruff, CPU admission, and
  JSON validation pass.
- Changed action: commit the render plan and runner, publish 36 base/control69/
  speaker7 candidates, and judge machine corruption relative to each exact
  2.4-second source window rather than its mostly unconsumed full sentence.

## 2026-08-13T13:18:42Z - EXP-039 rejected speaker7 generalization

- Agent: `primary-integrator`.
- Task: Render base, control69, and speaker7 on twelve new utterances from six
  of the same heldout speakers, with source durations from 2.184 to 9.612
  seconds.
- Dependencies: commit `664a54a`; exclusive `gpu0`; listener `8878`.
- Result: 36 candidates completed in 102.16 seconds with 5.13 GB peak GPU
  allocation. No arm gross-looped. On exact first-window source-relative ASR,
  control69 scored 0.184, base 0.263, and speaker7 0.345; speaker7's initial
  seven-row advantage did not survive changed utterances. Port 8878 exposed
  567 runs / 1,033 candidates after publication.
- Changed action: close speaker7 without a frozen-condition render. Preserve
  control69 and test one target-preserving 80/20 standard/reconstruction
  schedule, excluding all reversed donor-target updates.

## 2026-08-13T13:20:39Z - EXP-040 reconstruction pilot prepared

- Agent: `primary-integrator`.
- Task: Retain control69 and isolate the target-preserving portion of upstream
  role mixing after EXP-036's donor-target dilution failure.
- Result: a deterministic 1,044-update schedule contains 835 standard and 209
  same-Amitaro reconstruction updates, with exactly zero reversed updates.
  Twenty-seven focused tests, Ruff, all-1,044-artifact CPU admission, and
  `git diff --check` pass.
- Changed action: commit before execution and launch the sole GPU lane while
  the scheduled Grok audit runs read-only in parallel.

## 2026-08-13T13:21:58Z - Grok progress audit continued target reconstruction

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, exact 1,800-second cadence).
- Result: `CONTINUE`. Grok accepted the EXP-038/039 audio, rejection of
  speaker7 after changed utterances, and the target-preserving reconstruction
  hypothesis. It requested that EXP-040 be the sole GPU lane and explicitly
  required the twelve new utterances after the first external screen.
- Adopted: yes. EXP-040 was already committed as `042fada` and loading while
  the auditor read its snapshot; the sampled 2 MiB/0% state was transient, not
  an absent job. Closed-axis work and speaker7 refinements remain discarded.
- Expected time saved: skip speaker7 condition rendering and avoid selecting
  reconstruction from the original seven rows alone.

## 2026-08-13T13:27:25Z - EXP-040 seven-row audio published

- Agent: `primary-integrator`.
- Task: Train 835 standard plus 209 same-Amitaro reconstruction updates at
  fixed control69 scope, with zero reversed donor-target updates.
- Dependencies: commit `042fada`; exclusive `gpu0`; generated inventory
  `e909e465...`; listener `8878`.
- Result: all 1,044 generated hashes matched. Training completed in 269.36
  seconds with 5.13 GB peak allocation and published 21 candidates. No arm
  gross-looped. Reconstruction20 moved source-relative distance from 0.360 to
  0.349 versus all-standard, while known-text distance moved from 0.399 to
  0.409; both kept maximum source-relative distance 0.571.
- Changed action: no selection from mixed small changes. Commit a render-only
  EXP-041 on all twelve new utterances before any frozen-condition render.

## 2026-08-13T13:30:18Z - EXP-041 new-utterance render prepared

- Agent: `primary-integrator`.
- Task: Replace EXP-039's rejected speaker7 arm with EXP-040 reconstruction20
  while keeping the twelve sources, base, control69, target, and seeds fixed.
- Dependencies: EXP-039 frozen evaluation set; EXP-040 adapter; listener
  `8878`; exclusive `gpu0` during model execution.
- Result: the reusable renderer gained an explicit candidate policy. Ruff, 28
  focused tests, exact input/adapter CPU admission, and `git diff --check`
  passed. The first admission attempt intentionally stopped because the wrong
  Common Voice root did not match the frozen source identities; rerunning with
  the recorded root matched all twelve rows without GPU use.
- Rework: one path correction, under one minute; no artifact was changed.
- Changed action: commit the evaluation slice, then publish 36 candidates and
  run the source-window-relative corruption screen as the sole GPU lane.

## 2026-08-13T13:34:08Z - EXP-041 new-utterance audio published

- Agent: `primary-integrator`.
- Task: Test reconstruction20 on twelve changed utterances from six heldout
  Common Voice speakers, without retraining.
- Dependencies: commit `7a5e419`; exclusive `gpu0`; EXP-039 frozen input set;
  listener `8878`.
- Result: 36 converted candidates completed in 92.35 seconds and were
  published. No arm gross-looped. Reconstruction20 retained control69's 0.571
  maximum source-relative distance. Its primary source-relative mean moved
  slightly from 0.184 to 0.198, while the secondary full-text reference moved
  from 0.576 to 0.565. The listener exposed 586 runs after publication.
- Changed action: this mixed small result cannot select a winner or justify
  another training sweep. Admit one final render-only EXP-042 on the frozen ten
  clean/tempo/F0/noise/silence conditions; the existing 0.375 noise regression
  is the condition the reconstruction hypothesis could plausibly change.

## 2026-08-13T13:36:02Z - EXP-042 condition render prepared

- Agent: `primary-integrator`.
- Task: Generalize the existing frozen-condition renderer for an explicit
  control69/reconstruction20 policy without changing the ten source rows.
- Result: Ruff, 29 focused tests, exact CPU admission for ten rows and both
  adapters, and `git diff --check` passed. No training update is scheduled.
- Changed action: commit before execution, then use the sole GPU lane for 30
  converted candidates and one condition-stratified corruption screen.

## 2026-08-13T13:39:02Z - EXP-042 condition audio published; reconstruction closed

- Agent: `primary-integrator`.
- Task: Compare reconstruction20 with control69 on six clean rows plus tempo,
  pitch, 20 dB noise, and 300 ms leading silence.
- Dependencies: commit `cf4becf`; exclusive `gpu0`; listener `8878`.
- Result: 30 converted candidates completed in 96.15 seconds with 4.77 GB peak
  allocation. Reconstruction20 and control69 produced identical auxiliary
  content/repetition results in every group: macro 0.153, noise 0.375, leading
  silence 0.400, tempo 0.250, pitch 0.000, and zero gross loops.
- Changed action: close target reconstruction as a training method. It did not
  address the robustness hypothesis and another ratio would be a low-value
  sweep. Keep the audio unheard and redirect training to source-side condition
  augmentation.

## 2026-08-13T13:41:36Z - EXP-043 robust-source training prepared

- Agent: `primary-integrator`.
- Task: Hold EXP-035's exact 1,044 target/donor/update schedule and replace 418
  clean generated-source windows with deterministic noise20, tempo1.2,
  pitch+3, or leading-300ms windows; targets remain clean Amitaro.
- Result: the exact schedule is 626 clean, 105 noise, 105 tempo, 104 pitch, and
  104 leading-silence updates, all with the standard training role. Ruff, 30
  focused tests, all-1,044-artifact CPU admission, and `git diff --check`
  passed after correcting the recorded predecessor directory name.
- Rework: one artifact-root correction; no source or training output changed.
- Changed action: commit before execution and launch EXP-043 as the sole GPU
  lane. The first decision remains a seven-speaker corruption screen; no
  naturalness selection occurs without hearing.

## 2026-08-13T13:44:40Z - EXP-043 v1 stopped before training

- Agent: `primary-integrator`.
- Task: Execute the committed robust-source schedule on `gpu0`.
- Result: fail closed after six generated files and before every optimizer
  update. Tempo 1.2 shortened an exact 2.4-second pseudo-source to about 2.0
  seconds, while the reusable transform path correctly rejected inputs shorter
  than one model window.
- Problems: the earlier evaluation sources were longer than 2.4 seconds, so
  this transform-boundary case had not been exercised by the fixed-condition
  render.
- Rework: add a deterministic FFmpeg `apad` minimum of 2.4 seconds after
  tempo/pitch transforms, test the exact filter, and use fresh v2 output paths.
  The partial v1 directory is neither resumed nor evaluated.

## 2026-08-13T13:47:11Z - EXP-043 v2 admitted after transform fix

- Agent: `primary-integrator`.
- Result: Ruff, 31 focused tests, all-1,044-artifact CPU admission, and an
  actual tempo1.2 FFmpeg probe passed. The probe output was exactly 2.400
  seconds. No v1 output is reused.
- Changed action: commit the preprocessing fix, then restart the same frozen
  source-condition schedule at update zero in fresh v2 directories.

## 2026-08-13T13:52:50Z - Grok progress audit continued robust-source training

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, exact 1,800-second cadence).
- Result: `CONTINUE`. Grok judged the frozen multi-condition evaluation,
  one-variable source-side hypothesis, commit-before-run, and sole GPU lane to
  be on the shortest quality path. It required completing EXP-043, screening
  before another lane, and avoiding reconstruction ratios or closed axes.
- Adopted: yes. The auditor sampled a transient 0% utilization point during an
  active one-job process; EXP-043 was already training and was not interrupted.
- Changed action: screen seven speakers immediately after publication, reject
  on clear content regression, and choose only one explanatory next method.

## 2026-08-13T13:53:42Z - EXP-043 completed and was technically rejected

- Agent: `primary-integrator`.
- Task: Train 626 clean plus 418 source-only noise/tempo/F0/silence updates and
  publish seven disjoint-speaker comparisons.
- Dependencies: commits `6107471` and `0355ed0`; exclusive `gpu0`; listener
  `8878`.
- Result: all 1,044 updates completed in 310.96 seconds with 4.77 GB peak
  allocation and 21 published candidates. The final tempo-row loss was 800.78.
  No arm gross-looped, but source augmentation regressed control69's
  source-relative mean 0.360 to 0.389, known-text distance 0.399 to 0.433, and
  maximum source-relative distance 0.571 to 1.0.
- Changed action: close source-only temporal augmentation without rendering the
  twelve new utterances or ten conditions. The failure is consistent with
  tempo/silence/F0 source changes being supervised against an unmodified target
  window, not evidence for another mixture-ratio sweep.

## 2026-08-13T13:56:04Z - EXP-044 aligned-condition training prepared

- Agent: `primary-integrator`.
- Task: Keep EXP-043's exact source-condition schedule, but apply tempo, F0,
  and leading silence to both the pseudo-source and its exact 2.4-second target
  window; recompute target SSL features. Noise stays source-only with a clean
  target.
- Result: the target schedule is 731 clean, 105 tempo, 104 pitch, and 104
  leading-silence rows. Ruff, 32 focused tests, exact all-artifact CPU
  admission, and `git diff --check` passed. Targets, donors, updates, scope, LR,
  loss, seed, and zero target conditioning remain fixed.
- Changed action: commit before execution and start EXP-044 as the only GPU
  lane. Screen seven external speakers before any follow-up render.

## 2026-08-13T14:05:38Z - EXP-044 external audio published and survived

- Agent: `primary-integrator`.
- Task: Train alignment-preserving varied conditions and screen seven disjoint
  Common Voice speakers.
- Dependencies: commit `0324358`; exclusive `gpu0`; listener `8878`.
- Result: all 1,044 updates completed in 405.25 seconds with 4.77 GB peak
  allocation and 21 published candidates. The final tempo-row loss fell from
  EXP-043's 800.78 to 208.90. No arm gross-looped. Against control69, the
  aligned candidate improved source-relative mean 0.360 to 0.278, known-text
  mean 0.399 to 0.362, and maximum source-relative distance 0.571 to 0.556.
- Changed action: do not select from seven rows. Commit a render-only EXP-045
  on the twelve changed utterances, then replan before fixed conditions.

## 2026-08-13T14:07:06Z - EXP-045 changed-utterance render prepared

- Agent: `primary-integrator`.
- Task: Replace EXP-041's reconstruction arm with the EXP-044 adapter while
  holding all twelve sources, base, control69, target, and seeds fixed.
- Result: Ruff, 33 focused tests, exact twelve-row CPU admission, and
  `git diff --check` passed. No training update is scheduled.
- Changed action: commit before execution, publish 36 candidates, then run the
  source-window-relative corruption screen as the sole GPU lane.

## 2026-08-13T14:10:16Z - EXP-045 audio published; augmentation closed

- Agent: `primary-integrator`.
- Task: Test the EXP-044 adapter on twelve changed utterances from six heldout
  speakers.
- Dependencies: commit `4e96ae9`; exclusive `gpu0`; listener `8878`.
- Result: 36 candidates completed in 109.43 seconds with 4.78 GB peak
  allocation. No arm gross-looped, but aligned conditions regressed control69's
  source-relative mean 0.184 to 0.289, known-text reference 0.576 to 0.603, and
  maximum source-relative distance 0.571 to 1.0.
- Changed action: close the augmentation method without a ten-condition render.
  The initial seven-row improvement did not generalize to changed content.

## 2026-08-13T14:12:01Z - EXP-046 authentic-anchor training prepared

- Agent: `primary-integrator`.
- Task: Replace one synthetic donor exposure per each of 87 targets with its
  existing authorized, aligned Hadou source; keep eleven synthetic exposures,
  twelve total exposures per target, and 1,044 updates.
- Result: all 87 source/target pairs and 1,044 predecessor pseudo-sources passed
  CPU admission. Ruff, 34 focused tests, and `git diff --check` passed. Roles,
  target voice, control69 scope, LR, loss, seed, and zero condition stay fixed.
- Changed action: commit the mixed-data method before execution and start it as
  the sole GPU lane. Screen seven external speakers before other renders.

## 2026-08-13T14:19:53Z - EXP-046 audio published; seven-row screen regressed

- Agent: `primary-integrator`.
- Task: Train eleven synthetic plus one authentic source per target and publish
  seven external comparisons.
- Dependencies: commit `97466dd`; exclusive `gpu0`; listener `8878`.
- Result: all 1,044 updates completed in 305.35 seconds with 4.77 GB peak
  allocation and 21 published candidates. There were no gross loops, but the
  authentic anchor regressed control69's source-relative mean 0.360 to 0.430,
  known-text distance 0.399 to 0.505, and maximum distance 0.571 to 1.0.
- Initial action: mark the seven-row screen as a clear technical regression,
  pending the scheduled progress audit's challenge to that evaluation gate.

## 2026-08-13T14:22:46Z - Grok audit broadened the method decision gate

- Agent: `grok-4.6` in tmux session `liveconv-grok-auditor` (independent,
  read-only, exact 1,800-second cadence).
- Result: `CONTINUE`. Grok accepted the one-variable authentic-source method
  and GPU use, but found the seven-row-first gate too weak because it had
  produced EXP-044's false positive. It required judging EXP-046 on the frozen
  twelve changed utterances plus ten audio conditions before selecting another
  method.
- Adopted: yes. This overturns the initial seven-row-only closure, not its
  recorded regression. No new training or mixture point is admitted.
- Expected time saved: remove the recurring seven-row false-positive stage from
  future method decisions and avoid choosing a loss axis from an incomplete
  evaluation.

## 2026-08-13T14:24:09Z - EXP-047/048 combined renders prepared

- Agent: `primary-integrator`.
- Task: Reuse the EXP-046 adapter on twelve changed utterances and ten frozen
  clean/tempo/F0/noise/silence rows with base/control69 fixed.
- Result: Ruff, 36 focused tests, exact CPU admission for both frozen sets, and
  `git diff --check` passed. Both runs have zero training updates.
- Changed action: commit both render-only slices, execute sequentially on the
  sole GPU, screen each, then choose one loss/conditioning/learning-target
  method only from the combined 7 + 12 + 10 evidence.

## 2026-08-13T14:30:34Z - EXP-047/048 combined gate closed authentic anchor

- Agent: `primary-integrator`.
- Task: Evaluate EXP-046 on twelve changed utterances and ten frozen audio
  conditions after the seven-row gate proved unreliable.
- Dependencies: commit `7e8604f`; sequential exclusive `gpu0`; listener `8878`.
- Result: EXP-047 published 36 candidates in 108.94 seconds. Authentic-anchor
  regressed control69's source-relative mean 0.184 to 0.266, known-text mean
  0.576 to 0.607, and maximum 0.571 to 0.625. EXP-048 published 30 candidates
  in 106.32 seconds and exactly matched control69 in every condition summary:
  macro 0.153, noise 0.375, leading silence 0.400, tempo 0.250, pitch 0.000.
  Neither run gross-looped.
- Changed action: close authentic-anchor. It harms changed clean utterances and
  does not improve any frozen limitation. Future method decisions use the full
  7 + 12 + 10 bundle rather than staging on seven rows.

## 2026-08-13T14:32:08Z - EXP-049 semantic-loss training prepared

- Agent: `primary-integrator`.
- Task: Return to EXP-035 clean synthetic training and double only semantic SSL
  reconstruction weight from 1000 to 2000; keep mel 15, speaker 10, VQ 1, and
  every data/optimizer control fixed.
- Result: Ruff, 37 focused tests, exact 1,044-artifact CPU admission, explicit
  loss-weight validation, and `git diff --check` passed.
- Changed action: commit before training and launch one GPU lane. Seven rows are
  published but cannot decide the method; twelve changed utterances and ten
  conditions remain mandatory before replan.

## 2026-08-13T14:37:41Z - EXP-049 training and external audio completed

- Agent: `primary-integrator`.
- Task: Double semantic SSL reconstruction weight at fixed EXP-035 data and
  publish seven external comparisons.
- Dependencies: commit `bfe143a`; exclusive `gpu0`; listener `8878`.
- Result: all 1,044 updates completed in 273.28 seconds with 4.77 GB peak
  allocation and 21 published candidates. The explicit loss weights were
  semantic 2000, mel 15, speaker 10, and VQ 1; total loss moved 230.36 to
  216.30. No method decision is made from this result alone.
- Changed action: commit the already-tested EXP-050/051 render policies, then
  run seven, twelve, and ten-row screens before selecting another method.

## 2026-08-13T14:44:36Z - EXP-049/050/051 combined gate closed semantic2x

- Agent: `primary-integrator`.
- Task: Screen semantic2x on seven external rows, twelve changed utterances,
  and ten frozen audio conditions.
- Result: the seven-row result was mixed: source-relative mean improved 0.360
  to 0.338, known-text distance regressed 0.399 to 0.409, and maximum remained
  0.571. EXP-050 published 36 candidates in 102.53 seconds and regressed the
  twelve-row source-relative mean 0.184 to 0.238 and maximum 0.571 to 1.0.
  EXP-051 published 30 candidates in 95.66 seconds; macro improved 0.153 to
  0.126 entirely from the six clean rows, while noise 0.375, silence 0.400,
  tempo 0.250, and pitch 0.000 were unchanged. No arm gross-looped.
- Problems: the first EXP-050 screen raced the atomic listener publication and
  stopped before model load; the same committed screen succeeded after the
  directory appeared. Audio was not rerendered.
- Changed action: close semantic-loss reweighting without another multiplier.
  It fits the fixed clean subset but harms changed utterances and does not
  improve the named limitations.

## 2026-08-13T14:47:02Z - EXP-052 source-path scope prepared

- Agent: `primary-integrator`.
- Task: Exclude frame-condition `c` modules while retaining the 36 source `x`
  attention and FFN linears. Both the custom trainer and inference route pass an
  all-zero target waveform, so this tests whether adapting an input-invariant
  condition path is unnecessary or overfits. It differs from the rejected seven
  speaker modulators.
- Result: exact topology has 36 targets and 442,368 trainable parameters. Ruff,
  40 focused tests, exact 1,044-artifact CPU admission, standard loss-weight
  validation, and `git diff --check` passed.
- Changed action: commit before the sole GPU run. The mandatory evaluation is
  again the complete 7 + 12 + 10 bundle; no adjacent scope point is admitted.

## 2026-08-13T14:50:57Z - EXP-052 hypothesis wording corrected

- Agent: `primary-integrator`.
- Problem: the prepared note incorrectly described frame conditioning as target
  mel during training versus zeros during inference. `_gpu_batch` explicitly
  supplies `torch.zeros_like(target)` during this campaign's training too.
- Result: the runnable method is unchanged. The precise hypothesis is now
  input-varying source-path adaptation versus also adapting the deterministic
  zero-waveform-condition path. No held-out target audio is exposed.
- Rework: documentation and result-policy wording only; the already-running
  one-variable source36 job remains valid.

## 2026-08-13T14:52:26Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: keep one sequential GPU lane, complete the mandatory 7 + 12 + 10
  bundle before choosing another method, discard adjacent scope and semantic
  multiplier sweeps, and make no machine quality winner.
- Not adopted: the audit described source36 as repairing a train/inference
  condition mismatch. The campaign passes a zero target waveform in both
  training and inference; the corrected input-invariant-path hypothesis is the
  one used for interpretation.

## 2026-08-13T15:00:00Z - EXP-052/053/054 combined gate closed source36

- Agent: `primary-integrator`.
- Task: Train source-path-only LoRA and screen seven external rows, twelve
  changed utterances, and ten frozen audio conditions.
- Result: EXP-052 completed 1,044 updates in 266.63 seconds at 5.13 GB peak and
  published 21 candidates. Seven rows were mixed: source-relative mean improved
  0.360 to 0.349, known-text mean regressed 0.399 to 0.409, maximum stayed
  0.571. EXP-053 published 36 candidates in 97.93 seconds and regressed the
  twelve-row mean 0.184 to 0.278, known-text mean 0.576 to 0.616, and maximum
  0.571 to 1.0. EXP-054 published 30 candidates in 94.98 seconds and improved
  the ten-condition macro 0.153 to 0.113, including clean and leading silence,
  while noise, tempo, and pitch remained unchanged. No arm gross-looped.
- Changed action: close source36 without an adjacent module-count point. The
  frozen subset improvement does not survive changed sentences.

## 2026-08-13T15:08:00Z - EXP-055 target-text breadth prepared

- Agent: `primary-integrator`.
- Task: Replace the 87-target-text distribution with 275 authorized Amitaro
  first-active windows while holding the 1,044 updates, twelve-donor pool,
  control69 scope, loss, LR, seed, target voice, and zero condition fixed.
- Result: the manifest has 334 train rows; 275 have at least 1.8 seconds active
  speech. The deterministic schedule gives 219 targets four exposures, 56
  targets three, and every donor 87. Ruff, two focused tests, exact archive and
  manifest admission, and `git diff --check` passed. All 33 locally present
  Common Voice clips unused by EXP-035/039 are frozen before training as an
  additional sentence-diversity set.
- Changed action: commit before the sole GPU run. Judge only after the complete
  7 + 12 + 10 + 33 corruption bundle; do not sweep target counts.

## 2026-08-13T15:22:05Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: keep the frozen 7 + 12 + 10 + 33 evaluation bundle, reject another
  target-count or exposure-ratio point, keep one sequential GPU lane, and make
  no machine quality winner while operator hearing is unavailable.
- Not adopted: the snapshot interpreted EXP-055 as not yet started and gpu0 as
  idle. At verdict time EXP-055 training plus the 7 + 12 + 10 renders had
  already completed; EXP-058 was in its CPU-heavy model-load phase with an
  active process and 498 MiB allocated on gpu0. No job or plan change followed
  from that stale observation.

## 2026-08-13T15:25:00Z - EXP-055/056/057/058 combined gate closed target breadth

- Agent: `primary-integrator`.
- Task: Train at fixed 1,044 updates over 275 target texts, then screen seven
  external rows, twelve changed utterances, ten frozen conditions, and 33
  additional locally available Common Voice sentences.
- Result: EXP-055 completed in 270.50 seconds at 5.13 GB peak and published 21
  candidates; loss moved 144.22 to 88.42. Seven rows regressed 0.360 to 0.389
  source-relative and 0.399 to 0.457 known-text. EXP-056 published 36 candidates
  in 96.09 seconds and matched control69 source-relative at 0.184 while known
  text improved 0.576 to 0.559. EXP-057 published 30 candidates in 96.04 seconds
  and matched every control69 condition. EXP-058 published 99 candidates in
  106.39 seconds. Its raw mean improved 1.084 to 0.762, but one still-gross-loop
  row and two empty-source-ASR rows dominated that aggregate. Removing the
  gross-loop row left six wins, nineteen ties, seven losses, means 0.732 versus
  0.736, and equal 0.600 medians; known-text summaries regressed. No quality or
  naturalness winner was inferred.
- Problems: starting a separate process for each 12, 10, and 33-row render paid
  three redundant loads of the large X-VC models while gpu0 appeared idle.
- Changed action: retain all audio as unheard on 8878, close target-count and
  exposure-ratio sweeps, and make the next method about generated pseudo-source
  content quality. The next runner should load models once for its full bundle.

## 2026-08-13T15:35:00Z - EXP-059 pseudo-source content audit prepared

- Agent: `primary-integrator`.
- Task: Audit the immutable 1,044 EXP-035 generated training sources against
  their own 87 target windows, then admit at most one content-quality-filtered
  retraining method.
- Dependencies: EXP-035 generated inventory digest `e909e465`; local pinned
  faster-whisper-small; exclusive `gpu0` only during execution.
- Result: CPU admission bound all 87 targets, twelve donors, and 1,044 source
  WAV hashes to the original EXP-035 inventory. Three focused tests and Ruff
  passed. The frozen policy keeps the best six nonempty, non-gross sources per
  target and uses two passes for the same 1,044-update budget.
- Changed action: commit the audit before its single GPU pass. Stop before
  retraining unless every target retains six candidates, at least ten donors
  survive globally, and selected mean content distance improves at least 25%.
  No keep-count sweep is admitted.

## 2026-08-13T15:39:00Z - EXP-059 audit passed and EXP-060 admitted

- Agent: `primary-integrator`.
- Task: Execute the one committed training-input audit and decide whether a
  content-filtered retraining run has enough signal to justify gpu0.
- Result: all 1,044 sources completed in 118.39 seconds. There were zero empty
  transcripts and two gross-repetition rows. The frozen best-six policy reduced
  mean target-relative distance from 0.341 to 0.217 (36.3%) and median from
  0.267 to 0.188. All 87 targets retained six sources and all twelve donors
  survived, contributing 54--126 updates each after two passes.
- Changed action: admit exactly one filtered6x2 run at fixed control69, target87,
  loss, LR, seed, zero condition, and 1,044 updates. Freeze 31 clean Hadou
  heldout rows before training and prepare the existing twelve changed-utterance
  plus ten-condition policies. Do not test another keep count.

## 2026-08-13T15:50:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: retain a sole sequential GPU lane, finish the already-frozen
  7 + 12 + 10 + 31 evaluation bundle, prohibit keep-count, target, exposure,
  donor, role, and context sweeps, and make no machine quality winner.
- Not adopted: the audit snapshot described EXP-060 as not yet started and
  gpu0 as idle. EXP-060 had completed at 15:47 and EXP-061 was actively
  rendering. No job or method change followed from that stale observation.

## 2026-08-13T15:58:00Z - EXP-060--063 closed pseudo-source filtering

- Agent: `primary-integrator`.
- Task: Train the sole admitted best-six-per-target pseudo-source schedule at
  fixed 1,044 updates and screen it across seven external rows, twelve changed
  utterances, ten conditions, and 31 clean Hadou heldout sentences.
- Result: training completed in 196.15 seconds at 5.13 GB peak; loss moved
  159.57 to 131.81. The seven-row candidate and all ten condition summaries
  exactly matched control69. Twelve changed utterances regressed from 0.184 to
  0.222 mean source-relative distance without loops. Hadou produced three
  wins, twenty-five ties, three losses, and one new gross loop; excluding that
  loop, means were 0.171 versus 0.185 and medians 0.080 versus 0.097. Full
  official-text CER is not interpreted because only 2.4-second windows were
  consumed. In total the bundle published 180 comparison/reference WAVs.
- Problems: filtering the generated training transcripts improved their
  target-relative audit but did not transfer robustly to unseen input content.
- Rework: none; the selection and Hadou set were frozen before training.
- Changed action: close the filtered-pair method and any keep-count sweep.
  Retain all audio unheard on 8878. The next distinct method tests the pretrained
  waveform discriminator and upstream alternating adversarial loss omitted by
  the local adapter runner; ASR cannot judge its intended naturalness effect.

## 2026-08-13T16:08:00Z - EXP-064 waveform-adversarial method prepared

- Agent: `primary-integrator`.
- Task: Restore the upstream X-VC adversarial branch without changing EXP-035's
  generated data, target exposure, updates, LoRA topology, LR, condition, or
  base generative loss.
- Dependencies: the pinned checkpoint contains `generator`, `ema_generator`,
  and a 324-tensor pretrained `discriminator`; the EXP-035 generated inventory
  digest remains fixed at `e909e465`.
- Result: the runner restores alternating discriminator and generator updates,
  discriminator feature matching, upstream optimizer settings, and gradient
  clipping. Twenty-five focused policy/schedule tests, Ruff, exact CPU admission,
  and `git diff --check` passed. EXP-065--067 freeze the twelve changed rows,
  ten conditions, and 31 Hadou sentences before training.
- Changed action: after committing, admit one 1,044-update GPU run only. Do not
  sweep adversarial weights, warmup, or D/G learning rates. Publish viable audio
  but make no naturalness claim without hearing.

## 2026-08-13T16:20:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: keep the sole adversarial method point, finish its frozen
  7 + 12 + 10 + 31 bundle, reject objective/warmup/D/G-rate sweeps, and make no
  naturalness or quality claim from machine scores.
- Not adopted: the audit snapshot inferred that EXP-064 was still waiting to
  launch and that gpu0 was idle. EXP-064 had completed at 16:15, its seven-row
  screen was complete, and EXP-065 had already published twelve more rows.
  The audit's listener concern came from a `ready` sample limited to twenty
  historical entries rather than proof that the new artifact directories were
  absent. No running work was stopped.

## 2026-08-13T16:27:00Z - EXP-064--067 completed waveform-adversarial gate

- Agent: `primary-integrator`.
- Task: Restore the pretrained waveform discriminator for one fixed-data
  control69 adapter and screen it across the full varied evaluation bundle.
- Result: training completed 1,044 alternating D/G updates in 330.37 seconds
  at 5.13 GB peak. Discriminator loss moved 1.686 to 0.387 and total
  generator-side loss 199.76 to 181.57. All 60 evaluated rows avoided gross
  repetition. Seven external rows and ten frozen conditions were transcript-
  identical to control69. Twelve changed utterances moved from 0.184 to 0.204
  mean source-relative distance with the same 0.571 maximum. Hadou31 produced
  five wins, twenty-four ties, and two losses; mean improved 0.210 to 0.186 and
  median 0.111 to 0.083. The bundle published 180 model-output WAVs plus source
  and target references on the listener.
- Problems: the first EXP-065 invocation exposed an omitted CLI choice after
  the underlying policy had passed tests. It failed before creating an output
  directory; a direct CLI-choice regression test and commit `d0649b9` fixed it.
- Rework: about two minutes; no GPU training or audio was discarded.
- Changed action: retain EXP-064 unheard because its intended naturalness
  effect cannot be judged by ASR; prohibit adjacent adversarial sweeps. The next
  distinct method tests only the final normalization and converter-to-decoder
  projection, rather than revisiting attention count or the human87 scope.

## 2026-08-13T16:35:00Z - EXP-068--071 decoder-interface method prepared

- Agent: `primary-integrator`.
- Task: Test one function-aware X-VC adaptation scope at the boundary between
  the acoustic converter and frozen decoder.
- Dependencies: exact EXP-035 generated inventory digest `e909e465`; fixed
  all-standard loss, LR, seed, target87, zero condition, and 1,044 updates.
- Result: the scope contains only final `norm_out.linear` and `proj_out`, for
  22,016 trainable rank-8 LoRA parameters. Thirty-six focused tests, Ruff, all
  four CPU admissions, and `git diff --check` passed. EXP-069--071 freeze the
  twelve changed utterances, ten conditions, and 31 Hadou windows before
  training, in addition to EXP-068's seven external rows.
- Changed action: commit and admit one GPU run. Do not sweep output layers,
  rank, LR, or adjacent scope counts. Machine ASR can reject corruption but
  cannot decide the naturalness hypothesis or select a winner.

## 2026-08-13T16:46:00Z - EXP-068--071 rejected decoder-interface output2

- Agent: `primary-integrator`.
- Task: Train output2 and screen seven external, twelve changed-utterance, ten
  condition, and 31 Hadou rows.
- Result: 1,044 updates completed in 245.40 seconds at 5.13 GB peak; loss moved
  144.22 to 137.90. The first seven rows had one ASR-empty output. Changed
  utterances produced zero wins, five ties, seven losses, and mean distance
  `0.375` versus control69 `0.184`. Conditions improved two and tied eight.
  Hadou produced ten wins, eighteen ties, three losses, but introduced one
  gross repeated-number loop. All 180 model-output WAVs plus references are on
  the listener and remain unheard.
- Problems: a tmux watcher used prefix target matching and waited on its own
  `liveconv-exp068-bundle` session after training. Exact-name matching fixed it
  before any downstream job started; idle time was under one minute.
- Changed action: reject output2 and all adjacent output-scope/rank/LR sweeps.
  Prepare one real-speech rehearsal data point that retains control69 and
  replaces 209 target-conversion updates with real donor self-reconstruction.

## 2026-08-13T16:49:00Z - EXP-072--075 real-speech rehearsal prepared

- Agent: `primary-integrator`.
- Task: Replace one fixed 20% share of target-conversion updates with
  reconstruction of real, evaluation-disjoint Common Voice training donors.
- Dependencies: exact EXP-035 pair inventory; the same twelve admitted donor
  identities and 87 target windows; fixed control69, loss, LR, seed, zero
  condition, and 1,044 total updates.
- Result: the deterministic schedule contains 835 standard target conversions
  and 209 real-donor self-reconstructions. Every rehearsal row binds the real
  donor waveform, its semantic tokens, waveform target, and SSL target. Forty
  focused tests, Ruff, four CPU admissions, and `git diff --check` passed.
- Changed action: commit and admit exactly one run plus the frozen
  7 + 12 + 10 + 31 screen. Do not sweep the rehearsal ratio or train on any
  heldout evaluation row.

## 2026-08-13T16:50:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: EXP-072 is a valid single-variable data hypothesis for recurrent
  changed-utterance forgetting; run only this point, retain the frozen varied
  gate, reject rehearsal-ratio and adjacent method sweeps, and make no machine
  naturalness or voice-quality claim.
- Not adopted: the audit snapshot reported gpu0 idle and EXP-072 unlaunched.
  The committed job started at 16:52 while the audit was generating its answer.
  No running work was stopped or redirected.

## 2026-08-13T17:04:00Z - EXP-072--075 closed; EXP-076 broadened EXP-064

- Agent: `primary-integrator`.
- Result: real rehearsal regressed changed utterances (2/4/6) and added one
  Hadou gross loop (4/21/6), so the method and ratio sweep are closed. A
  separate 33-speaker Common Voice render then found an EXP-064 repeated-`フッ`
  loop with distance 223, revoking its prior no-loop observation.
- Changed action: adapt one bounded final waveform decoder stage rather than
  another converter/output scope or data ratio.

## 2026-08-13T17:20:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: finish the single committed final-decoder point, then close it on a
  failed frozen screen without a depth/LR/adjacent-scope sweep and move to a
  distinct loss or conditioning hypothesis. Continue one committed GPU lane
  while hearing is unavailable and do not use ASR to rank naturalness.
- Not adopted: the snapshot reported gpu0 idle and the job unlaunched while
  EXP-077 had already completed and its follow-up renders were in progress. No
  running work was interrupted.

## 2026-08-13T17:27:00Z - EXP-077--080 rejected final decoder adaptation

- Agent: `primary-integrator`.
- Task: train only `acoustic_decoder.model.4--6` and screen the result on seven
  external, twelve changed-utterance, ten condition, and 31 Hadou rows.
- Dependencies: commit `74b502f`; fixed EXP-035 data, loss, LR, seed, zero
  condition, and 1,044 updates; exclusive `gpu0`.
- Result: training completed in 234.13 seconds at 5.13 GB peak, but loss rose
  from 144.22 to 165.58. The candidate lost all seven first comparisons,
  produced 0/3/9 wins/ties/losses on changed utterances (`0.394` versus
  `0.184` mean), 0/6/4 on conditions (`0.243` versus `0.153`), and 3/11/17 on
  Hadou (`0.305` versus `0.210`). No gross loop was detected. The full bundle
  is on 8878 and remains unheard.
- Changed action: reject decoder adaptation and all adjacent decoder-depth/LR
  points. Next test changes the semantic supervision target itself: preserve
  source hidden states while retaining target waveform and speaker losses.

## 2026-08-13T17:32:00Z - EXP-081--085 source-semantic method prepared

- Agent: `primary-integrator`.
- Task: change only semantic-decoder MSE supervision from the target-voice
  Whisper hidden states to the generated source's frozen Whisper hidden states.
- Dependencies: exact EXP-035 generated inventory, target waveforms, target
  speaker objective, standard loss weights, control69 scope, LR, seed, zero
  condition, and 1,044 updates remain fixed.
- Result: 47 focused tests, Ruff, `git diff --check`, and exact CPU admissions
  for 7 + 12 + 10 + 31 + 33 rows passed. The 33-row set adds 33 locally unused
  Common Voice speakers without adding a training row.
- Changed action: commit before one GPU run, then publish every frozen screen.
  Do not sweep source/target blend weights and do not interpret machine ASR as
  naturalness or target-voice quality.

## 2026-08-13T17:50:00Z - EXP-081--085 completed mixed source-semantic gate

- Agent: `primary-integrator`.
- Task: replace only the semantic MSE target with source hidden states and
  screen 7 + 12 + 10 + 31 + 33 frozen rows.
- Dependencies: commit `e985798`; exclusive `gpu0`; listener 8878.
- Result: training completed in 280.32 seconds at 5.13 GB; loss moved 135.04 to
  96.75. The seven-row mean improved `0.360` to `0.299` (2/4/1), conditions
  improved `0.153` to `0.075` (3/7/0), and Hadou improved `0.210` to `0.194`
  (5/22/4). Changed utterances regressed `0.184` to `0.303` (1/8/3). On 33
  unused speakers the mean improved `1.084` to `0.942` (9/16/8), but the
  candidate gross-looped one ASR-empty input. All 279 model outputs plus their
  references are published and unheard.
- Problems: each renderer reloads the 4.7 GB checkpoint, leaving GPU compute
  idle during storage-bound initialization. This is a throughput issue, not a
  result failure; do not refactor the renderer inside this experiment.
- Changed action: retain source-semantic as mixed unheard audio without a blend
  sweep or quality claim. Before another retraining method, replace the
  statistically weak one-noise/one-silence evidence with a multi-speaker stress
  matrix over the twelve real changed utterances.

## 2026-08-13T17:56:00Z - EXP-086 multi-speaker stress matrix prepared

- Agent: `primary-integrator`.
- Task: cross the twelve real changed Common Voice utterances with clean,
  noise20, leading-silence300, tempo1.2, and pitch+3 conditions.
- Dependencies: EXP-039 source identities; deterministic transform code;
  EXP-035 control69 and EXP-081 source-semantic adapters; evaluation only.
- Result: the plan contains exactly sixty balanced rows, twelve per condition.
  Forty-nine focused tests, Ruff, CPU admission, and `git diff --check` passed.
- Problems: first materialization stopped before a manifest because the shared
  condition transform assumed every source was already 2.4 seconds; one real
  input is 2.184 seconds. The partial ignored directory was moved to
  `/tmp/liveconv-exp086-stress-inputs-failed-20260813T1758Z`.
- Rework: normalize every source to the renderer's existing first-2.4-second,
  right-pad-if-short policy before applying conditions. A short-source
  regression and 21 focused tests passed; no model render was started or lost.
- Changed action: commit, materialize and freeze source WAV identities, then
  render base/control/candidate in one bounded GPU run. Do not tune condition
  levels or start another training method before this result.

## 2026-08-13T17:50:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: source-semantic is a valid one-variable method hypothesis; finish
  7 + 12 + 10 + 31 + 33, reject source/target blend sweeps, and keep ASR out of
  naturalness and voice-quality decisions.
- Not adopted: the snapshot inferred EXP-081 was unlaunched and gpu0 idle.
  EXP-081 had started at 17:36, completed at 17:41, and its final screen
  completed at 17:49. No running job was changed.

## 2026-08-13T18:01:00Z - EXP-086 rejected source-semantic robustness

- Agent: `primary-integrator`.
- Task: test clean, noise20, leading-silence300, tempo1.2, and pitch+3 across
  twelve real Common Voice utterances for control69 and source-semantic.
- Dependencies: commits `5b4a7a5` and short-input fix `fbc27b8`; exclusive
  `gpu0`; frozen manifest digest `a1460657`; listener 8878.
- Result: all sixty rows and 180 outputs published. Source-semantic versus
  control69 was clean `0.233` versus `0.260`, noise `1.247` versus `0.397`,
  silence `0.322` versus `0.288`, tempo `0.241` versus `0.374`, and pitch
  `0.379` versus `0.279`. Macro regressed `0.320` to `0.484`; a noise row added
  one gross repeated-character loop.
- Changed action: reject direct source-hidden robustness and blend sweeps.
  Preserve the useful tempo diagnostic, but address the catastrophic noise
  result with one denoising-semantic method: noisy input waveform/tokens,
  clean-source hidden target, and fixed clean/noise alternation.

## 2026-08-13T18:07:00Z - EXP-087--092 denoising-semantic method prepared

- Agent: `primary-integrator`.
- Task: alternate 522 clean and 522 deterministic noise20 generated sources,
  pass their current waveform and semantic tokens, and supervise semantic MSE
  with the corresponding clean generated-source hidden state.
- Dependencies: EXP-035 data identities, target waveform/speaker, control69,
  standard loss weights, LR, seed, zero condition, and 1,044 updates fixed.
- Result: 53 focused tests, Ruff, `git diff --check`, exact 522/522 CPU
  admission, and all 7 + 12 + 10 + 31 + 33 + 60 render admissions passed.
- Changed action: commit and admit one training lane. Do not sweep noise ratio,
  SNR, or semantic blend; machine diagnostics remain content/corruption only.

## 2026-08-13T18:18:00Z - EXP-087--092 completed; generic method rejected

- Agent: `primary-integrator`.
- Task: train one clean/noise20 denoising-semantic adapter and screen the same
  checkpoint on 7 + 12 + 10 + 31 + 33 + 60 frozen rows.
- Dependencies: commit `8a4da06`; exact 522/522 clean/noise schedule; fixed
  EXP-035 identities, target waveform/speaker losses, control69, LR, seed,
  zero condition, and 1,044 updates; exclusive `gpu0`; listener 8878.
- Result: training completed in 267.04 seconds at 5.13 GB peak; loss moved
  `135.04` to `108.65`. Seven external rows were 2/2/3 and effectively tied
  control69 (`0.362` versus `0.360`). Changed utterances regressed `0.184` to
  `0.232` (1/6/5). The original ten conditions improved `0.153` to `0.075`
  (3/7/0), and Hadou31 improved `0.210` to `0.185` (7/22/2). On the balanced
  stress matrix, noise20 improved `0.397` to `0.258`, tempo `0.374` to `0.287`,
  and macro `0.320` to `0.311`, but pitch regressed `0.279` to `0.512`.
  Expanded33 added a candidate repeated-`ぷ` loop on ASR-empty
  `cv41934139u`, with maximum distance `111`. All comparison audio is on 8878
  and remains unheard.
- Changed action: the denoising hypothesis is supported narrowly for noise but
  rejected as a generic keeper. Close noise-ratio, SNR, condition-level, and
  semantic-blend sweeps. Before another retraining method, measure frozen
  source-side semantic/acoustic statistics for loop-prone low-information
  inputs; machine ASR still cannot rank naturalness or voice quality.

## 2026-08-13T18:20:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: denoising-semantic was a valid one-variable response to EXP-086;
  retain the fixed varied gate, reject ratio/SNR/blend sweeps, keep a single
  GPU lane moving without human hearing, and make no machine naturalness or
  voice-quality claim.
- Not adopted: the audit snapshot reported EXP-087 unlaunched and prescribed
  starting it. Training had already completed, all six frozen screens had been
  published, and the severe EXP-091 loop was known by audit completion. The
  next action therefore uses the completed evidence rather than rerunning the
  same job.

## 2026-08-13T18:27:00Z - EXP-093 representation audit prepared

- Agent: `primary-integrator`.
- Task: extract waveform, semantic-token, and frozen Whisper-hidden statistics
  for all 33 expanded Common Voice inputs, then apply the existing loop labels
  from EXP-058, EXP-076, EXP-085, and EXP-091.
- Dependencies: frozen EXP-055 source set; unadapted X-VC checkpoint; exclusive
  `gpu0`; no new ASR or audio render.
- Result: the diagnostic keeps metric extraction independent of the labels and
  reports only exploratory one-sided separation. Pure tests cover token
  collapse, waveform active span, and false-positive accounting.
- Changed action: commit before one GPU extraction. Do not fit a production
  threshold on these 33 rows. The result must either name a new testable
  training/bypass hypothesis or close source-validity gating.

## 2026-08-13T18:31:00Z - EXP-093 first extraction exposed report-key collision

- Agent: `primary-integrator`.
- Result: all 33 source representations completed in 82.18 seconds at 2.58 GB
  peak. The first exploratory table showed that the best simple rule covering
  all three loop-prone sources flagged eleven rows, eight of them non-loop.
- Problems: the table enumerated metric names without their section, so
  waveform and hidden `mean_abs` collided and duplicated the waveform rule.
  Extracted row metrics and loop labels were intact.
- Rework: qualify every metric by section, add a regression asserting all
  homonymous paths remain distinct, and regenerate the deterministic report.
  This reporting fix does not change model inference or add a threshold sweep.

## 2026-08-13T18:33:00Z - EXP-093 completed; universal source gate rejected

- Agent: `primary-integrator`.
- Dependencies: fix commit `802e983`; frozen base X-VC encoder; 33 expanded
  sources; existing loop labels only; exclusive `gpu0`.
- Result: corrected extraction completed in 75.56 seconds at 2.58 GB peak. The
  best one-sided rule covering all three loop-prone sources flagged eleven
  rows, including eight of thirty non-loop rows. Whisper-hidden rules were
  weaker. The base/control loop source had 30 unique tokens in 30 frames, so
  token collapse is not a universal explanation. The two sources on which
  retrained adapters introduced new loops did have only 4/5 unique tokens and
  27/13-frame runs; the same in-sample cutoff also flagged three non-loop rows.
- Problems: the first generated report was moved recoverably to
  `/tmp/liveconv-exp093-report-key-collision-20260813T1831Z.json`; no source,
  model, or user data was deleted.
- Changed action: do not bind a universal gate or tune a threshold on EXP-093.
  Preserve low token diversity for disjoint safety validation. Since failures
  remain model-dependent, admit a distinct X-VC method that replaces the
  always-zero target frame condition with same-speaker cross-utterance context.

## 2026-08-13T18:40:00Z - EXP-094--099 cross-target conditioning prepared

- Agent: `primary-integrator`.
- Task: exercise X-VC's previously zeroed frame-condition path with
  same-speaker, content-disjoint target context.
- Dependencies: exact EXP-035 generated inventory; 87 Amitaro target windows;
  fixed control69, target waveform/speaker/semantic losses, LR, seed, clean
  sources, and 1,044 updates.
- Result: every target rotates deterministically to the next different target
  window; inference fixes `EMOTION100_009` as frame condition while retaining
  `EMOTION100_003` as the target/speaker reference. EXP-095--099 reuse the
  frozen 12 + 10 + 31 + 33 + 60 sets in addition to the seven-row pilot.
- Changed action: after focused tests and CPU admission, commit and run one GPU
  lane. Do not sweep condition ratio, identity, strength, scope, or LR. Reject
  content copy/corruption mechanically but leave naturalness and voice quality
  for hearing.

## 2026-08-13T18:53:00Z - EXP-094--099 completed; conditioning method rejected

- Agent: `primary-integrator`.
- Dependencies: commit `2baa6b1`; exact cross-target rotation; fixed
  `EMOTION100_009` inference condition; exclusive `gpu0`; listener 8878.
- Result: training completed in 262.04 seconds at 5.13 GB peak, with loss
  `141.10` to `123.42`. External7 regressed `0.360` to `0.410` (2/4/1), and
  changed12 regressed `0.184` to `0.306` (1/5/6). Conditions improved only one
  leading-silence row; Hadou moved `0.210` to `0.199` (4/25/2). Expanded33
  regressed `1.084` to `1.247` (9/15/9) and added one repeated-`ヘイ` loop.
  Stress60 improved noise20 `0.397` to `0.275` and tempo `0.374` to `0.339`,
  but regressed silence, pitch, clean, and macro (`0.320` to `0.329`). The
  fixed condition sentence was absent from all candidate ASR transcripts. All
  459 model-output WAVs plus references are on 8878 and remain unheard.
- Problems: the bundle watcher initially used tmux prefix matching and waited
  on its own `liveconv-exp094-bundle` session. It was replaced with exact-name
  matching after three seconds; no GPU work or audio was discarded.
- Changed action: reject cross-target conditioning and close reference,
  strength, ratio, scope, and LR follow-ups. Preserve the narrow noise signal
  only as a diagnostic. Next test semantic-token corruption during training to
  force the redundant acoustic path to carry content under token collapse.

## 2026-08-13T18:50:25Z - Grok progress audit

- Agent: `grok` in tmux `liveconv-grok-auditor`; read-only, no delegation.
- Verdict: `CONTINUE`.
- Adopted: EXP-094 was a legitimate one-variable conditioning hypothesis;
  screen only content copy, empty output, and gross loops mechanically, keep
  naturalness/voice quality unheard, and close the method on failure rather
  than sweeping it.
- Not adopted: the audit snapshot saw only the seven-row render and advised
  against blindly launching EXP-095--099. Those were not new training points
  but precommitted frozen screens of the same checkpoint, and all had completed
  by audit return. No job was stopped or repeated.

## 2026-08-13T19:00:00Z - EXP-100--105 semantic-token hold prepared

- Agent: `primary-integrator`.
- Task: make the redundant acoustic path preserve content when source semantic
  tokens collapse locally.
- Dependencies: exact EXP-035 generated inventory; fixed target waveform,
  target speaker and target-hidden semantic objectives; control69, LR, seed,
  zero frame condition, clean waveforms, and 1,044 updates.
- Result: the fixed schedule alternates 522 clean rows with 522 rows whose six
  contiguous five-frame token blocks each repeat their first token. EXP-101--
  105 reuse the 12 + 10 + 31 + 33 + 60 screens in addition to the seven-row
  pilot. Focused tests cover exact block values and counts.
- Changed action: commit after CPU admission and run one lane. Do not sweep
  block size or corruption ratio. EXP-104 contains known low-token failure rows
  and is therefore a failure-recurrence screen, not independent robustness
  proof; other frozen sets still govern broad regression.

## 2026-08-13T19:17:22Z - semantic-token hold X-VC bundle rejected

- Agent: `primary-integrator`.
- Task: Train EXP-100 with 522 clean and 522 deterministic five-frame-held
  semantic-token rows, then render the frozen 7 + 12 + 10 + 31 + 33 + 60 gate.
- Start: 2026-08-13T19:01:50Z.
- End: 2026-08-13T19:17:22Z.
- Dependencies: commit `a1494f0`; gpu0; EXP-035 control69; listener 8878.
- Result: 1,044 updates completed in 272.03 seconds at 4.77 GiB peak, but loss
  rose `144.22 -> 371.95`. External was 1/3/3 and `0.360 -> 0.462`; changed
  utterances 1/4/7 and `0.184 -> 0.323`; Hadou added one number loop; expanded33
  added seven loops and regressed `1.084 -> 3.612`; stress60 was 14/21/25 and
  `0.320 -> 0.362`.
- Problems: the corruption objective destabilized training. The broader gate
  prevented the superficially improved Hadou mean from becoming a false pass.
- Rework: none. Close block-size and corruption-ratio sweeps.

## 2026-08-13T19:19:38Z - EXP-106--111 real-source teacher method prepared

- Agent: `primary-integrator`.
- Task: replace EXP-072's donor-voice self-reconstruction rows with semantic-only
  distillation from immutable base X-VC on the same real Common Voice inputs
  under Amitaro target-speaker context.
- Dependencies: EXP-100--105 rejection; exact EXP-072 835/209 schedule
  positions; EXP-035 donors/control69/LR/seed/zero frame condition.
- Result: implementation and six frozen evaluation policies prepared. Focused
  tests passed 60 cases; exact CPU admissions passed 7 + 12 + 10 + 31 + 33 +
  60 rows. A runtime Torch smoke confirmed the teacher-only branch computes
  only `1000 * semantic MSE`.
- Problems: the configured Luna subagent runtime was unavailable in this client
  on two start attempts, so the parent completed the bounded design directly
  instead of retrying orchestration.
- Rework: the first CPU admission used `/tmp` outputs and correctly failed the
  artifact-root safety rule; rerunning with the intended artifact paths passed.
- Changed action: wait for the scheduled 19:20 Grok audit, then commit and run
  exactly one EXP-106 lane if the audit does not identify a stop or redirect.

## 2026-08-13T19:20:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: the fixed 7 + 12 + 10 + 31 + 33 + 60 gate correctly prevented the
  Hadou mean from becoming a false pass; close all token-hold sweeps. Grok
  accepted EXP-106 as a one-variable method comparison against EXP-072's exact
  real-input schedule positions and instructed one committed gpu0 lane followed
  by the same coarse corruption/content gate and 8878 publication.
- Not adopted: none. Its warning about 155 dirty entries is handled by staging
  only the EXP-106 method slice and leaving unrelated user changes untouched.

## 2026-08-13T19:39:38Z - EXP-106--111 teacher-semantic bundle completed

- Agent: `primary-integrator`.
- Start: 2026-08-13T19:23:47Z.
- End: 2026-08-13T19:39:38Z.
- Dependencies: method commit `871ee2b`; gpu0; exact EXP-035 control69 and
  EXP-072 835/209 positions; listener 8878.
- Result: training completed 1,044 updates in 270.33 seconds at 4.77 GiB peak,
  with loss `144.22 -> 134.13`. External7 was 2/4/1 (`0.360 -> 0.367`),
  changed12 4/5/3 (`0.184 -> 0.146`), conditions10 3/6/1 (`0.153 -> 0.060`),
  Hadou31 7/19/5 (`0.210 -> 0.184`) with one number loop, expanded33 12/8/13
  (`1.084 -> 0.620`) with no candidate loops, and stress60 27/18/15 (`0.320 ->
  0.254`) with every condition mean improved and no loop.
- Problems: expanded33's aggregate gain was outlier-driven. Excluding the three
  previously known loop sources, the mean regressed `0.514 -> 0.607` and the
  candidate was 9/8/13. The Hadou loop prevents a clean technical pass.
- Rework: none. Keep the audio unheard and unselected. Do not tune the 20%
  teacher share or semantic weight; acquire a genuinely fresh disjoint source
  set from the already-pinned Common Voice revision for the next check.

## 2026-08-13T19:44:00Z - EXP-112 fresh48 generalization gate prepared

- Agent: `primary-integrator`.
- Task: evaluate the unchanged EXP-106 checkpoint on 48 new Japanese speakers
  and sentences instead of reshuffling the 64 repeatedly used local clips.
- Dependencies: pinned Common Voice metadata revision and SHA; EXP-035 control69;
  EXP-106 checkpoint; one gpu0 lease after input materialization.
- Result: deterministic selection excludes every client represented by the 64
  local MP3s, requires one row per fresh client, two up-votes, zero down-votes,
  and 10--80 normalized characters. The renderer additionally rejects overlap
  with frozen donor, external, and expanded manifests. Focused tests passed 26
  cases and Ruff passed.
- Problems: none. Raw Common Voice client IDs are hashed in the generated
  manifest and source audio remains ignored.
- Rework: the first fresh48 CPU admission exposed that the donor-breadth loader
  cannot read the older expanded33 schema because it requires an ASR-distance
  field. The dedicated heldout-evaluation loader replaced that reuse; no CUDA
  job or rendered output had started.
- Changed action: commit the selection and evaluation contract before network
  acquisition, then render exactly base, control69, and EXP-106 once. Do not
  tune from individual fresh rows and do not infer naturalness from auxiliary
  ASR.

## 2026-08-13T19:50:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: Grok classified EXP-112 as the shortest way to test EXP-106 without
  another training cycle, explicitly closed teacher share/weight, old human87,
  DTW, and tongue-twister work, and directed one base/control/candidate render
  on fresh48 with only coarse content/corruption screening.
- Not adopted: none. Acquisition had already completed and the render began in
  parallel with the audit; its verdict required no interruption.

## 2026-08-13T19:55:02Z - EXP-112 fresh48 screen completed

- Agent: `primary-integrator`.
- Start: 2026-08-13T19:52:00Z.
- End: 2026-08-13T19:55:02Z.
- Dependencies: commits `e450d8f` and `6c1caa8`; gpu0; frozen fresh48 manifest;
  EXP-035 control69 and unchanged EXP-106 adapter; listener 8878.
- Result: 48 fresh speakers produced 144 model outputs in 116.26 seconds at
  4.77 GiB peak. Raw source-relative means were base `0.414`, control `1.001`,
  and EXP-106 `0.666`, but control and candidate each added a different severe
  loop. On the common 45 non-loop rows, EXP-106 regressed control mean `0.326 ->
  0.357`, median `0.250 -> 0.308`, and W/T/L was `10/19/16`.
- Problems: one naturally repetitive source tripped the gross-repetition rule
  in all three arms; it was not counted as an adapter-added failure. Auxiliary
  source ASR was unreliable on some crowd recordings, so both known-text and
  source-relative results were retained and no perceptual claim was made.
- Rework: none after admission. Close EXP-106 as a generic method without
  teacher-share, loss-weight, or fresh48 row tuning. Keep all audio unheard and
  unselected on 8878.

## 2026-08-13T19:58:00Z - EXP-113 adversarial fresh48 screen prepared

- Agent: `primary-integrator`.
- Task: use the now-frozen fresh48 set to test the retained EXP-064
  waveform-adversarial checkpoint while the next training-only data method is
  prepared.
- Dependencies: completed EXP-112; unchanged EXP-064 adapter; gpu0; base and
  control69; listener 8878.
- Result: one fixed-checkpoint render policy and focused regression test added.
- Problems: none.
- Changed action: run one 48-row comparison without retraining or objective
  tuning. This fills the otherwise idle GPU and supplies cross-method evidence
  from new data; it does not reuse fresh48 for fitting.

## 2026-08-13T20:04:00Z - EXP-113 adversarial fresh48 rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T20:00:00Z.
- End: 2026-08-13T20:04:00Z.
- Dependencies: commit `bf45dd3`; unchanged EXP-064 adapter; frozen fresh48;
  gpu0; listener 8878.
- Result: 144 model outputs completed in 115.65 seconds at 4.77 GiB peak. Raw
  candidate mean was `1.306`. On the common 45 non-loop rows it nearly tied
  control69 (`0.321` versus `0.326`, median `0.200` versus `0.250`, W/T/L
  `6/33/6`) but inherited one control loop and added another catastrophic loop.
- Problems: the old smaller gates had not exposed these source-dependent
  failures. The fresh split changed the technical disposition without being
  tuned.
- Rework: none. Reject waveform adversarial as a generic keeper and close its
  weight sweep. Keep the new audio unheard and unselected.

## 2026-08-13T20:05:00Z - EXP-114 teacher breadth48 method prepared

- Agent: `primary-integrator`.
- Task: replace EXP-106's twelve repeatedly used real teacher sources with 48
  training-only speakers while holding all 209 teacher positions and every
  optimization setting fixed.
- Dependencies: EXP-112 rejection; pinned Common Voice metadata; frozen
  fresh48 exclusion; EXP-035 pseudo sources/control69; one gpu0 lane.
- Result: commit `07d7a0d` fixed deterministic selection, disjoint-pool
  admission, balanced 209-slot cycling, and the training policy. Focused tests
  passed 53 cases. Materialization produced 48 unique files/speakers with
  manifest SHA `cd093f43c52f79294cd5c5d9d17b8932845cedd03d17530885eff1711c2a8eab`.
  Exact CPU admission confirmed 835 standard plus 209 teacher roles, 87 target
  texts, 48 real teacher sources, and 1,044 updates. Seventeen training speakers
  receive five teacher exposures and 31 receive four.
- Problems: none so far.
- Changed action: commit before acquisition, materialize the training pool,
  then train one point. Do not add 24/96-source or teacher-share variants.

## 2026-08-13T20:18:14Z - EXP-114/115 teacher breadth48 rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T20:09:00Z.
- End: 2026-08-13T20:18:14Z.
- Dependencies: commits `07d7a0d` and `23f9d6b`; train48 manifest
  `cd093f43...`; frozen fresh48; gpu0; listener 8878.
- Result: training completed 1,044 updates in 304.05 seconds at 4.77 GiB peak.
  Standard loss moved `144.22 -> 134.83`, while teacher-semantic loss moved
  `0.0079 -> 1.3302`. External7 regressed `0.360 -> 0.430` without a loop.
  EXP-115 then produced 144 fresh48 outputs in 124.01 seconds. The candidate
  had four gross-repetition rows total, adding two failures beyond the natural
  repeated source and control's existing failure. On the common 44 non-loop
  rows it was 10/22/12, mean `0.319 -> 0.324`, median `0.225 -> 0.304`.
- Problems: more real teacher speakers did not constrain waveform-level output
  stability. The broad fresh gate prevented a near-tied non-loop mean from
  hiding two catastrophic added failures.
- Rework: none. Stop before stress60. Close teacher-source count, share, and
  semantic-weight sweeps. Preserve train48 as training-only and fresh48 as
  evaluation-only for a genuinely different objective.

## 2026-08-13T20:20:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `REDIRECT`.
- Adopted: stop teacher count/share/weight and adversarial-weight neighbors;
  move immediately to one committed method-level loss or learning-target point
  that directly addresses waveform instability. EXP-116 does exactly that by
  changing only the same train48 teacher rows from semantic-only targets to
  frozen-base complete converted outputs and full composite loss.
- Not adopted: Grok reported that noise, tempo, F0, silence, and clean axes were
  not yet frozen because its short snapshot omitted EXP-086. The existing
  60-row, 12-source balanced stress matrix already freezes those five named
  conditions. Rebuilding it would duplicate work; it remains downstream of a
  fresh48 survival gate.
- Evidence gap resolved: Grok's file snapshot missed the newest EXP-115 WAVs,
  but 48 base/control/candidate rows and listener 8878 were verified directly.
  No operator keep/continue/rejected result is claimed.

## 2026-08-13T20:24:00Z - EXP-116 full-output teacher prepared

- Agent: `primary-integrator`.
- Task: replace semantic-only supervision on EXP-114's same 209 train48 slots
  with the frozen base's full Amitaro-conditioned converted waveform, retaining
  standard semantic, speaker, mel, and VQ losses.
- Dependencies: Grok `REDIRECT`; frozen train48/fresh48; EXP-114 rejection;
  exact 835/209 schedule and control69 optimization.
- Result: training policy, complete teacher-target construction, a one-row LoRA
  backward smoke path, EXP-117 fresh48 policy, and focused tests prepared.
- Problems: none so far.
- Changed action: commit before the runtime smoke. Run one smoke and one lane
  only; stop at fresh48 before stress60 on added repetition or broad regression.

## 2026-08-13T20:33:00Z - EXP-116 full-output backward smoke passed

- Agent: `primary-integrator`.
- Dependencies: commit `2fe309a`; exact train48/fresh48 bindings; gpu0.
- Result: one frozen-base converted target had 38,400 samples. Standard full
  composite loss was `161.0455`; LoRA backward gradient norm was `24.3294`;
  peak GPU allocation was 3.30 GiB; exit status was zero.
- Problems: the first invocation's execution wrapper lost stdout/exit status
  after the process detached, although it produced the teacher reference. The
  same one-row smoke was rerun with explicit log and status capture; no adapter
  or comparison output from either smoke was retained.
- Rework: runtime evidence only. Admit one 1,044-update EXP-116 lane now.

## 2026-08-13T20:43:00Z - EXP-116/117 full-output teacher retained with stop

- Agent: `primary-integrator`.
- Start: 2026-08-13T20:33:00Z.
- End: 2026-08-13T20:43:00Z.
- Dependencies: commits `2fe309a` and `28ddbd0`; train48 manifest; frozen
  fresh48; gpu0; listener 8878.
- Result: training completed 1,044 updates in 329.15 seconds at 4.77 GiB peak.
  Standard loss moved `144.221 -> 131.102`; full-output teacher loss moved
  `161.018 -> 72.944`. External7 improved source-relative `0.360 -> 0.320`
  and known-text `0.399 -> 0.359` without a gross loop. EXP-117 produced 144
  fresh48 outputs. Candidate raw mean was `0.334`, versus base `0.414` and
  control69 `1.001`; maximum was `1.25`, versus control69 `32.4`. On the 45
  common non-loop rows, candidate versus control was 10/25/10, mean `0.329`
  versus `0.319`, median `0.154` versus `0.250`, and known-text mean `0.586`
  versus `0.610`.
- Problems: one low-quality source produced a new 12-character repeated-`ぷ`
  output. The exact method therefore fails the precommitted no-added-loop stop
  even though it is the strongest broad technical signal so far.
- Rework: stop before stress60 and do not tune the failed row. Retain the audio
  unheard and unselected. Next change only freeze scope: remove all 47 attention
  targets and keep the 22 converter FFN linears under the same objective/data.

## 2026-08-13T20:50:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: EXP-116/117 satisfied the recent-audio condition; keep train48,
  fresh48, the full-output objective, and the no-added-loop stop fixed, and run
  the selected 22-FFN freeze-scope point as one sequential lane.
- Discarded as requested: individual tuning of the repeated-`ぷ` row, stress60
  before fresh48 survival, adjacent scope points, old human87/DTW retries, the
  non-ChatGPT 8.17-second diagnostic, and promote ceremony.
- Evidence gap: Grok could not observe operator browser localStorage or whether
  the new lane had started. Direct process inspection confirmed the committed
  smoke was already active; no second lane was opened.

## 2026-08-13T20:54:00Z - EXP-118 FFN-only output-teacher smoke passed

- Agent: `primary-integrator`.
- Dependencies: commit `481efb9`; exact train48/fresh48 bindings; gpu0.
- Result: 52 focused tests passed. CPU admission fixed 22 FFN LoRA targets
  (ten `ff_c`, twelve `ff_x`), 450,560 trainable parameters, 835 standard and
  209 full-output teacher rows. One real-model smoke produced a 38,400-sample
  teacher target, loss `161.0455`, gradient norm `11.5205`, and 3.28 GiB peak
  GPU allocation; exit status zero.
- Problems: checkpoint load was disk-bound for roughly two minutes; backward
  itself completed normally.
- Rework: runtime evidence only. Admit exactly one 1,044-update EXP-118 lane,
  followed by external7 and frozen fresh48. Do not run adjacent scopes.

## 2026-08-13T21:04:26Z - EXP-118/119 FFN-only teacher rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T20:55:13Z.
- End: 2026-08-13T21:04:26Z.
- Dependencies: commits `481efb9` and `b01793e`; train48; frozen fresh48;
  gpu0; listener 8878.
- Result: 1,044 updates completed in 310.78 seconds at 4.77 GiB peak.
  Standard loss moved `144.22 -> 135.37`; teacher loss moved `161.05 ->
  72.51`. External7 improved control source-relative `0.360 -> 0.290` and
  known-text `0.399 -> 0.383`, with no loop. EXP-119 produced 144 outputs.
  On the 45 common non-loop rows candidate versus control was 14/21/10,
  source-relative mean `0.329` versus `0.326`, median `0.273` versus `0.250`,
  and known-text mean `0.606` versus `0.610`.
- Problems: the candidate retained control69's catastrophic repeated-family
  row and added a new 110-character repeated-`ぃ` run. Together with the
  naturally repetitive source it had three flagged rows versus control's two.
- Rework: reject FFN-only, stop before stress60, and do not run adjacent scope
  points. Return to EXP-116's stronger control69 signal and test one materially
  different PEFT parameterization, DoRA, before considering conditioning or
  data-construction changes.
