import {
  normalizeGatewayUrl,
  websocketUrl,
} from "./gateway-url.js";

const CONFIGURATION_KEY = "liveconv.session-configuration.v1";
const ACTIVE_SESSION_KEY = "liveconv.active-session.v1";
const OFFSCREEN_PATH = "offscreen/offscreen.html";
const PROFILE_ID = /^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function requireMethod(value, owner, method) {
  if (value === null || typeof value !== "object") {
    throw new TypeError(`${owner} dependency must be an object`);
  }
  if (typeof value[method] !== "function") {
    throw new TypeError(`${owner}.${method} dependency must be a function`);
  }
}

function errorMessage(error) {
  return error instanceof Error ? error.message : "Extension operation failed";
}

function normalizeConfiguration(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("configuration must be an object");
  }
  const gatewayUrl = normalizeGatewayUrl(value.gatewayUrl);
  if (typeof value.profileId !== "string" || !PROFILE_ID.test(value.profileId)) {
    throw new TypeError("profileId has an invalid format");
  }
  const tokenBytes =
    typeof value.token === "string"
      ? new TextEncoder().encode(value.token).length
      : 0;
  if (tokenBytes < 32 || tokenBytes > 4_096) {
    throw new TypeError("session token must contain between 32 and 4096 bytes");
  }
  if (![...value.token].every((character) => {
    const code = character.charCodeAt(0);
    return code >= 0x21 && code <= 0x7e;
  })) {
    throw new TypeError("session token must contain printable ASCII only");
  }
  return Object.freeze({ gatewayUrl, profileId: value.profileId, token: value.token });
}

function publicConfiguration(configuration) {
  if (!configuration) {
    return Object.freeze({ configured: false, gatewayUrl: null, profileId: null });
  }
  return Object.freeze({
    configured: true,
    gatewayUrl: configuration.gatewayUrl,
    profileId: configuration.profileId,
  });
}

function requireSessionResponse(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway returned an invalid session response");
  }
  if (typeof value.session_id !== "string" || !UUID.test(value.session_id)) {
    throw new Error("gateway returned an invalid session_id");
  }
  if (
    typeof value.ticket !== "string" ||
    value.ticket.length === 0 ||
    new TextEncoder().encode(value.ticket).length > 4_096
  ) {
    throw new Error("gateway returned an invalid one-use ticket");
  }
  if (
    typeof value.websocket_path !== "string" ||
    value.websocket_path.length > 2_048 ||
    !value.websocket_path.startsWith("/") ||
    value.websocket_path.startsWith("//") ||
    /[\\\u0000-\u001f\u007f]/u.test(value.websocket_path) ||
    /%5c/iu.test(value.websocket_path)
  ) {
    throw new Error("gateway returned an invalid websocket_path");
  }
  return value;
}

function authorizedHeaders(token) {
  return Object.freeze({
    "content-type": "application/json",
    authorization: ["Bearer", token].join(" "),
  });
}

async function jsonResponse(response, operation) {
  if (!response?.ok) {
    const status = Number.isInteger(response?.status) ? response.status : "unknown";
    throw new Error(`${operation} failed with HTTP ${status}`);
  }
  try {
    return await response.json();
  } catch {
    throw new Error(`${operation} returned invalid JSON`);
  }
}

export function createBrowserRuntime(options = {}) {
  const chromeApi = options.chromeApi;
  const fetchFn = options.fetchFn ?? globalThis.fetch;
  requireMethod(chromeApi?.runtime, "chrome.runtime", "getURL");
  requireMethod(chromeApi?.runtime, "chrome.runtime", "getContexts");
  requireMethod(chromeApi?.runtime, "chrome.runtime", "sendMessage");
  requireMethod(chromeApi?.offscreen, "chrome.offscreen", "createDocument");
  requireMethod(chromeApi?.offscreen, "chrome.offscreen", "closeDocument");
  requireMethod(chromeApi?.tabCapture, "chrome.tabCapture", "getMediaStreamId");
  requireMethod(chromeApi?.tabs, "chrome.tabs", "query");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "get");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "set");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "remove");
  if (typeof fetchFn !== "function") {
    throw new TypeError("fetchFn must be a function");
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
  const setTimer = options.setTimer ?? globalThis.setTimeout;
  const clearTimer = options.clearTimer ?? globalThis.clearTimeout;
  if (typeof setTimer !== "function" || typeof clearTimer !== "function") {
    throw new TypeError("timer dependencies must be functions");
  }

  let capture = "stopped";
  let requestedCapture = "stopped";
  let route = "native";
  let remote = "disconnected";
  let generationId = null;
  let lastError = null;
  let transition = Promise.resolve();
  let cleanupBarrier = Promise.resolve();
  let requestedTransition = transition;
  let creatingOffscreen = null;
  let capturedTabId = null;
  let activeStartController = null;
  let stopOperation = null;
  let sessionMetadataKnown = false;
  let currentSession = null;
  let sessionMetadataEpoch = 0;
  const requestControllers = new Set();

  function createStartController() {
    const canceledMarker = Object.freeze({});
    let canceled = false;
    let cancel;
    const cancellation = new Promise((resolve) => {
      cancel = () => {
        if (!canceled) {
          canceled = true;
          resolve(canceledMarker);
        }
      };
    });
    return Object.freeze({
      cancel,
      get canceled() {
        return canceled;
      },
      async wait(operation) {
        return Promise.race([Promise.resolve(operation), cancellation]);
      },
      canceledMarker,
    });
  }

  async function waitForStart(controller, operation) {
    const result = await controller.wait(operation);
    if (result === controller.canceledMarker) {
      const error = new Error("capture start was canceled");
      error.name = "AbortError";
      throw error;
    }
    return result;
  }

  async function fetchWithDeadline(url, requestOptions, operation) {
    const controller = new AbortController();
    requestControllers.add(controller);
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimer(() => {
        controller.abort();
        const error = new Error(`${operation} timed out`);
        error.name = "TimeoutError";
        reject(error);
      }, requestTimeoutMilliseconds);
    });
    const aborted = new Promise((_, reject) => {
      controller.signal.addEventListener(
        "abort",
        () => {
          const error = new Error(`${operation} was canceled`);
          error.name = "AbortError";
          reject(error);
        },
        { once: true },
      );
    });
    try {
      return await Promise.race([
        Promise.resolve(fetchFn(url, { ...requestOptions, signal: controller.signal })),
        timeout,
        aborted,
      ]);
    } finally {
      clearTimer(timer);
      requestControllers.delete(controller);
    }
  }

  function abortRequests() {
    for (const controller of requestControllers) {
      controller.abort();
    }
  }

  async function activeTabId(startController = null) {
    const operation = chromeApi.tabs.query({ active: true, currentWindow: true });
    const tabs = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const tabId = tabs?.[0]?.id;
    if (!Number.isInteger(tabId) || tabId < 0) {
      throw new Error("the active tab is unavailable");
    }
    return tabId;
  }

  async function storedConfiguration(startController = null) {
    const operation = chromeApi.storage.session.get(CONFIGURATION_KEY);
    const stored = startController
      ? await waitForStart(startController, operation)
      : await operation;
    return stored?.[CONFIGURATION_KEY] ?? null;
  }

  async function activeSession(startController = null) {
    if (sessionMetadataKnown) {
      return currentSession;
    }
    const readEpoch = sessionMetadataEpoch;
    const operation = chromeApi.storage.session.get(ACTIVE_SESSION_KEY);
    const stored = startController
      ? await waitForStart(startController, operation)
      : await operation;
    if (!sessionMetadataKnown && sessionMetadataEpoch === readEpoch) {
      const recovered = stored?.[ACTIVE_SESSION_KEY] ?? null;
      currentSession = recovered ? Object.freeze({ ...recovered }) : null;
      sessionMetadataKnown = true;
    }
    return currentSession;
  }

  function persistSessionMetadata(session, epoch) {
    const operation = session
      ? chromeApi.storage.session.set({ [ACTIVE_SESSION_KEY]: session })
      : chromeApi.storage.session.remove(ACTIVE_SESSION_KEY);
    Promise.resolve(operation).then(
      () => {
        if (epoch !== sessionMetadataEpoch) {
          void reconcileSessionMetadata();
        }
      },
      () => {},
    );
    return operation;
  }

  function setActiveSession(session) {
    currentSession = session ? Object.freeze({ ...session }) : null;
    sessionMetadataKnown = true;
    sessionMetadataEpoch += 1;
    return persistSessionMetadata(currentSession, sessionMetadataEpoch);
  }

  async function reconcileSessionMetadata() {
    if (!sessionMetadataKnown) {
      return;
    }
    const epoch = sessionMetadataEpoch;
    const session = currentSession;
    try {
      await persistSessionMetadata(session, epoch);
    } catch {
      // The foreground mutation reports its own failure; stale repair is best effort.
    }
  }

  async function hasOffscreenDocument(startController = null) {
    const operation = chromeApi.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [chromeApi.runtime.getURL(OFFSCREEN_PATH)],
    });
    const contexts = startController
      ? await waitForStart(startController, operation)
      : await operation;
    return Array.isArray(contexts) && contexts.length > 0;
  }

  function cleanupCanceledStart(controller) {
    if (!controller.canceled || requestedCapture !== "stopped") {
      return;
    }
    const cleanup = async () => {
      if (!controller.canceled || requestedCapture !== "stopped") {
        return;
      }
      try {
        const operation = chromeApi.runtime.sendMessage({
          type: "offscreen.stop",
          target: "offscreen",
        });
        Promise.resolve(operation).catch(() => {});
      } catch {
        // A canceled start may settle after its Offscreen Document was closed.
      }
      if (!controller.canceled || requestedCapture !== "stopped") {
        return;
      }
      try {
        await chromeApi.offscreen.closeDocument();
      } catch {
        // Late cleanup is best effort when no Offscreen Document remains.
      }
    };
    const operation = cleanupBarrier.then(cleanup, cleanup);
    cleanupBarrier = operation;
  }

  async function waitForCleanupBarrier() {
    let pending;
    do {
      pending = cleanupBarrier;
      await pending;
    } while (pending !== cleanupBarrier);
  }

  async function ensureOffscreenDocument(startController) {
    if (await hasOffscreenDocument(startController)) {
      return;
    }
    if (!creatingOffscreen) {
      const creation = Promise.resolve(
        chromeApi.offscreen.createDocument({
          url: OFFSCREEN_PATH,
          reasons: ["USER_MEDIA"],
          justification:
            "Capture the selected tab and provide exclusive native or converted playout.",
        }),
      );
      creatingOffscreen = creation;
      creation.then(
        () => {
          if (creatingOffscreen === creation) {
            creatingOffscreen = null;
          }
          cleanupCanceledStart(startController);
        },
        () => {
          if (creatingOffscreen === creation) {
            creatingOffscreen = null;
          }
        },
      );
    }
    await waitForStart(startController, creatingOffscreen);
  }

  async function sendOffscreen(message, startController = null) {
    const operation = chromeApi.runtime.sendMessage({
      ...message,
      target: "offscreen",
    });
    if (startController && message.type === "offscreen.native.start") {
      Promise.resolve(operation).then(
        () => cleanupCanceledStart(startController),
        () => {},
      );
    }
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    if (!response?.ok) {
      throw new Error(response?.error ?? "Offscreen command failed");
    }
    return response.state;
  }

  async function createGatewaySession(configuration, startController) {
    const response = await waitForStart(
      startController,
      fetchWithDeadline(
        `${configuration.gatewayUrl}/v1/sessions`,
        {
          method: "POST",
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          referrerPolicy: "no-referrer",
          headers: authorizedHeaders(configuration.token),
          body: JSON.stringify({
            protocol_version: 1,
            profile_id: configuration.profileId,
            input: {
              sample_rate: 48_000,
              channels: 1,
              sample_format: "f32le",
              frame_ms: 20,
            },
            voice_id: null,
          }),
        },
        "session creation",
      ),
    );
    return requireSessionResponse(
      await waitForStart(
        startController,
        jsonResponse(response, "session creation"),
      ),
    );
  }

  async function deleteGatewaySession(session, knownConfiguration = null) {
    if (!session) {
      return;
    }
    const configuration =
      knownConfiguration ?? (await storedConfiguration());
    if (!configuration || configuration.gatewayUrl !== session.gatewayUrl) {
      return;
    }
    try {
      await fetchWithDeadline(
        `${session.gatewayUrl}/v1/sessions/${encodeURIComponent(session.sessionId)}`,
        {
          method: "DELETE",
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          referrerPolicy: "no-referrer",
          headers: authorizedHeaders(configuration.token),
        },
        "session deletion",
      );
    } catch {
      // The local stop path remains authoritative when remote cleanup is unavailable.
    }
  }

  async function compensateCanceledGatewaySession(
    configuration,
    gatewaySession,
  ) {
    if (!gatewaySession) {
      return;
    }
    const session = {
      gatewayUrl: configuration.gatewayUrl,
      sessionId: gatewaySession.session_id,
    };
    await Promise.all([
      deleteGatewaySession(session, configuration),
      reconcileSessionMetadata(),
    ]);
  }

  async function synchronize(startController = null) {
    if (!(await hasOffscreenDocument(startController))) {
      if (capture !== "starting" && capture !== "stopping") {
        capture = "stopped";
        route = "native";
        remote = "disconnected";
        generationId = null;
      }
      return;
    }
    try {
      const state = await sendOffscreen(
        { type: "offscreen.status" },
        startController,
      );
      capture = state.capture;
      route = state.route;
      remote = state.remote;
      generationId = state.generationId ?? null;
    } catch (error) {
      if (startController?.canceled) {
        throw error;
      }
      route = "native";
    }
  }

  async function snapshot({ synchronizeState = false } = {}) {
    if (synchronizeState) {
      await synchronize();
    }
    const configuration = await storedConfiguration();
    const state = {
      capture,
      route,
      remote,
      generationId,
      configuration: publicConfiguration(configuration),
    };
    if (lastError !== null) {
      state.lastError = lastError;
    }
    return Object.freeze(state);
  }

  async function configure(value) {
    const configuration = normalizeConfiguration(value);
    await synchronize();
    if (capture !== "stopped") {
      throw new Error("configuration can change only while capture is stopped");
    }
    await chromeApi.storage.session.set({ [CONFIGURATION_KEY]: configuration });
    lastError = null;
    return snapshot();
  }

  async function performStart(startController) {
    capture = "starting";
    lastError = null;
    try {
      await ensureOffscreenDocument(startController);
      const tabId = await activeTabId(startController);
      const streamId = await waitForStart(
        startController,
        chromeApi.tabCapture.getMediaStreamId({ targetTabId: tabId }),
      );
      if (typeof streamId !== "string" || streamId.length === 0) {
        throw new Error("tabCapture returned an invalid stream ID");
      }
      await sendOffscreen(
        {
          type: "offscreen.native.start",
          streamId,
          tabId,
        },
        startController,
      );
      capturedTabId = tabId;
      capture = "running";
      route = "native";

      const configuration = await storedConfiguration(startController);
      if (!configuration) {
        remote = "disabled";
        return;
      }

      remote = "connecting";
      let gatewaySession = null;
      try {
        gatewaySession = await createGatewaySession(configuration, startController);
        const previous = await activeSession(startController);
        const nextGenerationId = Math.max(previous?.generationId ?? 0, 0) + 1;
        const session = {
          gatewayUrl: configuration.gatewayUrl,
          sessionId: gatewaySession.session_id,
          generationId: nextGenerationId,
        };
        const sessionWrite = setActiveSession(session);
        await waitForStart(
          startController,
          sessionWrite,
        );
        generationId = nextGenerationId;
        await sendOffscreen(
          {
            type: "offscreen.remote.connect",
            url: websocketUrl(
              configuration.gatewayUrl,
              gatewaySession.websocket_path,
            ),
            sessionId: gatewaySession.session_id,
            ticket: gatewaySession.ticket,
            generationId: nextGenerationId,
          },
          startController,
        );
        remote = "pending";
      } catch (error) {
        if (startController.canceled) {
          await compensateCanceledGatewaySession(
            configuration,
            gatewaySession,
          );
          throw error;
        }
        route = "native";
        remote = "degraded";
        generationId = null;
        lastError = errorMessage(error);
        const session = gatewaySession
          ? {
              gatewayUrl: configuration.gatewayUrl,
              sessionId: gatewaySession.session_id,
            }
          : null;
        await deleteGatewaySession(session);
        await setActiveSession(null);
      }
    } catch (error) {
      if (startController.canceled) {
        return;
      }
      capture = "stopped";
      route = "native";
      remote = "disconnected";
      generationId = null;
      capturedTabId = null;
      lastError = errorMessage(error);
      if (await hasOffscreenDocument()) {
        try {
          await sendOffscreen({ type: "offscreen.stop" });
        } catch {
          // Preserve the original capture failure.
        }
        await chromeApi.offscreen.closeDocument();
      }
      throw error;
    }
  }

  function start({ userGesture = false } = {}) {
    if (userGesture !== true) {
      return Promise.reject(
        new TypeError("capture start requires an explicit user gesture"),
      );
    }
    if (requestedCapture === "running") {
      return requestedTransition;
    }
    requestedCapture = "running";
    const startController = createStartController();
    activeStartController = startController;
    const run = async () => {
      try {
        if (startController.canceled || requestedCapture !== "running") {
          return;
        }
        await synchronize(startController);
        if (startController.canceled || requestedCapture !== "running") {
          return;
        }
        if (capture === "running") {
          return;
        }
        await performStart(startController);
      } catch (error) {
        if (startController.canceled) {
          return;
        }
        if (requestedCapture === "running") {
          requestedCapture = "stopped";
        }
        throw error;
      } finally {
        if (activeStartController === startController) {
          activeStartController = null;
        }
      }
    };
    const runAfterCleanup = async () => {
      await waitForCleanupBarrier();
      return run();
    };
    const operation = transition.then(runAfterCleanup, runAfterCleanup);
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  async function performStop() {
    capture = "stopping";
    route = "native";
    const session = await activeSession();
    if (await hasOffscreenDocument()) {
      try {
        await sendOffscreen({ type: "offscreen.stop" });
      } finally {
        await chromeApi.offscreen.closeDocument();
      }
    }
    await deleteGatewaySession(session);
    await setActiveSession(null);
    capture = "stopped";
    route = "native";
    remote = "disconnected";
    generationId = null;
    capturedTabId = null;
    lastError = null;
  }

  function stop() {
    requestedCapture = "stopped";
    activeStartController?.cancel();
    if (stopOperation) {
      return stopOperation;
    }
    abortRequests();
    const operation = performStop().finally(() => {
      stopOperation = null;
    });
    stopOperation = operation;
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  async function generationCommand(type) {
    await synchronize();
    if (capture !== "running" || generationId === null) {
      throw new Error("no remote generation is active");
    }
    if ((await activeTabId()) !== capturedTabId) {
      throw new Error("generation commands must originate from the captured tab");
    }
    const currentGenerationId = generationId;
    const state = await sendOffscreen({ type, generationId: currentGenerationId });
    route = state.route;
    remote = state.remote;
    generationId = state.generationId ?? null;
    return state;
  }

  async function startNextGeneration() {
    await synchronize();
    if (
      capture !== "running" ||
      remote === "disconnected" ||
      remote === "disabled"
    ) {
      throw new Error("remote transport is not available");
    }
    if ((await activeTabId()) !== capturedTabId) {
      throw new Error("generation commands must originate from the captured tab");
    }
    if (generationId !== null) {
      throw new Error("a remote generation is already active");
    }
    const session = await activeSession();
    if (!session) {
      throw new Error("remote session metadata is unavailable");
    }
    const nextGenerationId = session.generationId + 1;
    await setActiveSession({ ...session, generationId: nextGenerationId });
    const state = await sendOffscreen({
      type: "offscreen.generation.start",
      generationId: nextGenerationId,
    });
    remote = state.remote;
    generationId = state.generationId ?? null;
    return state;
  }

  async function handleMessage(message, sender) {
    if (sender?.id !== chromeApi.runtime.id) {
      return null;
    }
    const popupUrl = chromeApi.runtime.getURL("popup/popup.html");
    const offscreenUrl = chromeApi.runtime.getURL(OFFSCREEN_PATH);
    const isOffscreenEvent =
      message?.target === "background" && message?.type === "offscreen.event";
    if (
      (isOffscreenEvent && sender.url !== offscreenUrl) ||
      (!isOffscreenEvent && message?.target !== "offscreen" && sender.url !== popupUrl)
    ) {
      return null;
    }
    if (message?.target === "offscreen") {
      return null;
    }
    if (message?.target === "background" && message.type === "offscreen.event") {
      const event = message.event ?? {};
      if (event.route === "native" || event.route === "remote") {
        route = event.route;
      }
      if (typeof event.remote === "string") {
        remote = event.remote;
      }
      if (event.generationId === null || Number.isInteger(event.generationId)) {
        generationId = event.generationId;
      }
      if (typeof event.error === "string") {
        lastError = event.error;
      }
      if (event.sourceEnded === true) {
        await stop();
      }
      return { ok: true, state: await snapshot() };
    }

    try {
      if (message?.type === "session.status") {
        return { ok: true, state: await snapshot({ synchronizeState: true }) };
      }
      if (message?.type === "session.configure") {
        return { ok: true, state: await configure(message.configuration) };
      }
      if (message?.type === "session.start") {
        await start({ userGesture: message.userGesture === true });
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "session.stop") {
        await stop();
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.start") {
        await startNextGeneration();
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.end") {
        await generationCommand("offscreen.generation.end");
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.cancel") {
        await generationCommand("offscreen.generation.cancel");
        return { ok: true, state: await snapshot() };
      }
      return null;
    } catch (error) {
      lastError = errorMessage(error);
      return { ok: false, state: await snapshot(), error: lastError };
    }
  }

  return Object.freeze({ configure, handleMessage, snapshot, start, stop });
}

export function installBrowserMessageListener(runtime, chromeApi) {
  requireMethod(
    chromeApi?.runtime?.onMessage,
    "chrome.runtime.onMessage",
    "addListener",
  );
  const listener = (message, sender, sendResponse) => {
    const popupUrl = chromeApi.runtime.getURL("popup/popup.html");
    const offscreenUrl = chromeApi.runtime.getURL(OFFSCREEN_PATH);
    const expectedUrl =
      message?.target === "background" && message?.type === "offscreen.event"
        ? offscreenUrl
        : popupUrl;
    if (
      sender?.id !== chromeApi.runtime.id ||
      sender.url !== expectedUrl ||
      message?.target === "offscreen" ||
      (message?.target === "background" && message?.type !== "offscreen.event")
    ) {
      return false;
    }
    Promise.resolve(runtime.handleMessage(message, sender)).then(
      (response) => sendResponse(response),
      (error) => sendResponse({ ok: false, error: errorMessage(error) }),
    );
    return true;
  };
  chromeApi.runtime.onMessage.addListener(listener);
  return listener;
}

export const sessionStorageKeys = Object.freeze({
  activeSession: ACTIVE_SESSION_KEY,
  configuration: CONFIGURATION_KEY,
});
