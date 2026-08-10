const UINT32_MAX = 0xffff_ffff;
const SAMPLE_RATE = 48_000;
const BUFFERED_PREVIEW_CAPTURE_FRAMES = 25;
const MAXIMUM_RECEIPT_INPUT_REFERENCES = 500;
const PROGRESS_NOTIFICATION_FRAMES = 25;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HASH = /^sha256:[0-9a-f]{64}$/;
const EXP005_INJECTION_MARKER = Symbol("EXP-005 explicit failure injection");

function requireFunction(value, name) {
  if (typeof value !== "function") {
    throw new TypeError(`${name} must be a function`);
  }
  return value;
}

function requireGenerationId(value) {
  if (!Number.isInteger(value) || value < 0 || value > UINT32_MAX) {
    throw new TypeError("generationId must be a uint32");
  }
  return value;
}

function requireInvocationMode(value) {
  if (value !== "live" && value !== "buffered_end") {
    throw new TypeError("invocationMode must be live or buffered_end");
  }
  return value;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : "Offscreen operation failed";
}

function defaultNowNanoseconds() {
  return BigInt(Math.round(performance.now() * 1_000_000));
}

function defaultOffscreenEpoch() {
  return crypto.randomUUID();
}

export function createOffscreenRuntime(options = {}) {
  const audioGraphFactory = requireFunction(
    options.audioGraphFactory,
    "audioGraphFactory",
  );
  const remoteClientFactory = requireFunction(
    options.remoteClientFactory,
    "remoteClientFactory",
  );
  const sendMessage = requireFunction(options.sendMessage, "sendMessage");
  const nowNanoseconds = requireFunction(
    options.nowNanoseconds ?? defaultNowNanoseconds,
    "nowNanoseconds",
  );
  const offscreenEpochFactory = requireFunction(
    options.offscreenEpochFactory ?? defaultOffscreenEpoch,
    "offscreenEpochFactory",
  );
  const setTimer = requireFunction(
    options.setTimer ?? globalThis.setTimeout,
    "setTimer",
  );
  const clearTimer = requireFunction(
    options.clearTimer ?? globalThis.clearTimeout,
    "clearTimer",
  );
  const drainTimeoutMilliseconds = options.drainTimeoutMilliseconds ?? 1_000;
  if (
    !Number.isSafeInteger(drainTimeoutMilliseconds) ||
    drainTimeoutMilliseconds <= 0
  ) {
    throw new TypeError("drainTimeoutMilliseconds must be a positive safe integer");
  }

  let capture = "stopped";
  let route = "native";
  let remote = "disconnected";
  let generationId = null;
  let sequence = 0;
  let sourceFrameBase = null;
  let timestampBase = 0n;
  let graph = null;
  let client = null;
  let stopping = false;
  let handlingFallback = false;
  let generationEpoch = 0;
  let captureAcceptance = null;
  let graphEpoch = 0;
  let connectionEpoch = 0;
  let captureCreditFrames = 4;
  let invocationMode = null;
  let bufferedPreviewRelease = null;
  let offscreenEpoch = null;
  let profileIdentity = null;
  let receiptEnabled = false;
  let receiptOutputSummary = null;
  let receiptRemotePlayoutEmitted = false;
  let inputFrameCount = 0;
  let outputFrameCount = 0;
  let lastNotifiedOutputFrameCount = 0;
  let receiptNotificationChain = Promise.resolve();
  const receiptInputFrames = new Map();

  function snapshot() {
    return Object.freeze({ capture, route, remote, generationId });
  }

  function snapshotWithEpoch() {
    const state = { ...snapshot() };
    if (offscreenEpoch !== null) {
      state.offscreenEpoch = offscreenEpoch;
    }
    return Object.freeze(state);
  }

  function notify(event) {
    return Promise.resolve(
      sendMessage({ target: "background", type: "offscreen.event", event }),
    ).catch(() => {});
  }

  function receiptIdentity(event) {
    if (
      event === null ||
      typeof event !== "object" ||
      typeof event.profile_id !== "string" ||
      !HASH.test(event.profile_hash) ||
      !HASH.test(event.configuration_hash) ||
      typeof event.pipeline_id !== "string" ||
      !UUID.test(event.pipeline_id)
    ) {
      return null;
    }
    return Object.freeze({
      profileId: event.profile_id,
      profileHash: event.profile_hash,
      configurationHash: event.configuration_hash,
      pipelineId: event.pipeline_id,
    });
  }

  function receiptEvent(type, value = {}) {
    if (!receiptEnabled) {
      return Promise.resolve();
    }
    const operation = receiptNotificationChain.then(() =>
      notify({ receipt: { type, ...value } }),
    );
    receiptNotificationChain = operation.catch(() => {});
    return operation;
  }

  async function configureReceipt(enabled) {
    if (enabled !== true && enabled !== false) {
      throw new TypeError("receipt enabled state must be a boolean");
    }
    receiptEnabled = enabled;
    if (!enabled) {
      await receiptNotificationChain;
      clearReceiptInputFrames();
      receiptOutputSummary = null;
      receiptRemotePlayoutEmitted = false;
    }
    return snapshot();
  }

  function receiptNoStaleOutput(currentGenerationId, currentIdentity) {
    if (currentGenerationId !== null && currentIdentity !== null) {
      return receiptEvent("generation.stale-output", {
        generationId: currentGenerationId,
        pipelineId: currentIdentity.pipelineId,
        accepted: false,
      });
    }
    return Promise.resolve();
  }

  function clearReceiptInputFrames() {
    receiptInputFrames.clear();
  }

  function recordReceiptInput(timestamp, samples) {
    if (!receiptEnabled || !(samples instanceof Float32Array)) {
      return;
    }
    receiptInputFrames.set(timestamp.toString(), samples.slice());
    while (receiptInputFrames.size > MAXIMUM_RECEIPT_INPUT_REFERENCES) {
      receiptInputFrames.delete(receiptInputFrames.keys().next().value);
    }
  }

  function receiptOutputObservation(timestamp, samples) {
    if (!(samples instanceof Float32Array)) {
      return Object.freeze({ finite: false, changed: false });
    }
    const input = receiptInputFrames.get(BigInt(timestamp).toString());
    let finite = true;
    const comparable = input instanceof Float32Array && input.length === samples.length;
    let changed = false;
    for (let index = 0; index < samples.length; index += 1) {
      const sample = samples[index];
      if (!Number.isFinite(sample)) {
        finite = false;
      }
      if (comparable && sample !== input[index]) {
        changed = true;
      }
    }
    return Object.freeze({ finite, changed });
  }

  function summarizeReceiptOutput(observation, currentGenerationId, identity) {
    if (!receiptEnabled || identity === null || observation === null) {
      return;
    }
    if (
      receiptOutputSummary === null ||
      receiptOutputSummary.generationId !== currentGenerationId ||
      receiptOutputSummary.pipelineId !== identity.pipelineId
    ) {
      receiptOutputSummary = {
        generationId: currentGenerationId,
        pipelineId: identity.pipelineId,
        finite: true,
        changed: false,
      };
    }
    receiptOutputSummary.finite &&= observation.finite;
    receiptOutputSummary.changed ||= observation.changed;
  }

  function flushReceiptOutputSummary(currentGenerationId, identity) {
    if (
      receiptOutputSummary?.generationId === currentGenerationId &&
      receiptOutputSummary.pipelineId === identity?.pipelineId
    ) {
      const operation = receiptEvent("generation.output", receiptOutputSummary);
      receiptOutputSummary = null;
      return operation;
    }
    return Promise.resolve();
  }

  function clearGeneration() {
    captureAcceptance = null;
    bufferedPreviewRelease = null;
    generationId = null;
    sequence = 0;
    sourceFrameBase = null;
    timestampBase = 0n;
    clearReceiptInputFrames();
    receiptOutputSummary = null;
    receiptRemotePlayoutEmitted = false;
    inputFrameCount = 0;
    outputFrameCount = 0;
    lastNotifiedOutputFrameCount = 0;
  }

  function notifyProgress({ force = false } = {}) {
    if (
      generationId === null ||
      outputFrameCount === 0 ||
      (!force &&
        outputFrameCount - lastNotifiedOutputFrameCount <
          PROGRESS_NOTIFICATION_FRAMES)
    ) {
      return;
    }
    lastNotifiedOutputFrameCount = outputFrameCount;
    notify({
      progress: {
        generationId,
        inputFrames: inputFrameCount,
        outputFrames: outputFrameCount,
      },
    });
  }

  function openCaptureAcceptance(nextId) {
    captureAcceptance = Object.freeze({
      generationId: nextId,
      generationEpoch,
    });
  }

  function closeCaptureAcceptance(currentId, currentEpoch) {
    if (
      captureAcceptance?.generationId === currentId &&
      captureAcceptance.generationEpoch === currentEpoch
    ) {
      captureAcceptance = null;
    }
  }

  function releaseBufferedPreview(currentId, currentEpoch) {
    if (invocationMode !== "buffered_end") {
      return;
    }
    bufferedPreviewRelease = Object.freeze({
      generationId: currentId,
      generationEpoch: currentEpoch,
    });
  }

  function mayDeliverRemotePlayout(currentId) {
    return (
      invocationMode !== "buffered_end" ||
      (bufferedPreviewRelease?.generationId === currentId &&
        bufferedPreviewRelease.generationEpoch === generationEpoch)
    );
  }

  function generationCaptureOptions() {
    if (invocationMode === "buffered_end") {
      return Object.freeze({
        captureCreditFrames: Math.min(
          captureCreditFrames,
          BUFFERED_PREVIEW_CAPTURE_FRAMES,
        ),
        maximumCaptureFrames: BUFFERED_PREVIEW_CAPTURE_FRAMES,
      });
    }
    return Object.freeze({
      captureCreditFrames,
    });
  }

  function sourceTimestamp(sourceFrame) {
    if (!Number.isSafeInteger(sourceFrame) || sourceFrame < 0) {
      throw new TypeError("sourceFrame must be a non-negative safe integer");
    }
    if (sourceFrameBase === null) {
      sourceFrameBase = sourceFrame;
      timestampBase = nowNanoseconds();
    }
    if (sourceFrame < sourceFrameBase) {
      throw new RangeError("capture sourceFrame cannot move backwards");
    }
    return (
      timestampBase +
      (BigInt(sourceFrame - sourceFrameBase) * 1_000_000_000n) /
        BigInt(SAMPLE_RATE)
    );
  }

  function sourceFrame(timestamp) {
    const normalized = BigInt(timestamp);
    if (sourceFrameBase === null || normalized < timestampBase) {
      throw new RangeError("output timestamp precedes the captured generation");
    }
    const offset =
      ((normalized - timestampBase) * BigInt(SAMPLE_RATE)) / 1_000_000_000n;
    const frame = sourceFrameBase + Number(offset);
    if (!Number.isSafeInteger(frame)) {
      throw new RangeError("output source frame exceeds the safe integer range");
    }
    return frame;
  }

  function cancelClientGeneration(currentGenerationId, candidate = client) {
    try {
      const operation = candidate?.cancelGeneration(currentGenerationId);
      Promise.resolve(operation).catch(() => {});
    } catch {
      // Local invalidation is already complete and never waits on the server.
    }
  }

  function closeClient(candidate) {
    try {
      const operation = candidate?.close();
      Promise.resolve(operation).catch(() => {});
    } catch {
      // Closing a stale or partially connected transport is best effort.
    }
  }

  function boundedDrain(operation) {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimer(
        () => reject(new Error("local playout drain timed out")),
        drainTimeoutMilliseconds,
      );
    });
    return Promise.race([operation, timeout]).finally(() => clearTimer(timer));
  }

  function performFallback(event = {}, injectionMarker = null) {
    if (handlingFallback || stopping) {
      return;
    }
    handlingFallback = true;
    const receiptOperations = [];
    try {
      const currentGenerationId = generationId;
      const currentIdentity = profileIdentity;
      if (currentGenerationId !== null) {
        graph?.cancelGeneration(
          currentGenerationId,
          event.reasonCode ?? event.reason_code ?? "WORKER_CRASH",
        );
        cancelClientGeneration(currentGenerationId);
      } else {
        graph?.fallback(event);
      }
      route = "native";
      remote = "degraded";
      if (
        event.type === "fallback.required" &&
        currentGenerationId !== null &&
        currentIdentity !== null
      ) {
        receiptOperations.push(
          flushReceiptOutputSummary(currentGenerationId, currentIdentity),
          receiptNoStaleOutput(currentGenerationId, currentIdentity),
          receiptEvent("fallback.required", {
          generationId: currentGenerationId,
          pipelineId: currentIdentity.pipelineId,
          profileId: currentIdentity.profileId,
          profileHash: currentIdentity.profileHash,
          configurationHash: currentIdentity.configurationHash,
          injected: injectionMarker === EXP005_INJECTION_MARKER,
          }),
          receiptEvent("native.fallback", {
          generationId: currentGenerationId,
          pipelineId: currentIdentity.pipelineId,
          profileId: currentIdentity.profileId,
          profileHash: currentIdentity.profileHash,
          configurationHash: currentIdentity.configurationHash,
          nativeAudible: true,
          remoteAudible: false,
          }),
        );
      }
      clearGeneration();
      notify({
        route,
        remote,
        generationId: null,
        error: event.message ?? event.reasonCode ?? event.reason_code,
      });
    } finally {
      handlingFallback = false;
    }
    return Promise.allSettled(receiptOperations);
  }

  async function injectExp005Failure(injectingId) {
    requireGenerationId(injectingId);
    if (
      injectingId !== generationId ||
      profileIdentity === null ||
      invocationMode !== "buffered_end"
    ) {
      throw new Error("EXP-005 failure injection requires the active buffered generation");
    }
    await performFallback(
      {
        type: "fallback.required",
        reasonCode: "EXP005_INJECTED_FAILURE",
        message: "EXP-005 explicit failure injection",
      },
      EXP005_INJECTION_MARKER,
    );
    return snapshot();
  }

  function retireClosedTransport({
    candidateClient,
    candidateEpoch,
    candidateGraph,
    event = {},
  }) {
    if (
      connectionEpoch !== candidateEpoch ||
      client !== candidateClient ||
      graph !== candidateGraph
    ) {
      return false;
    }
    const fallbackAlreadyApplied =
      route === "native" && remote === "degraded" && generationId === null;
    generationEpoch += 1;
    if (!fallbackAlreadyApplied) {
      const currentGenerationId = generationId;
      handlingFallback = true;
      try {
        if (currentGenerationId !== null) {
          candidateGraph.cancelGeneration(
            currentGenerationId,
            event.reasonCode ?? "TRANSPORT_CLOSED",
          );
        } else {
          candidateGraph.fallback(event);
        }
      } catch {
        try {
          candidateGraph.fallback(event);
        } catch {
          // Transport retirement and native state remain authoritative.
        }
      } finally {
        handlingFallback = false;
      }
    }
    route = "native";
    remote = "degraded";
    clearGeneration();
    connectionEpoch = candidateEpoch + 1;
    client = null;
    closeClient(candidateClient);
    const detail = event.message ? `${event.message}. ` : "";
    notify({
      capture,
      route,
      remote,
      generationId: null,
      transportClosed: true,
      requiresFreshSession: true,
      error: `${detail}Stop and Start to create a fresh authenticated session.`,
    });
    return true;
  }

  function onCaptureFrame(frame) {
    if (
      generationId === null ||
      frame.generationId !== generationId ||
      captureAcceptance?.generationId !== generationId ||
      captureAcceptance.generationEpoch !== generationEpoch
    ) {
      return false;
    }
    if (sequence > UINT32_MAX) {
      performFallback({ reasonCode: "QUEUE_OVERFLOW" });
      return false;
    }
    let sent = false;
    try {
      const timestamp = sourceTimestamp(frame.sourceFrame);
      sent = client?.sendFrame({
        header: {
          kind: 1,
          flags: 0,
          generation_id: generationId,
          sequence,
          sample_rate: SAMPLE_RATE,
          channels: 1,
          samples_per_channel: 960,
          source_monotonic_ns: timestamp,
        },
        samples: frame.samples,
      });
      if (sent) {
        recordReceiptInput(timestamp, frame.samples);
      }
    } catch (error) {
      performFallback({ reasonCode: "UNSUPPORTED_AUDIO", message: errorMessage(error) });
      return false;
    }
    if (!sent && generationId !== null) {
      performFallback({ reasonCode: "INVALID_STATE" });
      return false;
    }
    if (sent) {
      sequence += 1;
      inputFrameCount += 1;
    }
    return sent;
  }

  function onOutputFrame(frame) {
    if (
      generationId === null ||
      frame?.header?.generation_id !== generationId ||
      !mayDeliverRemotePlayout(generationId)
    ) {
      return;
    }
    let alignedFrame;
    try {
      alignedFrame = {
        ...frame,
        sourceFrame: sourceFrame(frame?.header?.source_monotonic_ns),
      };
    } catch (error) {
      performFallback({
        reasonCode: "UNSUPPORTED_AUDIO",
        message: errorMessage(error),
      });
      return;
    }
    if (invocationMode === "buffered_end") {
      alignedFrame = graph?.rebasePreviewFrame?.(alignedFrame) ?? alignedFrame;
    }
    const outputObservation =
      receiptEnabled && profileIdentity !== null
        ? receiptOutputObservation(
            frame.header.source_monotonic_ns,
            alignedFrame.samples,
          )
        : null;
    const enqueued = graph?.enqueueRemoteFrame(alignedFrame);
    if (!enqueued && generationId !== null) {
      performFallback({ reasonCode: "STALE_GENERATION" });
      return;
    }
    if (enqueued && profileIdentity !== null) {
      summarizeReceiptOutput(
        outputObservation,
        generationId,
        profileIdentity,
      );
    }
    if (enqueued) {
      outputFrameCount += 1;
      notifyProgress();
    }
  }

  function createGraph(candidateEpoch) {
    let candidate;
    const isCurrent = () =>
      graphEpoch === candidateEpoch && graph === candidate;
    candidate = audioGraphFactory({
      onCaptureFrame(event) {
        if (isCurrent()) {
          return onCaptureFrame(event);
        }
        return false;
      },
      onFallback(event) {
        if (isCurrent()) {
          return performFallback(event);
        }
        return undefined;
      },
      onRemoteReady(event) {
        if (
          !isCurrent() ||
          event.generationId !== generationId ||
          !mayDeliverRemotePlayout(generationId)
        ) {
          return;
        }
        route = "remote";
        remote = remote === "draining" ? "draining" : "ready";
        if (
          profileIdentity !== null &&
          generationId !== null &&
          !receiptRemotePlayoutEmitted
        ) {
          receiptRemotePlayoutEmitted = true;
          receiptEvent("remote.playout", {
            generationId,
            pipelineId: profileIdentity.pipelineId,
            nativeAudible: false,
            remoteAudible: true,
          });
        }
        notify({ route, remote, generationId });
        notifyProgress({ force: true });
      },
      onSourceEnded() {
        if (!isCurrent()) {
          return;
        }
        void stop().then(() => {
          notify({
            capture: "stopped",
            route: "native",
            remote: "disconnected",
            generationId: null,
            sourceEnded: true,
            error: "Captured tab audio ended",
          });
        });
      },
    });
    return candidate;
  }

  async function startNative({ streamId, tabId } = {}) {
    if (capture === "running") {
      return snapshotWithEpoch();
    }
    const candidateOffscreenEpoch = offscreenEpochFactory();
    if (
      typeof candidateOffscreenEpoch !== "string" ||
      !UUID.test(candidateOffscreenEpoch)
    ) {
      throw new Error("offscreenEpochFactory must return a UUID");
    }
    const candidateEpoch = graphEpoch + 1;
    graphEpoch = candidateEpoch;
    capture = "starting";
    remote = "disconnected";
    profileIdentity = null;
    const candidate = createGraph(candidateEpoch);
    graph = candidate;
    try {
      await candidate.startNativeLoopback({ streamId, tabId });
      if (graphEpoch !== candidateEpoch || graph !== candidate) {
        await candidate.stop();
        return snapshot();
      }
      capture = "running";
      route = "native";
      offscreenEpoch = candidateOffscreenEpoch;
      return snapshotWithEpoch();
    } catch (error) {
      if (graphEpoch === candidateEpoch && graph === candidate) {
        capture = "stopped";
        graph = null;
        offscreenEpoch = null;
      }
      throw error;
    }
  }

  async function connectRemote({
    url,
    sessionId,
    ticket,
    generationId: nextId,
    expectedProfile,
    expectedLimits,
    invocationMode: nextInvocationMode = "live",
  } = {}) {
    requireGenerationId(nextId);
    requireInvocationMode(nextInvocationMode);
    if (capture !== "running" || !graph) {
      throw new Error("native audio graph must be running before remote connect");
    }
    if (client) {
      throw new Error("remote client is already connected");
    }
    const candidateEpoch = connectionEpoch + 1;
    connectionEpoch = candidateEpoch;
    const candidateGraph = graph;
    let candidateClient;
    let candidateTransportClosed = false;
    const isCurrent = () =>
      connectionEpoch === candidateEpoch &&
      client === candidateClient &&
      graph === candidateGraph;
    remote = "connecting";
    invocationMode = nextInvocationMode;
    candidateClient = remoteClientFactory({
      onFallback(event) {
        if (isCurrent()) {
          return performFallback(event);
        }
        return undefined;
      },
      onTransportClosed(event) {
        if (isCurrent()) {
          candidateTransportClosed = true;
          retireClosedTransport({
            candidateClient,
            candidateEpoch,
            candidateGraph,
            event,
          });
        }
      },
      onOutputFrame(frame) {
        if (isCurrent()) {
          onOutputFrame(frame);
        }
      },
    });
    client = candidateClient;
    try {
      const attached = await candidateClient.connect({
        url,
        sessionId,
        ticket,
        expectedProfile,
        expectedLimits,
      });
      if (!isCurrent()) {
        closeClient(candidateClient);
        return snapshot();
      }
      profileIdentity = receiptIdentity(attached);
      if (profileIdentity !== null) {
        await receiptEvent("gateway.attached", {
          sessionId,
          pipelineId: profileIdentity.pipelineId,
          profileId: profileIdentity.profileId,
          profileHash: profileIdentity.profileHash,
          configurationHash: profileIdentity.configurationHash,
        });
      }
      captureCreditFrames = expectedLimits?.maxIngressFrames ?? 4;
      remote = "loading";
      notify({ capture, route, remote, generationId: null });
      const generationReady = await candidateClient.startGeneration(nextId);
      if (!isCurrent()) {
        closeClient(candidateClient);
        return snapshot();
      }
      generationEpoch += 1;
      generationId = nextId;
      const readyIdentity = receiptIdentity(generationReady);
      if (readyIdentity !== null) {
        profileIdentity = readyIdentity;
        await receiptEvent("generation.ready", {
          generationId: nextId,
          pipelineId: readyIdentity.pipelineId,
          profileId: readyIdentity.profileId,
          profileHash: readyIdentity.profileHash,
          configurationHash: readyIdentity.configurationHash,
        });
      }
      openCaptureAcceptance(nextId);
      sequence = 0;
      sourceFrameBase = null;
      timestampBase = 0n;
      candidateGraph.beginGeneration(nextId, generationCaptureOptions());
      remote = "pending";
      route = "native";
      return snapshot();
    } catch (error) {
      if (candidateTransportClosed) {
        throw error;
      }
      if (!isCurrent()) {
        closeClient(candidateClient);
        return snapshot();
      }
      remote = "degraded";
      route = "native";
      clearGeneration();
      candidateGraph.fallback({ reasonCode: "WORKER_CRASH" });
      closeClient(candidateClient);
      client = null;
      throw error;
    }
  }

  async function startGeneration(nextId, nextInvocationMode = invocationMode) {
    requireGenerationId(nextId);
    requireInvocationMode(nextInvocationMode);
    if (!client || remote === "disconnected" || remote === "degraded") {
      throw new Error("remote client is not ready");
    }
    if (generationId !== null) {
      throw new Error("a generation is already active");
    }
    remote = "loading";
    notify({ capture, route, remote, generationId: null });
    const generationReady = await client.startGeneration(nextId);
    invocationMode = nextInvocationMode;
    generationEpoch += 1;
    generationId = nextId;
    const readyIdentity = receiptIdentity(generationReady);
    if (readyIdentity !== null) {
      profileIdentity = readyIdentity;
      await receiptEvent("generation.ready", {
        generationId: nextId,
        pipelineId: readyIdentity.pipelineId,
        profileId: readyIdentity.profileId,
        profileHash: readyIdentity.profileHash,
        configurationHash: readyIdentity.configurationHash,
      });
    }
    openCaptureAcceptance(nextId);
    sequence = 0;
    sourceFrameBase = null;
    timestampBase = 0n;
    graph.beginGeneration(nextId, generationCaptureOptions());
    route = "native";
    remote = "pending";
    return snapshot();
  }

  async function selectProfile(expectedProfile, nextInvocationMode = "live") {
    if (!client || remote !== "ready" || generationId !== null) {
      throw new Error("profile selection requires an idle ready remote session");
    }
    if (
      expectedProfile === null ||
      typeof expectedProfile !== "object" ||
      typeof expectedProfile.profileId !== "string"
    ) {
      throw new TypeError("expectedProfile must identify a catalog profile");
    }
    requireInvocationMode(nextInvocationMode);
    remote = "selecting";
    notify({ capture, route, remote, generationId: null });
    try {
      const selected = await client.selectProfile(
        expectedProfile.profileId,
        expectedProfile,
      );
      const selectedIdentity = receiptIdentity(selected);
      if (selectedIdentity !== null) {
        profileIdentity = selectedIdentity;
      }
      invocationMode = nextInvocationMode;
      remote = "ready";
      notify({ capture, route, remote, generationId: null });
      return snapshot();
    } catch (error) {
      remote = "degraded";
      route = "native";
      notify({
        capture,
        route,
        remote,
        generationId: null,
        error: errorMessage(error),
      });
      throw error;
    }
  }

  async function endGeneration(endingId) {
    requireGenerationId(endingId);
    if (endingId !== generationId) {
      throw new Error("generation is not active");
    }
    const endingIdentity = profileIdentity;
    const endingEpoch = generationEpoch;
    closeCaptureAcceptance(endingId, endingEpoch);
    releaseBufferedPreview(endingId, endingEpoch);
    graph.endGeneration(endingId);
    remote = "draining";
    try {
      await client.endGeneration(endingId);
    } catch (error) {
      if (endingEpoch !== generationEpoch || endingId !== generationId) {
        return snapshot();
      }
      handlingFallback = true;
      try {
        graph.cancelGeneration(endingId, "WORKER_CRASH");
      } finally {
        handlingFallback = false;
      }
      route = "native";
      remote = "degraded";
      clearGeneration();
      notify({
        route,
        remote,
        generationId: null,
        error: errorMessage(error),
      });
      throw error;
    }
    if (endingEpoch !== generationEpoch || endingId !== generationId) {
      return snapshot();
    }
    try {
      await boundedDrain(graph.drainGeneration(endingId));
    } catch (error) {
      if (endingEpoch !== generationEpoch || endingId !== generationId) {
        return snapshot();
      }
      handlingFallback = true;
      try {
        graph.cancelGeneration(endingId, "QUEUE_OVERFLOW");
      } finally {
        handlingFallback = false;
      }
      route = "native";
      remote = "degraded";
      clearGeneration();
      notify({
        route,
        remote,
        generationId: null,
        error: errorMessage(error),
      });
      throw error;
    }
    if (endingEpoch !== generationEpoch || endingId !== generationId) {
      return snapshot();
    }
    handlingFallback = true;
    try {
      graph.completeGeneration(endingId);
    } finally {
      handlingFallback = false;
    }
    route = "native";
    remote = "ready";
    if (endingIdentity !== null) {
      await flushReceiptOutputSummary(endingId, endingIdentity);
      await receiptNoStaleOutput(endingId, endingIdentity);
      await receiptEvent("generation.terminal", {
        generationId: endingId,
        pipelineId: endingIdentity.pipelineId,
        endTriggered: invocationMode === "buffered_end",
      });
    }
    clearGeneration();
    notify({ route, remote, generationId: null });
    return snapshot();
  }

  async function cancelGeneration(cancelingId) {
    requireGenerationId(cancelingId);
    if (cancelingId !== generationId) {
      throw new Error("generation is not active");
    }
    const cancelingIdentity = profileIdentity;
    generationEpoch += 1;
    handlingFallback = true;
    try {
      graph.cancelGeneration(cancelingId);
    } finally {
      handlingFallback = false;
    }
    route = "native";
    remote = "canceling";
    clearGeneration();
    notify({ route, remote, generationId: null });
    try {
      await client.cancelGeneration(cancelingId);
      remote = "ready";
    } catch (error) {
      remote = "degraded";
      notify({
        route,
        remote,
        generationId: null,
        error: errorMessage(error),
      });
      throw error;
    }
    if (cancelingIdentity !== null) {
      await flushReceiptOutputSummary(cancelingId, cancelingIdentity);
      await receiptNoStaleOutput(cancelingId, cancelingIdentity);
      await receiptEvent("generation.terminal", {
        generationId: cancelingId,
        pipelineId: cancelingIdentity.pipelineId,
        endTriggered: false,
      });
    }
    notify({ route, remote, generationId: null });
    return snapshot();
  }

  async function stop() {
    if (stopping || capture === "stopped") {
      return snapshot();
    }
    stopping = true;
    connectionEpoch += 1;
    const stopEpoch = graphEpoch + 1;
    graphEpoch = stopEpoch;
    const stoppingGraph = graph;
    const stoppingClient = client;
    graph = null;
    client = null;
    offscreenEpoch = null;
    try {
      const currentGenerationId = generationId;
      if (currentGenerationId !== null) {
        stoppingGraph?.cancelGeneration(currentGenerationId);
        cancelClientGeneration(currentGenerationId, stoppingClient);
      }
      route = "native";
      clearGeneration();
      captureCreditFrames = 4;
      invocationMode = null;
      profileIdentity = null;
      closeClient(stoppingClient);
      await stoppingGraph?.stop();
      if (graphEpoch === stopEpoch) {
        capture = "stopped";
        remote = "disconnected";
      }
      return snapshot();
    } finally {
      stopping = false;
    }
  }

  async function handleMessage(message, sender, extensionId) {
    if (sender?.id !== extensionId || message?.target !== "offscreen") {
      return null;
    }
    try {
      let state;
      if (message.type === "offscreen.status") {
        state = snapshotWithEpoch();
      } else if (message.type === "offscreen.native.start") {
        state = await startNative(message);
      } else if (message.type === "offscreen.remote.connect") {
        state = await connectRemote(message);
      } else if (message.type === "offscreen.generation.start") {
        state = await startGeneration(message.generationId, message.invocationMode);
      } else if (message.type === "offscreen.generation.end") {
        state = await endGeneration(message.generationId);
      } else if (message.type === "offscreen.generation.cancel") {
        state = await cancelGeneration(message.generationId);
      } else if (message.type === "offscreen.exp005.inject-failure") {
        state = await injectExp005Failure(message.generationId);
      } else if (message.type === "offscreen.receipt.configure") {
        state = await configureReceipt(message.enabled);
      } else if (message.type === "offscreen.model.select") {
        state = await selectProfile(
          message.expectedProfile,
          message.invocationMode,
        );
      } else if (message.type === "offscreen.stop") {
        state = await stop();
      } else {
        return null;
      }
      return { ok: true, state };
    } catch (error) {
      return { ok: false, state: snapshot(), error: errorMessage(error) };
    }
  }

  return Object.freeze({ handleMessage, snapshot, stop });
}

export function installOffscreenMessageListener(runtime, chromeApi) {
  const listener = (message, sender, sendResponse) => {
    if (
      sender?.id !== chromeApi.runtime.id ||
      sender.url !== chromeApi.runtime.getURL("src/background.js") ||
      message?.target !== "offscreen"
    ) {
      return false;
    }
    Promise.resolve(runtime.handleMessage(message, sender, chromeApi.runtime.id)).then(
      (response) => sendResponse(response),
      (error) => sendResponse({ ok: false, error: errorMessage(error) }),
    );
    return true;
  };
  chromeApi.runtime.onMessage.addListener(listener);
  return listener;
}
