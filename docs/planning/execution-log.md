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

## 2026-08-13T21:14:12Z - EXP-120 DoRA output-teacher smoke passed

- Agent: `primary-integrator`.
- Dependencies: commit `4606474`; exact train48/fresh48 bindings; gpu0.
- Result: 54 focused tests passed. CPU admission retained the exact 69
  control69 targets and added 52,224 magnitude parameters for 887,808 trainable
  parameters total. One real-model backward smoke produced a 38,400-sample
  target, loss `161.0455`, finite pre-clip gradient norm `32.0441`, and 3.34
  GiB peak GPU allocation; exit status zero.
- Problems: none. The larger pre-clip norm is diagnostic only; the unchanged
  norm-5 clipping contract remains active during training.
- Rework: runtime evidence only. Admit exactly one 1,044-update EXP-120 lane,
  external7, and frozen fresh48. Do not open another PEFT variant.

## 2026-08-13T21:24:21Z - EXP-120/121 DoRA teacher rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T21:14:43Z.
- End: 2026-08-13T21:24:21Z.
- Dependencies: commits `4606474` and `effa73d`; train48; frozen fresh48;
  gpu0; listener 8878.
- Result: 1,044 updates completed in 337.18 seconds at 4.77 GiB peak.
  External7 improved control source-relative `0.360 -> 0.270` and known-text
  `0.399 -> 0.359`, without a loop. EXP-121 produced 144 outputs. On the 45
  common non-loop rows DoRA improved control mean `0.319 -> 0.296`, median
  `0.250 -> 0.200`, and known-text mean `0.610 -> 0.581`; W/T/L was 12/23/10.
- Problems: DoRA retained control69's catastrophic `32.4` repeated-family row
  and added the separate 12-character repeated-`ぷ` failure seen in EXP-116.
  Counting the naturally repetitive source, candidate had three flagged rows.
- Rework: reject and stop before stress60. Close PEFT neighbors. Keep the
  non-loop content signal as evidence and change the learning objective next:
  add direct temporal first-difference matching to aligned teacher outputs.

## 2026-08-13T21:20:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: recent new audio, frozen external7/fresh48, one-variable jobs, and
  result-driven sequential replanning remain the shortest path. After DoRA's
  later failure, close all neighboring PEFT variants as the audit warned.
- Not adopted: the snapshot inferred gpu0 might be idle because it sampled a
  model transition at 0% utilization. Direct process and result evidence show
  EXP-120 training, rendering, and screening were active across the window.
- Changed action: proceed to a different learning-objective point, not another
  PEFT point. Continue excluding stress60 until fresh48 survival.

## 2026-08-13T21:31:37Z - EXP-122 temporal-loss smoke passed

- Agent: `primary-integrator`.
- Dependencies: commit `bbca644`; exact train48/fresh48 bindings; gpu0.
- Result: 57 focused tests passed. One real-model teacher row produced a
  38,400-sample target, total loss `169.1617` versus standard composite
  `161.0455`, finite pre-clip gradient norm `24.8603`, 835,584 trainable
  parameters, and 3.30 GiB peak allocation; exit status zero. The weight-1000
  temporal term contributed about 8.12 loss units at initialization.
- Problems: none.
- Rework: runtime evidence only. Admit exactly one 1,044-update EXP-122 lane,
  external7, and frozen fresh48. Do not run a temporal-weight neighbor.

## 2026-08-13T21:41:33Z - EXP-122/123 temporal teacher rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T21:32:11Z.
- End: 2026-08-13T21:41:33Z.
- Dependencies: commits `bbca644` and `d3b774a`; train48; frozen fresh48;
  gpu0; listener 8878.
- Result: 1,044 updates completed in 335.44 seconds at 4.77 GiB peak.
  External7 improved control source-relative `0.360 -> 0.279` and known-text
  `0.399 -> 0.383` with no loop. EXP-123 produced 144 outputs. On the 45
  common non-loop rows candidate versus control was 11/23/11, mean `0.316`
  versus `0.319`, median `0.267` versus `0.250`, and known-text mean `0.585`
  versus `0.610`.
- Problems: the candidate retained control69's catastrophic `32.4`
  repeated-family row and added the same 12-character repeated-`ぷ` failure
  seen in EXP-116 and EXP-120.
- Rework: reject and stop before stress60. Close temporal-weight neighbors.
  Change data construction next by holding count/share fixed while crossing
  Common Voice, Hadou, and JVS training-source domains.

## 2026-08-13T22:53:01Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: the source-window teacher remained one committed variable on one
  GPU lane with frozen external7/fresh48 screens and 8878 publication. Close
  coverage methods if the same repetition survives.
- Not adopted: none. The sampled 0% GPU was a load transition; direct process
  evidence showed EXP-134 active.
- Changed action: retain the no-added-loop stop, do not open stress60, and
  validate the pre-existing semantic-collapse hypothesis on disjoint inputs if
  the same loop returns.

## 2026-08-13T23:02:00Z - EXP-133--136 source-window method completed

- Agent: `primary-integrator`.
- Start: 2026-08-13T22:42:59Z.
- End: 2026-08-13T23:02:00Z.
- Dependencies: commits `ee9f3eb`, `8e69a32`, `2d69380`; gpu0; frozen
  external7/fresh48/Hadou31; listener 8878.
- Result: EXP-133 audited 247 training-only Hadou utterances at start, middle,
  and end windows. Only 21 had identical ASR content at all three positions;
  middle windows exposed 2,196 unique normalized trigrams versus 1,489 at the
  start. EXP-134 then trained once in 322.89 seconds at 4.77 GiB peak and
  published 35 external, 240 fresh48, and 155 Hadou31 WAV files. External7
  improved control `0.360 -> 0.320`. Common non-loop fresh48 improved mean
  `0.341 -> 0.321` (14/23/9); common non-loop Hadou30 improved `0.185 ->
  0.160` (6/21/3).
- Problems: the candidate retained control's fresh `32.4` family collapse and
  added the same 53-count `三・四` loop on heldout `RECITATION324_138` as the
  two previous cross-corpus teachers. Its 209 pseudo-teacher outputs contained
  no gross loop.
- Rework: reject a generic keeper and close further source-coverage selection.
  Keep the broad audio unselected. Validate EXP-093's preregistered
  `unique semantic tokens <= 5` safety hypothesis on disjoint fresh48/Hadou31;
  if it misses the failures, move to a different training objective rather
  than another coverage point.

## 2026-08-13T23:07:00Z - EXP-137 disjoint semantic gate rejected

- Agent: `primary-integrator`.
- Dependencies: commit `6c0a3ca`; frozen EXP-135/136 inputs and loop labels;
  gpu0.
- Result: all 79 source windows completed in 94.77 seconds at 2.40 GiB peak.
  The unchanged EXP-093 `unique_tokens <= 5` rule flagged zero rows and missed
  both adapter-added loops. The fresh failure had 24 unique tokens and the
  Hadou failure had 29 versus a dataset median of 28.
- Problems: the earlier low-token association did not generalize.
- Rework: reject the input gate and do not fit a threshold on these 79 outputs.
  Replace repeated exposure to 48 teacher sources with a near-one-pass pool of
  about 201 disjoint training sources/windows while keeping teacher positions,
  standard rows, loss, LR, target, and evaluation fixed.

## 2026-08-13T23:22:33Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: run the already admitted 201-source near-one-pass teacher lane, then
  screen only frozen external7/fresh48/Hadou31 and publish its audio on 8878.
  Treat EXP-138 as the final coverage/breadth point; if either known heldout
  repetition failure remains, move to objective, conditioning, or trainable
  target changes instead of adding another source-count or window point.
- Not adopted: the audit snapshot could not confirm GPU activity during model
  load. Direct inspection immediately afterward showed EXP-138 active at 34%
  GPU utilization and 3.8 GiB process memory.
- Changed action: close threshold refitting, stress60-before-survival, and all
  further coverage neighbors. Preserve the no-adapter-added-loop stop and do
  not treat auxiliary ASR as a keep or promote decision.

## 2026-08-13T23:32:00Z - EXP-138--140 window breadth rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T23:17:36Z.
- End: 2026-08-13T23:31:00Z.
- Dependencies: commits `cced615` and `a6f8727`; frozen external7/fresh48/
  Hadou31; gpu0; listener 8878.
- Result: EXP-138 trained 1,044 updates in 310.55 seconds at 4.77 GiB peak and
  published 35 external, 240 fresh48, and 155 Hadou31 WAVs. On the 45 common
  non-loop fresh rows it improved control69 mean `0.326 -> 0.289`, median
  `0.250 -> 0.200`, known-text mean `0.610 -> 0.594`, and W/T/L `15/24/6`.
- Problems: the candidate added a 109-character repeated-vowel failure on
  fresh48 and repeated the heldout `RECITATION324_138` numeric loop. More
  importantly, the actual 209 frozen-base teacher targets contained two gross
  loops and 33 rows at source-relative distance at least `0.5`; increasing
  source breadth had admitted broken converted targets as supervision.
- Rework: reject EXP-138 and close source-count/window coverage. Bind the
  existing `<0.5`, no-gross diagnostic before training, deduplicate to 170
  real teacher IDs, and test one materially different two-stage optimization:
  start from control69 and make one clean teacher-only rehearsal pass.

## 2026-08-13T23:39:00Z - EXP-141 post-rehearsal smoke passed

- Agent: `primary-integrator`.
- Dependencies: commit `727b27f`; clean manifest SHA-256 `86822d41`; frozen
  control69 adapter; gpu0.
- Result: 68 focused tests passed. One admitted teacher row loaded control69
  as trainable and completed backward with loss `213.5427`, finite pre-clip
  gradient norm `156.4660`, 835,584 trainable parameters, and 3.30 GiB peak.
- Problems: the first-row gradient is much larger than the fresh-base teacher
  smoke, but the unchanged norm-5 clip operated normally.
- Rework: admit exactly one 170-update clean pass. Do not change LR, clip,
  threshold, or row count. Render external7, fresh48, and Hadou31 only.

## 2026-08-13T23:52:58Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: finish the single EXP-141 screen before another training lane;
  record known heldout repetition, added corruption, and broad content change.
  Treat JSUT24 only as a frozen evaluation and never as an optimization target.
  If clean teachers still leave a loop, close data-filter/coverage neighbors.
- Not adopted: the audit sampled GPU at 0% during model loading and could not
  see the new EXP-141 WAV mtimes. Direct inspection showed the sole renderer
  alive and it completed all three frozen screens moments later.
- Changed action: do not run EXP-141 on JSUT after its fresh/Hadou stop. Use the
  untouched set for a later surviving method. Before another training point,
  ask whether control69's collapse can be reproduced on training-only inputs.

## 2026-08-13T23:57:35Z - EXP-141--143 clean rehearsal rejected

- Agent: `primary-integrator`.
- Start: 2026-08-13T23:44:40Z; committed retry 2026-08-13T23:48:42Z.
- End: 2026-08-13T23:57:35Z.
- Dependencies: commits `2b6dc18`, `cebe17c`, and `e6369ef`; clean manifest
  SHA-256 `86822d41`; control69; frozen external7/fresh48/Hadou31; gpu0;
  listener 8878.
- Result: the retry completed 170 updates in 144.40 seconds at 5.10 GiB peak,
  loss `213.54 -> 53.78`, and published 35 external, 240 fresh48, and 155
  Hadou31 WAVs. The clean pass removed EXP-138's candidate-only 109-character
  vowel collapse. On 30 non-gross Hadou rows it improved control mean `0.185
  -> 0.148` (8/19/3); on 46 non-gross fresh rows it regressed `0.341 ->
  0.352` (9/22/15).
- Problems: the initial run finished training and inference but a missing
  listener `slug` raised `KeyError` before publication. A contract test and
  one-field fix were committed before the exact retry. The retry retained the
  fresh `cv30615849f` 32.4-distance control collapse and added an 85-repeat
  `24` loop on heldout `RECITATION324_138`.
- Rework: reject the generic candidate; close clean-threshold, row-count, and
  rehearsal-pass neighbors. Preserve the broad unheard audio. Do not spend
  untouched JSUT24 on this failed checkpoint. Admit only a training-only
  control-collapse probe; if it finds no reproducible hard negatives, redirect
  directly to loss, conditioning, or trainable-target design.

## 2026-08-14T00:02:06Z - EXP-145 reproduced a control-only collapse

- Agent: `primary-integrator`.
- Start: 2026-08-13T23:59:07Z.
- End: 2026-08-14T00:02:06Z.
- Dependencies: commit `19aaf74`; all 170 clean training-only sources from
  EXP-141; frozen control69; gpu0. No evaluation row was opened.
- Result: 170 control outputs rendered in 128.66 seconds at 2.48 GiB peak and
  were screened against their own source ASR. Eleven had source-relative
  distance at least `0.5`; one was gross. On training-only
  `hadou-RECITATION324_031-start`, the frozen base teacher transcribed the
  source exactly at distance `0.0`, while control69 repeated `コ` 216 times at
  distance `23.78`.
- Problems: two Common Voice source windows had empty prior ASR text. The CPU
  admission initially required non-empty text and stopped before GPU launch;
  the contract was corrected to make known text optional while preserving
  audio identity and source-relative screening.
- Rework: the hard-negative mechanism is reproducible independently of heldout
  rows. Admit one 170-update sampling-method change: alternate 85 positions
  round-robin over the 11 hard rows with 85 distinct domain-stratified easy
  rows, retaining control69 initialization and every objective/hyperparameter.
  Do not run a ratio or exposure neighbor. JSUT stays untouched until the
  fresh48 and Hadou31 stop gates survive.

## 2026-08-14T00:20:05Z - EXP-146--149 hard-negative sampling rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T00:10:04Z.
- End: 2026-08-14T00:20:05Z.
- Dependencies: commit `3c158df`; hard-curriculum manifest SHA-256
  `419fd1a9`; frozen control69; 11 training-only hard rows; external7,
  fresh48, Hadou31; gpu0; listener 8878.
- Result: the real smoke passed with loss `227.88`, finite pre-clip gradient
  norm `143.75`, and 3.30 GiB peak. Training completed 170 updates in 149.62
  seconds at 5.10 GiB peak and moved loss `227.88 -> 66.92`. It published 35
  external, 240 fresh48, and 155 Hadou31 WAVs. The external mean regressed
  `0.360 -> 0.455`. On 46 common non-gross fresh rows the candidate scored
  `10/20/16`, regressing mean `0.341 -> 0.402` and median `0.275 -> 0.326`.
  On 30 non-gross Hadou rows it improved mean `0.185 -> 0.153` with `9/18/3`.
- Problems: the candidate retained fresh48's control `32.4` collapse and added
  the mandatory-stop `RECITATION324_138` failure, repeating `24` through a
  long numeric tail. Hard-row oversampling repaired many ordinary Hadou rows
  but did not remove the heldout collapse mechanism and caused broad Common
  Voice drift.
- Rework: reject EXP-146 and do not run conditional JSUT EXP-149. Close the
  hard/easy ratio, exposure-count, and threshold neighbors. The next admitted
  lane must change one method-level loss, conditioning, or learning-target
  policy while preserving training/evaluation separation; machine screening
  remains corruption/content evidence only.

## 2026-08-14T00:22:54Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: run the single committed EXP-146 hard-negative lane, preserve
  external7/fresh48/Hadou31 as the stop sequence, keep JSUT unopened, and close
  ratio/exposure/threshold neighbors on failure. That exact lane and all three
  screens had already completed while the audit prompt was sampled.
- Not adopted: Grok inferred `3c158df` had not launched from `gpu=0%`,
  `active_audio_jobs=0`, and retained WAV mtimes. Direct result/status evidence
  showed exit `0`, 430 new model-output WAVs, broad fresh48 regression, and the
  added Hadou numeric loop. Relaunching would duplicate a failed experiment.
- Changed action: follow the audit's own failure branch immediately: sampling
  is closed and the next single lane must change loss, conditioning, or the
  learning target. Preserve JSUT24 and make no machine quality selection.

## 2026-08-14T00:29:00Z - EXP-150--153 selective retention prepared

- Agent: `primary-integrator`.
- Dependencies: EXP-146 rejection; frozen 170-position hard curriculum;
  EXP-145's 170 training-only control outputs; frozen external7/fresh48/
  Hadou31/JSUT24; control69; gpu0.
- Result: bind the same 85-hard/85-easy EXP-146 schedule while changing only
  easy-row learning targets from base-X-VC outputs to their frozen non-gross
  control69 outputs. Hard rows retain clean base-teacher repair targets. The
  manifest has SHA-256 `6322a9c`, composition 56 Common Voice/111 Hadou/3 JVS,
  and exact 85 repair/85 retention targets. Focused tests and real CPU runner
  admission passed all 170 audio identities and the external7 contract.
- Problems: none. The method deliberately retains EXP-146's hard exposure so
  its causal comparison changes learning-target policy rather than sampling.
- Rework: commit, then run one lane and the external7/fresh48/Hadou31 stop
  sequence. Do not add blend, ratio, exposure, threshold, or scope neighbors.
  Open JSUT24 only if all earlier screens survive.

## 2026-08-14T00:36:41Z - EXP-150--153 selective retention rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T00:30:12Z.
- End: 2026-08-14T00:36:41Z.
- Dependencies: commit `eb82428`; selective manifest SHA-256 `6322a9c5`;
  frozen control69 and its 85 easy-row outputs; 85 base-teacher hard targets;
  external7/fresh48/Hadou31; gpu0; listener 8878.
- Result: training completed 170 updates in 115.62 seconds at 5.10 GiB peak,
  loss `227.88 -> 45.00`, and published 35 external, 240 fresh48, and 155
  Hadou31 WAVs. External source-relative distance was `0.378` versus control
  `0.360`, a large recovery from EXP-146's `0.455`. On 46 common non-gross
  fresh rows the candidate improved mean `0.341 -> 0.310` with `12/22/12`;
  known-text mean improved `0.618 -> 0.610`. On 30 non-gross Hadou rows it
  improved mean `0.185 -> 0.170` with `5/23/2`.
- Problems: the candidate retained fresh48's control `32.4` family collapse
  and added the mandatory-stop `RECITATION324_138` numeric failure, repeating
  `9` for a 66-character run. Retention fixed broad drift but did not make hard
  repair generalize across the frozen Hadou split.
- Rework: reject the exact candidate, keep its unheard audio, and do not open
  JSUT24 or tune blend/ratio/exposure/threshold. Since the learning-target
  policy helped normal rows while the 69-module LoRA still failed on the same
  heldout mechanism, the next one-variable lane should keep the selective
  targets and change the trainable target to the full acoustic converter.

## 2026-08-14T00:43:00Z - EXP-154--157 full-converter retention prepared

- Agent: `primary-integrator`.
- Task: preserve EXP-150's selective learning targets and test a genuinely
  different trainable target rather than another data-ratio or LoRA neighbor.
- Dependencies: EXP-150 rejection; committed selective manifest SHA-256
  `6322a9c5`; merged control69 initialization; external7, frozen fresh48,
  Hadou31, and unopened JSUT24; gpu0; listener 8878.
- Result: add a full `acoustic_converter` path with exactly 42,357,760 trainable
  parameters, a converter-only safetensors checkpoint, and exact reconstruction
  from base plus merged control69 for later evaluation. Keep the same 170 rows,
  repair/retention targets, loss, LR, clip, zero condition, and update order.
- Problems: human listening remains unavailable, so machine screens may only
  reject gross corruption or content collapse. The historical local
  tongue-twister is excluded from both training and gating.
- Rework: commit before the real GPU smoke and training. Gate unchanged audio
  external7 -> fresh48 -> Hadou31; consume JSUT24 only after all survive. Do not
  tune LR, loss, ratio, blend, threshold, or converter sub-scope in this lane.

## 2026-08-14T00:50:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: finish the committed full-converter pilot, screen external7 then
  fresh48 then Hadou31, reject gross corruption immediately, leave JSUT24
  unopened unless all survive, and make no machine naturalness selection.
- Adopted redirect condition: if the same collapse family survives or another
  collapse appears, close trainable-scope neighbors and move to data, loss, or
  conditioning. Make speaking-rate, F0, silence, and noise a first-class frozen
  gate for the next surviving candidate.
- Changed action: none during the running lane. The audit stayed parallel to
  the GPU job and did not become a gate.

## 2026-08-14T00:57:00Z - EXP-154--157 full converter rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T00:49:00Z.
- End: 2026-08-14T00:57:00Z.
- Dependencies: commit `7afe5c5`; EXP-150 selective manifest; merged control69;
  external7 and frozen fresh48; gpu0; listener 8878.
- Result: the real smoke exposed finite gradients on all 42,357,760 converter
  parameters. Training completed 170 updates in 117.83 seconds at 5.56 GiB
  peak, loss `227.96 -> 44.63`, and published external7 plus fresh48 audio.
  External7 had no gross loop and tied source-relative mean (`0.360 -> 0.358`),
  though known-text mean regressed `0.399 -> 0.494`. Frozen fresh48 then added
  one gross row: `cv39028774f` repeated `ん` for 223 normalized characters.
  On 45 common non-gross rows, source-relative W/T/L was `9/25/11`, mean
  `0.326 -> 0.353`, and median `0.250 -> 0.294`.
- Problems: increasing trainable capacity added a new collapse and did not
  generalize the repair target. Auxiliary known-text mean alone was nearly tied
  on non-gross rows and is not a quality decision.
- Rework: reject without Hadou31 or JSUT24. Close converter and LoRA-scope
  neighbors. The next lane changes objective, data construction, or
  conditioning, and a surviving checkpoint must also pass stress60 before
  JSUT24. Keep the local tongue-twister excluded.

## 2026-08-14T01:00:00Z - EXP-158--162 real-reference adversarial prepared

- Agent: `primary-integrator`.
- Task: move off the closed trainable-scope branch and test one naturalness- and
  collapse-motivated objective while retaining EXP-150's useful anti-drift
  learning targets.
- Dependencies: EXP-150 broad-retention signal; EXP-154 fresh48 rejection;
  EXP-064's pretrained discriminator path and no-new-loop stress60 result;
  authorized original Amitaro target references; external7, frozen fresh48,
  Hadou31, stress60, and unopened JSUT24; gpu0; listener 8878.
- Result: separate target roles. The composite generator loss receives the
  exact committed repair/retention output targets, while discriminator real and
  feature matching receive the corresponding original Amitaro recordings.
  Generated teacher audio is never labeled real. Training rows, order,
  initialization, LoRA69 scope, LR, clip, condition, and 170 updates stay fixed.
- Problems: adversarial naturalness cannot be selected without hearing. Coarse
  screens may only reject repetition/content corruption.
- Rework: focused tests and a real one-update smoke, then commit before one GPU
  lane. Gate external7 -> fresh48 -> Hadou31 -> stress60; only all-survival may
  consume JSUT24. Do not tune adversarial weights or neighboring schedules.

## 2026-08-14T01:11:00Z - EXP-158--162 real-reference adversarial rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T01:03:00Z.
- End: 2026-08-14T01:11:00Z.
- Dependencies: commit `ca91011`; selective 85-repair/85-retention targets;
  original Amitaro discriminator references; external7 and frozen fresh48;
  gpu0; listener 8878.
- Result: the real smoke separated synthetic generative targets from original
  discriminator-real audio with finite losses. Training completed 170 updates
  in 149.25 seconds at 5.47 GiB peak, total loss `298.40 -> 102.46`, and
  published external7 plus fresh48. External7 had no gross loop and nearly tied
  source-relative mean (`0.360 -> 0.356`). On 45 common non-gross fresh rows,
  source-relative W/T/L was `12/24/9`, mean improved `0.319 -> 0.301`, and
  median improved `0.250 -> 0.200`.
- Problems: the candidate added a gross `フ` run on fresh row `cv39042955f`.
  Real-reference waveform adversarial improved ordinary rows but did not act as
  a content-collapse safety mechanism.
- Rework: reject without Hadou31, stress60, or JSUT24 and do not tune loss
  weights. A differentiable output-to-Whisper cycle is not available through
  the current wrapper because extraction is no-grad and crosses CPU NumPy.
  The next bounded method restores the upstream-configured EMA omission once,
  using pinned package defaults and the same training/evaluation contract.

## 2026-08-14T01:16:00Z - EXP-163--167 upstream EMA prepared

- Agent: `primary-integrator`.
- Task: restore one omitted upstream X-VC training mechanism rather than tune
  EXP-158's adversarial weights or add another scope point.
- Dependencies: EXP-158's 45-row ordinary-content gain and new fresh collapse;
  pinned X-VC `ema_update: True`; pinned `ema-pytorch==0.7.7` defaults;
  external7, fresh48, Hadou31, stress60, and unopened JSUT24; gpu0; listener
  8878.
- Result: implement the exact default inverse-decay schedule over the only
  mutable tensors: 835,584 LoRA parameters. In 170 calls it performs 11 exact
  copies through step 100 and six moving-average updates through step 160.
  Preserve the final online adapter separately and evaluate only EMA. Focused
  tests verify the schedule, decay, copy-back, policies, and frozen gates.
- Problems: EMA may stabilize parameter trajectory but cannot guarantee content
  correctness or perceived naturalness. It must hit the same gross stop.
- Rework: run one real smoke, commit, then one unchanged GPU lane. Do not sweep
  EMA settings. Gate external7 -> fresh48 -> Hadou31 -> stress60, then JSUT24
  only on all-survival.

## 2026-08-14T01:20:25Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: finish the exact committed EMA lane, reject on external7/fresh48
  gross corruption, proceed to Hadou31 only on survival, make no metric quality
  winner, and do not sweep EMA settings or start a second method early.
- Clarification: the sampled GPU utilization was zero during checkpoint load,
  but PID and later result evidence show the committed EMA job was active. No
  duplicate launch was performed.
- Changed action: after fresh48 added no gross row and improved common non-gross
  summaries, continue unchanged to Hadou31, then the preregistered stress60 and
  JSUT24 gates.

## 2026-08-14T01:34:00Z - EXP-163--167 upstream EMA technical survivor

- Agent: `primary-integrator`.
- Start: 2026-08-14T01:18:00Z.
- End: 2026-08-14T01:34:00Z.
- Dependencies: commit `7658d61`; exact EXP-158 online trajectory; pinned
  upstream EMA defaults; external7, fresh48, Hadou31, stress60, JSUT24; gpu0;
  listener 8878.
- Result: 170 online updates completed in 155.74 seconds at 5.47 GiB peak. EMA
  performed 11 copies and six moving-average updates, last decay `0.93547`.
  External7 regressed source-relative mean `0.360 -> 0.411`, but no later set
  reproduced a broad technical failure. Fresh46 common non-gross improved mean
  `0.341 -> 0.328`, W/T/L `12/25/9`, with no candidate-added gross row. Hadou31
  had no gross row and improved source-relative mean `0.210 -> 0.171`, W/T/L
  `6/23/2`; the prior numeric loop did not recur. Stress60 added no gross row,
  tied source-relative macro `0.31959 -> 0.32000`, and improved known-text macro
  `0.6726 -> 0.6588`. Untouched JSUT24 added no gross row and improved
  source-relative macro `0.165 -> 0.142`, W/T/L `3/21/0`, while known-text mean
  regressed `0.552 -> 0.571`.
- Problems: metrics conflict by set and condition; external7/clean/pitch/tempo
  have regressions, and no machine measure decides naturalness or target voice.
- Rework: retain exact EMA and online checkpoints plus 850 new comparison WAVs
  on 8878. Mark the EMA arm a technical survivor only. Stop EMA/adversarial
  sweeps and await human hearing for keep/reject; further GPU work must use a
  distinct data or model method and a frozen cross-corpus gate.

## 2026-08-14T01:38:00Z - EXP-168 expanded33 posthoc gate prepared

- Agent: `primary-integrator`.
- Task: keep gpu0 productive while the next distinct data method is designed,
  using one already-frozen evaluation set rather than an EMA parameter sweep.
- Dependencies: exact EXP-163 EMA adapter; frozen EXP-055 expanded33 manifest;
  gpu0; listener 8878.
- Result: bind unchanged base, control69, and EMA identities to 33 additional
  Common Voice speakers/utterances. The set is evaluation-only and cannot
  select EMA settings or promotion.
- Problems: posthoc evidence is weaker than the preregistered gate and contains
  known source-side ASR pathologies; report common non-gross rows separately.
- Rework: commit, render once, reject on candidate-added gross corruption, and
  do not use the outcome to tune EMA. In parallel after launch, prepare a
  disjoint category-balanced JSUT training-data method.

## 2026-08-14T01:43:00Z - EXP-168 expanded33 posthoc gate survived

- Agent: `primary-integrator`.
- Dependencies: commit `afc38d0`; exact EXP-163 EMA adapter; frozen expanded33;
  gpu0; listener 8878.
- Result: published 165 more comparison WAVs. The candidate added no gross row,
  while base and control69 both gross-looped on `cv41748688u`. Raw
  source-relative mean improved `1.084 -> 0.596`, known-text `1.738 -> 1.078`,
  and maximum `12.33 -> 2.83`. On 32 common non-gross rows, source-relative
  mean improved `0.732 -> 0.526` and median `0.600 -> 0.333`, despite W/T/L
  `4/21/7`; known-text mean regressed `0.848 -> 0.899` with W/T/L `3/19/10`.
- Problems: the shared gross-row rescue dominates raw means, and source-relative
  versus known-text evidence conflicts on common rows. This is not a quality
  selection.
- Rework: retain unchanged posthoc audio and do not tune EMA. Continue the
  separate CPU design for disjoint category-balanced JSUT retention training;
  any next GPU lane must be a committed data-method change, not another EMA
  evaluation or hyperparameter point.

## 2026-08-14T01:47:00Z - EXP-169 JSUT retention sources designed

- Agent: `primary-integrator`.
- Task: answer the operator's request for broader data with a distinct training
  construction, not another EMA/adversarial hyperparameter point.
- Dependencies: official JSUT 1.1 archive SHA-256 `081da547`; frozen JSUT24;
  EXP-150's 85 easy curriculum positions; exact EXP-163 method controls.
- Result: define 85 training sources disjoint from JSUT24 using output-blind
  transcript-order bin centers: basic 29 and four constraint categories at 14
  each. Bind them one-to-one to the existing easy positions; hard 85 and total
  170 updates remain fixed.
- Problems: JSUT training and JSUT24 share one corpus speaker, so JSUT24 becomes
  sentence/category-heldout rather than speaker-heldout. Fresh48, Hadou31,
  stress60, and expanded33 remain independent earlier gates.
- Rework: focused tests and real archive check, commit, materialize ignored
  audio, then render control69 retention targets once. Stop before training if
  any generated target gross-loops; do not replace or cherry-pick rows.

## 2026-08-14T01:46:00Z - EXP-170 JSUT retention target render prepared

- Agent: `primary-integrator`.
- Task: make the shortest committed GPU path from frozen JSUT85 sources to
  control69 retention targets without changing the historical EXP-145 runner.
- Dependencies: EXP-169 source manifest; frozen control69 adapter; existing 74
  target inventory and base X-VC checkpoint.
- Result: add a dedicated 85-row renderer that validates all source hashes and
  category counts, caches target tensors, and emits one output per committed
  row plus a training-only pool. No evaluation input is consumed.
- Problems: generated teachers can themselves collapse; this is why training
  admission remains conditional on the existing source-relative ASR and gross
  repetition screen.
- Rework: focused tests, no-CUDA real-input check, commit, then one GPU render.

## 2026-08-14T01:54:00Z - EXP-170 first render stopped before inference

- Agent: `primary-integrator`.
- Task: render the 85 committed JSUT control69 retention targets.
- Dependencies: commit `e29cb86`; X-VC runtime with matching PEFT 0.20.0.
- Result: the first launch used the wrong lightweight Python and exited before
  CUDA load. After restoring the pinned X-VC runtime dependency, the committed
  runner loaded the checkpoint and produced 65 partial outputs before finding
  `LOANWORD128_078.wav` is 2.3 seconds, shorter than the exact 2.4-second model
  window.
- Problems: the source freezer preserved official variable-length JSUT audio,
  while the inherited tensor extractor assumes at least 38,400 samples at
  16 kHz.
- Rework: preserve all 85 selected rows and add deterministic PCM windowing in
  the renderer: right-zero-pad short rows and use the leading 2.4 seconds of
  long rows. Do not replace the failing utterance or alter the selection.

## 2026-08-14T01:58:00Z - EXP-170 JSUT teachers passed gross screen

- Agent: `primary-integrator`.
- Task: rerun all 85 frozen sources after deterministic window normalization,
  then apply the existing source-relative ASR and gross-repetition diagnostic.
- Dependencies: commit `5c0cf72`; exact control69 adapter; frozen source rows.
- Result: 85/85 targets rendered in 88.97 seconds at 2.63 GiB peak CUDA.
  Gross repetition was 0/85; source-relative distance mean 0.132, median 0.071,
  with 5 rows at or above 0.5. The coarse ASR result is not naturalness or a
  quality decision.
- Problems: distance outliers include script-equivalent counters and possible
  ASR/content changes. Dropping only those rows would be output-dependent
  cherry-picking, so all precommitted non-gross rows stay together as one
  method-level pilot.
- Rework: bind EXP-150 hard85 unchanged and replace easy85 position-for-position;
  run one smoke before the full EXP-171 training lane.

## 2026-08-14T02:05:00Z - EXP-171 curriculum admitted for smoke

- Agent: `primary-integrator`.
- Task: bind and validate the one-variable JSUT retention training lane.
- Dependencies: commit `fe89222`; EXP-150 hard rows; EXP-169 sources; EXP-170
  generated targets and screen; frozen external7.
- Result: all 170 source/target hashes validate with composition Common Voice
  40, Hadou 45, and JSUT 85. The no-CUDA runner check admits the exact LoRA69,
  real-reference adversarial, upstream-EMA method.
- Problems: the inherited one-row smoke would cover only a hard row and miss
  the new diverse-work source/target roots.
- Rework: make EXP-171 smoke exercise exactly one unchanged hard row and one new
  easy row; full training remains the same ordered 170 updates.

## 2026-08-14T02:12:00Z - EXP-171 training and external7 completed

- Agent: `primary-integrator`.
- Task: smoke both training roots, run one 170-update JSUT-retention lane, and
  publish the first comparison batch.
- Dependencies: commit `8d2d3cc`; control69 initialization; exact EXP-163
  objective and EMA controls; frozen external7.
- Result: two-row hard/easy smoke was finite at 4.55 GB peak. Full training
  completed 170 updates in 146.49 seconds at 6.07 GB peak; total loss moved
  298.40 to 114.65 and every recorded objective component remained finite.
  External7 published 35 WAVs to the 8878 library and added no gross repetition.
  Candidate source-relative mean exactly tied control69 at 0.3596; known-text
  mean regressed from 0.3993 to 0.4655.
- Problems: external7 is only seven speakers and gives mixed auxiliary content
  evidence. It cannot decide naturalness or justify rejecting a data method
  before the broader frozen gates.
- Rework: continue the unchanged adapter through fresh48, then Hadou31 and
  stress60 only if no candidate-added gross corruption appears.

## 2026-08-14T01:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction and resource audit.
- Result: `CONTINUE`. It judged the disjoint category-balanced data method to be
  a valid one-variable lane, required immediate teacher render and gross screen,
  and warned that JSUT24 is same-speaker evidence rather than the primary gate.
- Rework: verdict adopted. The lane proceeded teacher render -> screen -> one
  retraining run -> external7 -> fresh48 -> Hadou31, with stress/JSUT held behind
  a candidate-added-gross stop.

## 2026-08-14T02:18:00Z - EXP-172/173 froze and rejected EXP-171

- Agent: `primary-integrator`.
- Task: test the unchanged EXP-171 adapter on frozen fresh48 and Hadou31.
- Dependencies: commit `1054bef`; exact EXP-171 EMA adapter; frozen evaluation
  sets; auxiliary ASR/gross screen.
- Result: fresh48 added no gross failure beyond control69. On 46 common
  non-gross rows source-relative W/T/L was 14/24/8, mean 0.341 to 0.320, median
  0.275 to 0.177; known-text mean moved 0.618 to 0.608. Hadou31 then added one
  candidate-only gross failure on `RECITATION324_138`, repeating `三、四` 53
  times. Control69 had no gross Hadou row.
- Problems: raw Hadou mean improved 0.210 to 0.186 despite the catastrophic row;
  aggregate means would falsely retain this checkpoint.
- Rework: reject EXP-171, do not run stress60 or JSUT24, and do not sweep JSUT
  share/category counts. Keep all comparison WAVs on 8878 for later hearing.

## 2026-08-14T02:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence, and idle-resource audit.
- Result: `CONTINUE`. It confirmed that the JSUT-retention lane was a valid
  method test and was correctly rejected at its first candidate-only gross
  Hadou loop. It required the next lane to leave the JSUT-mixture neighborhood
  and either explain that failure or test a still-open method axis.
- Problems: GPU was idle after the completed rejection; aggregate auxiliary
  improvements could tempt an invalid continuation despite the catastrophic
  row.
- Rework: verdict adopted. Drop JSUT share/category sweeps and remaining
  EXP-171 gates. Test one paired gradient-conflict method on the frozen
  EXP-150 hard/easy objectives, with no naturalness or winner claim.

## 2026-08-14T02:25:00Z - EXP-176 paired PCGrad prepared

- Agent: `primary-integrator`.
- Task: test a causal alternative to another data-mixture or hyperparameter
  point after EXP-171's ordinary-row gains and isolated number-loop failure.
- Dependencies: frozen EXP-150 alternating hard85/easy85 manifest; control69;
  standard upstream generative objective; Grok `CONTINUE` with redirect away
  from JSUT-neighbor methods.
- Result: add a deterministic two-task PCGrad mode. Each adjacent hard/easy
  pair is evaluated at one shared parameter state; only negative-dot-product
  components are symmetrically projected, then summed. All 170 examples remain,
  producing 85 explicit pair optimizer steps. Unit tests cover policy isolation,
  role order, conflicting projection, and the unchanged non-conflict path.
- Problems: paired PCGrad necessarily changes optimizer-step geometry and count,
  so this is a method pilot rather than a drop-in one-coordinate comparison.
- Rework: commit before CUDA, smoke one hard/easy pair, then run one full lane.
  Stop at the first candidate-added gross corruption; do not tune projection or
  reopen EXP-150/171 ratios.

## 2026-08-14T02:32:00Z - EXP-176 first smoke result was not observable

- Agent: `primary-integrator`.
- Task: run the committed hard/easy PCGrad smoke before full training.
- Dependencies: commit `77728a1`; exact pinned X-VC runtime and gpu0 lease.
- Result: the process loaded the 5 GB checkpoint, occupied CUDA, and exited,
  but the execution wrapper detached during the quiet load and lost the final
  stdout-only result. No full job was admitted from an unobservable smoke.
- Problems: the inherited smoke path created its work directory but persisted
  no result file, so process exit alone could not distinguish a finite method
  smoke from an external execution-wrapper loss.
- Rework: persist the same smoke payload as `smoke.json`, commit that operational
  fix, and rerun once. Do not change projection, data, loss, or GPU admission.

## 2026-08-14T02:36:00Z - EXP-176 paired smoke stopped before training

- Agent: `primary-integrator`.
- Task: rerun PCGrad smoke with a persistent result and attached PTY.
- Dependencies: commit `31a4065`; same frozen inputs and gpu0 lease.
- Result: after the immutable base load, input validation correctly stopped
  before any optimizer step with `paired PCGrad requires an even row count`.
- Problems: the inherited smoke reducer kept one row for every non-JSUT
  manifest, whereas PCGrad requires one complete adjacent hard/easy pair.
- Rework: make only the PCGrad smoke reducer retain the first two frozen rows,
  add a regression test for their roles, commit, and rerun. Full training stays
  blocked until this two-row smoke persists finite geometry.

## 2026-08-14T02:41:00Z - PCGrad result identity collision caught

- Agent: `primary-integrator`.
- Task: screen the completed paired-PCGrad external7 comparison before opening
  the fresh48 gate.
- Dependencies: commit `3554cae`; finite hard/easy smoke; 85-pair training run.
- Result: training completed all 170 examples in 85 optimizer steps, with 74/85
  pairs conflicting and cosine mean `-0.207`. External7 published 35 WAVs and
  added no gross repetition. During follow-up policy binding, the provisional
  `EXP-174` ID was found to collide with the already-reserved EXP-171 stress
  gate (`EXP-174`, with JSUT at `EXP-175`).
- Problems: the model checkpoint is technically valid, but its result and
  listener index carry an ambiguous experiment identity and cannot be kept as
  the canonical run.
- Rework: assign PCGrad to the next free ID `EXP-176` and frozen gates to
  `EXP-177--180`; quarantine the wrong-ID ignored outputs and deterministically
  rerun from control69. Do not posthoc relabel a committed run receipt.

## 2026-08-14T02:53:00Z - EXP-176--178 PCGrad reproduced and rejected

- Agent: `primary-integrator`.
- Task: rerun the corrected canonical identity, then apply the frozen
  external7 -> fresh48 -> Hadou31 corruption/content gates.
- Dependencies: commit `c9a648e`; finite paired smoke; control69; frozen
  EXP-150 sources/targets and evaluation manifests.
- Result: the canonical adapter SHA-256 and all seven candidate WAV hashes were
  bit-exact with the quarantined wrong-ID run. Training exposed all 170 rows in
  85 pair steps, found 74 conflicts, and published 35 external WAVs. Fresh48
  published 240 more and added no gross row beyond control69's same two known
  failures; on 46 common non-gross rows source mean was `0.341 -> 0.299` with
  W/T/L `13/25/8`, while median was `0.275 -> 0.293`. Hadou31 published 155
  more, then added one candidate-only gross `RECITATION324_138` collapse that
  repeated `三、四`; control69 had zero gross Hadou rows.
- Problems: the other 30 Hadou rows improved mean `0.185 -> 0.171` with W/T/L
  `6/22/2`, so aggregate ASR would falsely retain a checkpoint that still has
  catastrophic content instability. Gradient interference was real but was
  not the sufficient cause of the loop.
- Rework: technically reject EXP-176, keep its 430 canonical WAVs on 8878, and
  stop EXP-179 stress60 and EXP-180 JSUT24. Do not tune projection, pair order,
  weights, or data mix. Wait for the concurrent 02:50 Grok verdict before
  selecting another materially different method.

## 2026-08-14T02:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `SIMPLIFY`. It accepted the committed PCGrad pilot and new audio, but
  challenged the smoke/ID rework, the paired method's coupled step geometry,
  and any move to another training method before screening existing audio and
  binding diverse frozen evaluation conditions.
- Problems: the snapshot arrived before the canonical exact rerun, fresh48,
  and Hadou gate had completed, so its request to stop the ID rerun could no
  longer change that action. It also did not observe that fresh48, Hadou31,
  stress60, JSUT24, and expanded33 were already frozen.
- Rework: verdict adopted where actionable: stop new training-method work,
  screen the existing checkpoint, and do not spend on receipts/review. The
  completed canonical rerun is retained because it proved exact adapter and
  WAV reproducibility; no further identity rerun is admitted.

## 2026-08-14T02:57:00Z - beam-5 gross-loop decision invalidated

- Agent: `primary-integrator`.
- Task: determine whether the repeated-number Hadou stop was an acoustic loop
  or an artifact of the acknowledged weak auxiliary ASR evaluation.
- Dependencies: existing EXP-178 WAVs only; no new model or training job.
- Result: every arm is exactly 2.4 seconds. Beam 5 transcribed the source as a
  physically impossible 428-character number sequence and the PCGrad candidate
  as 223 repeated-number characters. Beam 1 instead produced a plausible
  13-character source and the same short 11-character text for control69 and
  candidate. VAD on/off changed neither result. The prior claim that the audio
  literally repeated `三、四` dozens of times is unsupported.
- Problems: `screen.py` used only beam 5 and promoted its transcript repetition
  directly into the gross corruption gate. It did not expose decoder
  disagreement, so a single ASR search hallucination could reject a method.
- Rework: retract the v2 rejection, keep the checkpoint unselected, and commit
  a v3 screen: greedy primary transcript for content, beam-5 diagnostic, and a
  gross repetition flag only when both deterministic decodes agree. Re-screen
  existing external7/fresh48/Hadou31 before opening any new GPU render.

## 2026-08-14T03:03:00Z - v3 exposed symmetric decoder instability

- Agent: `primary-integrator`.
- Task: re-screen all 430 existing PCGrad WAVs without trusting beam 5 alone.
- Dependencies: commit `3ea4a66`; no new training or render.
- Result: the two-decode gross rule removed the false Hadou stop: candidate
  gross rows became 0/31, source mean `0.202 -> 0.159`, known-text mean
  `0.411 -> 0.400`. The same pass found the inverse failure on fresh48:
  greedy alone transcribed one 2.4-second candidate as 46 repeats of
  `あったなぁ`, while beam 5 returned a short plausible sentence.
- Problems: replacing beam 5 with greedy as the primary transcript merely
  moved which decoder hallucination could dominate aggregate content means.
  Fresh48 raw candidate mean was therefore not decision-grade.
- Rework: keep the two-decode gross consensus, but mark a row
  `decoder_unstable` whenever source or output greedy/beam normalized distance
  exceeds `0.5`. Report stable and all-row summaries separately; compare arms
  only on their common decoder-stable, non-gross set. Commit as v4 and rerun the
  same WAVs before any new render.

## 2026-08-14T03:11:00Z - EXP-176--180 survived the corrected diverse gates

- Agent: `primary-integrator`.
- Task: apply committed v4 to existing audio, then render only the still-closed
  stress60 and balanced JSUT24 gates for the unchanged PCGrad checkpoint.
- Dependencies: commit `17f7a9c`; canonical adapter SHA-256 `f755f6d7`;
  frozen evaluation manifests; gpu0 single lease.
- Result: v4 found no candidate-added consensus gross row on external7,
  fresh48, or Hadou31. Common stable/non-gross results were external5 source
  tie and known improvement, fresh36 source `0.216 -> 0.229` and known
  `0.568 -> 0.566`, Hadou25 source `0.133 -> 0.110` and known `0.369 -> 0.352`.
  EXP-179 then published 300 stress WAVs: common stable44 macro source was
  `0.221 -> 0.214` and known was equal at `0.593`, with strong noise20 gain but
  tempo1.2 and leading-silence regressions. EXP-180 published 120 JSUT WAVs:
  common stable22 source regressed `0.115 -> 0.136` while known improved
  `0.553 -> 0.536`; consensus gross remained zero.
- Problems: decoder instability excluded 5--25% of rows depending on set/arm,
  and remaining evidence is mixed by metric and condition. Auxiliary ASR cannot
  convert this technical survival into naturalness or target-identity quality.
- Rework: retain all 850 canonical comparison WAVs on 8878 as an unselected
  candidate. Do not tune PCGrad. Before training another method, re-screen the
  recent EXP-171 data-method checkpoint under v4 because its identical Hadou
  stop may also have been a beam-search false rejection.

## 2026-08-14T03:19:00Z - EXP-171--175 false rejection retracted

- Agent: `primary-integrator`.
- Task: timebox the existing JSUT-retention checkpoint under the corrected v4
  content/corruption screen, then complete only its already-frozen stress60 and
  JSUT24 comparison surfaces.
- Dependencies: unchanged EXP-171 adapter; frozen external7, fresh48, Hadou31,
  stress60, and JSUT24 manifests; no ratio or category sweep.
- Result: the old Hadou repeated-number claim was the same beam-5 search
  hallucination. Candidate-added consensus gross rows were zero on every set.
  Common stable source-relative means moved external `0.256 -> 0.253`, fresh
  `0.198 -> 0.187`, Hadou `0.133 -> 0.108`, stress `0.218 -> 0.212`, and JSUT
  `0.115 -> 0.134`. Stress showed noise/silence gains and a tempo regression;
  JSUT known-text improved `0.553 -> 0.544`. EXP-174/175 added 420 WAVs, taking
  the unchanged method to 850 comparison WAVs on 8878.
- Problems: JSUT is one speaker and auxiliary ASR remains too unstable to score
  naturalness or identity. The mixed category/condition signs do not select a
  winner.
- Rework: retain EXP-171 as an unheard mixed technical survivor. Stop its data
  mix; do not add another ASR decoder or re-screen all historical experiments.

## 2026-08-14T03:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `REDIRECT`. It accepted the v4 correction and diverse PCGrad audio,
  but warned that further ASR work or historical re-screening would turn the
  decoder into the product. It required one new training hypothesis that
  explains the observed noise/Hadou gain versus tempo/ordinary-content loss.
- Problems: GPU was idle at the audit snapshot and no concrete next method had
  yet been committed.
- Rework: verdict adopted. End screen development at v4, stop historical
  re-screening, retain both completed candidates unselected, and prepare one
  parameter-retention method on the exact EXP-163 baseline.

## 2026-08-14T03:25:00Z - EXP-181 parameter-anchor lane prepared

- Agent: `primary-integrator`.
- Task: retain EXP-163's hard repair/adversarial signal while reducing its
  tempo and ordinary-content forgetting without changing data or step geometry.
- Dependencies: exact EXP-163 curriculum, real-reference adversarial objective,
  control69 initialization, 170 sequential updates, LoRA69 scope, and upstream
  EMA schedule.
- Result: add one coefficient-1 L2-SP term around the immutable control69
  trainable parameters. At EXP-163's unregularized online endpoint the same
  penalty would be about `4.19`, roughly 4% of its final total objective; this
  is a light retention pressure, not a coefficient sweep. Focused runtime tests
  cover policy isolation, smoke coverage, exact penalty value, and gradients.
- Problems: machine content metrics cannot establish the expected naturalness
  effect, and the coefficient remains one bounded method point.
- Rework: commit runner and plan before CUDA, smoke two rows so the second sees
  nonzero displacement, then run one 170-update lane and external7 render.

## 2026-08-14T03:37:00Z - EXP-181 trained and published external7

- Agent: `primary-integrator`.
- Task: smoke then execute the single precommitted coefficient-1 parameter
  anchor on the exact EXP-163 method.
- Dependencies: commit `f43df26`; explicit gpu0 lease; exact control69,
  curriculum, real-reference adversarial objective, and EMA schedule.
- Result: the two-row smoke moved anchor loss `0 -> 0.00412`. The full run
  completed 170 updates in 155.73 seconds at 5.74 GiB peak. Final online anchor
  loss was `1.348`, squared distance `2.697`, versus about `8.386` for the
  unregularized EXP-163 online adapter. All objectives were finite. External7
  published 35 WAVs with zero candidate-added consensus gross rows. Across five
  common stable rows, source mean moved `0.256 -> 0.268`, known-text mean
  `0.371 -> 0.283`, and both W/T/L counts were `2/1/2`.
- Problems: external7 is too small and mixed to establish retention or quality;
  one-arm aggregate means are also distorted by different decoder-unstable rows.
- Rework: keep the adapter unchanged, bind EXP-182--185 follow-up identities,
  and render frozen fresh48 next. Stop on gross corruption or broad common-row
  regression; do not tune anchor coefficient.

## 2026-08-14T03:42:00Z - EXP-182 fresh48 completed

- Agent: `primary-integrator`.
- Task: test the unchanged EXP-181 EMA adapter on 48 disjoint Common Voice
  speakers and sentences.
- Dependencies: commit `9a62118`; frozen EXP-112 manifest; no retraining.
- Result: published 240 more WAVs. Candidate and control69 had the same two
  consensus gross rows, so the candidate added none. Across 36 cross-arm common
  stable, non-gross rows, source-relative mean moved `0.216 -> 0.240` with W/T/L
  `4/23/9`; known-text mean moved `0.568 -> 0.563` with W/T/L `7/22/7`.
- Problems: the anchor did not remove fresh source-relative forgetting, though
  the known-text diagnostic is neutral and most rows tie. This is directional
  weakness rather than an across-metric catastrophic failure.
- Rework: do not tune the coefficient. Run the already-bound Hadou31 gate once
  to test the hypothesized hard-repair retention; reject the method if that
  signal is absent or a candidate-only gross row appears.

## 2026-08-14T03:47:00Z - EXP-183 Hadou31 completed

- Agent: `primary-integrator`.
- Task: determine whether the anchored adapter retained hard-sentence repair
  after its fresh48 source-relative weakness.
- Dependencies: unchanged EXP-181 adapter; frozen Hadou31; no retraining.
- Result: published 155 WAVs with zero gross row. Across 24 common stable rows,
  source-relative mean improved `0.118 -> 0.110` with W/T/L `2/20/2`; known-text
  improved `0.354 -> 0.343` with W/T/L `3/20/1`.
- Problems: the gain is sparse and small, while fresh48 remains directionally
  worse. Content diagnostics still cannot establish naturalness or identity.
- Rework: continue once to the prebound stress60 condition map, which directly
  tests whether the anchor preserved noise, tempo, pitch, and silence behavior.

## 2026-08-14T03:51:00Z - EXP-184 stress60 completed

- Agent: `primary-integrator`.
- Task: test the anchored checkpoint across six speakers crossed with clean,
  noise20, pitch+3, leading silence, and tempo1.2 conditions.
- Dependencies: unchanged EXP-181 adapter; frozen 60-row matrix; no retraining.
- Result: published 300 WAVs with zero gross row. Across 44 common stable rows,
  source mean was `0.215 -> 0.217` with W/T/L `7/27/10`; known-text was
  `0.588 -> 0.596` with W/T/L `5/31/8`. Clean and noise20 improved, while pitch,
  leading silence, and tempo1.2 regressed.
- Problems: the precommitted parameter-retention hypothesis did not generalize
  across conditions. Macro changes are small, but the direction is not a broad
  retention improvement.
- Rework: keep the 730 WAVs unselected and do not tune the coefficient. Wait for
  the active 03:50 Grok audit before deciding whether equalizing the final
  JSUT24 surface is worth one more render or should be deferred.

## 2026-08-14T03:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `CONTINUE`, conditional on stress60 being the final parameter-anchor
  refutation point. It accepted the committed single-variable training and
  sequential diverse renders, but required closing the family if stress showed
  no retention signal. It explicitly rejected coefficient/LR/epoch/scope tuning,
  ASR winner claims, and further anchor variants.
- Problems: the audit snapshot ended before the stress result and therefore
  could not itself observe the pitch, silence, and tempo regressions.
- Rework: verdict adopted. Stress60 completed with only noise/clean gains and
  regressions in the other three conditions, so the anchor hypothesis is closed.
  Defer EXP-185 rather than filling a symmetric matrix for ceremony. Move to a
  distinct data-construction hypothesis.

## 2026-08-14T04:05:00Z - EXP-186 first Common Voice target preflight stopped

- Agent: `primary-integrator`.
- Task: replace only EXP-163's easy85 retention data with balanced exposures
  from 48 frozen training-only Common Voice speakers.
- Dependencies: commits `921fd38`, `14890c1`, and `1b4c509`; frozen EXP-114
  speaker manifest; unchanged EXP-150 hard85; exact control69 adapter.
- Result: bound 48 speakers to 85 slots with exposure counts 37x2 and 11x1.
  Rendered 85 historical leading-window control69 targets in 106.4 seconds at
  2.49 GiB peak. The updated greedy+beam5 teacher screen found one
  candidate-added consensus gross loop.
- Problems: 12/85 source exposures, representing six speakers, decoded to only
  zero through three characters under both decoders. The gross source's full
  MP3 contains its utterance later, but the reused leading 2.4-second window
  decoded only `ん`. This is a source-window construction failure, not evidence
  against multi-speaker retention.
- Rework: stop the entire v1 target set before training; do not delete or replace
  the one failed row. Apply one signal-only speech-active window policy to all
  48 original MP3s, then rerender all 85 targets as v2.

## 2026-08-14T04:16:00Z - EXP-186 speech-active source revision prepared

- Agent: `primary-integrator`.
- Task: correct the source-window role without selecting by ASR or model output.
- Dependencies: the same 48 source MP3 identities and 85 slot schedule.
- Result: implement 2.4-second windows at 100 ms hops, maximizing the count of
  samples above absolute amplitude 0.01, then energy, then earliest start. The
  rule is applied to every source and reads no transcript, ASR, target, or
  evaluation. All 48 speakers and 85 exposures remain unchanged; the prior
  gross row moves from 0.0 to 3.7 seconds with active fraction 0.814.
- Problems: two complete source MP3s are extremely quiet, but X-VC's pinned
  config performs volume normalization before feature extraction. Do not add a
  second waveform normalization or treat raw ASR silence as model-input silence.
- Rework: commit the v2 source construction, rerender all 85 control69 targets,
  and require zero candidate-added consensus gross rows before training.

## 2026-08-14T04:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `SIMPLIFY`. It accepted EXP-186 as a distinct data-construction lane
  and the v1 gross preflight stop, but required ending source construction at
  committed v2. It explicitly rejected window/threshold/normalization tuning,
  quiet-source exceptions, v3, symmetric gate filling, and machine winners.
- Problems: the audit snapshot ended while v2 target work was in flight and
  therefore did not observe the zero-gross result or hard/easy smoke.
- Rework: verdict adopted. V2 completed 85 targets in 98.4 seconds at 2.49 GiB
  peak with zero consensus gross rows. The 170-row curriculum validates as
  Common Voice 125 / Hadou 45; its two-row hard/easy smoke was finite at 4.32
  GiB peak. Start the one 170-update lane immediately with no v3 preprocessing.

## 2026-08-14T04:28:00Z - EXP-186 training and external7 completed

- Agent: `primary-integrator`.
- Task: run the one admitted speech-active 48-speaker retention lane and publish
  its first independent comparison audio.
- Dependencies: commit `5158e1a`; v2 teacher gross 0/85; finite hard/easy smoke;
  exact EXP-163 objective, scope, optimizer, and upstream EMA controls.
- Result: completed 170 updates in 125.9 seconds at 5.74 GiB peak. Loss moved
  `298.40 -> 140.30`. Published 35 external7 WAVs to port 8878 with zero gross
  row. Across five cross-arm common stable rows, control69 to EXP-186 moves
  source distance `0.256 -> 0.206` and known-text `0.371 -> 0.254`; both W/T/L
  are `3/1/1`.
- Problems: external7 has only seven speakers and cannot establish naturalness,
  identity, or a winner. The method changes both speaker composition and source
  window policy relative to EXP-163, so it is evidence for the combined data
  construction, not speaker count alone.
- Rework: bind EXP-187--190 identities and render the unchanged adapter on
  frozen fresh48 next. Stop on candidate-added gross corruption or broad common
  stable regression; do not tune the source policy or training method.

## 2026-08-14T04:32:00Z - EXP-187 fresh48 completed

- Agent: `primary-integrator`.
- Task: test the unchanged EXP-186 adapter on 48 disjoint speakers and texts.
- Dependencies: commit `6e6acfa`; frozen EXP-112 inputs; no retraining.
- Result: published 240 WAVs in 88.5 seconds. Candidate and control69 share the
  same two gross rows, so the candidate adds none. Across 35 common stable rows,
  source moves `0.210 -> 0.203` with W/T/L `6/24/5`; known text moves
  `0.560 -> 0.550` with `8/23/4`.
- Problems: most rows tie and the gain is small; this is technical survival, not
  perceptual evidence.
- Rework: continue the unchanged checkpoint to the prebound Hadou31 gate.

## 2026-08-14T04:36:00Z - EXP-188 Hadou31 completed

- Agent: `primary-integrator`.
- Task: test the same adapter on a different single-speaker Japanese corpus.
- Dependencies: frozen 31-row Hadou set; no retraining.
- Result: published 155 WAVs with zero gross row. Across 24 common stable rows,
  source moves `0.119 -> 0.0777` with W/T/L `5/19/0`; known text moves
  `0.351 -> 0.323` with `5/18/1`.
- Problems: one speaker cannot establish speaker generalization, but it is a
  useful corpus/content shift after fresh48.
- Rework: render stress60 to test named route constraints directly.

## 2026-08-14T04:39:00Z - EXP-189 stress60 completed

- Agent: `primary-integrator`.
- Task: test six speakers crossed with clean, noise20, pitch+3, leading silence,
  and tempo1.2.
- Dependencies: unchanged EXP-186 adapter; frozen 60-row matrix.
- Result: published 300 WAVs with zero gross row. Across 44 common stable rows,
  source is `0.216 -> 0.212` and known text `0.591 -> 0.601`. Noise and leading
  silence improve, pitch is mixed, and tempo has W/T/L `0/4/4` on both metrics.
- Problems: multi-speaker retention did not repair the tempo residual shared by
  earlier methods.
- Rework: run the already-bound JSUT24 category gate once, then close the family.

## 2026-08-14T04:41:00Z - EXP-190 JSUT24 completed

- Agent: `primary-integrator`.
- Task: test untouched basic, counter, loanword, onomatopoeia, and travel rows.
- Dependencies: unchanged EXP-186 adapter; frozen category-balanced JSUT24.
- Result: published 120 WAVs with zero gross row. Across 22 common stable rows,
  source moves `0.115 -> 0.131` with W/T/L `2/16/4`; known text moves
  `0.553 -> 0.543` with `4/17/1`. The complete family now has 850 WAVs.
- Problems: source-relative and known-text evidence conflict and category
  directions vary. Neither diagnostic can decide naturalness or identity.
- Rework: preserve EXP-186 as an unheard mixed survivor and close its training
  family. A next method may target condition retention, but must not repeat the
  closed EXP-043 source-only or EXP-044 aligned-target augmentation methods.

## 2026-08-14T04:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `CONTINUE`. It accepted closing EXP-186--190 after 850 diverse WAVs
  and moving to one conditioned-retention pilot from commit `376348f`. It
  required a coarse corruption/content screen, port-8878 publication, and a
  stop-and-replan after the pilot rather than reserving a full render cascade.
- Problems: the audit had not read the EXP-191 plan and therefore flagged the
  risk that it could be a disguised repeat of EXP-043/044 or a condition sweep.
- Rework: verdict adopted. EXP-191 keeps one five-way balanced curriculum as a
  single data-policy change, generates each target from the already-conditioned
  source, and otherwise holds EXP-186 fixed. Do not add another plan, method,
  coefficient, or evaluation family before this pilot produces audio.

## 2026-08-14T04:54:00Z - EXP-191 conditioned teachers completed

- Agent: `primary-integrator`.
- Task: render the frozen control69 retention target for each of 85 conditioned
  Common Voice exposures spanning 48 training-only speakers.
- Dependencies: commit `376348f`; 17 rows each of clean, noise15, tempo1.1,
  pitch+2 semitones, and leading-silence150; no ASR/output selection.
- Result: rendered 85 sources and 85 targets in 91.2 seconds at 2.49 GiB peak.
- Problems: target existence alone does not admit training and says nothing
  about naturalness, identity, or quality.
- Rework: run only the frozen consensus content/corruption screen. If the
  candidate adds no gross row, bind the 170-row curriculum and start the single
  smoke-to-full training lane.

## 2026-08-14T05:00:00Z - EXP-191 training and external7 completed

- Agent: `primary-integrator`.
- Task: run the single condition-balanced retention pilot and publish its first
  independent comparison audio.
- Dependencies: commit `376348f`; teacher consensus gross 0/85; frozen 170-row
  hard85/easy85 curriculum; finite two-row smoke.
- Result: completed 170 updates in 141.1 seconds at 5.74 GiB peak. Total loss
  moved `298.40 -> 128.46`. Published 35 external7 WAVs to port 8878 with zero
  gross row. Across five cross-arm common stable rows, control69 to EXP-191
  moves source distance `0.256 -> 0.191` and known-text distance
  `0.371 -> 0.254`; both W/T/L are `3/1/1`.
- Problems: external7 is too small to establish generalization, naturalness,
  identity, or a winner. ASR remains only a content/corruption diagnostic.
- Rework: bind one frozen fresh48 identity and render the unchanged checkpoint.
  Stop before stress60 on candidate-added gross corruption or broad common
  stable regression.

## 2026-08-14T05:06:00Z - EXP-192 fresh48 completed

- Agent: `primary-integrator`.
- Task: test the unchanged EXP-191 adapter on 48 disjoint speakers and texts.
- Dependencies: commit `794cd06`; byte-identical re-materialization of the
  frozen EXP-112 manifest and its 48 revision-pinned source MP3s.
- Result: published 240 WAVs in 103.6 seconds. Candidate and control69 share the
  same two gross rows, so the candidate adds none. Across 37 common stable rows,
  source distance is `1.074 -> 1.076` with W/T/L `5/24/8`; known-text distance
  is `0.811 -> 0.807` with `8/23/6`.
- Problems: the raw means are dominated by two shared gross rows. The stable
  signal is mixed and cannot establish perceptual quality.
- Rework: admit the unchanged checkpoint to the one final stress60 gate because
  cross-severity condition retention is the experiment question. Do not add
  Hadou, JSUT, a condition sweep, or retraining afterward.

## 2026-08-14T05:12:00Z - EXP-193 stress60 completed

- Agent: `primary-integrator`.
- Task: run the final cross-severity condition gate for the unchanged EXP-191
  checkpoint.
- Dependencies: commit `2ad0f0b`; frozen 60-row clean/noise20/pitch+3/
  silence300/tempo1.2 matrix; no retraining.
- Result: published 300 WAVs in 92.2 seconds with zero gross row. Across 43
  common stable rows, source distance moved `0.187 -> 0.203` with W/T/L
  `5/28/10`; known-text moved `0.584 -> 0.587` with `5/33/5`. Noise20 improved
  on both diagnostics.
- Problems: clean and pitch regress on source-relative content, and tempo1.2
  remains worse with `0/6/1` on both diagnostics. The motivating residual was
  not repaired.
- Rework: close conditioned-retention after 575 new WAVs. Preserve it as an
  unheard mixed comparison, but do not tune ratios, severities, schedule, or
  add Hadou/JSUT renders. Select the next retraining lane from a different
  mechanism axis.

## 2026-08-14T05:18:00Z - EXP-194 source36 placement prepared

- Agent: `primary-integrator`.
- Task: select and implement one retraining mechanism outside the closed data-
  condition family.
- Dependencies: EXP-186's frozen hard85/easy85 curriculum and surviving
  adversarial/EMA method; the local function-placement research map; control69
  source36 is a contained adapter path.
- Result: selected one variable: freeze the non-source control69 adapter tensors
  and update only 36 source-side attention/`ff_x` LoRA modules. Data, targets,
  initialization, objective, optimizer, LR, clip, updates, zero condition, and
  EMA stay at EXP-186. Added an exact contained-scope setter and distinct
  EXP-194 identity.
- Problems: EXP-052 previously rejected source36 under a different fresh-base,
  1,044-standard-update method. EXP-194 is evidence only about placement inside
  the later selective-retention/adversarial/EMA method, not a generic source36
  retry or proof of causality.
- Rework: commit after focused tests, then run one hard/easy smoke and one
  170-update external7 lane. Stop on candidate-added gross corruption or broad
  common-stable regression; do not open adjacent scope points.

## 2026-08-14T05:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `REDIRECT`. It accepted closing EXP-191--193 and accepted source36 as
  one distinct placement variable, but rejected returning to an external7-first
  sequential evaluation gate after the motivating residual appeared on stress.
- Problems: the snapshot predated commit `7d6523a` and did not see EXP-192/193
  files on its recent-WAV listing, but its evaluation-contract criticism does
  not depend on either gap.
- Rework: verdict adopted. Prebind external7 and stress60 before CUDA, publish
  both from the unchanged checkpoint, and close the family afterward. Do not
  reserve fresh48/Hadou/JSUT or adjacent source/condition/target scope points.

## 2026-08-14T05:34:00Z - EXP-194--195 source36 placement completed

- Agent: `primary-integrator`.
- Task: train one source-path-only adapter and publish both prebound evaluation
  surfaces.
- Dependencies: commits `7d6523a` and `4136d11`; exact EXP-186 curriculum and
  objective; Grok's fixed external7+stress60 evaluation redirect.
- Result: smoke exposed 442,368 mutable parameters and was finite. Training
  completed 170 updates in 140.4 seconds at 5.73 GiB peak, with total loss
  `298.40 -> 136.76`. Published 35 external7 and 300 stress60 WAVs with zero
  candidate-added gross row.
- Problems: external7 is mixed. Across 45 stress common stable rows, source
  distance is `0.212 -> 0.214` with W/T/L `7/27/11`, and known text is
  `0.591 -> 0.592` with `7/31/7`. Noise20 improves, but tempo1.2 is `0/5/2`
  on both diagnostics and silence300 regresses.
- Rework: close source36 after the fixed 335 WAVs. Do not try adjacent placement
  scopes. Select a different mechanism that directly expresses the product's
  source-timing preservation rule rather than another data or scope variant.

## 2026-08-14T05:37:00Z - EXP-196--197 source timing objective prepared

- Agent: `primary-integrator`.
- Task: turn the open source-timing product rule into one bounded retraining
  mechanism and freeze its evaluation contract before using CUDA.
- Dependencies: closed EXP-186 data family and EXP-194 placement family; the
  recurring stress60 tempo/silence residual; no human hearing availability.
- Result: selected one fixed weight-10 L1 penalty between normalized 20 ms/10 ms
  source and converted activity envelopes. EXP-186 data, LoRA69 scope,
  adversarial/EMA method, updates, LR, optimizer, clip, and zero condition remain
  fixed. External7 and stress60 are both prebound before training.
- Problems: this waveform envelope is a coarse timing prior, not a phonetic,
  naturalness, identity, or quality objective. It may trade timbre detail for
  activity alignment, and machine screens cannot judge that trade.
- Rework: commit and run one finite smoke plus one 170-update lane, then publish
  both fixed evaluation surfaces and close. Do not sweep loss weight/window/hop,
  add evaluation sets after seeing results, or return to the obsolete 8.17-second
  tongue-twister target.

## 2026-08-14T05:48:00Z - EXP-196--197 source timing objective completed

- Agent: `primary-integrator`.
- Task: train the fixed source activity-envelope objective and publish both
  prebound evaluation surfaces.
- Dependencies: commit `421b618`; 209 focused source-diversity tests and
  `make control-check` green; exact EXP-186 curriculum and controls.
- Result: smoke was finite with 835,584 trainable parameters. Full training
  completed 170 updates in 129.4 seconds at 6,163,570,688 peak allocated bytes;
  total loss moved `300.93 -> 142.58`, while activity-envelope distance moved
  `0.253 -> 0.293`. Published 35 external7 and 300 stress60 WAVs with no
  candidate-added consensus gross row. External7 common-stable rows improved
  on both auxiliary diagnostics (`3/1/1`), but 45 stress common-stable rows
  moved source `0.223 -> 0.233` (`7/25/13`) and known text `0.599 -> 0.612`
  (`6/30/9`). Tempo1.2 was `0/4/4` on both; only noise20 clearly improved.
- Problems: the explicit timing prior did not repair the motivating tempo
  residual and the broader result contradicts the small external7 signal.
  Auxiliary ASR cannot assess naturalness, identity, or audible timing quality.
- Rework: close source-envelope weight/window/hop and adjacent timing-loss
  points after 335 WAVs. Keep the audio unselected on 8878 and choose the next
  lane from a different mechanism; do not optimize the old tongue twister.

## 2026-08-14T05:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `REDIRECT`. It accepted the two committed source36/envelope pilots,
  their 670 WAVs, and immediate family closures, but rejected another
  EXP-163/186 retention/timing/LoRA-neighbor point evaluated only on external7
  plus stress60.
- Problems: its recent-WAV listing stopped at EXP-194 despite the committed
  EXP-196 result, and it could not observe operator localStorage. Neither gap
  changes the direction verdict.
- Rework: verdict adopted. Freeze external7/fresh48/Hadou31/stress60/JSUT24
  before the next CUDA run. Move to one different mechanism that can explain
  why converter-only changes fail, keep the plan to one page, and do not let
  evaluation documentation become a GPU-idle project.

## 2026-08-14T05:54:00Z - EXP-198--202 acoustic representation prepared

- Agent: `primary-integrator`.
- Task: select one non-neighbor X-VC retraining mechanism under the five-surface
  audit contract.
- Dependencies: recurring converter-only tempo/silence residual; EXP-196's
  activity loss rose `0.253 -> 0.293`; local X-VC module inspection.
- Result: selected the source `acoustic_encoder` as the sole mutable target
  after merging control69. It has 21,521,536 parameters across 119 tensors;
  converter, quantizer, prenet, decoders, predictors, speaker path, and all
  other modules remain frozen. EXP-163's CV/Hadou/JVS data, targets,
  adversarial objective, 170 updates, LR, optimizer, clip, zero condition, and
  upstream EMA remain fixed. All five evaluation identities are prebound.
- Problems: representation adaptation could destabilize the frozen quantizer
  interface or consume more memory. A smoke can establish finiteness/resource
  use only; it cannot predict audible quality.
- Rework: implement exact save/reload and focused tests, commit, then run one
  smoke and one full lane. Stop this target family afterward; no encoder-depth,
  LR, or adjacent-module sweep.

## 2026-08-14T06:19:00Z - EXP-198--202 acoustic representation completed

- Agent: `primary-integrator`.
- Task: train the source acoustic encoder once, then publish the unchanged
  checkpoint on all five evaluation surfaces fixed before CUDA.
- Dependencies: commits `147e15a` and `a9a86f4`; 212 focused tests plus 30
  post-fix role-coverage tests; `make control-check`; EXP-163's frozen
  hard85/easy85 curriculum and training method.
- Result: the hard/easy smoke was finite with 21,521,536 trainable parameters.
  Full training completed 170 updates in 132.0 seconds at 6,206,943,744 peak
  allocated bytes, and total loss moved `298.554 -> 117.298`. The exact
  119-tensor checkpoint SHA-256 is
  `642a8f85450d08a078001da68ff6661fbbba7c31889315540ac9cb95f85b1db2`.
  Published 35 external7, 240 fresh48, 155 Hadou31, 300 stress60, and 120
  JSUT24 WAVs to port 8878: 850 total. No surface adds a consensus gross row.
  Cross-arm common-stable source distance moved external7 `0.256 -> 0.238`
  (`1/3/1`), fresh48 `0.205 -> 0.323` (`3/14/14`), Hadou31
  `0.149 -> 0.114` (`8/17/1`), stress60 `0.206 -> 0.237`
  (`11/18/14`), and JSUT24 `0.115 -> 0.145` (`3/14/5`). Within stress60,
  tempo1.2 regressed `0.156 -> 0.268` (`1/3/3`).
- Problems: Hadou improves, but the disjoint-speaker, tempo, and balanced JSUT
  surfaces contradict a general improvement. Auxiliary ASR cannot assess
  naturalness, target identity, timing quality, or an audible winner.
- Rework: close the acoustic-encoder target family. Do not try adjacent depth,
  learning rate, freeze scope, or modules. Keep all audio unheard and
  unselected for later operator listening, and select a genuinely different
  system/data mechanism only after the active Grok direction audit.

## 2026-08-14T06:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `CONTINUE`. It accepted the one-variable acoustic-encoder target and
  the five-surface contract, rejected encoder/LR/module neighbors, and required
  finishing fresh48, Hadou31, stress60, and JSUT24 before selecting another
  method.
- Problems: its snapshot saw only the 06:09 external7 WAVs and not the four
  surfaces that completed before the audit ended. It therefore described the
  fixed evaluation cascade as pending even though all 850 WAVs and v4 screens
  were already complete.
- Rework: verdict adopted and already satisfied. Close EXP-198--202 using the
  complete five-surface result. Do not continue the encoder family. Commit the
  closure before admitting one genuinely different system/data mechanism.

## 2026-08-14T06:31:00Z - EXP-203--207 unpaired human factorization prepared

- Agent: `primary-integrator`.
- Task: select and implement one data/objective architecture outside the
  closed converter-retention, timing-loss, and acoustic-encoder families.
- Dependencies: the complete EXP-198--202 five-surface rejection; existing
  424-row human Hadou/Amitaro manifest with 334 train IDs; operator-authorized
  Amitaro target archive; no human hearing availability.
- Result: selected 170 Hadou source IDs spread across all 334 train rows and
  paired each with a unique Amitaro target 167 train positions away. The
  materializer produced 170 unique source and 170 unique target active windows,
  zero same-text pair, no stretch, no DTW, and no heldout access; curriculum
  SHA-256 is
  `f191882641bbff714c4e03a247e38fdca959ca4f7bb7f6a2fd658b0f67c0d727`.
  The new objective supervises source Whisper content separately from the
  unrelated target speaker embedding and real-wave adversarial/feature target.
  Control69 LoRA69, 170 updates, LR, optimizer, clip, zero frame condition, and
  EMA stay fixed. External7/fresh48/Hadou31/stress60/JSUT24 are prebound.
  Focused implementation tests passed `92/92`; the real-input validation passed
  all 170 rows without CUDA.
- Problems: factorizing aligned waveform loss may remove an important acoustic
  anchor and permit unintelligible but target-like output. The smoke can detect
  nonfinite execution only; machine ASR cannot judge naturalness or identity.
- Rework: commit this exact slice, run one two-row smoke and one 170-update GPU
  pilot, then render all five fixed surfaces and close. Do not tune objective
  weights, pairing rotation, windows, scope, LR, horizon, or EMA.

## 2026-08-14T06:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evidence-cost, and idle-resource audit.
- Result: `CONTINUE`. It accepted the fixed five-surface evaluation contract,
  the method-level factorization hypothesis, one-point training run, and new
  listener audio; it rejected tuning neighbors and required all five screens
  before selecting the next mechanism.
- Problems: the audit snapshot only exposed the first EXP-203 listener files,
  so it could not see EXP-204--207 already rendering or complete. It cannot
  observe operator localStorage, which remains unknown by design.
- Rework: verdict adopted and satisfied. All 850 WAVs and five v4 screens are
  complete; the new gross failure triggers the declared stop. Commit the
  closure before admitting one different source-content-preservation method.

## 2026-08-14T06:58:00Z - EXP-203--207 unpaired human factorization completed

- Agent: `primary-integrator`.
- Task: train the one-point alignment-free human factorization method and
  publish its unchanged checkpoint on all five prebound evaluation surfaces.
- Dependencies: commits `6a0f208` and `150ccde`; 219 focused tests;
  `make control-check`; curriculum SHA-256
  `f191882641bbff714c4e03a247e38fdca959ca4f7bb7f6a2fd658b0f67c0d727`.
- Result: the two-row smoke was finite with 835,584 trainable parameters and
  4,623,464,960 peak allocated bytes. The full run completed 170 updates and
  saved an EMA adapter with SHA-256
  `432917a9c4b3bda307daf81c469655cf4247e5001be7890d1eb30c647a37a8b5`.
  Published 35 external7, 240 fresh48, 155 Hadou31, 300 stress60, and 120
  JSUT24 WAVs to port 8878: 850 total. Cross-arm common-stable source distance
  moved external7 `0.256 -> 0.287` (`1/3/1`), fresh48 `0.192 -> 0.188`
  (`13/15/7`), Hadou31 `0.133 -> 0.100` (`10/13/2`), stress60
  `0.197 -> 0.218` (`13/14/16`), and JSUT24 `0.121 -> 0.141`
  (`6/11/4`). Pitch+3 and silence300 improved, but tempo1.2 regressed
  `0.262 -> 0.465` (`0/4/4`).
- Problems: the candidate repaired control69's gross loop on `cv30615849f`
  but added a different consensus gross failure on `cv39028774f`, producing a
  223-character repeated `ん` run. After the checkpoint and external audio
  were safely written, the terminal receipt step failed because standalone
  curricula lacked `source_work/result.json`; `150ccde` repaired that receipt
  path. The weights were not rerun just to recreate a receipt.
- Rework: the predeclared candidate-added-corruption stop closes this exact
  objective despite useful Hadou and category-specific signal. Do not sweep
  weight, pairing, window, scope, LR, horizon, or EMA neighbors. Preserve the
  unheard audio as unselected diagnosis and choose the next method from a
  different mechanism that explicitly preserves source content under tempo.

## 2026-08-14T07:07:00Z - EXP-208--212 final-waveform content cycle prepared

- Agent: `primary-integrator`.
- Task: choose one method-level X-VC successor that explains EXP-203's internal
  semantic improvement, final-waveform repetition, and tempo regression.
- Dependencies: EXP-203--207's complete five-surface stop; X-VC's frozen
  WhisperVQ encoder and exact differentiable torch log-mel definition; the
  unchanged 170-row unpaired curriculum.
- Result: selected one output-level linguistic cycle. Only the content loss
  site changes: replace weight-1000 internal semantic-decoder MSE with
  weight-1000 frame-aligned MSE between frozen source Whisper hidden states and
  the same frozen encoder applied differentiably to the converted WAV. Target
  speaker loss, real-wave adversarial/feature objective, data, pairing,
  control69 LoRA69, 170 updates, LR, optimizer, clip, zero condition, EMA, and
  all five evaluation identities stay fixed. All 225 focused source-diversity
  tests and `make control-check` passed; exact CPU admission confirmed 170
  training rows and seven external evaluation rows without CUDA.
- Problems: X-VC's convenience extractor intentionally detaches through numpy;
  the runner must reproduce its 400-point STFT, 160-hop, 128-bin mel frontend
  in torch and demonstrate a real waveform gradient. The extra frozen-encoder
  backward may increase memory or runtime.
- Rework: pass focused tests plus one exact two-row backward smoke and commit
  before the full lane. Stop on frontend mismatch, no waveform gradient,
  nonfinite execution, or OOM. Do not sweep cycle weight, feature layer,
  alignment, data, pairing, scope, LR, horizon, or EMA.

## 2026-08-14T07:16:00Z - EXP-208 output-cycle runtime admission passed

- Agent: `primary-integrator`.
- Task: prove the torch Whisper frontend matches X-VC's detached helper and
  that final-WAV content loss reaches the LoRA parameters on real data.
- Dependencies: commit `9e23e62`; exact EXP-203 curriculum; pinned X-VC
  checkpoint and frozen GLM-4-Voice tokenizer.
- Result: the two-row backward smoke completed with 835,584 trainable
  parameters and 5,366,944,768 peak allocated bytes. Differentiable versus
  detached hidden states differed by maximum `0.00026691` under the `0.001`
  stop threshold and mean `0.00000336`. Content-cycle MSE was finite at
  `0.06174` and `0.13544`; both generator/discriminator updates completed.
- Problems: PyTorch warned that reflection-padding backward has no strict
  deterministic CUDA implementation. The configured warn-only path completed;
  no nonfinite value or OOM occurred. The first launcher left an empty `v1`
  smoke directory while its delayed exit was being polled; the successful,
  unchanged run is recorded under `v2`.
- Rework: admit exactly one 170-update run. Do not tune weight, feature layer,
  frontend, pairing, data, scope, LR, horizon, or EMA from the smoke values.

## 2026-08-14T07:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, rigor-cost, and GPU-idle audit.
- Result: `CONTINUE`. It accepted the five prebound surfaces, the single change
  from internal semantic MSE to final-WAV content cycling, and commits
  `9e23e62` / `712d55f`; it instructed immediate one-lane training and rejected
  further admission ceremony or any weight/frontend/data neighbor before the
  complete result.
- Problems: its 07:20 snapshot sampled the GPU during model loading at 0% and
  could not see the just-launched process or later EXP-208 audio. Operator
  localStorage also remains unobservable by design.
- Rework: verdict adopted. The exact committed lane subsequently completed 170
  updates and all five surfaces. No second training lane or promote work was
  started while it ran.

## 2026-08-14T07:32:00Z - EXP-208--212 output-cycle bundle completed

- Agent: `primary-integrator`.
- Task: train the final-WAV content cycle once and publish/screen its unchanged
  EMA checkpoint on all five prebound evaluation surfaces.
- Dependencies: commits `9e23e62` and `712d55f`; 225 focused tests;
  `make control-check`; successful two-row real-model backward admission.
- Result: training completed 170 updates in 152.17 seconds at 5,875,919,872
  peak allocated bytes. The EMA adapter SHA-256 is
  `c8b1e28ac138bf0d63d86ad2745a584eb4f2c71e3f4beea046d9413334f57092`.
  Published 35 external7, 240 fresh48, 155 Hadou31, 300 stress60, and 120
  JSUT24 WAVs to 8878: 850 total. Common-stable source distance moved
  external7 `0.256 -> 0.272` (`0/4/1`), fresh48 `0.202 -> 0.219`
  (`8/19/9`), Hadou31 `0.149 -> 0.124` (`9/15/2`), stress60
  `0.215 -> 0.180` (`11/26/6`), and JSUT24 `0.115 -> 0.114`
  (`6/13/3`). Clean/noise/silence improved, while tempo1.2 remained worse at
  `0.262 -> 0.267` (`1/5/2`).
- Problems: fresh48 added a consensus gross failure on low-information
  `cv44571685f`, whose source transcript was empty. The candidate repeated a
  short phrase through 334 normalized characters while control69 was
  non-gross. Final-waveform cycling therefore did not supply a collapse safety
  mechanism. Auxiliary ASR cannot judge naturalness, identity, or quality.
- Rework: the predeclared corruption stop rejects and closes the exact
  pointwise output-cycle method. Do not tune weight, frontend, data, pairing,
  scope, LR, horizon, or EMA. Preserve the broad stress/Hadou signal as method
  evidence; the next lane must be a distinct data/generalization or
  anti-collapse architecture, not another coefficient point.

## 2026-08-14T07:44:00Z - EXP-213--217 cross-corpus data method prepared

- Agent: `primary-integrator`.
- Task: act on the user's broader-data correction and test whether EXP-208's
  unknown-speaker collapse comes from Hadou-only source training rather than
  opening another loss-weight or frontend point.
- Dependencies: EXP-208--212's complete five-surface stop; the correction that
  the local tongue-twister is not actual ChatGPT input; frozen training-only
  Common Voice48, JSUT85 excluding JSUT24, JVS3, Hadou170, and the unchanged
  authorized Amitaro target windows.
- Result: materialized one fixed 170-row source curriculum containing all CV48,
  all disjoint JSUT85, all JVS3, and 34 Hadou rows spread over the predecessor.
  Rows are deterministically mixed by `sha256(domain:teacher_id)`; the exact
  ordered 170-target Amitaro multiset is unchanged. Curriculum SHA-256 is
  `44d2ba9c03d44437711c7b7d359f519672dca32696ba73b3fcd178b07024b931`.
  Focused tests passed `97/97`; exact CPU admission confirmed 170 training rows
  and seven external rows. External7/fresh48/Hadou31/stress60/JSUT24 remain the
  fixed comparison surfaces.
- Problems: changing corpus distribution and sequential order is a data-method
  point, not an isolated loss change. It cannot prove which corpus is causal,
  and the one-pass schedule may still forget tempo or collapse on
  low-information speech. Auxiliary ASR still cannot judge voice quality.
- Rework: commit this one fixed composition, run a two-row real backward smoke,
  then one 170-update GPU lane and all five screens. Do not sweep corpus ratios,
  counts, order, target pairing, weight, frontend, scope, LR, horizon, or EMA.

## 2026-08-14T07:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, evaluation-cost, and GPU-idle audit.
- Result: `CONTINUE`. It accepted the correction that the tongue-twister is not
  ChatGPT input, the five fixed broad surfaces, and the single fixed
  CV48/JSUT85/JVS3/Hadou34 data hypothesis. It rejected corpus-ratio/count/order
  sweeps, old output-cycle neighbors, review ceremony, and human-wait GPU idle.
- Problems: the snapshot was assembled from state just before the two-row smoke
  and 170-update launch, so it reported GPU 0% and instructed the already
  executing action. It could not observe operator localStorage by design.
- Rework: verdict adopted. The smoke, 170 updates, five renders, and five coarse
  screens completed from commit `2830fc3`; no extra admission work or parallel
  training lane was inserted.

## 2026-08-14T08:00:00Z - EXP-213--217 cross-corpus bundle completed

- Agent: `primary-integrator`.
- Task: train the fixed cross-corpus source method once and publish/screen its
  unchanged EMA checkpoint on all five prebound evaluation surfaces.
- Dependencies: commit `2830fc3`; 231 focused tests; `make control-check`;
  curriculum SHA-256
  `44d2ba9c03d44437711c7b7d359f519672dca32696ba73b3fcd178b07024b931`.
- Result: the real two-row smoke was finite and matched the detached Whisper
  path within `0.00014424`. Training completed 170 updates in 152.44 seconds at
  5,875,919,872 peak allocated bytes. The EMA adapter SHA-256 is
  `006e369c270fc00eab4f15115935332c90bb138e231799547e97685f6b9597f5`.
  Published 850 WAVs to 8878. On exact cross-arm common-stable rows, source
  distance moved external7 `0.256 -> 0.254`, fresh48 `0.208 -> 0.214`, Hadou31
  `0.133 -> 0.091`, stress60 `0.221 -> 0.185`, and JSUT24 `0.115 -> 0.134`.
  Noise20 improved `0.271 -> 0.163`; tempo1.2 regressed `0.262 -> 0.280`.
- Problems: ordinary JSUT basic rows regressed and pointwise cycle content still
  fails to retain tempo. Auxiliary ASR cannot establish naturalness or target
  identity. Fresh48 retains the two gross loops already present in control69,
  but adds none; EXP-208's new low-information loop did not recur.
- Rework: retain the checkpoint as an unheard technical survivor, not a winner.
  Close corpus ratio/count/schedule neighbors. A next independent lane may test
  an explicit anti-collapse content architecture while holding this exact data,
  targets, updates, and evaluation contract fixed.

## 2026-08-14T08:12:00Z - EXP-218--222 contrastive output cycle prepared

- Agent: `primary-integrator`.
- Task: select one anti-collapse X-VC objective that acts on EXP-213's remaining
  content failure without reopening corpus, target, scope, LR, or horizon axes.
- Dependencies: EXP-213--217's no-added-gross technical survival; the exact
  cross-corpus170 curriculum; frozen final-WAV Whisper frontend; no operator
  hearing availability.
- Result: replaced only pointwise final-WAV/source hidden-state MSE with a
  two-way framewise cosine InfoNCE classification at temperature 0.1. Each row's
  own source is positive and the next row in the frozen mixed schedule is the
  sole negative. The exact source/target rows, speaker/adversarial objectives,
  control69 LoRA69 initialization, 170 updates, LR, optimizer, clip, zero
  condition, EMA, and five evaluation surfaces remain fixed. Focused tests
  passed `97/97`; exact CPU admission passed all 170 rows and external7.
- Problems: one deterministic negative is only a collapse probe, not complete
  contrastive learning, and temperature 0.1 is a fixed method choice rather
  than an optimized value. Double source extraction may increase admission
  time or memory. Pointwise frame comparison may still miss tempo behavior.
- Rework: commit this exact point, run one two-row real backward smoke, then one
  170-update lane and all five screens. Stop on shape/gradient/nonfinite/OOM or
  candidate-added corruption. Do not sweep temperature, negative count/mining,
  weight, data, pairing, frontend, scope, LR, horizon, or EMA.

## 2026-08-14T08:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, method-value, and GPU-idle audit.
- Result: `CONTINUE`. It accepted the fixed five broad surfaces and the one
  source-versus-negative objective point, while explicitly warning that
  framewise InfoNCE may not solve tempo. It rejected temperature/negative/mining
  sweeps and required a different timing/continuation hypothesis if the five
  screens fail.
- Problems: its snapshot again sampled a model-load boundary at GPU 0% and did
  not see the already completed smoke/training or newer listener files. Operator
  localStorage remains unobservable by design.
- Rework: verdict adopted. Complete the already-running five surfaces before
  replanning; do not interpret the stale GPU sample as a reason to duplicate
  the lane.

## 2026-08-14T08:29:00Z - EXP-218--222 contrastive bundle completed

- Agent: `primary-integrator`.
- Task: train the fixed source-versus-negative objective once and publish/screen
  the unchanged checkpoint on all five surfaces.
- Dependencies: commits `6a01fbc` and `6e61a9f`; 234 focused tests;
  `make control-check`; exact EXP-213 curriculum and target multiset.
- Result: smoke v2 proved positive cosine above negative on both rows and a
  finite final-WAV gradient. Training completed 170 updates in 154.47 seconds
  at 5,876,534,272 peak allocated bytes. EMA adapter SHA-256 is
  `2ded4bec936abb6390f6330514848f1e2cd510d724b2a1ceaf33c8102354419b`.
  Published and screened 850 WAVs. Exact common-stable source distance moved
  external7 `0.256 -> 0.254`, fresh48 `0.155 -> 0.226`, Hadou31
  `0.149 -> 0.128`, stress60 `0.221 -> 0.203`, and JSUT24
  `0.115 -> 0.158`. Tempo1.2 improved `0.262 -> 0.237`.
- Problems: the first smoke exposed a local plumbing bug: the inherited GPU
  batch helper silently omitted the new negative key. Commit `6e61a9f` fixed
  that transfer only. The completed method added no gross row, but fresh48 and
  JSUT regressed broadly, and it gave up much of EXP-213's Hadou/noise gain.
- Rework: the broad-content stop rejects this exact method. Do not sweep or
  blend temperature, negative identity/count, mining, or weight. Inspect a
  different final-WAV semantic representation, preferably direct frozen
  WhisperVQ token classification, before admitting another GPU lane.

## 2026-08-14T08:37:00Z - EXP-223--227 discrete semantic cycle prepared

- Agent: `primary-integrator`.
- Task: choose a different final-WAV content representation after the
  source-versus-negative objective traded tempo gains for fresh48/JSUT loss.
- Dependencies: completed EXP-218--222 stop; exact cross-corpus170 data and
  target multiset; X-VC's frozen GLM-4-Voice tokenizer, source semantic tokens,
  four-frame pooling boundary, and 16,384-entry codebook.
- Result: replaced only contrastive final-WAV content loss with direct
  vocabulary-size-normalized cross-entropy against the existing source token
  IDs. Differentiable 50 Hz final-WAV hidden states are pooled exactly four
  frames and scored using squared Euclidean distance to the frozen codebook.
  Data, target speaker/adversarial objectives, control69 LoRA69, updates, LR,
  optimizer, clip, zero condition, EMA, and five surfaces remain fixed. Focused
  tests passed `100/100`; CPU admission passed 170 rows and external7.
- Problems: the 16,384-way logits are larger than prior hidden MSE and actual
  runtime shape/memory remains unproved. Frame-position token classification may
  still penalize tempo shifts. Machine token accuracy is an optimization
  diagnostic, not naturalness or perceived quality.
- Rework: commit, run one two-row real backward smoke, then one 170-update GPU
  lane only if codebook shape, finite loss, waveform gradient, and memory pass.
  Do not sweep token weight, distance scale, codebook, pooling, layer, data,
  pairing, scope, LR, horizon, or EMA.

## 2026-08-14T09:20:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction and GPU-idle audit.
- Result: `REDIRECT`. The method and five fixed surfaces remained relevant, but
  no new audio existed and the committed EXP-223 smoke had not actually
  launched for more than 40 minutes.
- Problems: the original terminal had exited without a smoke result while GPU0
  remained idle. Operator localStorage remained unobservable.
- Rework: verdict adopted. Stop additional design, recover the exact committed
  command, and execute smoke -> one 170-update lane -> five screens.

## 2026-08-14T09:40:00Z - EXP-223 real-axis correction committed

- Agent: `primary-integrator`.
- Task: resolve the real smoke's `discrete output-cycle codebook drifted` stop.
- Dependencies: commit `7c029b2`; official local WhisperVQ implementation; one
  failed real smoke with no checkpoint or audio.
- Result: the codebook was correctly 16,384 by 1,280. The adapter had mistaken
  the official `[batch, channel, time]` saved hidden state for
  `[batch, time, channel]`. Commit `3972ab0` changed only that axis boundary and
  its test. The X-VC-runtime focused test passed; smoke v3 completed two finite
  backward steps with nonzero waveform gradient at 5,414,245,888 peak bytes.
- Problems: the lightweight project `.venv` does not contain torch; ten
  torch-dependent tests fail to import there. The pinned X-VC runtime is the
  admitted environment and passed the changed test.
- Rework: no method parameter changed. Launch the already-admitted full lane.

## 2026-08-14T09:50:25Z - Grok progress audit

- Agent: `grok-project-progress-auditor` in tmux `liveconv-grok-auditor`.
- Task: independent 30-minute direction, method-value, and GPU-use audit.
- Result: `CONTINUE`. New committed code and EXP-223 audio satisfied the time
  gate. It required completing the same checkpoint's fixed five screens before
  another training idea and closing the content-cycle family on broad
  fresh/JSUT regression.
- Problems: its snapshot could not yet prove all five surfaces or see operator
  localStorage.
- Rework: verdict adopted. Finish the frozen surfaces and screen once; do not
  open a token-weight, codebook, pooling, layer, LR, or horizon neighbor.

## 2026-08-14T09:56:26Z - EXP-223--227 discrete semantic cycle rejected

- Agent: `primary-integrator`.
- Task: train the one fixed categorical final-WAV objective and publish/screen
  the unchanged EMA checkpoint on all five surfaces.
- Dependencies: commits `7c029b2` and `3972ab0`; exact cross-corpus170 source
  and target schedule; fixed external7/fresh48/Hadou31/stress60/JSUT24 sets.
- Result: training completed 170 updates in 112.79 seconds at 5,876,832,256
  peak allocated bytes. EMA adapter SHA-256 is
  `6915c3129cea36f7f729c55a5b6c5d42aaa8988bb7266f5b73c84330ebbc9aad`.
  Published and screened 850 WAVs. Exact common-stable source distance moved
  external7 `0.256 -> 0.190`, fresh48 `0.192 -> 0.197`, Hadou31
  `0.133 -> 0.096`, stress60 `0.223 -> 0.171`, and JSUT24
  `0.115 -> 0.152`. Fresh retained control69's same two gross rows and added
  none; every other surface had zero consensus gross rows.
- Problems: the normalized training token loss diverged `1.309 -> 5.315` and
  accuracy fell `0.267 -> 0.133`. Despite external/Hadou/noise gains, JSUT
  produced only one win, seventeen ties, and four losses on common-stable rows.
- Rework: the predefined broad-content stop rejects this exact method. Close
  discrete loss neighbors and the three-point final-WAV content-cycle family.
  Retain EXP-213 as the unheard cross-corpus technical survivor and choose a
  genuinely different retraining axis next.

## 2026-08-14T10:04:00Z - EXP-228--232 content/voice PCGrad prepared

- Agent: `primary-integrator`.
- Task: choose a genuinely different retraining axis after three final-WAV
  content representations preserved the Hadou/noise versus ordinary-JSUT
  tradeoff.
- Dependencies: EXP-213's best technical survivor; exact cross-corpus170 data,
  targets, losses, LoRA69, 170-step optimizer geometry, EMA, and five surfaces;
  the already-tested symmetric two-task projection primitive from EXP-176.
- Result: return to EXP-213's pointwise frozen-Whisper MSE and change only
  within-row generator gradient composition. Weighted content is task one;
  unchanged target-speaker plus real-wave adversarial/feature loss is task two.
  Negative-dot-product components are symmetrically projected, while aligned
  gradients are summed unchanged. Unlike EXP-176, every source row retains one
  optimizer step. EXP-229--232 bind the complete frozen evaluation contract.
- Problems: two generator gradient extractions can increase peak memory and
  wall time. PCGrad can expose conflict but cannot prove perceptual quality.
- Rework: focused tests, exact no-CUDA admission, commit, then one two-row real
  smoke and one 170-step lane. Stop if task-sum/geometry is nonfinite, conflicts
  are absent, a gross row is added, or broad JSUT remains worse. Do not sweep
  weights, grouping, projection, data, scope, LR, horizon, or EMA.

## 2026-08-14T10:22:28Z - Grok project-progress audit

- Agent: `grok-4.6` in tmux `liveconv-grok-auditor`; independent, read-only,
  no tools or delegation.
- Verdict: `CONTINUE`.
- Adopted: finish the already committed EXP-228 lane through its five fixed
  surfaces and one coarse screen, then replan once. Do not open PCGrad weight,
  grouping, projection, data, scope, LR, horizon, or EMA neighbors.
- Discarded as requested: content-cycle neighbors, human87/DTW retries, the
  local tongue-twister as a browser target, hash/review ceremony, automatic
  quality claims, and a second training lane.
- Evidence gap resolved: the auditor snapshot ended just after commit and could
  not see the smoke or 170-step job. Direct runtime evidence below records both;
  its observed GPU load was the active screen, not an idle or stray process.

## 2026-08-14T10:24:00Z - EXP-228--232 content/voice PCGrad rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T10:09:00Z.
- End: 2026-08-14T10:24:00Z.
- Dependencies: commit `33be19c`; exact cross-corpus170 curriculum; fixed
  external7/fresh48/Hadou31/stress60/JSUT24 sets; gpu0; listener 8878.
- Result: the real two-row smoke was finite at 5,371,280,896 peak allocated
  bytes and observed cosine `-0.08924`. Training completed 170 updates in
  127.28 seconds at 5,872,224,256 peak bytes. PCGrad found 92 conflicts in 170
  rows, cosine mean `-0.02275`. EMA adapter SHA-256 is
  `6d09a5bd053e448cdc56b90a3aa5890bb903278620cf4c4aae1991e95080ccb0`.
  Published and screened 850 WAVs. No candidate-added consensus gross row
  appeared. Exact common-stable source distance moved external7
  `0.256410 -> 0.223077`, fresh48 `0.195897 -> 0.187880`, Hadou31
  `0.148912 -> 0.129832`, stress60 `0.221115 -> 0.198264`, and JSUT24
  `0.115028 -> 0.145764`.
- Problems: the motivating ordinary-JSUT stop still fired despite conflicts on
  more than half the rows; basic5000 regressed `0.103554 -> 0.170221`. The
  auxiliary ASR screen cannot decide naturalness, target identity, or emotion.
- Rework: reject this exact method and close optimizer-surgery neighbors. Do
  not tune weights or projection. Move to a function-path, target-data, or
  conditioning intervention while retaining one committed GPU lane at a time.

## 2026-08-14T10:31:00Z - EXP-233--237 speaker-path overlay prepared

- Agent: `primary-integrator`.
- Task: convert EXP-228's frequent content/voice conflict into a distinct
  function-path intervention instead of another loss or optimizer neighbor.
- Dependencies: frozen control69 content converter; exact cross-corpus170
  source/target schedule; speaker7 topology already mapped by EXP-038; fixed
  five-surface gate; no operator hearing availability.
- Result: select a second-stage overlay that merges control69, freezes every
  content/condition parameter, and adds a fresh rank-8 LoRA only to the seven
  speaker-conditioned AdaLN linears. Train those 166,400 parameters using only
  target-speaker MSE plus real-wave adversarial/feature loss. EXP-234--237 bind
  the unchanged fresh48/Hadou31/stress60/JSUT24 evaluations.
- Problems: content stability can be screened, but the intended naturalness and
  identity effect cannot be selected without later hearing. Speaker modulation
  can still indirectly disturb content even when the content path is frozen.
- Rework: focused tests, exact no-CUDA admission, commit, then one two-row smoke
  and one 170-step lane. Stop on added corruption or broad content regression;
  do not tune rank, scope, loss weights, data, LR, condition, or EMA.

## 2026-08-14T10:45:08Z - EXP-233--237 speaker-path overlay rejected

- Agent: `primary-integrator`.
- Start: 2026-08-14T10:32:00Z.
- End: 2026-08-14T10:45:08Z.
- Dependencies: commit `135e6ed`; merged EXP-035 control69; exact
  cross-corpus170 schedule; fixed five surfaces; gpu0; listener 8878.
- Result: smoke proved 14 trainable tensors / 166,400 parameters at
  4,603,096,064 peak bytes. Training completed 170 updates in 110.13 seconds at
  5,859,044,352 peak bytes. Voice plus adversarial loss moved
  `70.1457 -> 50.0250`; speaker MSE moved `0.17721 -> 0.11189`. EMA overlay
  SHA-256 is
  `d58b604cbec07d1d21c64740c7409d74524ae4818957b9c455ab1acc52db4fe9`.
  Published and screened 850 WAVs with no candidate-added consensus gross row.
  Exact common-stable source distance moved external7 `0.256410 -> 0.238462`,
  fresh48 `0.209620 -> 0.248118`, Hadou31 `0.148912 -> 0.133097`, stress60
  `0.190836 -> 0.206823`, and JSUT24 `0.115028 -> 0.130505`.
- Problems: voice-only speaker modulation still disturbed broad content despite
  the frozen converter. Fresh unknown speakers, clean/silence/tempo/pitch, and
  ordinary JSUT reproduce the recurring cross-domain tradeoff. Machine metrics
  do not decide whether the overlay changed naturalness or target identity.
- Rework: reject this exact function-path intervention and close adjacent
  rank/scope/weight/schedule points. The repeated failure now implicates the
  unrelated source/target training contract. Next restore source-aligned
  pseudo-parallel targets while retaining the broad cross-corpus source set.

## 2026-08-14T10:52:18Z - Grok progress audit

- Agent: `grok-4.6-project-progress-auditor` in
  `liveconv-grok-auditor` tmux.
- Task: independent read-only 30-minute audit of whether the active X-VC quality
  search is the shortest route to a usable realtime Japanese conversation
  system.
- Dependencies: completed EXP-233--237 five-surface screen; idle gpu0; operator
  unavailable for hearing; corrected non-browser tongue-twister provenance.
- Result: `CONTINUE`. The auditor accepted the fixed diverse five-surface gate,
  the completed single-lane render/screen/replan loop, and the next change from
  unrelated targets to source-aligned pseudoparallel targets as a testable data
  contract hypothesis.
- Problems: gpu0 was idle after the last close, and 143 dirty entries could
  obscure the identity if the next runner itself were not committed.
- Rework: adopted. Discard speaker-path neighbors and further loss/optimizer
  changes on the same unpaired contract. Commit only the EXP-238 runner, tests,
  and plan before rendering 170 training targets and starting one GPU lane;
  do not block on unrelated dirty files.

## 2026-08-14T10:53:00Z - EXP-238--242 pseudoparallel pilot prepared

- Agent: `primary-integrator`.
- Task: replace the repeated unrelated-content training contradiction with one
  source-aligned target-data intervention.
- Dependencies: frozen control69; exact EXP-213 CV48/JSUT85/JVS3/Hadou34
  source order and Amitaro target assignment; fixed five-surface gate; gpu0.
- Result: materializer binds each source to the frozen control69 conversion of
  that same source under its assigned Amitaro reference. Training returns to
  the complete standard generative loss, while the original real Amitaro WAV
  remains only the discriminator real side. EXP-239--242 prebind the unchanged
  fresh48/Hadou31/stress60/JSUT24 renders.
- Problems: the frozen control69 teacher can distill its existing defects and
  automatic diagnostics cannot establish naturalness or target-voice quality.
- Rework: focused tests, exact CPU admission, commit, then 170 target renders,
  one two-row smoke, one 170-step lane, five-surface publish, and coarse screen.
  Stop rather than sweep if broad content or corruption fails.

## 2026-08-14T11:18:00Z - EXP-238--242 pseudoparallel technical survivor

- Agent: `primary-integrator`.
- Start: 2026-08-14T10:53:00Z.
- End: 2026-08-14T11:18:00Z.
- Dependencies: commit `edbe8c5`; frozen control69; exact cross-corpus170
  source order and real Amitaro target assignment; gpu0; listener 8878.
- Result: generated 170 same-content control69 targets in 95.37 seconds at
  2,668,426,752 peak bytes. Two-row smoke was finite at 4,636,175,872 bytes.
  Training completed 170 updates in 136.83 seconds at 6,163,570,688 bytes; EMA
  adapter SHA-256 is
  `778b430133b5397d86bd70bd7c9fa7bd4f7f9cc4d737ca94e4b91e5c7bc8a9da`.
  Published and screened 850 WAVs with no candidate-added consensus gross row.
  Exact common-stable source distance moved external7
  `0.256410 -> 0.256410`, fresh48 `0.214090 -> 0.206909`, Hadou31
  `0.148912 -> 0.127328`, stress60 `0.222702 -> 0.193036`, and JSUT24
  `0.115028 -> 0.123253`. W/T/L were `0/5/0`, `4/30/3`, `3/22/1`,
  `7/36/2`, and `1/20/1`; known-text distance improved on all five surfaces.
- Problems: JSUT source-relative mean has one loss despite 20 ties and one win;
  pitch+3 has one loss among eight common-stable rows. Machine diagnostics do
  not establish naturalness, target identity, emotion, or audible preference.
- Rework: the predefined broad-regression stop does not fire. Retain the exact
  checkpoint as an unheard technical survivor and prioritize it for later
  hearing. Do not call it a winner or sweep target/LR/scope/horizon neighbors.
  Replan the next bounded method or evaluation axis before another GPU lane.

## 2026-08-14T11:22:34Z - Grok progress audit broadened evaluation first

- Agent: `grok-4.6-project-progress-auditor` in tmux
  `liveconv-grok-auditor`; independent, read-only, and no delegation.
- Task: challenge whether another X-VC retraining lane or the same five
  automatic surfaces were the shortest path to robust Japanese voice
  conversion while the operator is unavailable for hearing.
- Result: `CONTINUE`. The auditor accepted EXP-238's committed one-lane
  render/screen/replan loop and its source-aligned data-contract intervention.
  It rejected target/LR/scope/horizon/rank neighbors and warned that repeatedly
  accumulating technical survivors on the same five surfaces would no longer
  add enough information.
- Adopted: yes. Keep EXP-238 unheard and unselected. Before another training
  lane, add fixed diversity across speaker, text length, speed, F0, silence,
  and noise, then let the observed failure strata select one new method axis.
- Problems: gpu0 is idle during the bounded runner/test/commit preparation;
  automatic content diagnostics still cannot measure naturalness, identity,
  emotion, or preference.
- Rework: prepare EXP-243 as 16 disjoint fresh48 speakers in four text-length
  bands crossed with nine symmetric conditions. Commit before CUDA, then
  render base/control69/EXP-238 and publish 720 WAVs on 8878. Do not register a
  human speaker model or widen promotion evidence for this listen-now slice.

## 2026-08-14T11:38:00Z - EXP-243 expanded stress matrix completed

- Agent: `primary-integrator`.
- Start: 2026-08-14T11:22:34Z.
- End: 2026-08-14T11:38:00Z.
- Dependencies: commit `19abe49`; sixteen disjoint fresh48 speakers; four
  normalized-text-length bands; nine symmetric transforms; base, control69,
  and exact EXP-238 EMA; gpu0; listener 8878.
- Result: froze 144 rows and published 720 WAVs. Rendering completed in 109.64
  seconds at 5,126,684,160 peak allocated bytes. The v4 screen found zero
  gross rows for control and candidate. On 104 exact common-stable rows,
  source-relative distance moved `0.401210 -> 0.311316`, W/T/L `17/74/13`.
  Long rows moved `0.922435 -> 0.423835`; short and very-long rows improved
  slightly, while medium rows were near flat.
- Problems: the thirteen losses span eight speakers and no single condition
  dominates. Clean, noise30, pitch+3, and some other strata remain mixed.
  Known-text distance is intentionally not interpreted for long rows because
  the fixed 2.4-second window truncates their transcripts. Automatic metrics
  still cannot judge naturalness, identity, emotion, or audible preference.
- Rework: retain EXP-238 and EXP-243 as unheard technical evidence, not a
  winner. Do not reopen source/target condition augmentation: EXP-043,
  EXP-044, and EXP-191 already closed nearby source, target, and
  condition-balanced variants. Change one genuinely different source-data
  block while keeping the pseudoparallel contract and optimizer fixed.

## 2026-08-14T11:47:00Z - EXP-244 SRC4VC source substitution selected

- Agent: `primary-integrator`.
- Task: choose a one-variable retraining intervention after the expanded matrix
  showed distributed rather than condition-local failures.
- Dependencies: SRC4VC version 1 official corpus page and terms; pinned
  3,417,630,585-byte archive; exact central-directory range and SHA-256;
  existing EXP-213/238 170-row curriculum.
- Result: select 85 distinct SRC4VC smartphone-recorded train speakers and
  reserve fifteen evenly spread, disjoint speakers with two rows each for
  evaluation. Replace only JSUT85 in the curriculum, retaining CV48, JVS3,
  Hadou34, the exact ordered Amitaro target assignment, frozen-control69
  pseudoparallel target construction, loss, LoRA scope, LR, 170 updates, and
  EMA. A byte-range fetch avoids downloading the full 3.4 GB archive.
- Problems: SRC4VC permits research use and prohibits redistribution. Raw audio
  and derived private manifests therefore remain ignored under `artifacts/`;
  no corpus audio will be committed or redistributed. Human naturalness and
  identity assessment remains unavailable.
- Rework: commit the bounded fetcher, split, tests, and plan before
  materialization. Stop on archive identity drift, invalid WAV, metadata drift,
  or train/evaluation speaker overlap. Do not vary corpus ratio, horizon, loss,
  scope, LR, or EMA in this lane.

## 2026-08-14T11:52:12Z - Grok progress audit admits EXP-244 lane

- Agent: `grok-4.6-project-progress-auditor` in tmux
  `liveconv-grok-auditor`; independent, read-only, and no delegation.
- Task: decide whether the expanded evaluation followed by a one-block SRC4VC
  source substitution is the shortest route to improved voice quality.
- Result: `CONTINUE`. The auditor accepted that EXP-243 first broadened the
  fixed evaluation, found distributed failures, and selected one new
  recording-domain data variable while retaining the pseudoparallel method and
  every optimizer choice.
- Adopted: yes. Stop evaluation redesign and move the committed bounded fetcher
  directly into one gpu0 EXP-244 lane. Human hearing remains deferred; coarse
  ASR remains content/corruption screening only.
- Problems: gpu0 remains idle until private data acquisition and runner
  admission complete. The auditor cannot observe operator localStorage and did
  not inspect the listening UI index.
- Rework: discard additional conditions, corpus-ratio neighbors, promotion
  ceremony, human87/DTW retries, multiple lanes, and automatic naturalness
  claims. Record acquisition drift without expanding the training variable.

## 2026-08-14T12:00:00Z - SRC4VC acquisition drift handled

- Agent: `primary-integrator`.
- Task: materialize the exact 115-row private research subset after commit
  `d4f89ec`.
- Result: archive identity, central directory, selected member inventory, ZIP
  CRCs, transcripts, and most audio passed. Two real corpus shapes required a
  bounded parser correction: three speaker metadata files contain quoted
  indented continuation lines, and SRC4VC025 RECITATION audio is native
  44.1 kHz rather than 48 kHz. Both rates remain mono PCM16 and the existing
  curriculum window preserves native rate.
- Problems: the first two attempts stopped safely after writing 3 files/8.3 MB
  and 28 files/44 MB. Neither wrote `subset.json`.
- Rework: moved the incomplete outputs to explicit recoverable
  `.partial-metadata-shape` and `.partial-native-rate` directories. Added a
  strict flat multiline parser and admitted only native 44.1/48 kHz mono PCM16,
  recording each row's actual rate. No resampling, row substitution, training
  method, or split changed.
