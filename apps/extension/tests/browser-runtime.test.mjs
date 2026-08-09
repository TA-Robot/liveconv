import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/browser-runtime.js", import.meta.url);

function createHarness(stageHooks = {}) {
  const calls = [];
  const sessionStorage = new Map();
  let offscreenOpen = false;
  const offscreenState = {
    capture: "stopped",
    route: "native",
    remote: "disconnected",
    generationId: null,
  };
  const extensionId = "abcdefghijklmnopabcdefghijklmnop";
  let activeTabId = 42;
  const chromeApi = {
    runtime: {
      id: extensionId,
      getURL(path) {
        return `chrome-extension://${extensionId}/${path}`;
      },
      async getContexts(options) {
        calls.push({ name: "runtime.getContexts", options });
        return offscreenOpen ? [{ contextType: "OFFSCREEN_DOCUMENT" }] : [];
      },
      async sendMessage(message) {
        calls.push({ name: "runtime.sendMessage", message });
        await stageHooks.sendMessage?.(message);
        if (message.type === "offscreen.status") {
          return { ok: true, state: { ...offscreenState } };
        }
        if (message.type === "offscreen.native.start") {
          offscreenState.capture = "running";
        } else if (message.type === "offscreen.remote.connect") {
          offscreenState.remote = "pending";
          offscreenState.generationId = message.generationId;
        } else if (message.type === "offscreen.generation.cancel") {
          offscreenState.route = "native";
          offscreenState.remote = "ready";
          offscreenState.generationId = null;
        } else if (message.type === "offscreen.generation.end") {
          offscreenState.route = "native";
          offscreenState.remote = "ready";
          offscreenState.generationId = null;
        } else if (message.type === "offscreen.generation.start") {
          offscreenState.route = "native";
          offscreenState.remote = "pending";
          offscreenState.generationId = message.generationId;
        } else if (message.type === "offscreen.stop") {
          Object.assign(offscreenState, {
            capture: "stopped",
            route: "native",
            remote: "disconnected",
            generationId: null,
          });
        }
        return { ok: true, state: { ...offscreenState } };
      },
      onMessage: {
        addListener(listener) {
          calls.push({ name: "runtime.onMessage.addListener", listener });
        },
      },
    },
    offscreen: {
      async createDocument(options) {
        calls.push({ name: "offscreen.createDocument", options });
        await stageHooks.createDocument?.(options);
        offscreenOpen = true;
      },
      async closeDocument() {
        calls.push({ name: "offscreen.closeDocument" });
        await stageHooks.closeDocument?.();
        offscreenOpen = false;
      },
    },
    tabCapture: {
      async getMediaStreamId(options) {
        calls.push({ name: "tabCapture.getMediaStreamId", options });
        await stageHooks.getMediaStreamId?.(options);
        return "synthetic-stream-id";
      },
    },
    tabs: {
      async query(options) {
        calls.push({ name: "tabs.query", options });
        await stageHooks.queryTabs?.(options);
        return [{ id: activeTabId, active: true }];
      },
    },
    storage: {
      session: {
        async get(key) {
          calls.push({ name: "storage.session.get", key });
          await stageHooks.storageGet?.(key);
          return sessionStorage.has(key) ? { [key]: sessionStorage.get(key) } : {};
        },
        async set(values) {
          calls.push({ name: "storage.session.set", values });
          await stageHooks.storageSet?.(values);
          for (const [key, value] of Object.entries(values)) {
            sessionStorage.set(key, value);
          }
        },
        async remove(key) {
          calls.push({ name: "storage.session.remove", key });
          sessionStorage.delete(key);
        },
      },
    },
  };
  return {
    calls,
    chromeApi,
    extensionId,
    offscreenState,
    sessionStorage,
    get offscreenOpen() {
      return offscreenOpen;
    },
    setActiveTabId(value) {
      activeTabId = value;
    },
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

async function waitForCall(calls, predicate) {
  for (let turn = 0; turn < 20; turn += 1) {
    if (calls.some(predicate)) {
      return;
    }
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert.fail("expected Chrome stage was not reached");
}

async function assertSettlesPromptly(operation) {
  let settled = false;
  operation.finally(() => {
    settled = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, true, "Stop must settle while the Start stage is pending");
  await operation;
}

function okJson(value, status = 201) {
  return {
    ok: true,
    status,
    async json() {
      return value;
    },
  };
}

function sessionResponse() {
  return {
    session_id: "11111111-1111-4111-8111-111111111111",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
    websocket_path: "/v1/ws",
    ticket: "one-use-ticket-never-persisted",
  };
}

test("explicit start establishes Offscreen native loopback before any optional remote work", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn() {
      assert.fail("native-only start must not issue a gateway request");
    },
  });

  await assert.rejects(runtime.start(), /explicit user gesture/i);
  await runtime.start({ userGesture: true });

  const names = harness.calls.map((call) => call.name);
  assert(names.indexOf("offscreen.createDocument") < names.indexOf("tabCapture.getMediaStreamId"));
  const nativeMessage = harness.calls.find(
    (call) => call.name === "runtime.sendMessage" && call.message.type === "offscreen.native.start",
  );
  assert.equal(nativeMessage.message.streamId, "synthetic-stream-id");
  assert.equal(nativeMessage.message.tabId, 42);
  assert.deepEqual(
    harness.calls.find((call) => call.name === "tabCapture.getMediaStreamId")
      .options,
    { targetTabId: 42 },
  );
  assert.deepEqual(await runtime.snapshot(), {
    capture: "running",
    route: "native",
    remote: "disabled",
    generationId: null,
    configuration: { configured: false, gatewayUrl: null, profileId: null },
  });

  await runtime.stop();
  assert.equal(harness.calls.at(-1).name, "storage.session.remove");
  assert(harness.calls.some((call) => call.name === "offscreen.closeDocument"));
});

test("bearer configuration is redacted publicly and persists only in storage.session", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn: async () => {} });
  const token = "0123456789abcdefghijklmnopqrstuv";

  const state = await runtime.configure({
    gatewayUrl: "https://audio.example.test/",
    profileId: "test.gain.v1",
    token,
  });

  assert.deepEqual(state.configuration, {
    configured: true,
    gatewayUrl: "https://audio.example.test",
    profileId: "test.gain.v1",
  });
  assert.equal(JSON.stringify(state).includes(token), false);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).token,
    token,
  );
  assert.equal(Object.hasOwn(harness.chromeApi.storage, "local"), false);
  assert.equal(Object.hasOwn(harness.chromeApi.storage, "sync"), false);
});

test("configuration rejects non-ASCII bearer values before storing them", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {},
  });
  await assert.rejects(
    runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: "test.gain.v1",
      token: "0123456789abcdefghijklmnopqrstuあ",
    }),
    /printable ASCII/i,
  );
});

test("configured start creates an authenticated session and passes only the one-use ticket to Offscreen", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const requests = [];
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      requests.push({ url, options });
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(sessionResponse());
    },
  });
  const token = "0123456789abcdefghijklmnopqrstuv";
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token,
  });

  await runtime.start({ userGesture: true });

  assert.equal(requests[0].url, "https://audio.example.test/v1/sessions");
  assert.equal(requests[0].options.method, "POST");
  assert.equal(requests[0].options.headers.authorization, `Bearer ${token}`);
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    protocol_version: 1,
    profile_id: "test.passthrough.v1",
    input: {
      sample_rate: 48_000,
      channels: 1,
      sample_format: "f32le",
      frame_ms: 20,
    },
    voice_id: null,
  });
  const remoteMessage = harness.calls.find(
    (call) => call.name === "runtime.sendMessage" && call.message.type === "offscreen.remote.connect",
  ).message;
  assert.equal(remoteMessage.url, "wss://audio.example.test/v1/ws");
  assert.equal(remoteMessage.ticket, sessionResponse().ticket);
  assert.equal(remoteMessage.generationId, 1);
  assert.equal(
    JSON.stringify([...harness.sessionStorage.values()]).includes(sessionResponse().ticket),
    false,
  );

  await runtime.stop();
  assert.equal(requests[1].options.method, "DELETE");
  assert.equal(
    requests[1].url,
    "https://audio.example.test/v1/sessions/11111111-1111-4111-8111-111111111111",
  );
});

test("gateway failure degrades to the already-running native path", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn() {
      return { ok: false, status: 503 };
    },
  });
  await runtime.configure({
    gatewayUrl: "http://127.0.0.1:8765",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  await runtime.start({ userGesture: true });
  const state = await runtime.snapshot();

  assert.equal(state.capture, "running");
  assert.equal(state.route, "native");
  assert.equal(state.remote, "degraded");
  assert.match(state.lastError, /HTTP 503/);
});

test("malicious websocket paths cannot escape the configured gateway origin", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn() {
      return okJson({ ...sessionResponse(), websocket_path: "/\\evil.test/ws" });
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });

  assert.equal((await runtime.snapshot()).remote, "degraded");
  assert.equal(
    harness.calls.some(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.remote.connect",
    ),
    false,
  );
});

test("Stop preempts a session POST that never resolves", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  let fetchStarted = false;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {
      fetchStarted = true;
      return new Promise(() => {});
    },
    requestTimeoutMilliseconds: 10_000,
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  const start = runtime.start({ userGesture: true });
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
    if (fetchStarted) {
      break;
    }
  }
  assert.equal(fetchStarted, true);
  await runtime.stop();
  await start;
  assert.equal((await runtime.snapshot()).capture, "stopped");
  assert(harness.calls.some((call) => call.name === "offscreen.closeDocument"));
});

const pendingStartStages = [
  {
    name: "offscreen.createDocument",
    hooks(pending) {
      return { createDocument: () => pending };
    },
    reached(call) {
      return call.name === "offscreen.createDocument";
    },
    forbidden(call) {
      return (
        call.name === "tabs.query" ||
        call.name === "tabCapture.getMediaStreamId" ||
        (call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.native.start")
      );
    },
  },
  {
    name: "tabs.query",
    hooks(pending) {
      return { queryTabs: () => pending };
    },
    reached(call) {
      return call.name === "tabs.query";
    },
    forbidden(call) {
      return (
        call.name === "tabCapture.getMediaStreamId" ||
        (call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.native.start")
      );
    },
  },
  {
    name: "tabCapture.getMediaStreamId",
    hooks(pending) {
      return { getMediaStreamId: () => pending };
    },
    reached(call) {
      return call.name === "tabCapture.getMediaStreamId";
    },
    forbidden(call) {
      return (
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.native.start"
      );
    },
  },
  {
    name: "runtime.sendMessage for native start",
    hooks(pending) {
      return {
        sendMessage(message) {
          return message.type === "offscreen.native.start" ? pending : undefined;
        },
      };
    },
    reached(call) {
      return (
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.native.start"
      );
    },
    forbidden(call) {
      return (
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.remote.connect"
      );
    },
  },
];

for (const stage of pendingStartStages) {
  test(`Stop preempts Start while ${stage.name} is pending`, async () => {
    const { createBrowserRuntime } = await import(moduleUrl);
    const blocker = deferred();
    const harness = createHarness(stage.hooks(blocker.promise));
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      fetchFn: async () => assert.fail("native-only start must not fetch"),
    });

    const start = runtime.start({ userGesture: true });
    await waitForCall(harness.calls, stage.reached);
    await assertSettlesPromptly(runtime.stop());
    await start;
    const callsBeforeRelease = harness.calls.length;
    const startSideEffectsBeforeRelease = harness.calls.filter(
      (call) =>
        call.name === "offscreen.createDocument" ||
        (call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.native.start"),
    ).length;

    blocker.resolve();
    await new Promise((resolve) => setImmediate(resolve));

    assert.equal(
      harness.calls.slice(callsBeforeRelease).some(stage.forbidden),
      false,
      "a canceled Start must not advance to a later capture stage",
    );
    assert.equal(
      harness.calls.filter(
        (call) =>
          call.name === "offscreen.createDocument" ||
          (call.name === "runtime.sendMessage" &&
            call.message.type === "offscreen.native.start"),
      ).length,
      startSideEffectsBeforeRelease,
      "a canceled Start must not issue a late create or native-start command",
    );
    assert.equal(harness.offscreenState.capture, "stopped");
    assert.equal(harness.offscreenOpen, false);
    assert.equal((await runtime.snapshot()).capture, "stopped");
  });
}

test("a second Stop cancels Start B queued behind Stop A", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const closeGate = deferred();
  let blockClose = false;
  const harness = createHarness({
    closeDocument() {
      return blockClose ? closeGate.promise : undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("native-only lifecycle must not fetch"),
  });
  await runtime.start({ userGesture: true });
  blockClose = true;

  const stopA = runtime.stop();
  await waitForCall(
    harness.calls,
    (call) => call.name === "offscreen.closeDocument",
  );
  const startB = runtime.start({ userGesture: true });
  const stopB = runtime.stop();
  assert.equal(stopB, stopA);

  closeGate.resolve();
  await stopB;
  await startB;

  assert.equal((await runtime.snapshot()).capture, "stopped");
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.native.start",
    ).length,
    1,
    "Start B must not issue a native-start command after the second Stop",
  );
});

test("a second Stop preserves Stop A gateway cleanup while canceling Start B", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const deleteGate = deferred();
  const harness = createHarness();
  const requests = [];
  let deleteSignal = null;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      requests.push({ url, options });
      if (options.method === "DELETE") {
        deleteSignal = options.signal;
        return deleteGate.promise;
      }
      return okJson(sessionResponse());
    },
    requestTimeoutMilliseconds: 10_000,
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });

  const stopA = runtime.stop();
  for (let turn = 0; turn < 20 && deleteSignal === null; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert(deleteSignal, "Stop A must reach gateway DELETE");

  const startB = runtime.start({ userGesture: true });
  const stopB = runtime.stop();
  assert.equal(stopB, stopA);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(
    deleteSignal.aborted,
    false,
    "Stop B must not abort the cleanup request owned by Stop A",
  );
  let stopped = false;
  stopB.then(() => {
    stopped = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(stopped, false, "Stop must wait for the explicit DELETE response");

  deleteGate.resolve({ ok: true, status: 204 });
  await stopB;
  await startB;

  assert.equal((await runtime.snapshot()).capture, "stopped");
  assert.equal(
    requests.filter((request) => request.options.method === "DELETE").length,
    1,
  );
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.native.start",
    ).length,
    1,
    "Start B must remain canceled after Stop A cleanup completes",
  );
});

test("late Start A cleanup is serialized before Start B opens Offscreen", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const createGate = deferred();
  const closeGate = deferred();
  let createCount = 0;
  let closeCount = 0;
  const harness = createHarness({
    createDocument() {
      createCount += 1;
      return createCount === 1 ? createGate.promise : undefined;
    },
    closeDocument() {
      closeCount += 1;
      return closeCount === 1 ? closeGate.promise : undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("native-only lifecycle must not fetch"),
  });

  const startA = runtime.start({ userGesture: true });
  await waitForCall(
    harness.calls,
    (call) => call.name === "offscreen.createDocument",
  );
  await runtime.stop();
  await startA;

  createGate.resolve();
  await waitForCall(
    harness.calls,
    (call) => call.name === "offscreen.closeDocument",
  );
  const startB = runtime.start({ userGesture: true });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(
    harness.calls.filter((call) => call.name === "offscreen.createDocument").length,
    1,
    "Start B must wait for detached cleanup to finish",
  );

  closeGate.resolve();
  await startB;

  assert.equal((await runtime.snapshot()).capture, "running");
  assert.equal(harness.offscreenOpen, true);
  assert.equal(
    harness.calls.filter((call) => call.name === "offscreen.createDocument").length,
    2,
  );
});

test("a redundant Stop cannot hide late cleanup from Start B", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const createGate = deferred();
  const lateCloseGate = deferred();
  let createCount = 0;
  let closeCount = 0;
  const harness = createHarness({
    createDocument() {
      createCount += 1;
      return createCount === 1 ? createGate.promise : undefined;
    },
    closeDocument() {
      closeCount += 1;
      return closeCount === 1 ? lateCloseGate.promise : undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("native-only lifecycle must not fetch"),
  });

  const startA = runtime.start({ userGesture: true });
  await waitForCall(
    harness.calls,
    (call) => call.name === "offscreen.createDocument",
  );
  await runtime.stop();
  await startA;

  createGate.resolve();
  await waitForCall(
    harness.calls,
    (call) => call.name === "offscreen.closeDocument",
  );
  await runtime.stop();

  let startBSettled = false;
  const startB = runtime.start({ userGesture: true });
  startB.then(() => {
    startBSettled = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(startBSettled, false, "Start B must wait for late cleanup A");
  assert.equal(
    harness.calls.filter((call) => call.name === "offscreen.createDocument").length,
    1,
  );

  lateCloseGate.resolve();
  await startB;

  assert.equal(harness.offscreenOpen, true);
  assert.equal((await runtime.snapshot({ synchronizeState: true })).capture, "running");
  assert.equal(
    harness.calls.filter((call) => call.name === "offscreen.createDocument").length,
    2,
  );
});

const pendingGatewayMetadataStages = [
  {
    name: "active-session metadata read",
    hooks(pending, activeSessionKey) {
      let blocked = false;
      return {
        storageGet(key) {
          if (key === activeSessionKey && !blocked) {
            blocked = true;
            return pending;
          }
          return undefined;
        },
      };
    },
    reached(call, activeSessionKey) {
      return call.name === "storage.session.get" && call.key === activeSessionKey;
    },
  },
  {
    name: "active-session metadata write",
    hooks(pending, activeSessionKey) {
      let blocked = false;
      return {
        storageSet(values) {
          if (Object.hasOwn(values, activeSessionKey) && !blocked) {
            blocked = true;
            return pending;
          }
          return undefined;
        },
      };
    },
    reached(call, activeSessionKey) {
      return (
        call.name === "storage.session.set" &&
        Object.hasOwn(call.values, activeSessionKey)
      );
    },
  },
];

for (const stage of pendingGatewayMetadataStages) {
  test(`Stop compensates a created gateway session during ${stage.name}`, async () => {
    const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
    const blocker = deferred();
    const harness = createHarness(
      stage.hooks(blocker.promise, sessionStorageKeys.activeSession),
    );
    const requests = [];
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      async fetchFn(url, options) {
        requests.push({ url, options });
        if (options.method === "DELETE") {
          return { ok: true, status: 204 };
        }
        return okJson(sessionResponse());
      },
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: "test.passthrough.v1",
      token: "0123456789abcdefghijklmnopqrstuv",
    });

    const start = runtime.start({ userGesture: true });
    await waitForCall(harness.calls, (call) =>
      stage.reached(call, sessionStorageKeys.activeSession),
    );
    await assertSettlesPromptly(runtime.stop());
    await start;

    assert(
      requests.some(
        (request) =>
          request.options.method === "DELETE" &&
          request.url ===
            "https://audio.example.test/v1/sessions/11111111-1111-4111-8111-111111111111",
      ),
      "a canceled start must DELETE the gateway session it created",
    );
    assert.equal(
      harness.sessionStorage.has(sessionStorageKeys.activeSession),
      false,
    );

    blocker.resolve();
    await new Promise((resolve) => setImmediate(resolve));

    assert.equal(
      harness.sessionStorage.has(sessionStorageKeys.activeSession),
      false,
      "a late storage write must not restore canceled session metadata",
    );
    assert.equal(
      harness.calls.some(
        (call) =>
          call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.remote.connect",
      ),
      false,
    );
  });
}

test("a late session write from Start A restores Start B metadata", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const firstWrite = deferred();
  let blockedFirstSessionWrite = false;
  const harness = createHarness({
    storageSet(values) {
      if (
        Object.hasOwn(values, sessionStorageKeys.activeSession) &&
        !blockedFirstSessionWrite
      ) {
        blockedFirstSessionWrite = true;
        return firstWrite.promise;
      }
      return undefined;
    },
  });
  const sessionA = {
    ...sessionResponse(),
    session_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    ticket: "ticket-a",
  };
  const sessionB = {
    ...sessionResponse(),
    session_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    ticket: "ticket-b",
  };
  const pendingResponses = [sessionA, sessionB];
  const requests = [];
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      requests.push({ url, options });
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(pendingResponses.shift());
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  const startA = runtime.start({ userGesture: true });
  await waitForCall(
    harness.calls,
    (call) =>
      call.name === "storage.session.set" &&
      call.values[sessionStorageKeys.activeSession]?.sessionId ===
        sessionA.session_id,
  );
  await assertSettlesPromptly(runtime.stop());
  await startA;

  await runtime.start({ userGesture: true });
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).sessionId,
    sessionB.session_id,
  );

  firstWrite.resolve();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).sessionId,
    sessionB.session_id,
    "late Start A metadata must reconcile to the running Start B session",
  );
  assert(
    requests.some(
      (request) =>
        request.options.method === "DELETE" &&
        request.url.endsWith(`/v1/sessions/${sessionA.session_id}`),
    ),
    "Stop A must DELETE gateway session A",
  );
  const remoteConnects = harness.calls.filter(
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.remote.connect",
  );
  assert.equal(remoteConnects.at(-1).message.sessionId, sessionB.session_id);
});

test("Stop recovers persisted session metadata after a service-worker reload", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const token = "0123456789abcdefghijklmnopqrstuv";
  harness.sessionStorage.set(sessionStorageKeys.configuration, {
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token,
  });
  harness.sessionStorage.set(sessionStorageKeys.activeSession, {
    gatewayUrl: "https://audio.example.test",
    sessionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    generationId: 7,
  });
  const requests = [];
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      requests.push({ url, options });
      return { ok: true, status: 204 };
    },
  });

  await runtime.stop();

  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.method, "DELETE");
  assert.equal(
    requests[0].url,
    "https://audio.example.test/v1/sessions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  );
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
  );
});

test("generation controls are bound to the captured tab", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => okJson(sessionResponse()),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  harness.setActiveTabId(84);
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const response = await runtime.handleMessage({ type: "generation.end" }, sender);
  assert.equal(response.ok, false);
  assert.match(response.error, /captured tab/i);
});

test("popup generation End, Next, and Interrupt reach the Offscreen lifecycle", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => okJson(sessionResponse()),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: "test.passthrough.v1",
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };

  assert.equal(
    (await runtime.handleMessage({ type: "generation.end" }, sender)).ok,
    true,
  );
  assert.equal(
    (await runtime.handleMessage({ type: "generation.start" }, sender)).ok,
    true,
  );
  assert.equal(
    (await runtime.handleMessage({ type: "generation.cancel" }, sender)).ok,
    true,
  );
  assert.deepEqual(
    harness.calls
      .filter(
        (call) =>
          call.name === "runtime.sendMessage" &&
          call.message.type.startsWith("offscreen.generation."),
      )
      .map((call) => call.message.type),
    [
      "offscreen.generation.end",
      "offscreen.generation.start",
      "offscreen.generation.cancel",
    ],
  );
});

test("message dispatch rejects foreign senders and carries the explicit gesture bit", async () => {
  const { createBrowserRuntime, installBrowserMessageListener } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn: async () => {} });
  const listener = installBrowserMessageListener(runtime, harness.chromeApi);

  assert.equal(
    await runtime.handleMessage(
      { type: "session.status" },
      { id: "foreign-extension-id" },
    ),
    null,
  );

  assert.equal(
    await runtime.handleMessage(
      { type: "session.status" },
      {
        id: harness.extensionId,
        url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
      },
    ),
    null,
  );

  const response = await new Promise((resolve) => {
    assert.equal(
      listener(
        { type: "session.start", userGesture: false },
        {
          id: harness.extensionId,
          url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
        },
        resolve,
      ),
      true,
    );
  });
  assert.equal(response.ok, false);
  assert.match(response.error, /explicit user gesture/i);
  assert.equal(
    harness.calls.some((call) => call.name === "tabCapture.getMediaStreamId"),
    false,
  );

  let backgroundResponded = false;
  assert.equal(
    listener(
      { target: "offscreen", type: "offscreen.status" },
      {
        id: harness.extensionId,
        url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
      },
      () => {
        backgroundResponded = true;
      },
    ),
    false,
  );
  assert.equal(backgroundResponded, false);
});
