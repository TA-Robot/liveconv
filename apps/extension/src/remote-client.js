import { decodeServerEvent, encodeControlMessage } from "./protocol/control.js";
import { decodePcmFrame, encodePcmFrame, frameV1 } from "./protocol/frame.js";

const UINT32_MAX = 0xffff_ffff;
const DEFAULT_UPLINK_FRAMES = Math.floor(250 / 20);
const DEFAULT_GENERATION_START_TIMEOUT_MILLISECONDS = 190_000;
const MAXIMUM_GENERATION_START_TIMEOUT_MILLISECONDS = 300_000;
const RETIRED_REQUEST_LIMIT = 64;

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

function defaultRequestId() {
  return crypto.randomUUID();
}

function defaultSocketFactory(url) {
  return new WebSocket(url);
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function serverError(event) {
  const error = new Error(`${event.code}: ${event.message}`);
  error.code = event.code;
  error.recoverable = event.recoverable;
  error.requiredAction = event.required_action;
  return error;
}

export function createRemoteClient(options = {}) {
  const socketFactory = requireFunction(
    options.socketFactory ?? defaultSocketFactory,
    "socketFactory",
  );
  const requestIdFactory = requireFunction(
    options.requestIdFactory ?? defaultRequestId,
    "requestIdFactory",
  );
  const onFallback = requireFunction(
    options.onFallback ?? (() => {}),
    "onFallback",
  );
  const onTransportClosed = requireFunction(
    options.onTransportClosed ?? (() => {}),
    "onTransportClosed",
  );
  const onOutputFrame = requireFunction(
    options.onOutputFrame ?? (() => {}),
    "onOutputFrame",
  );
  const maximumBufferedBytes =
    options.maximumBufferedBytes ?? frameV1.frameLength * DEFAULT_UPLINK_FRAMES;
  if (!Number.isSafeInteger(maximumBufferedBytes) || maximumBufferedBytes <= 0) {
    throw new TypeError("maximumBufferedBytes must be a positive safe integer");
  }
  const requestTimeoutMilliseconds = options.requestTimeoutMilliseconds ?? 5_000;
  if (
    !Number.isSafeInteger(requestTimeoutMilliseconds) ||
    requestTimeoutMilliseconds <= 0
  ) {
    throw new TypeError(
      "requestTimeoutMilliseconds must be a positive safe integer",
    );
  }
  const generationStartTimeoutMilliseconds =
    options.generationStartTimeoutMilliseconds ??
    DEFAULT_GENERATION_START_TIMEOUT_MILLISECONDS;
  if (
    !Number.isSafeInteger(generationStartTimeoutMilliseconds) ||
    generationStartTimeoutMilliseconds <= 0 ||
    generationStartTimeoutMilliseconds >
      MAXIMUM_GENERATION_START_TIMEOUT_MILLISECONDS
  ) {
    throw new TypeError(
      "generationStartTimeoutMilliseconds must be between 1 and 300000",
    );
  }
  const setTimer = requireFunction(
    options.setTimer ?? globalThis.setTimeout,
    "setTimer",
  );
  const clearTimer = requireFunction(
    options.clearTimer ?? globalThis.clearTimeout,
    "clearTimer",
  );

  let socket = null;
  let sessionId = null;
  let transport = "disconnected";
  let generationState = "idle";
  let generationId = null;
  let lastGenerationId = -1;
  let profileId = null;
  let profileHash = null;
  let configurationHash = null;
  let pipelineId = null;
  let clockId = null;
  let limits = null;
  let connectOperation = null;
  let connectDeferred = null;
  let closing = false;
  let selectingProfile = false;
  let connectionEpoch = 0;
  let notifiedTransportEpoch = -1;
  const pending = new Map();
  const retiredRequests = new Map();

  function snapshot() {
    return Object.freeze({
      transport,
      generationState,
      generationId,
      profileId,
      profileHash,
      configurationHash,
      pipelineId,
      clockId,
      limits: limits === null ? null : Object.freeze({ ...limits }),
    });
  }

  function rejectPending(error) {
    const requests = [...pending.values()];
    pending.clear();
    selectingProfile = false;
    for (const request of requests) {
      clearTimer(request.timer);
      request.reject(error);
    }
  }

  function retireRequest(requestId, request) {
    retiredRequests.set(requestId, {
      expectedType: request.expectedType,
      metadata: request.metadata,
      type: request.type,
    });
    while (retiredRequests.size > RETIRED_REQUEST_LIMIT) {
      retiredRequests.delete(retiredRequests.keys().next().value);
    }
  }

  function rejectGenerationRequests(canceledGenerationId, error) {
    for (const [requestId, request] of pending) {
      if (
        request.metadata.generationId === canceledGenerationId &&
        request.type !== "generation.cancel"
      ) {
        pending.delete(requestId);
        clearTimer(request.timer);
        retireRequest(requestId, request);
        request.reject(error);
      }
    }
  }

  function rejectConnect(error) {
    if (connectDeferred) {
      connectDeferred.reject(error);
      connectDeferred = null;
    }
  }

  function invalidateGeneration(event) {
    if (generationId === null || generationState === "failed") {
      return false;
    }
    const failure = new Error(
      event?.message ?? `generation ${generationId} was invalidated`,
    );
    failure.code = event?.reason_code ?? "GENERATION_FAILED";
    rejectGenerationRequests(generationId, failure);
    generationState = "failed";
    onFallback(event);
    return true;
  }

  function closeTransport(code, reason) {
    if (socket && socket.readyState !== 2 && socket.readyState !== 3) {
      socket.close(code, reason);
    }
  }

  function notifyTransportClosed(epoch, event = {}) {
    if (
      closing ||
      epoch !== connectionEpoch ||
      notifiedTransportEpoch === epoch
    ) {
      return false;
    }
    notifiedTransportEpoch = epoch;
    onTransportClosed({
      ...event,
      connectionEpoch: epoch,
      reasonCode: "TRANSPORT_CLOSED",
    });
    return true;
  }

  function protocolFailure(error) {
    const failure =
      error instanceof Error ? error : new Error("remote protocol failure");
    invalidateGeneration({
      generation_id: generationId,
      reason_code: "UNSUPPORTED_AUDIO",
      message: failure.message,
    });
    rejectConnect(failure);
    rejectPending(failure);
    transport = "degraded";
    closeTransport(1002, "protocol error");
  }

  function request(type, fields, expectedType, metadata = {}) {
    if (!socket || socket.readyState !== 1) {
      throw new Error("remote transport is not open");
    }
    const requestId = requestIdFactory();
    if (pending.has(requestId)) {
      throw new Error(`duplicate request ID: ${requestId}`);
    }
    const deferred = createDeferred();
    const requestEntry = {
      ...deferred,
      type,
      expectedType,
      metadata,
      timer: null,
    };
    requestEntry.timer = setTimer(() => {
      if (pending.delete(requestId)) {
        retireRequest(requestId, requestEntry);
        const error = new Error(`${type} timed out`);
        error.name = "TimeoutError";
        error.code = "REQUEST_TIMEOUT";
        requestEntry.reject(error);
        if (type === "session.attach") {
          rejectConnect(error);
          transport = "degraded";
          closeTransport(1008, "attach timeout");
        } else if (
          type === "generation.start" &&
          generationId === metadata.generationId
        ) {
          invalidateGeneration({
            generation_id: generationId,
            reason_code: "MODEL_TIMEOUT",
            message: `generation ${generationId} did not become ready within ${generationStartTimeoutMilliseconds} ms`,
          });
          transport = "degraded";
          closeTransport(1008, "generation start timeout");
        } else if (type === "model.select") {
          selectingProfile = false;
        }
      }
    }, type === "generation.start"
      ? generationStartTimeoutMilliseconds
      : requestTimeoutMilliseconds);
    pending.set(requestId, requestEntry);
    try {
      socket.send(
        encodeControlMessage({
          type,
          protocol_version: 1,
          request_id: requestId,
          session_id: sessionId,
          ...fields,
        }),
      );
    } catch (error) {
      pending.delete(requestId);
      clearTimer(requestEntry.timer);
      deferred.reject(error);
      throw error;
    }
    return deferred.promise;
  }

  function verifyResponse(event, requestEntry) {
    if (event.type !== requestEntry.expectedType) {
      throw new Error(
        `unexpected ${event.type} response for ${requestEntry.type}`,
      );
    }
    if (event.session_id !== sessionId) {
      throw new Error("server response session_id does not match the session");
    }
    const expectedGenerationId = requestEntry.metadata.generationId;
    if (
      expectedGenerationId !== undefined &&
      event.generation_id !== expectedGenerationId
    ) {
      throw new Error("server response generation_id does not match the request");
    }
    const expectedProfile = requestEntry.metadata.expectedProfile;
    if (expectedProfile) {
      for (const [eventField, expectedField] of [
        ["profile_id", "profileId"],
        ["profile_hash", "profileHash"],
        ["configuration_hash", "configurationHash"],
        ["pipeline_id", "pipelineId"],
      ]) {
        if (
          expectedProfile[expectedField] !== undefined &&
          event[eventField] !== expectedProfile[expectedField]
        ) {
          throw new Error(
            `server response ${eventField} does not match the selected profile`,
          );
        }
      }
    }
    const expectedLimits = requestEntry.metadata.expectedLimits;
    if (
      expectedLimits &&
      (event.limits?.ingress_budget_ms !== expectedLimits.ingressBudgetMs ||
        event.limits?.max_ingress_frames !== expectedLimits.maxIngressFrames)
    ) {
      throw new Error("session.ready limits do not match session creation");
    }
  }

  function applyResponse(event, requestEntry) {
    verifyResponse(event, requestEntry);
    if (event.type === "session.ready") {
      profileId = event.profile_id;
      profileHash = event.profile_hash;
      configurationHash = event.configuration_hash;
      pipelineId = event.pipeline_id;
      clockId = event.clock_id;
      limits = { ...event.limits };
      transport = "ready";
    } else if (event.type === "model.selected") {
      profileId = event.profile_id;
      profileHash = event.profile_hash;
      configurationHash = event.configuration_hash;
      pipelineId = event.pipeline_id;
      selectingProfile = false;
    } else if (event.type === "generation.ready") {
      if (event.pipeline_id !== pipelineId) {
        throw new Error("generation.ready changed the selected pipeline");
      }
      if (
        event.profile_id !== profileId ||
        event.profile_hash !== profileHash ||
        event.configuration_hash !== configurationHash
      ) {
        throw new Error("generation.ready changed the selected profile identity");
      }
      if (generationState === "starting") {
        generationState = "streaming";
      }
    } else if (
      event.type === "generation.completed" ||
      event.type === "generation.canceled"
    ) {
      if (event.pipeline_id !== pipelineId) {
        throw new Error("terminal response changed the generation pipeline");
      }
      generationState = "idle";
      generationId = null;
    } else if (event.type === "session.closed") {
      closing = true;
      transport = "closed";
      generationState = "idle";
      generationId = null;
    }
  }

  function handleErrorEvent(event) {
    const error = serverError(event);
    if (event.request_id) {
      const requestEntry = pending.get(event.request_id);
      if (requestEntry) {
        pending.delete(event.request_id);
        clearTimer(requestEntry.timer);
        if (requestEntry.type === "model.select") {
          selectingProfile = false;
        }
        requestEntry.reject(error);
      }
    }
    if (
      event.required_action === "fallback" &&
      (event.generation_id === undefined || event.generation_id === generationId)
    ) {
      invalidateGeneration({
        ...event,
        generation_id: event.generation_id ?? generationId,
        reason_code: event.code,
      });
    }
    if (event.required_action === "close_session") {
      transport = "degraded";
      rejectPending(error);
      closeTransport(1008, "server closed session");
    }
  }

  function handleServerEvent(event) {
    if (event.type === "fallback.required") {
      if (
        event.session_id === sessionId &&
        event.generation_id === generationId &&
        event.pipeline_id === pipelineId
      ) {
        invalidateGeneration(event);
      }
      return;
    }
    if (event.type === "error") {
      handleErrorEvent(event);
      return;
    }
    const requestEntry = pending.get(event.request_id);
    if (!requestEntry) {
      if (event.type === "pong") {
        return;
      }
      const retired = retiredRequests.get(event.request_id);
      if (retired) {
        verifyResponse(event, retired);
        retiredRequests.delete(event.request_id);
        return;
      }
      throw new Error(`unsolicited server event: ${event.type}`);
    }
    pending.delete(event.request_id);
    clearTimer(requestEntry.timer);
    try {
      applyResponse(event, requestEntry);
      requestEntry.resolve(event);
      if (event.type === "session.closed") {
        closeTransport(1000, "session closed");
      }
    } catch (error) {
      if (requestEntry.type === "model.select") {
        selectingProfile = false;
      }
      requestEntry.reject(error);
      throw error;
    }
  }

  function handleBinary(data) {
    if (
      generationId === null ||
      (generationState !== "streaming" && generationState !== "draining")
    ) {
      return;
    }
    let frame;
    try {
      frame = decodePcmFrame(data);
    } catch (error) {
      invalidateGeneration({
        generation_id: generationId,
        reason_code: "UNSUPPORTED_AUDIO",
        message: error instanceof Error ? error.message : "invalid PCM frame",
      });
      return;
    }
    if (frame.header.kind !== 2) {
      invalidateGeneration({
        generation_id: generationId,
        reason_code: "UNSUPPORTED_AUDIO",
      });
      return;
    }
    if (frame.header.generation_id < generationId) {
      return;
    }
    if (frame.header.generation_id !== generationId) {
      invalidateGeneration({
        generation_id: generationId,
        received_generation_id: frame.header.generation_id,
        reason_code: "STALE_GENERATION",
      });
      return;
    }
    onOutputFrame(frame);
  }

  function onMessage(event) {
    if (typeof event.data !== "string") {
      handleBinary(event.data);
      return;
    }
    try {
      handleServerEvent(decodeServerEvent(event.data));
    } catch (error) {
      protocolFailure(error);
    }
  }

  function onSocketError(event, epoch, candidateSocket) {
    if (epoch !== connectionEpoch || socket !== candidateSocket) {
      return;
    }
    const error = event?.error instanceof Error
      ? event.error
      : new Error("remote WebSocket failed");
    invalidateGeneration({
      generation_id: generationId,
      reason_code: "WORKER_CRASH",
      message: error.message,
    });
    transport = "degraded";
    rejectConnect(error);
    rejectPending(error);
    notifyTransportClosed(epoch, { message: error.message });
  }

  function onSocketClose(event, epoch, candidateSocket) {
    if (epoch !== connectionEpoch || socket !== candidateSocket) {
      return;
    }
    const wasClosing = closing;
    const error = new Error(
      `remote WebSocket closed (${event?.code ?? "unknown"})`,
    );
    if (!wasClosing) {
      invalidateGeneration({
        generation_id: generationId,
        reason_code: "WORKER_CRASH",
      });
    }
    rejectConnect(error);
    rejectPending(error);
    transport = wasClosing ? "closed" : "disconnected";
    socket = null;
    connectOperation = null;
    if (!wasClosing) {
      notifyTransportClosed(epoch, {
        closeCode: event?.code,
        message: error.message,
      });
    }
  }

  function connect({
    url,
    sessionId: nextSessionId,
    ticket,
    expectedProfile,
    expectedLimits,
  } = {}) {
    if (transport === "ready") {
      if (nextSessionId === sessionId) {
        return Promise.resolve();
      }
      return Promise.reject(new Error("a different remote session is active"));
    }
    if (connectOperation) {
      return connectOperation;
    }
    if (typeof url !== "string" || url.length === 0) {
      return Promise.reject(new TypeError("url must be a non-empty string"));
    }

    sessionId = nextSessionId;
    transport = "connecting";
    closing = false;
    const candidateEpoch = connectionEpoch + 1;
    connectionEpoch = candidateEpoch;
    const deferred = createDeferred();
    connectDeferred = deferred;
    const operation = deferred.promise.finally(() => {
      if (connectDeferred === deferred) {
        connectDeferred = null;
      }
      if (connectOperation === operation) {
        connectOperation = null;
      }
    });
    connectOperation = operation;
    try {
      const candidateSocket = socketFactory(url);
      if (candidateSocket === null || typeof candidateSocket !== "object") {
        throw new TypeError("socketFactory must return a WebSocket-like object");
      }
      socket = candidateSocket;
      candidateSocket.binaryType = "arraybuffer";
      candidateSocket.addEventListener("message", (event) => {
        if (
          candidateEpoch === connectionEpoch &&
          socket === candidateSocket
        ) {
          onMessage(event);
        }
      });
      candidateSocket.addEventListener("error", (event) => {
        onSocketError(event, candidateEpoch, candidateSocket);
      });
      candidateSocket.addEventListener("close", (event) => {
        onSocketClose(event, candidateEpoch, candidateSocket);
      });
      candidateSocket.addEventListener("open", () => {
        if (
          candidateEpoch !== connectionEpoch ||
          socket !== candidateSocket
        ) {
          return;
        }
        let attach;
        try {
          attach = request(
            "session.attach",
            { ticket },
            "session.ready",
            { expectedLimits, expectedProfile },
          );
        } catch (error) {
          deferred.reject(error);
          protocolFailure(error);
          return;
        }
        attach.then(deferred.resolve, deferred.reject);
      });
    } catch (error) {
      socket = null;
      transport = "disconnected";
      connectDeferred = null;
      deferred.reject(error);
    }
    return connectOperation ?? deferred.promise;
  }

  function selectProfile(nextProfileId, expectedProfile) {
    if (transport !== "ready") {
      throw new Error("remote transport is not ready");
    }
    if (generationState !== "idle" || generationId !== null) {
      throw new Error("profile selection is allowed only at a generation boundary");
    }
    if (selectingProfile) {
      throw new Error("profile selection is already pending");
    }
    selectingProfile = true;
    try {
      return request(
        "model.select",
        { profile_id: nextProfileId },
        "model.selected",
        { expectedProfile },
      );
    } catch (error) {
      selectingProfile = false;
      throw error;
    }
  }

  function startGeneration(nextGenerationId) {
    requireGenerationId(nextGenerationId);
    if (transport !== "ready") {
      throw new Error("remote transport is not ready");
    }
    if (generationState !== "idle" || generationId !== null) {
      throw new Error("a generation is already active");
    }
    if (selectingProfile) {
      throw new Error("model selection must be acknowledged before generation start");
    }
    if (nextGenerationId <= lastGenerationId) {
      throw new Error("generationId must strictly increase");
    }
    generationId = nextGenerationId;
    lastGenerationId = nextGenerationId;
    generationState = "starting";
    try {
      const operation = request(
        "generation.start",
        { generation_id: nextGenerationId },
        "generation.ready",
        {
          generationId: nextGenerationId,
          expectedProfile: {
            profileId,
            profileHash,
            configurationHash,
            pipelineId,
          },
        },
      );
      return operation.catch((error) => {
        if (
          generationId === nextGenerationId &&
          generationState === "starting"
        ) {
          invalidateGeneration({
            generation_id: nextGenerationId,
            reason_code: error?.code ?? "MODEL_UNAVAILABLE",
            message: error instanceof Error ? error.message : undefined,
          });
        }
        throw error;
      });
    } catch (error) {
      generationState = "failed";
      throw error;
    }
  }

  function endGeneration(endingGenerationId) {
    requireGenerationId(endingGenerationId);
    if (
      generationState !== "streaming" ||
      generationId !== endingGenerationId
    ) {
      throw new Error("generation is not streaming");
    }
    generationState = "draining";
    try {
      return request(
        "generation.end",
        { generation_id: endingGenerationId },
        "generation.completed",
        { generationId: endingGenerationId },
      );
    } catch (error) {
      generationState = "failed";
      throw error;
    }
  }

  function cancelGeneration(canceledGenerationId) {
    requireGenerationId(canceledGenerationId);
    if (
      generationId !== canceledGenerationId ||
      !["starting", "streaming", "draining"].includes(generationState)
    ) {
      throw new Error("generation is not cancelable");
    }
    const canceled = new Error(
      `generation ${canceledGenerationId} was superseded by cancellation`,
    );
    canceled.name = "AbortError";
    canceled.code = "GENERATION_CANCELED";
    rejectGenerationRequests(canceledGenerationId, canceled);
    generationState = "canceling";
    try {
      return request(
        "generation.cancel",
        { generation_id: canceledGenerationId },
        "generation.canceled",
        { generationId: canceledGenerationId },
      );
    } catch (error) {
      generationState = "failed";
      throw error;
    }
  }

  function sendFrame(frame) {
    if (
      transport !== "ready" ||
      generationState !== "streaming" ||
      generationId === null
    ) {
      return false;
    }
    let encoded;
    let decoded;
    if (frame?.header && frame?.samples) {
      decoded = frame;
      encoded = encodePcmFrame(frame.header, frame.samples);
    } else {
      decoded = decodePcmFrame(frame);
      encoded = frame;
    }
    if (
      decoded.header.kind !== 1 ||
      decoded.header.generation_id !== generationId
    ) {
      return false;
    }
    const bufferedAmount = Number(socket.bufferedAmount ?? 0);
    if (
      !Number.isFinite(bufferedAmount) ||
      bufferedAmount < 0 ||
      bufferedAmount + encoded.byteLength > maximumBufferedBytes
    ) {
      invalidateGeneration({
        generation_id: generationId,
        reason_code: "QUEUE_OVERFLOW",
        message: "remote uplink budget exceeded",
      });
      transport = "degraded";
      closeTransport(1008, "uplink queue overflow");
      return false;
    }
    socket.send(encoded);
    return true;
  }

  function close() {
    if (!socket || transport === "closed" || transport === "disconnected") {
      return Promise.resolve();
    }
    if (transport !== "ready") {
      closing = true;
      rejectConnect(new Error("remote WebSocket was closed by the client"));
      closeTransport(1000, "client closed");
      return Promise.resolve();
    }
    if (generationId !== null) {
      invalidateGeneration({
        generation_id: generationId,
        reason_code: "WORKER_CRASH",
      });
    }
    closing = true;
    return request("session.close", {}, "session.closed");
  }

  return Object.freeze({
    cancelGeneration,
    close,
    connect,
    endGeneration,
    selectProfile,
    sendFrame,
    snapshot,
    startGeneration,
  });
}
