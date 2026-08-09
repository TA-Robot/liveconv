const UINT32_MAX = 0xffff_ffff;
const SAMPLE_RATE = 48_000;

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

function errorMessage(error) {
  return error instanceof Error ? error.message : "Offscreen operation failed";
}

function defaultNowNanoseconds() {
  return BigInt(Math.round(performance.now() * 1_000_000));
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
  let graphEpoch = 0;
  let connectionEpoch = 0;

  function snapshot() {
    return Object.freeze({ capture, route, remote, generationId });
  }

  function notify(event) {
    Promise.resolve(
      sendMessage({ target: "background", type: "offscreen.event", event }),
    ).catch(() => {});
  }

  function clearGeneration() {
    generationId = null;
    sequence = 0;
    sourceFrameBase = null;
    timestampBase = 0n;
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

  function performFallback(event = {}) {
    if (handlingFallback || stopping) {
      return;
    }
    handlingFallback = true;
    try {
      const currentGenerationId = generationId;
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
  }

  function onCaptureFrame(frame) {
    if (frame.generationId !== generationId || generationId === null) {
      return;
    }
    if (sequence > UINT32_MAX) {
      performFallback({ reasonCode: "QUEUE_OVERFLOW" });
      return;
    }
    let sent = false;
    try {
      sent = client?.sendFrame({
        header: {
          kind: 1,
          flags: 0,
          generation_id: generationId,
          sequence,
          sample_rate: SAMPLE_RATE,
          channels: 1,
          samples_per_channel: 960,
          source_monotonic_ns: sourceTimestamp(frame.sourceFrame),
        },
        samples: frame.samples,
      });
    } catch (error) {
      performFallback({ reasonCode: "UNSUPPORTED_AUDIO", message: errorMessage(error) });
      return;
    }
    if (!sent && generationId !== null) {
      performFallback({ reasonCode: "INVALID_STATE" });
      return;
    }
    if (sent) {
      sequence += 1;
    }
  }

  function onOutputFrame(frame) {
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
    if (!graph?.enqueueRemoteFrame(alignedFrame) && generationId !== null) {
      performFallback({ reasonCode: "STALE_GENERATION" });
    }
  }

  function createGraph(candidateEpoch) {
    let candidate;
    const isCurrent = () =>
      graphEpoch === candidateEpoch && graph === candidate;
    candidate = audioGraphFactory({
      onCaptureFrame(event) {
        if (isCurrent()) {
          onCaptureFrame(event);
        }
      },
      onFallback(event) {
        if (isCurrent()) {
          performFallback(event);
        }
      },
      onRemoteReady(event) {
        if (!isCurrent() || event.generationId !== generationId) {
          return;
        }
        route = "remote";
        remote = "ready";
        notify({ route, remote, generationId });
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
      return snapshot();
    }
    const candidateEpoch = graphEpoch + 1;
    graphEpoch = candidateEpoch;
    capture = "starting";
    remote = "disconnected";
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
      return snapshot();
    } catch (error) {
      if (graphEpoch === candidateEpoch && graph === candidate) {
        capture = "stopped";
        graph = null;
      }
      throw error;
    }
  }

  async function connectRemote({ url, sessionId, ticket, generationId: nextId } = {}) {
    requireGenerationId(nextId);
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
    const isCurrent = () =>
      connectionEpoch === candidateEpoch &&
      client === candidateClient &&
      graph === candidateGraph;
    remote = "connecting";
    candidateClient = remoteClientFactory({
      onFallback(event) {
        if (isCurrent()) {
          performFallback(event);
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
      await candidateClient.connect({ url, sessionId, ticket });
      if (!isCurrent()) {
        closeClient(candidateClient);
        return snapshot();
      }
      await candidateClient.startGeneration(nextId);
      if (!isCurrent()) {
        closeClient(candidateClient);
        return snapshot();
      }
      generationEpoch += 1;
      generationId = nextId;
      sequence = 0;
      sourceFrameBase = null;
      timestampBase = 0n;
      candidateGraph.beginGeneration(nextId);
      remote = "pending";
      route = "native";
      return snapshot();
    } catch (error) {
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

  async function startGeneration(nextId) {
    requireGenerationId(nextId);
    if (!client || remote === "disconnected" || remote === "degraded") {
      throw new Error("remote client is not ready");
    }
    if (generationId !== null) {
      throw new Error("a generation is already active");
    }
    await client.startGeneration(nextId);
    generationEpoch += 1;
    generationId = nextId;
    sequence = 0;
    sourceFrameBase = null;
    timestampBase = 0n;
    graph.beginGeneration(nextId);
    route = "native";
    remote = "pending";
    return snapshot();
  }

  async function endGeneration(endingId) {
    requireGenerationId(endingId);
    if (endingId !== generationId) {
      throw new Error("generation is not active");
    }
    graph.endGeneration(endingId);
    const endingEpoch = generationEpoch;
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
    clearGeneration();
    notify({ route, remote, generationId: null });
    return snapshot();
  }

  async function cancelGeneration(cancelingId) {
    requireGenerationId(cancelingId);
    if (cancelingId !== generationId) {
      throw new Error("generation is not active");
    }
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
    try {
      const currentGenerationId = generationId;
      if (currentGenerationId !== null) {
        stoppingGraph?.cancelGeneration(currentGenerationId);
        cancelClientGeneration(currentGenerationId, stoppingClient);
      }
      route = "native";
      clearGeneration();
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
        state = snapshot();
      } else if (message.type === "offscreen.native.start") {
        state = await startNative(message);
      } else if (message.type === "offscreen.remote.connect") {
        state = await connectRemote(message);
      } else if (message.type === "offscreen.generation.start") {
        state = await startGeneration(message.generationId);
      } else if (message.type === "offscreen.generation.end") {
        state = await endGeneration(message.generationId);
      } else if (message.type === "offscreen.generation.cancel") {
        state = await cancelGeneration(message.generationId);
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
