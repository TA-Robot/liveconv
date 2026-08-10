import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/browser-runtime.js", import.meta.url);
const gatewayUrlModuleUrl = new URL("../src/gateway-url.js", import.meta.url);
const popupStateModuleUrl = new URL("../popup/popup-state.js", import.meta.url);

function createHarness(stageHooks = {}) {
  const calls = [];
  const sessionStorage = new Map();
  const localStorage = new Map();
  let offscreenOpen = false;
  const offscreenState = {
    capture: "stopped",
    route: "native",
    remote: "disconnected",
    generationId: null,
  };
  const extensionId = "abcdefghijklmnopabcdefghijklmnop";
  let activeTab = {
    id: 42,
    active: true,
    audible: true,
    url: "https://chatgpt.com/",
  };
  let offscreenEpoch = 0;
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
        const stagedResponse = await stageHooks.sendMessage?.(message);
        if (message.type === "offscreen.status") {
          return stagedResponse ?? { ok: true, state: { ...offscreenState } };
        }
        if (message.type === "offscreen.native.start") {
          offscreenState.capture = "running";
          offscreenEpoch += 1;
          offscreenState.offscreenEpoch =
            `00000000-0000-4000-8000-${String(offscreenEpoch).padStart(12, "0")}`;
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
        } else if (message.type === "offscreen.exp005.inject-failure") {
          offscreenState.route = "native";
          offscreenState.remote = "degraded";
          offscreenState.generationId = null;
        } else if (message.type === "offscreen.model.select") {
          offscreenState.route = "native";
          offscreenState.remote = "ready";
        } else if (message.type === "offscreen.stop") {
          Object.assign(offscreenState, {
            capture: "stopped",
            route: "native",
            remote: "disconnected",
            generationId: null,
          });
          delete offscreenState.offscreenEpoch;
        }
        return stagedResponse ?? { ok: true, state: { ...offscreenState } };
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
        return [{ ...activeTab }];
      },
    },
    storage: {
      local: {
        async get(key) {
          calls.push({ name: "storage.local.get", key });
          await stageHooks.localStorageGet?.(key);
          return localStorage.has(key) ? { [key]: localStorage.get(key) } : {};
        },
        async set(values) {
          calls.push({ name: "storage.local.set", values });
          await stageHooks.localStorageSet?.(values);
          for (const [key, value] of Object.entries(values)) {
            localStorage.set(key, value);
          }
        },
      },
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
          await stageHooks.storageRemove?.(key);
          sessionStorage.delete(key);
        },
      },
    },
  };
  return {
    calls,
    chromeApi,
    extensionId,
    localStorage,
    offscreenState,
    sessionStorage,
    get offscreenOpen() {
      return offscreenOpen;
    },
    setActiveTabId(value) {
      activeTab = { ...activeTab, id: value };
    },
    setActiveTab(value) {
      activeTab = { ...activeTab, ...value };
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
    protocol_version: 1,
    session_id: "11111111-1111-4111-8111-111111111111",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
    profile_id: VC_PROFILE_IDS.rvc,
    profile_hash: catalogProfile(VC_PROFILE_IDS.rvc).profile_hash,
    configuration_hash: catalogProfile(VC_PROFILE_IDS.rvc).configuration_hash,
    limits: { ingress_budget_ms: 500, max_ingress_frames: 25 },
    websocket_path: "/v1/ws",
    ticket: "one-use-ticket-never-persisted",
  };
}

const VC_PROFILE_IDS = Object.freeze({
  rvc: "vc.rvc.synthetic-ja.v1",
  beatrice: "vc.beatrice.synthetic-ja.v1",
  xvc: "vc.x-vc.synthetic-ja.v1",
  openvoice: "vc.openvoice-v2.synthetic-ja.v1",
});

const VC_PACK_IDS = Object.freeze({
  [VC_PROFILE_IDS.rvc]: "rvc-v2",
  [VC_PROFILE_IDS.beatrice]: "beatrice-2",
  [VC_PROFILE_IDS.xvc]: "x-vc",
  [VC_PROFILE_IDS.openvoice]: "openvoice-v2",
});

function hash(character) {
  return `sha256:${character.repeat(64)}`;
}

function catalogProfile(profileId = VC_PROFILE_IDS.rvc, options = {}) {
  const kind = options.kind ??
    (Object.hasOwn(VC_PACK_IDS, profileId) ? "voice_conversion" : "deterministic_test");
  const profileHashCharacter = options.profileHashCharacter ??
    ({
      [VC_PROFILE_IDS.rvc]: "a",
      [VC_PROFILE_IDS.beatrice]: "b",
      [VC_PROFILE_IDS.xvc]: "c",
      [VC_PROFILE_IDS.openvoice]: "d",
      "test.passthrough.v1": "e",
      "test.gain.v1": "f",
    }[profileId] ?? "a");
  const configurationHashCharacter = options.configurationHashCharacter ??
    ({
      [VC_PROFILE_IDS.rvc]: "1",
      [VC_PROFILE_IDS.beatrice]: "2",
      [VC_PROFILE_IDS.xvc]: "3",
      [VC_PROFILE_IDS.openvoice]: "4",
      "test.passthrough.v1": "5",
      "test.gain.v1": "6",
    }[profileId] ?? "1");
  return {
    profile_id: profileId,
    kind,
    adapter_api_version: 1,
    implementation_revision: "synthetic-v1",
    weight_revision: null,
    streaming: options.streaming ?? true,
    cancellation: "immediate",
    input_sample_rates: [48_000],
    output_sample_rates: [48_000],
    frame_ms: 20,
    minimum_context_ms: 0,
    voice_requirement:
      options.voiceRequirement ??
      (kind === "voice_conversion" ? "pretrained_voice" : "none"),
    readiness: "ready",
    warmup_policy: "none",
    resource_class: "cpu",
    ...(kind === "voice_conversion"
      ? {
          promotion: {
            status: "technical_validation",
            pack_id: options.packId ?? VC_PACK_IDS[profileId],
            pack_sha256: hash("7"),
            evidence_sha256: hash("8"),
            endpoint_sha256: hash("9"),
          },
        }
      : {}),
    profile_hash: hash(profileHashCharacter),
    configuration_hash: hash(configurationHashCharacter),
  };
}

function modelCatalog() {
  return {
    protocol_version: 1,
    profiles: [
      catalogProfile("test.passthrough.v1"),
      catalogProfile("test.gain.v1"),
      catalogProfile(VC_PROFILE_IDS.rvc),
      catalogProfile(VC_PROFILE_IDS.beatrice),
      catalogProfile(VC_PROFILE_IDS.xvc),
      catalogProfile(VC_PROFILE_IDS.openvoice, { streaming: false }),
    ],
  };
}

function modelRoster(options = {}) {
  const catalog = modelCatalog().profiles;
  const entries = [
    ["rvc-v2", "RVC v2", VC_PROFILE_IDS.rvc, "live"],
    ["beatrice-2", "Beatrice 2", VC_PROFILE_IDS.beatrice, "live"],
    ["x-vc", "X-VC", VC_PROFILE_IDS.xvc, "live"],
    ["openvoice-v2", "OpenVoice V2", VC_PROFILE_IDS.openvoice, "buffered_end"],
  ];
  return {
    schema_version: 1,
    roster_id: "ms2-test-v1",
    roster_hash:
      "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    models: entries.map(([modelId, displayName, profileId, invocationMode]) => {
      const override = options[modelId] ?? {};
      const executionState = override.executionState ??
        (invocationMode === "live" ? "live-trial" : "buffered-preview");
      return {
        model_id: modelId,
        display_name: displayName,
        profile_id: profileId,
        invocation_mode: invocationMode,
        execution_state: executionState,
        decision_state: override.decisionState ?? "technical-only",
        voice_requirement: override.voiceRequirement ?? "pretrained_voice",
        reason_code:
          executionState === "unavailable"
            ? (override.reasonCode ?? "profile_unavailable")
            : null,
        profile:
          executionState === "unavailable"
            ? null
            : (override.profile ?? catalog.find((profile) => profile.profile_id === profileId)),
      };
    }),
  };
}

function gatewayDocument(url, session = sessionResponse()) {
  if (url.endsWith("/v1/models")) {
    return modelCatalog();
  }
  if (url.endsWith("/v1/model-roster")) {
    return modelRoster();
  }
  return session;
}

function exp005TrialFixture() {
  return {
    roster_revision: hash("9"),
    plan_revision: hash("8"),
    roster_entries: [
      ["rvc-v2", VC_PROFILE_IDS.rvc, "a", "1", "live"],
      ["beatrice-2", VC_PROFILE_IDS.beatrice, "b", "2", "live"],
      ["x-vc", VC_PROFILE_IDS.xvc, "c", "3", "live"],
      [
        "openvoice-v2",
        VC_PROFILE_IDS.openvoice,
        "d",
        "4",
        "buffered_preview_after_end",
      ],
    ].map(([modelId, profileId, profileHash, configurationHash, routeMode]) => ({
      model_id: modelId,
      profile_id: profileId,
      profile_hash: hash(profileHash),
      configuration_hash: hash(configurationHash),
      route_mode: routeMode,
    })),
    ssh_preflight: {
      schema_version: 1,
      check: "liveconv-ms2-ssh-preflight",
      status: "pass",
      client: {
        host_key_pinned: true,
        strict_host_key_checking: true,
        local_forward: {
          listen_host: "127.0.0.1",
          listen_port: 9765,
          target_host: "127.0.0.1",
          target_port: 8765,
        },
      },
      server: { forwarding_only: true, permitopen_loopback: true },
      gateway: {
        loopback_bound: true,
        bearer_auth_required: true,
        exact_extension_origin: true,
        one_use_ticket: true,
        max_sessions: 1,
      },
    },
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

test("bearer configuration is redacted publicly and persists across Chrome restarts", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn: async () => {} });
  const token = "0123456789abcdefghijklmnopqrstuv";

  const state = await runtime.configure({
    gatewayUrl: "https://audio.example.test/",
    profileId: VC_PROFILE_IDS.beatrice,
    token,
  });

  assert.deepEqual(state.configuration, {
    configured: true,
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.beatrice,
  });
  assert.equal(JSON.stringify(state).includes(token), false);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).token,
    token,
  );
  assert.equal(
    harness.localStorage.get(sessionStorageKeys.configuration).token,
    token,
  );
  assert.equal(Object.hasOwn(harness.chromeApi.storage, "sync"), false);
});

test("configuration restores from storage.local after session storage is cleared", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const token = "0123456789abcdefghijklmnopqrstuv";
  const firstRuntime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {},
  });
  await firstRuntime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.beatrice,
    token,
  });

  harness.sessionStorage.delete(sessionStorageKeys.configuration);
  const restartedRuntime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {},
  });
  const state = await restartedRuntime.snapshot();

  assert.deepEqual(state.configuration, {
    configured: true,
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.beatrice,
  });
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).token,
    token,
  );
});

test("saved bearer can be reused after popup reopen only for the same Gateway", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {},
  });
  const token = "0123456789abcdefghijklmnopqrstuv";
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });

  const updated = await runtime.configure({
    gatewayUrl: "https://audio.example.test/",
    profileId: VC_PROFILE_IDS.beatrice,
    token: "",
  });
  assert.equal(updated.configuration.profileId, VC_PROFILE_IDS.beatrice);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).token,
    token,
  );

  await assert.rejects(
    runtime.configure({
      gatewayUrl: "https://different.example.test",
      profileId: VC_PROFILE_IDS.beatrice,
      token: "",
    }),
    /token is required for a new Gateway/i,
  );
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
      profileId: VC_PROFILE_IDS.beatrice,
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
      return okJson(gatewayDocument(url));
    },
  });
  const token = "0123456789abcdefghijklmnopqrstuv";
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });

  await runtime.start({ userGesture: true });

  assert.equal(requests[0].url, "https://audio.example.test/v1/models");
  assert.equal(requests[0].options.method, "GET");
  assert.equal(requests[1].url, "https://audio.example.test/v1/model-roster");
  assert.equal(requests[1].options.method, "GET");
  assert.equal(requests[1].options.headers.authorization, `Bearer ${token}`);
  assert.equal(requests[2].url, "https://audio.example.test/v1/sessions");
  assert.equal(requests[2].options.method, "POST");
  assert.equal(requests[2].options.headers.authorization, `Bearer ${token}`);
  assert.deepEqual(JSON.parse(requests[2].options.body), {
    protocol_version: 1,
    profile_id: VC_PROFILE_IDS.rvc,
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
  assert.deepEqual(remoteMessage.expectedLimits, {
    ingressBudgetMs: 500,
    maxIngressFrames: 25,
  });
  assert.deepEqual(remoteMessage.expectedProfile, {
    profileId: VC_PROFILE_IDS.rvc,
    profileHash: sessionResponse().profile_hash,
    configurationHash: sessionResponse().configuration_hash,
    pipelineId: sessionResponse().pipeline_id,
  });
  assert.equal(
    JSON.stringify([...harness.sessionStorage.values()]).includes(sessionResponse().ticket),
    false,
  );

  await runtime.stop();
  assert.equal(requests[3].options.method, "DELETE");
  assert.equal(
    requests[3].url,
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
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  await runtime.start({ userGesture: true });
  const state = await runtime.snapshot();

  assert.equal(state.capture, "running");
  assert.equal(state.route, "native");
  assert.equal(state.remote, "degraded");
  assert.match(state.lastError, /HTTP 503/);
});

test("remote attach failure removes the persisted captured-tab session binding", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness({
    sendMessage(message) {
      if (message.type === "offscreen.remote.connect") {
        throw new Error("synthetic remote attach failure");
      }
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      if (options?.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(gatewayDocument(url));
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  await runtime.start({ userGesture: true });

  const state = await runtime.snapshot();
  assert.equal(state.capture, "running");
  assert.equal(state.remote, "degraded");
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "remote failure must remove the session and its captured-tab binding together",
  );
});

test("malicious websocket paths cannot escape the configured gateway origin", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url) {
      return okJson(
        gatewayDocument(url, {
          ...sessionResponse(),
          websocket_path: "/\\evil.test/ws",
        }),
      );
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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
    fetchFn: async (url) => {
      if (url.endsWith("/v1/models")) {
        return okJson(modelCatalog());
      }
      fetchStarted = true;
      return new Promise(() => {});
    },
    requestTimeoutMilliseconds: 10_000,
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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
      return okJson(gatewayDocument(url));
    },
    requestTimeoutMilliseconds: 10_000,
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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
        return okJson(gatewayDocument(url));
      },
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
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
      return okJson(
        url.endsWith("/v1/models")
          ? modelCatalog()
          : url.endsWith("/v1/model-roster")
            ? modelRoster()
            : pendingResponses.shift(),
      );
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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
    profileId: VC_PROFILE_IDS.rvc,
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

test("Stop expresses native stopped intent before a restarted worker metadata read fails", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  let rejectActiveSessionRead = false;
  const harness = createHarness({
    storageGet(key) {
      if (rejectActiveSessionRead && key === sessionStorageKeys.activeSession) {
        throw new Error("synthetic active-session read failure");
      }
    },
  });
  const token = "0123456789abcdefghijklmnopqrstuv";
  harness.sessionStorage.set(sessionStorageKeys.configuration, {
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });
  harness.sessionStorage.set(sessionStorageKeys.activeSession, {
    gatewayUrl: "https://audio.example.test",
    sessionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    generationId: 7,
  });
  await harness.chromeApi.offscreen.createDocument({});
  harness.offscreenState.capture = "running";
  harness.offscreenState.route = "remote";
  harness.offscreenState.remote = "ready";
  harness.offscreenState.generationId = 7;

  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("unread session metadata cannot be deleted"),
  });
  rejectActiveSessionRead = true;

  const stop = runtime.stop();
  assert.deepEqual(await runtime.snapshot(), {
    capture: "stopping",
    route: "native",
    remote: "disconnected",
    generationId: null,
    configuration: {
      configured: true,
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
    },
  });
  await assert.rejects(stop, /active-session read failure/i);

  const offscreenStop = harness.calls.findIndex(
    (call) =>
      call.name === "runtime.sendMessage" && call.message.type === "offscreen.stop",
  );
  const failedRead = harness.calls.findIndex(
    (call) =>
      call.name === "storage.session.get" && call.key === sessionStorageKeys.activeSession,
  );
  assert(offscreenStop >= 0, "Stop must reach Offscreen native fallback");
  assert(harness.calls.some((call) => call.name === "offscreen.closeDocument"));
  assert(offscreenStop < failedRead, "Offscreen shutdown must precede metadata recovery");
  assert.equal(harness.offscreenOpen, false);
  assert.equal((await runtime.snapshot()).capture, "stopped");
});

test("Stop closes native playout and attempts Gateway cleanup when metadata removal fails", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness({
    storageRemove(key) {
      if (key === sessionStorageKeys.activeSession) {
        throw new Error("synthetic active-session removal failure");
      }
    },
  });
  const requests = [];
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      requests.push({ url, options });
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(gatewayDocument(url));
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });

  await assert.rejects(runtime.stop(), /active-session removal failure/i);

  assert.equal(harness.offscreenOpen, false);
  assert.equal((await runtime.snapshot()).capture, "stopped");
  assert(
    harness.calls.some(
      (call) =>
        call.name === "runtime.sendMessage" && call.message.type === "offscreen.stop",
    ),
  );
  assert(
    requests.some((request) => request.options.method === "DELETE"),
    "Stop must retain best-effort Gateway cleanup after local metadata failure",
  );
});

test("configuration commit does not reread storage after the authoritative write", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  let configurationWritten = false;
  const harness = createHarness({
    storageSet(values) {
      if (Object.hasOwn(values, sessionStorageKeys.configuration)) {
        configurationWritten = true;
      }
    },
    storageGet(key) {
      if (configurationWritten && key === sessionStorageKeys.configuration) {
        throw new Error("synthetic post-write configuration read failure");
      }
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("configuration does not fetch"),
  });

  const state = await runtime.configure({
    gatewayUrl: "https://next.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  assert.deepEqual(state.configuration, {
    configured: true,
    gatewayUrl: "https://next.example.test",
    profileId: VC_PROFILE_IDS.rvc,
  });
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).gatewayUrl,
    "https://next.example.test",
  );
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "storage.session.get" &&
        call.key === sessionStorageKeys.configuration,
    ).length,
    0,
  );
});

test("a committed configuration keeps only its new optional host permission after a post-write read failure", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const { replaceGatewayPermission } = await import(gatewayUrlModuleUrl);
  let rejectConfigurationRead = false;
  const harness = createHarness({
    storageGet(key) {
      if (rejectConfigurationRead && key === sessionStorageKeys.configuration) {
        throw new Error("synthetic post-write configuration read failure");
      }
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => assert.fail("configuration does not fetch"),
  });
  const oldOrigin = "https://old.example.test/*";
  const nextOrigin = "https://next.example.test/*";
  const grants = new Set([oldOrigin]);
  const permissionCalls = [];
  const permissions = {
    async contains({ origins }) {
      return origins.every((origin) => grants.has(origin));
    },
    async request({ origins }) {
      permissionCalls.push({ name: "request", origins });
      for (const origin of origins) {
        grants.add(origin);
      }
      return true;
    },
    async remove({ origins }) {
      permissionCalls.push({ name: "remove", origins });
      for (const origin of origins) {
        grants.delete(origin);
      }
      return true;
    },
  };

  await runtime.configure({
    gatewayUrl: "https://old.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  rejectConfigurationRead = true;

  const result = await replaceGatewayPermission({
    permissions,
    nextOrigin,
    previousOrigin: oldOrigin,
    commit: async () => ({
      ok: true,
      state: await runtime.configure({
        gatewayUrl: "https://next.example.test",
        profileId: VC_PROFILE_IDS.rvc,
        token: "0123456789abcdefghijklmnopqrstuv",
      }),
    }),
  });

  assert.equal(result.granted, true);
  assert.equal(grants.has(nextOrigin), true);
  assert.equal(grants.has(oldOrigin), false);
  assert.deepEqual(permissionCalls, [
    { name: "request", origins: [nextOrigin] },
    { name: "remove", origins: [oldOrigin] },
  ]);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).gatewayUrl,
    "https://next.example.test",
  );
});

test("Stop clears the captured-tab session binding when Offscreen shutdown fails", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness({
    closeDocument() {
      throw new Error("synthetic Offscreen close failure");
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    true,
  );

  await assert.rejects(runtime.stop(), /Offscreen close failure/i);

  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "Stop failure must still remove the session and its captured-tab binding",
  );
});

test("fresh service-worker runtime restores the Offscreen-bound captured tab for every generation control", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const fetchFn = async (url, options) => {
    if (options?.method === "DELETE") {
      return { ok: true, status: 204 };
    }
    return okJson(gatewayDocument(url));
  };
  const originalRuntime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn,
  });
  await originalRuntime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await originalRuntime.start({ userGesture: true });

  const persisted = harness.sessionStorage.get(sessionStorageKeys.activeSession);
  assert.equal(persisted.capturedTabId, 42);
  assert.equal(persisted.offscreenEpoch, harness.offscreenState.offscreenEpoch);

  harness.sessionStorage.set(sessionStorageKeys.activeSession, {
    ...persisted,
    offscreenEpoch: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  });
  const mismatchedRuntime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn,
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const mismatched = await mismatchedRuntime.handleMessage(
    { type: "generation.end" },
    sender,
  );
  assert.equal(mismatched.ok, false);
  assert.match(mismatched.error, /captured tab/i);
  harness.sessionStorage.set(sessionStorageKeys.activeSession, persisted);

  const recoveredRuntime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn,
  });

  assert.equal(
    (await recoveredRuntime.handleMessage({ type: "generation.end" }, sender)).ok,
    true,
  );
  assert.equal(
    (await recoveredRuntime.handleMessage({ type: "generation.start" }, sender)).ok,
    true,
  );
  assert.equal(
    (await recoveredRuntime.handleMessage({ type: "generation.cancel" }, sender)).ok,
    true,
  );
  const selected = await recoveredRuntime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  assert.equal(selected.ok, true);

  assert.equal(
    (await recoveredRuntime.handleMessage({ type: "generation.start" }, sender)).ok,
    true,
  );
  harness.setActiveTabId(84);
  for (const type of ["generation.end", "generation.cancel"]) {
    const rejected = await recoveredRuntime.handleMessage({ type }, sender);
    assert.equal(rejected.ok, false, `${type} must reject a different active tab`);
    assert.match(rejected.error, /captured tab/i);
  }

  harness.setActiveTabId(42);
  assert.equal(
    (await recoveredRuntime.handleMessage({ type: "generation.end" }, sender)).ok,
    true,
  );
  harness.setActiveTabId(84);
  for (const message of [
    { type: "generation.start" },
    { type: "model.select", profileId: VC_PROFILE_IDS.rvc },
  ]) {
    const rejected = await recoveredRuntime.handleMessage(message, sender);
    assert.equal(
      rejected.ok,
      false,
      `${message.type} must reject a different active tab`,
    );
    assert.match(rejected.error, /captured tab/i);
  }

  harness.setActiveTabId(42);
  await recoveredRuntime.stop();
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "Stop must atomically remove the session and its captured-tab binding",
  );
});

test("generation controls are bound to the captured tab", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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

for (const control of [
  {
    label: "End",
    popupType: "generation.end",
    offscreenType: "offscreen.generation.end",
  },
  {
    label: "Interrupt",
    popupType: "generation.cancel",
    offscreenType: "offscreen.generation.cancel",
  },
]) {
  test(`Stop prevents a stale ${control.label} tab query from controlling a restarted session`, async () => {
    const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
    const staleTabQuery = deferred();
    const staleTabQueryReached = deferred();
    let blockNextTabQuery = false;
    const harness = createHarness({
      queryTabs() {
        if (!blockNextTabQuery) {
          return undefined;
        }
        blockNextTabQuery = false;
        staleTabQueryReached.resolve();
        return staleTabQuery.promise;
      },
    });
    const sessions = [
      sessionResponse(),
      {
        ...sessionResponse(),
        session_id: "33333333-3333-4333-8333-333333333333",
        pipeline_id: "44444444-4444-4444-8444-444444444444",
      },
    ];
    let sessionCreations = 0;
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      async fetchFn(url, options = {}) {
        if (options.method === "DELETE") {
          return { ok: true, status: 204 };
        }
        if (url.endsWith("/v1/sessions")) {
          return okJson(sessions[sessionCreations++]);
        }
        return okJson(gatewayDocument(url));
      },
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
      token: "0123456789abcdefghijklmnopqrstuv",
    });
    await runtime.start({ userGesture: true });

    const sender = {
      id: harness.extensionId,
      url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
    };
    const firstSession = harness.sessionStorage.get(
      sessionStorageKeys.activeSession,
    );
    blockNextTabQuery = true;
    const staleControl = runtime.handleMessage(
      { type: control.popupType },
      sender,
    );
    await staleTabQueryReached.promise;

    assert.equal(
      (await runtime.handleMessage({ type: "session.stop" }, sender)).ok,
      true,
    );
    assert.equal(
      (await runtime.handleMessage(
        { type: "session.start", userGesture: true },
        sender,
      )).ok,
      true,
    );
    const restartedSession = harness.sessionStorage.get(
      sessionStorageKeys.activeSession,
    );
    assert.equal(restartedSession.sessionId, sessions[1].session_id);
    assert.equal(restartedSession.generationId, firstSession.generationId);
    assert.equal(restartedSession.capturedTabId, firstSession.capturedTabId);
    assert.notEqual(restartedSession.offscreenEpoch, firstSession.offscreenEpoch);

    staleTabQuery.resolve();
    const staleResponse = await staleControl;
    assert.equal(staleResponse.ok, false);
    assert.match(staleResponse.error, /canceled by Stop/i);
    assert.equal(staleResponse.state.capture, "running");
    assert.equal(staleResponse.state.generationId, restartedSession.generationId);
    assert.equal(Object.hasOwn(staleResponse.state, "lastError"), false);
    assert.equal(harness.offscreenState.generationId, restartedSession.generationId);
    assert.equal(
      harness.calls.filter(
        (call) =>
          call.name === "runtime.sendMessage" &&
          call.message.type === control.offscreenType,
      ).length,
      0,
      `the stale ${control.label} must not be dispatched to session B`,
    );
  });
}

test("Stop prevents a stale Next tab query from advancing a restarted session", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const staleTabQuery = deferred();
  const queryReached = deferred();
  let blockNextQuery = false;
  const harness = createHarness({
    queryTabs() {
      if (blockNextQuery) {
        blockNextQuery = false;
        queryReached.resolve();
        return staleTabQuery.promise;
      }
      return undefined;
    },
  });
  const sessions = [
    sessionResponse(),
    {
      ...sessionResponse(),
      session_id: "33333333-3333-4333-8333-333333333333",
      pipeline_id: "44444444-4444-4444-8444-444444444444",
    },
  ];
  let sessionIndex = 0;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options = {}) {
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(
        url.endsWith("/v1/sessions")
          ? sessions[sessionIndex++]
          : gatewayDocument(url),
      );
    },
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);
  blockNextQuery = true;
  const staleNext = runtime.handleMessage({ type: "generation.start" }, sender);
  await queryReached.promise;
  await runtime.handleMessage({ type: "session.stop" }, sender);
  await runtime.handleMessage(
    { type: "session.start", userGesture: true },
    sender,
  );
  const generationStartsBeforeRelease = harness.calls.filter(
    (call) => call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.generation.start",
  ).length;
  staleTabQuery.resolve();
  const rejected = await staleNext;
  assert.equal(rejected.ok, false);
  assert.match(rejected.error, /canceled by Stop/i);
  assert.equal(
    harness.calls.filter(
      (call) => call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.start",
    ).length,
    generationStartsBeforeRelease,
  );
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).generationId,
    1,
  );
  assert.equal(harness.offscreenState.generationId, 1);
});

test("late Next metadata cannot overwrite a restarted session", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const nextWrite = deferred();
  const writeReached = deferred();
  let blockNextWrite = true;
  const harness = createHarness({
    storageSet(values) {
      if (
        blockNextWrite &&
        values[sessionStorageKeys.activeSession]?.generationId === 2
      ) {
        blockNextWrite = false;
        writeReached.resolve();
        return nextWrite.promise;
      }
      return undefined;
    },
  });
  const sessions = [
    sessionResponse(),
    {
      ...sessionResponse(),
      session_id: "33333333-3333-4333-8333-333333333333",
      pipeline_id: "44444444-4444-4444-8444-444444444444",
    },
  ];
  let sessionIndex = 0;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options = {}) {
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(
        url.endsWith("/v1/sessions")
          ? sessions[sessionIndex++]
          : gatewayDocument(url),
      );
    },
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);
  const staleNext = runtime.handleMessage({ type: "generation.start" }, sender);
  await writeReached.promise;
  await runtime.handleMessage({ type: "session.stop" }, sender);
  await runtime.handleMessage(
    { type: "session.start", userGesture: true },
    sender,
  );
  nextWrite.resolve();
  const rejected = await staleNext;
  assert.equal(rejected.ok, false);
  assert.match(rejected.error, /canceled by Stop/i);
  const active = harness.sessionStorage.get(sessionStorageKeys.activeSession);
  assert.equal(active.sessionId, sessions[1].session_id);
  assert.equal(active.generationId, 1);
  assert.equal(harness.offscreenState.generationId, 1);
});

test("Next accepts an Offscreen loading event nested before generation-start response", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  let runtime;
  let offscreenSender;
  let emitNestedLoading = false;
  const harness = createHarness({
    async sendMessage(message) {
      if (
        emitNestedLoading &&
        message.type === "offscreen.generation.start"
      ) {
        emitNestedLoading = false;
        const nested = await runtime.handleMessage(
          {
            target: "background",
            type: "offscreen.event",
            event: {
              capture: "running",
              route: "native",
              remote: "loading",
              generationId: null,
            },
          },
          offscreenSender,
        );
        assert.equal(nested.ok, true);
      }
    },
  });
  runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  assert.equal(
    (await runtime.handleMessage({ type: "generation.end" }, popupSender)).ok,
    true,
  );

  emitNestedLoading = true;
  const next = await runtime.handleMessage({ type: "generation.start" }, popupSender);
  assert.equal(next.ok, true, next.error);
  assert.equal(next.state.remote, "pending");
  assert.equal(next.state.generationId, 2);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).generationId,
    2,
  );
  assert.equal(harness.offscreenState.generationId, 2);
});

test("Next cancels a started generation whose Offscreen response identity is invalid", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  let corruptNextResponse = false;
  const harness = createHarness({
    sendMessage(message) {
      if (
        corruptNextResponse &&
        message.type === "offscreen.generation.start"
      ) {
        corruptNextResponse = false;
        return {
          ok: true,
          state: {
            capture: "running",
            route: "native",
            remote: "pending",
            generationId: message.generationId + 1,
          },
        };
      }
      return undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  assert.equal(
    (await runtime.handleMessage({ type: "generation.end" }, sender)).ok,
    true,
  );

  corruptNextResponse = true;
  const rejected = await runtime.handleMessage({ type: "generation.start" }, sender);
  assert.equal(rejected.ok, false);
  assert.match(rejected.error, /invalid next generation identity/i);
  assert.equal(
    harness.calls.some(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.cancel" &&
        call.message.generationId === 2,
    ),
    true,
  );
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).generationId,
    1,
  );
  assert.equal(harness.offscreenState.remote, "ready");
  assert.equal(harness.offscreenState.generationId, null);
});

test("Next cancels and reconciles when a started generation degrades during metadata commit", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const pendingWrite = deferred();
  const writeReached = deferred();
  let blockNextWrite = true;
  const harness = createHarness({
    storageSet(values) {
      if (
        blockNextWrite &&
        values[sessionStorageKeys.activeSession]?.generationId === 2
      ) {
        blockNextWrite = false;
        writeReached.resolve();
        return pendingWrite.promise;
      }
      return undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  assert.equal(
    (await runtime.handleMessage({ type: "generation.end" }, popupSender)).ok,
    true,
  );

  const next = runtime.handleMessage({ type: "generation.start" }, popupSender);
  await writeReached.promise;
  const degraded = await runtime.handleMessage(
    {
      target: "background",
      type: "offscreen.event",
      event: {
        capture: "running",
        route: "native",
        remote: "degraded",
        generationId: null,
        error: "synthetic post-start transport failure",
      },
    },
    offscreenSender,
  );
  assert.equal(degraded.ok, true);
  pendingWrite.resolve();

  const rejected = await next;
  assert.equal(rejected.ok, false);
  assert.equal(
    harness.calls.some(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.cancel" &&
        call.message.generationId === 2,
    ),
    true,
  );
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).generationId,
    1,
  );
  assert.equal(harness.offscreenState.remote, "ready");
  assert.equal(harness.offscreenState.generationId, null);
});

test("popup generation End, Next, and Interrupt reach the Offscreen lifecycle", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
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

test("idle disconnect reaches popup controls and only fresh Stop-Start authentication recovers", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const { derivePopupView } = await import(popupStateModuleUrl);
  const harness = createHarness();
  const sessions = [
    sessionResponse(),
    {
      ...sessionResponse(),
      session_id: "33333333-3333-4333-8333-333333333333",
      pipeline_id: "44444444-4444-4444-8444-444444444444",
      ticket: "fresh-one-use-ticket-never-persisted",
    },
  ];
  let sessionCreations = 0;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    async fetchFn(url, options) {
      if (url.endsWith("/v1/models")) {
        return okJson(modelCatalog(), 200);
      }
      if (url.endsWith("/v1/model-roster")) {
        return okJson(modelRoster(), 200);
      }
      if (options?.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      const session = sessions[sessionCreations];
      sessionCreations += 1;
      return okJson(session);
    },
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };

  assert.equal(
    (await runtime.handleMessage(
      { type: "session.start", userGesture: true },
      popupSender,
    )).ok,
    true,
  );
  assert.equal(
    (await runtime.handleMessage({ type: "generation.end" }, popupSender)).ok,
    true,
  );
  Object.assign(harness.offscreenState, {
    capture: "running",
    route: "native",
    remote: "degraded",
    generationId: null,
  });
  const disconnected = await runtime.handleMessage(
    {
      target: "background",
      type: "offscreen.event",
      event: {
        capture: "running",
        route: "native",
        remote: "degraded",
        generationId: null,
        transportClosed: true,
        requiresFreshSession: true,
        error:
          "remote WebSocket closed (1006). Stop and Start to create a fresh authenticated session.",
      },
    },
    offscreenSender,
  );
  assert.equal(disconnected.ok, true);
  assert.equal(disconnected.state.remote, "degraded");
  assert.equal(disconnected.state.generationId, null);

  const popupNotification = harness.calls
    .filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.target === "popup" &&
        call.message.type === "session.state",
    )
    .at(-1).message;
  assert.deepEqual(popupNotification.state, disconnected.state);
  const popupView = derivePopupView(popupNotification.state, {
    statusSynchronized: true,
  });
  assert.match(popupView.status, /fresh authenticated session/i);
  assert.equal(popupView.startDisabled, true);
  assert.equal(popupView.stopDisabled, false);
  assert.equal(popupView.endDisabled, true);
  assert.equal(popupView.cancelDisabled, true);
  assert.equal(popupView.nextDisabled, true);
  assert.equal(popupView.selectProfileDisabled, true);

  const generationStartsBefore = harness.calls.filter(
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.generation.start",
  ).length;
  const staleNext = await runtime.handleMessage(
    { type: "generation.start" },
    popupSender,
  );
  assert.equal(staleNext.ok, false);
  assert.match(staleNext.error, /not available/i);
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.start",
    ).length,
    generationStartsBefore,
  );
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).generationId,
    1,
  );

  assert.equal(
    (await runtime.handleMessage({ type: "session.stop" }, popupSender)).ok,
    true,
  );
  assert.equal(
    (await runtime.handleMessage(
      { type: "session.start", userGesture: true },
      popupSender,
    )).ok,
    true,
  );
  assert.equal(sessionCreations, 2);
  const connections = harness.calls
    .filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.remote.connect",
    )
    .map((call) => ({
      sessionId: call.message.sessionId,
      ticket: call.message.ticket,
    }));
  assert.deepEqual(connections, [
    {
      sessionId: sessions[0].session_id,
      ticket: sessions[0].ticket,
    },
    {
      sessionId: sessions[1].session_id,
      ticket: sessions[1].ticket,
    },
  ]);
  assert.notEqual(connections[0].ticket, connections[1].ticket);
});

test("catalog profiles switch only at a generation boundary with bound identity", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const configuration = {
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  };
  await runtime.configure(configuration);
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const listed = await runtime.handleMessage({ type: "models.list" }, sender);
  assert.equal(listed.ok, true);
  assert.deepEqual(
    listed.models.map((model) => model.modelId),
    ["rvc-v2", "beatrice-2", "x-vc", "openvoice-v2"],
  );
  await runtime.start({ userGesture: true });

  const activeSelection = await runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  assert.equal(activeSelection.ok, false);
  assert.match(activeSelection.error, /generation boundary/i);

  await runtime.handleMessage({ type: "generation.end" }, sender);
  const selected = await runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  assert.equal(selected.ok, true);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).profileId,
    VC_PROFILE_IDS.beatrice,
  );
  assert.deepEqual(
    harness.sessionStorage.get(sessionStorageKeys.activeSession),
    {
      gatewayUrl: "https://audio.example.test",
      sessionId: sessionResponse().session_id,
      generationId: 1,
      profileId: VC_PROFILE_IDS.beatrice,
      modelId: "beatrice-2",
      invocationMode: "live",
      capturedTabId: 42,
      offscreenEpoch: "00000000-0000-4000-8000-000000000001",
    },
  );
  const message = harness.calls.find(
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.model.select",
  ).message;
  assert.deepEqual(message.expectedProfile, {
    profileId: VC_PROFILE_IDS.beatrice,
    profileHash: catalogProfile(VC_PROFILE_IDS.beatrice).profile_hash,
    configurationHash: catalogProfile(VC_PROFILE_IDS.beatrice).configuration_hash,
  });
  assert.equal(message.invocationMode, "live");
});

test("roster and catalog semantic drift is rejected before any remote session or selection", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const cases = [
    {
      name: "outer voice requirement",
      mutate(catalog, roster) {
        roster.models[0].voice_requirement = "none";
      },
      error: /fixed MS-2 semantics/i,
    },
    {
      name: "outer invocation mode",
      mutate(catalog, roster) {
        roster.models[0].invocation_mode = "buffered_end";
        roster.models[0].execution_state = "buffered-preview";
      },
      error: /fixed MS-2 semantics/i,
    },
    {
      name: "catalog voice requirement",
      mutate(catalog) {
        catalog.profiles.find(
          (profile) => profile.profile_id === VC_PROFILE_IDS.rvc,
        ).voice_requirement = "none";
      },
      error: /invocation or voice requirement/i,
    },
    {
      name: "catalog streaming mode",
      mutate(catalog) {
        catalog.profiles.find(
          (profile) => profile.profile_id === VC_PROFILE_IDS.openvoice,
        ).streaming = true;
      },
      error: /invocation or voice requirement/i,
    },
  ];
  const sender = {
    id: "abcdefghijklmnopabcdefghijklmnop",
    url: "chrome-extension://abcdefghijklmnopabcdefghijklmnop/popup/popup.html",
  };

  for (const fixture of cases) {
    const harness = createHarness();
    const catalog = modelCatalog();
    const roster = modelRoster();
    fixture.mutate(catalog, roster);
    const requests = [];
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      async fetchFn(url, options = {}) {
        requests.push({ url, options });
        return okJson(url.endsWith("/v1/models") ? catalog : roster, 200);
      },
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
      token: "0123456789abcdefghijklmnopqrstuv",
    });

    const result = await runtime.handleMessage({ type: "models.list" }, sender);
    assert.equal(result.ok, false, fixture.name);
    assert.match(result.error, fixture.error, fixture.name);
    assert.equal(
      requests.some((request) => request.options.method === "POST"),
      false,
      `${fixture.name} must fail before session creation`,
    );
    assert.equal(
      harness.calls.some(
        (call) =>
          call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.model.select",
      ),
      false,
      `${fixture.name} must fail before profile selection`,
    );
  }
});

test("selection storage failures restore the active model before allowing Next", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  for (const failedRecord of ["configuration", "active session"]) {
    let failNextSelectionCommit = true;
    const harness = createHarness({
      storageSet(values) {
        const nextConfiguration = values[sessionStorageKeys.configuration];
        const nextSession = values[sessionStorageKeys.activeSession];
        if (
          failNextSelectionCommit &&
          nextConfiguration?.profileId === VC_PROFILE_IDS.beatrice &&
          nextSession?.profileId === VC_PROFILE_IDS.beatrice
        ) {
          failNextSelectionCommit = false;
          throw new Error(`synthetic ${failedRecord} persistence failure`);
        }
      },
    });
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      fetchFn: async (url) => okJson(gatewayDocument(url)),
    });
    const sender = {
      id: harness.extensionId,
      url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
    };
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
      token: "0123456789abcdefghijklmnopqrstuv",
    });
    await runtime.start({ userGesture: true });
    assert.equal(
      (await runtime.handleMessage({ type: "generation.end" }, sender)).ok,
      true,
    );

    const selected = await runtime.handleMessage(
      { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
      sender,
    );
    assert.equal(selected.ok, false, failedRecord);
    assert.match(selected.error, /synthetic .* persistence failure/i, failedRecord);
    assert.equal(
      harness.sessionStorage.get(sessionStorageKeys.configuration).profileId,
      VC_PROFILE_IDS.rvc,
      `${failedRecord} must restore the persisted configuration`,
    );
    assert.equal(
      harness.sessionStorage.get(sessionStorageKeys.activeSession).profileId,
      VC_PROFILE_IDS.rvc,
      `${failedRecord} must restore the persisted active session`,
    );
    const selectionMessages = harness.calls
      .filter(
        (call) =>
          call.name === "runtime.sendMessage" &&
          call.message.type === "offscreen.model.select",
      )
      .map((call) => call.message.expectedProfile.profileId);
    assert.deepEqual(selectionMessages, [
      VC_PROFILE_IDS.beatrice,
      VC_PROFILE_IDS.rvc,
    ]);

    const next = await runtime.handleMessage({ type: "generation.start" }, sender);
    assert.equal(next.ok, true, `${failedRecord} rollback must leave the old model ready`);
    const nextMessage = harness.calls.findLast(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.start",
    );
    assert.equal(nextMessage.message.invocationMode, "live");
  }
});

test("a failed selection rollback stops Offscreen and blocks Next", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  let failNextSelectionCommit = true;
  const harness = createHarness({
    storageSet(values) {
      const nextConfiguration = values[sessionStorageKeys.configuration];
      const nextSession = values[sessionStorageKeys.activeSession];
      if (
        failNextSelectionCommit &&
        nextConfiguration?.profileId === VC_PROFILE_IDS.beatrice &&
        nextSession?.profileId === VC_PROFILE_IDS.beatrice
      ) {
        failNextSelectionCommit = false;
        throw new Error("synthetic selection persistence failure");
      }
    },
  });
  const originalSendMessage = harness.chromeApi.runtime.sendMessage.bind(
    harness.chromeApi.runtime,
  );
  harness.chromeApi.runtime.sendMessage = async (message) => {
    if (
      message.type === "offscreen.model.select" &&
      message.expectedProfile?.profileId === VC_PROFILE_IDS.rvc
    ) {
      return { ok: false, error: "synthetic profile rollback failure" };
    }
    return originalSendMessage(message);
  };
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);

  const selected = await runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  assert.equal(selected.ok, false);
  assert.match(selected.error, /rollback was incomplete/i);
  assert.equal(selected.state.capture, "stopped");
  assert.equal(selected.state.remote, "disconnected");
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "fail-closed selection must remove the active session before a new start",
  );

  const nextCount = harness.calls.filter(
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.generation.start",
  ).length;
  const next = await runtime.handleMessage({ type: "generation.start" }, sender);
  assert.equal(next.ok, false);
  assert.match(next.error, /not ready/i);
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.start",
    ).length,
    nextCount,
  );
});

test("Next is rejected while profile selection is pending", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const selectionGate = deferred();
  let holdSelectionResponse = true;
  const harness = createHarness();
  const originalSendMessage = harness.chromeApi.runtime.sendMessage.bind(
    harness.chromeApi.runtime,
  );
  harness.chromeApi.runtime.sendMessage = async (message) => {
    const response = await originalSendMessage(message);
    if (
      holdSelectionResponse &&
      message.type === "offscreen.model.select" &&
      message.expectedProfile?.profileId === VC_PROFILE_IDS.beatrice
    ) {
      await selectionGate.promise;
    }
    return response;
  };
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);

  const selecting = runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  await waitForCall(
    harness.calls,
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.model.select" &&
      call.message.expectedProfile?.profileId === VC_PROFILE_IDS.beatrice,
  );
  const nextBeforeSelectionCommit = harness.calls.filter(
    (call) =>
      call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.generation.start",
  ).length;
  const next = await runtime.handleMessage({ type: "generation.start" }, sender);
  assert.equal(next.ok, false);
  assert.match(next.error, /selection is still in progress/i);
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.generation.start",
    ).length,
    nextBeforeSelectionCommit,
  );

  holdSelectionResponse = false;
  selectionGate.resolve();
  assert.equal((await selecting).ok, true);
});

test("profile selection is rejected while a Next metadata commit is pending", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const nextWrite = deferred();
  const writeReached = deferred();
  let blockNextWrite = true;
  const harness = createHarness({
    storageSet(values) {
      if (
        blockNextWrite &&
        values[sessionStorageKeys.activeSession]?.generationId === 2
      ) {
        blockNextWrite = false;
        writeReached.resolve();
        return nextWrite.promise;
      }
      return undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);
  const next = runtime.handleMessage({ type: "generation.start" }, sender);
  await writeReached.promise;
  const selection = await runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.openvoice },
    sender,
  );
  assert.equal(selection.ok, false);
  assert.match(selection.error, /generation control is still in progress/i);
  nextWrite.resolve();
  assert.equal((await next).ok, true);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.activeSession).profileId,
    VC_PROFILE_IDS.rvc,
  );
  const startMessage = harness.calls.findLast(
    (call) => call.name === "runtime.sendMessage" &&
      call.message.type === "offscreen.generation.start",
  );
  assert.equal(startMessage.message.invocationMode, "live");
});

test("Stop invalidates a profile selection whose combined storage commit completes late", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const selectionWrite = deferred();
  let blockedSelectionWrite = false;
  const harness = createHarness({
    storageSet(values) {
      if (
        !blockedSelectionWrite &&
        values[sessionStorageKeys.configuration]?.profileId ===
          VC_PROFILE_IDS.beatrice &&
        values[sessionStorageKeys.activeSession]?.profileId ===
          VC_PROFILE_IDS.beatrice
      ) {
        blockedSelectionWrite = true;
        return selectionWrite.promise;
      }
      return undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url, options = {}) =>
      options.method === "DELETE"
        ? { ok: true, status: 204 }
        : okJson(gatewayDocument(url)),
  });
  const sender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const token = "0123456789abcdefghijklmnopqrstuv";
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });
  await runtime.start({ userGesture: true });
  await runtime.handleMessage({ type: "generation.end" }, sender);

  const selecting = runtime.handleMessage(
    { type: "model.select", profileId: VC_PROFILE_IDS.beatrice },
    sender,
  );
  await waitForCall(
    harness.calls,
    (call) =>
      call.name === "storage.session.set" &&
      call.values[sessionStorageKeys.configuration]?.profileId ===
        VC_PROFILE_IDS.beatrice &&
      call.values[sessionStorageKeys.activeSession]?.profileId ===
        VC_PROFILE_IDS.beatrice,
  );

  const stopping = runtime.handleMessage({ type: "session.stop" }, sender);
  await assertSettlesPromptly(stopping);
  assert.equal(harness.offscreenOpen, false);
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "Stop must remove the active session while the stale selection write waits",
  );

  let configureSettled = false;
  const configuring = runtime
    .configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.xvc,
      token,
    })
    .finally(() => {
      configureSettled = true;
    });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(
    configureSettled,
    false,
    "a newer configuration must wait for canceled-selection repair",
  );

  selectionWrite.resolve();
  const selectionResult = await selecting;
  assert.equal(selectionResult.ok, false);
  assert.match(selectionResult.error, /canceled by Stop/i);
  assert.equal(selectionResult.state.capture, "stopped");
  assert.equal(selectionResult.state.remote, "disconnected");
  assert.equal(harness.offscreenOpen, false);
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.activeSession),
    false,
    "the late combined write must not resurrect stopped session metadata",
  );
  assert.equal(
    harness.calls.filter(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "offscreen.model.select",
    ).length,
    1,
    "canceled selection must not issue a rollback against closed Offscreen",
  );

  const configured = await configuring;
  assert.equal(configured.configuration.profileId, VC_PROFILE_IDS.xvc);
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.configuration).profileId,
    VC_PROFILE_IDS.xvc,
    "canceled-selection repair must not overwrite a newer configuration",
  );
  assert.equal(harness.sessionStorage.has(sessionStorageKeys.activeSession), false);
});

test("model roster parsing is strict and preserves the full prepared set", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const malformedRosters = [
    {
      name: "unexpected root field",
      mutate(roster) {
        roster.debug = true;
      },
      error: /unexpected fields/i,
    },
    {
      name: "missing prepared model",
      mutate(roster) {
        roster.models.pop();
      },
      error: /invalid model roster/i,
    },
    {
      name: "enabled entry without its profile",
      mutate(roster) {
        roster.models[0].profile = null;
      },
      error: /inconsistent availability/i,
    },
    {
      name: "unavailable entry without a reason",
      mutate(roster) {
        roster.models[0].execution_state = "unavailable";
        roster.models[0].profile = null;
        roster.models[0].reason_code = null;
      },
      error: /inconsistent availability/i,
    },
  ];
  const sender = {
    id: "abcdefghijklmnopabcdefghijklmnop",
    url: "chrome-extension://abcdefghijklmnopabcdefghijklmnop/popup/popup.html",
  };

  for (const fixture of malformedRosters) {
    const harness = createHarness();
    const roster = modelRoster();
    fixture.mutate(roster);
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      fetchFn: async (url) =>
        okJson(url.endsWith("/v1/models") ? modelCatalog() : roster, 200),
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
      token: "0123456789abcdefghijklmnopqrstuv",
    });
    const response = await runtime.handleMessage({ type: "models.list" }, sender);
    assert.equal(response.ok, false, fixture.name);
    assert.match(response.error, fixture.error, fixture.name);
  }

  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url), 200),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  const response = await runtime.handleMessage({ type: "models.list" }, sender);
  assert.equal(response.ok, true);
  assert.deepEqual(
    response.models.map((model) => model.modelId),
    ["rvc-v2", "beatrice-2", "x-vc", "openvoice-v2"],
  );
  assert.deepEqual(
    response.profiles.map((profile) => profile.profileId),
    [
      "test.passthrough.v1",
      "test.gain.v1",
      VC_PROFILE_IDS.rvc,
      VC_PROFILE_IDS.beatrice,
      VC_PROFILE_IDS.xvc,
      VC_PROFILE_IDS.openvoice,
    ],
  );
});

test("an enabled roster profile must have the catalog identity returned by /v1/models", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const roster = modelRoster();
  roster.models[0].profile.profile_hash =
    "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) =>
      okJson(url.endsWith("/v1/models") ? modelCatalog() : roster, 200),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  const response = await runtime.handleMessage(
    { type: "models.list" },
    {
      id: harness.extensionId,
      url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
    },
  );
  assert.equal(response.ok, false);
  assert.match(response.error, /identity does not match \/v1\/models/i);
});

test("enabled roster entries require the promoted VC catalog profile for their model", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const sender = {
    id: "abcdefghijklmnopabcdefghijklmnop",
    url: "chrome-extension://abcdefghijklmnopabcdefghijklmnop/popup/popup.html",
  };
  const cases = [
    {
      name: "non-VC profile despite matching identity hashes",
      error: /fixed MS-2 semantics/i,
      mutate(catalog, roster) {
        const beatrice = roster.models.find(
          (model) => model.model_id === "beatrice-2",
        );
        const gain = catalog.profiles.find(
          (profile) => profile.profile_id === "test.gain.v1",
        );
        beatrice.profile_id = gain.profile_id;
        beatrice.profile = gain;
      },
    },
    {
      name: "cross-pack VC profile despite matching identity hashes",
      error: /not promoted for beatrice-2/i,
      mutate(catalog, roster) {
        const catalogProfile = catalog.profiles.find(
          (profile) => profile.profile_id === VC_PROFILE_IDS.beatrice,
        );
        const rosterProfile = roster.models.find(
          (model) => model.model_id === "beatrice-2",
        ).profile;
        catalogProfile.promotion.pack_id = "rvc-v2";
        rosterProfile.promotion.pack_id = "rvc-v2";
      },
    },
  ];

  for (const fixture of cases) {
    const harness = createHarness();
    const catalog = modelCatalog();
    const roster = modelRoster();
    fixture.mutate(catalog, roster);
    const runtime = createBrowserRuntime({
      chromeApi: harness.chromeApi,
      fetchFn: async (url) =>
        okJson(url.endsWith("/v1/models") ? catalog : roster, 200),
    });
    await runtime.configure({
      gatewayUrl: "https://audio.example.test",
      profileId: VC_PROFILE_IDS.rvc,
      token: "0123456789abcdefghijklmnopqrstuv",
    });

    const response = await runtime.handleMessage({ type: "models.list" }, sender);
    assert.equal(response.ok, false, fixture.name);
    assert.match(response.error, fixture.error, fixture.name);
  }
});

test("voice-conversion catalog promotions must contain the complete reviewed identity", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const catalog = modelCatalog();
  delete catalog.profiles.find(
    (profile) => profile.profile_id === VC_PROFILE_IDS.rvc,
  ).promotion.endpoint_sha256;
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) =>
      okJson(url.endsWith("/v1/models") ? catalog : modelRoster(), 200),
  });
  await runtime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });

  const response = await runtime.handleMessage(
    { type: "models.list" },
    {
      id: harness.extensionId,
      url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
    },
  );
  assert.equal(response.ok, false);
  assert.match(response.error, /unexpected fields in promotion/i);
});

test("pretrained voice profiles use null voice_id and MS-2 roster target drift is rejected", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const token = "0123456789abcdefghijklmnopqrstuv";
  const senderFor = (harness) => ({
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  });

  const pretrainedHarness = createHarness();
  const pretrainedCatalog = modelCatalog();
  const pretrainedProfile = pretrainedCatalog.profiles.find(
    (profile) => profile.profile_id === VC_PROFILE_IDS.rvc,
  );
  pretrainedProfile.voice_requirement = "pretrained_voice";
  const pretrainedRoster = modelRoster();
  pretrainedRoster.models[0].voice_requirement = "pretrained_voice";
  pretrainedRoster.models[0].profile.voice_requirement = "pretrained_voice";
  const pretrainedRequests = [];
  const pretrainedRuntime = createBrowserRuntime({
    chromeApi: pretrainedHarness.chromeApi,
    async fetchFn(url, options) {
      pretrainedRequests.push({ url, options });
      if (url.endsWith("/v1/models")) {
        return okJson(pretrainedCatalog, 200);
      }
      if (url.endsWith("/v1/model-roster")) {
        return okJson(pretrainedRoster, 200);
      }
      return okJson(sessionResponse());
    },
  });
  await pretrainedRuntime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });
  await pretrainedRuntime.start({ userGesture: true });
  const creation = pretrainedRequests.find(
    (request) => request.options.method === "POST",
  );
  assert.equal(JSON.parse(creation.options.body).voice_id, null);
  assert.equal(
    (await pretrainedRuntime.handleMessage({ type: "models.list" }, senderFor(pretrainedHarness))).models[0]
      .selectable,
    true,
  );

  const authorizedHarness = createHarness();
  const authorizedCatalog = modelCatalog();
  const authorizedProfile = authorizedCatalog.profiles.find(
    (profile) => profile.profile_id === VC_PROFILE_IDS.rvc,
  );
  authorizedProfile.voice_requirement = "authorized_target_required";
  const authorizedRoster = modelRoster();
  authorizedRoster.models[0].voice_requirement = "authorized_target_required";
  authorizedRoster.models[0].profile.voice_requirement = "authorized_target_required";
  const authorizedRequests = [];
  const authorizedRuntime = createBrowserRuntime({
    chromeApi: authorizedHarness.chromeApi,
    async fetchFn(url, options) {
      authorizedRequests.push({ url, options });
      if (url.endsWith("/v1/models")) {
        return okJson(authorizedCatalog, 200);
      }
      if (url.endsWith("/v1/model-roster")) {
        return okJson(authorizedRoster, 200);
      }
      return okJson(sessionResponse());
    },
  });
  await authorizedRuntime.configure({
    gatewayUrl: "https://audio.example.test",
    profileId: VC_PROFILE_IDS.rvc,
    token,
  });
  await authorizedRuntime.start({ userGesture: true });
  assert.equal(
    authorizedRequests.some((request) => request.options.method === "POST"),
    false,
  );
  assert.match((await authorizedRuntime.snapshot()).lastError, /fixed MS-2 semantics/i);
  const listed = await authorizedRuntime.handleMessage(
    { type: "models.list" },
    senderFor(authorizedHarness),
  );
  assert.equal(listed.ok, false);
  assert.match(listed.error, /fixed MS-2 semantics/i);
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

test("validated Offscreen conversion progress is relayed to the popup", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async () => {},
  });
  const result = await runtime.handleMessage(
    {
      target: "background",
      type: "offscreen.event",
      event: {
        progress: { generationId: 7, inputFrames: 50, outputFrames: 25 },
      },
    },
    {
      id: harness.extensionId,
      url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
    },
  );
  assert.equal(result.ok, true);
  assert.deepEqual(
    harness.calls.find(
      (call) =>
        call.name === "runtime.sendMessage" &&
        call.message.type === "conversion.progress",
    )?.message,
    {
      target: "popup",
      type: "conversion.progress",
      progress: { generationId: 7, inputFrames: 50, outputFrames: 25 },
    },
  );
});

test("only the popup can begin, export, and clear an observed EXP-005 receipt", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const { createExp005RuntimeReceiptRecorder } = await import(
    new URL("../src/exp005-runtime-receipt.js", import.meta.url),
  );
  const harness = createHarness();
  const invalidReasons = [];
  const actualRecorder = createExp005RuntimeReceiptRecorder();
  const receiptRecorder = {
    ...actualRecorder,
    invalidate(reason) {
      invalidReasons.push(reason);
      actualRecorder.invalidate(reason);
    },
  };
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    receiptRecorder,
    async fetchFn(url, options = {}) {
      if (url.endsWith("/v1/runtime-boundary")) {
        return okJson({
          protocol_version: 1,
          transport_scope: "loopback",
          max_sessions: 1,
          ticket_one_use: true,
        });
      }
      if (options.method === "DELETE") {
        return { ok: true, status: 204 };
      }
      return okJson(gatewayDocument(url));
    },
  });
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };
  const trial = {
    roster_revision: hash("9"),
    plan_revision: hash("8"),
    roster_entries: [
      {
        model_id: "rvc-v2",
        profile_id: VC_PROFILE_IDS.rvc,
        profile_hash: hash("a"),
        configuration_hash: hash("1"),
        route_mode: "live",
      },
      {
        model_id: "beatrice-2",
        profile_id: VC_PROFILE_IDS.beatrice,
        profile_hash: hash("b"),
        configuration_hash: hash("2"),
        route_mode: "live",
      },
      {
        model_id: "x-vc",
        profile_id: VC_PROFILE_IDS.xvc,
        profile_hash: hash("c"),
        configuration_hash: hash("3"),
        route_mode: "live",
      },
      {
        model_id: "openvoice-v2",
        profile_id: VC_PROFILE_IDS.openvoice,
        profile_hash: hash("d"),
        configuration_hash: hash("4"),
        route_mode: "buffered_preview_after_end",
      },
    ],
    ssh_preflight: {
      schema_version: 1,
      check: "liveconv-ms2-ssh-preflight",
      status: "pass",
      client: {
        host_key_pinned: true,
        strict_host_key_checking: true,
        local_forward: {
          listen_host: "127.0.0.1",
          listen_port: 9765,
          target_host: "127.0.0.1",
          target_port: 8765,
        },
      },
      server: { forwarding_only: true, permitopen_loopback: true },
      gateway: {
        loopback_bound: true,
        bearer_auth_required: true,
        exact_extension_origin: true,
        one_use_ticket: true,
        max_sessions: 1,
      },
    },
  };
  assert.equal(
    await runtime.handleMessage({ type: "exp005.trial.begin", trial }, offscreenSender),
    null,
  );
  const begun = await runtime.handleMessage(
    { type: "exp005.trial.begin", trial },
    popupSender,
  );
  assert.equal(begun.ok, true);
  assert.match(begun.receipt.receiptId, /^[0-9a-f-]{36}$/);
  await runtime.configure({
    gatewayUrl: "http://127.0.0.1:9765",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  assert.equal(
    (await runtime.handleMessage(
      { type: "session.start", userGesture: true },
      popupSender,
    )).ok,
    true,
  );

  const receive = async (receipt) => runtime.handleMessage(
    { target: "background", type: "offscreen.event", event: { receipt } },
    offscreenSender,
  );
  const session = sessionResponse();
  const attempts = [
    ["rvc-v2", VC_PROFILE_IDS.rvc, hash("a"), hash("1"), session.pipeline_id, 1],
    ["beatrice-2", VC_PROFILE_IDS.beatrice, hash("b"), hash("2"), "30000000-0000-4000-8000-000000000002", 2],
    ["x-vc", VC_PROFILE_IDS.xvc, hash("c"), hash("3"), "30000000-0000-4000-8000-000000000003", 3],
    ["openvoice-v2", VC_PROFILE_IDS.openvoice, hash("d"), hash("4"), "30000000-0000-4000-8000-000000000004", 4],
  ];
  await receive({
    type: "gateway.attached",
    sessionId: session.session_id,
    pipelineId: attempts[0][4],
    profileId: attempts[0][1],
    profileHash: attempts[0][2],
    configurationHash: attempts[0][3],
  });
  for (const [index, [modelId, profileId, profileHash, configurationHash, pipelineId, generationId]] of attempts.entries()) {
    await receive({
      type: "generation.ready",
      generationId,
      pipelineId,
      profileId,
      profileHash,
      configurationHash,
    });
    await receive({
      type: "generation.output",
      generationId,
      pipelineId,
      finite: true,
      changed: true,
    });
    await receive({
      type: "remote.playout",
      generationId,
      pipelineId,
      nativeAudible: false,
      remoteAudible: true,
    });
    await receive({
      type: "generation.terminal",
      generationId,
      pipelineId,
      endTriggered: modelId === "openvoice-v2",
    });
    assert.equal(
      (await runtime.handleMessage({ type: "generation.end" }, popupSender)).ok,
      true,
    );
    if (index < attempts.length - 1) {
      assert.equal(
        (await runtime.handleMessage(
          { type: "model.select", profileId: attempts[index + 1][1] },
          popupSender,
        )).ok,
        true,
      );
      assert.equal(
        (await runtime.handleMessage({ type: "generation.start" }, popupSender)).ok,
        true,
      );
    }
  }
  assert.equal(
    (await runtime.handleMessage({ type: "generation.start" }, popupSender)).ok,
    true,
  );
  await receive({
    type: "generation.ready",
    generationId: 5,
    pipelineId: attempts[3][4],
    profileId: attempts[3][1],
    profileHash: attempts[3][2],
    configurationHash: attempts[3][3],
  });
  assert.equal(
    (await runtime.handleMessage(
      { type: "exp005.trial.inject-failure" },
      popupSender,
    )).ok,
    true,
  );
  await receive({
    type: "fallback.required",
    generationId: 5,
    pipelineId: attempts[3][4],
    injected: true,
  });
  await receive({
    type: "native.fallback",
    generationId: 5,
    pipelineId: attempts[3][4],
    nativeAudible: true,
    remoteAudible: false,
  });
  const exported = await runtime.handleMessage(
    { type: "exp005.trial.export" },
    popupSender,
  );
  assert.deepEqual(invalidReasons, []);
  assert.equal(exported.ok, true, exported.error);
  assert.equal(exported.receipt.attempts.length, 4);
  assert.equal(exported.receipt.forced_failure_event.generation_id, 5);
  assert.equal(exported.receipt.forced_failure_event.model_id, "openvoice-v2");
  assert.equal(JSON.stringify(exported.receipt).includes(session.ticket), false);
  assert.equal(
    await runtime.handleMessage({ type: "exp005.trial.export" }, offscreenSender),
    null,
  );
  assert.equal(
    (await runtime.handleMessage({ type: "exp005.trial.clear" }, popupSender)).ok,
    true,
  );
  const afterClear = await runtime.handleMessage(
    { type: "exp005.trial.export" },
    popupSender,
  );
  assert.equal(afterClear.ok, false);
  assert.match(afterClear.error, /has not begun/i);
});

test("EXP-005 capture evidence uses Chrome's actual active-tab audible state", async () => {
  const { createBrowserRuntime } = await import(moduleUrl);
  const harness = createHarness();
  harness.setActiveTab({ audible: false });
  const captureObservations = [];
  const noop = () => undefined;
  const receiptRecorder = {
    active: () => true,
    authorizeFailureInjection: () => false,
    begin: noop,
    checkpoint: () => ({ schema_version: 1 }),
    clear: noop,
    exportReceipt: noop,
    invalidate: noop,
    observeCaptureStarted(observation) {
      captureObservations.push(observation);
      return false;
    },
    observeForcedFallback: noop,
    observeGatewayAttached: noop,
    observeGatewayBoundary: noop,
    observeGatewaySession: noop,
    observeGenerationTerminal: noop,
    observeNativeFallback: noop,
    observeOutput: noop,
    observeRemotePlayout: noop,
    observeStaleOutputAccepted: noop,
    restore: noop,
    startAttempt: noop,
  };
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    receiptRecorder,
    async fetchFn() {
      assert.fail("a native-only start must not request the Gateway");
    },
  });

  await runtime.start({ userGesture: true });
  assert.deepEqual(captureObservations, [{
    tabUrl: "https://chatgpt.com/",
    tabAudible: false,
    userGesture: true,
  }]);
});

test("EXP-005 receipt resumes after service-worker restart and corrupt state fails closed", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const harness = createHarness();
  const fetchFn = async (url, options = {}) => {
    if (url.endsWith("/v1/runtime-boundary")) {
      return okJson({
        protocol_version: 1,
        transport_scope: "loopback",
        max_sessions: 1,
        ticket_one_use: true,
      });
    }
    if (options.method === "DELETE") {
      return { ok: true, status: 204 };
    }
    return okJson(gatewayDocument(url));
  };
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };
  const runtimeA = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn });
  assert.equal(
    (await runtimeA.handleMessage(
      { type: "exp005.trial.begin", trial: exp005TrialFixture() },
      popupSender,
    )).ok,
    true,
  );
  await runtimeA.configure({
    gatewayUrl: "http://127.0.0.1:9765",
    profileId: VC_PROFILE_IDS.rvc,
    token: "0123456789abcdefghijklmnopqrstuv",
  });
  await runtimeA.start({ userGesture: true });
  const session = sessionResponse();
  const sendReceipt = (runtime, receipt) => runtime.handleMessage(
    { target: "background", type: "offscreen.event", event: { receipt } },
    offscreenSender,
  );
  await sendReceipt(runtimeA, {
    type: "gateway.attached",
    sessionId: session.session_id,
    pipelineId: session.pipeline_id,
    profileId: session.profile_id,
    profileHash: session.profile_hash,
    configurationHash: session.configuration_hash,
  });
  await sendReceipt(runtimeA, {
    type: "generation.ready",
    generationId: 1,
    pipelineId: session.pipeline_id,
    profileId: session.profile_id,
    profileHash: session.profile_hash,
    configurationHash: session.configuration_hash,
  });
  await sendReceipt(runtimeA, {
    type: "generation.output",
    generationId: 1,
    pipelineId: session.pipeline_id,
    finite: true,
    changed: true,
  });

  const persisted = harness.sessionStorage.get(sessionStorageKeys.exp005ReceiptState);
  assert.equal(persisted.active_attempt_index, 0);
  assert.equal(
    /ticket|pcm|samples|tabUrl|gatewayUrl|websocket|path/i.test(
      JSON.stringify(persisted),
    ),
    false,
  );
  const runtimeB = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn });
  await sendReceipt(runtimeB, {
    type: "remote.playout",
    generationId: 1,
    pipelineId: session.pipeline_id,
    nativeAudible: false,
    remoteAudible: true,
  });
  await sendReceipt(runtimeB, {
    type: "generation.stale-output",
    generationId: 1,
    pipelineId: session.pipeline_id,
    accepted: false,
  });
  await sendReceipt(runtimeB, {
    type: "generation.terminal",
    generationId: 1,
    pipelineId: session.pipeline_id,
    endTriggered: false,
  });
  assert.equal(
    harness.sessionStorage.get(sessionStorageKeys.exp005ReceiptState).attempts[0]
      .terminal,
    true,
  );

  const corrupt = structuredClone(
    harness.sessionStorage.get(sessionStorageKeys.exp005ReceiptState),
  );
  corrupt.attempts[0].profileHash = hash("f");
  harness.sessionStorage.set(sessionStorageKeys.exp005ReceiptState, corrupt);
  const runtimeC = createBrowserRuntime({ chromeApi: harness.chromeApi, fetchFn });
  const rejected = await runtimeC.handleMessage(
    { type: "exp005.trial.export" },
    popupSender,
  );
  assert.equal(rejected.ok, false);
  assert.match(rejected.error, /corrupt/i);
  assert.equal(
    (await runtimeC.handleMessage({ type: "exp005.trial.clear" }, popupSender)).ok,
    true,
  );
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.exp005ReceiptState),
    false,
  );
});

test("EXP-005 clear cannot be undone by an older pending receipt write", async () => {
  const { createBrowserRuntime, sessionStorageKeys } = await import(moduleUrl);
  const pendingWrite = deferred();
  const writeReached = deferred();
  let blockNextReceiptWrite = false;
  const harness = createHarness({
    storageSet(values) {
      if (
        blockNextReceiptWrite &&
        Object.hasOwn(values, sessionStorageKeys.exp005ReceiptState)
      ) {
        blockNextReceiptWrite = false;
        writeReached.resolve();
        return pendingWrite.promise;
      }
      return undefined;
    },
  });
  const runtime = createBrowserRuntime({
    chromeApi: harness.chromeApi,
    fetchFn: async (url) => okJson(gatewayDocument(url)),
  });
  const popupSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/popup/popup.html`,
  };
  const offscreenSender = {
    id: harness.extensionId,
    url: `chrome-extension://${harness.extensionId}/offscreen/offscreen.html`,
  };
  assert.equal(
    (await runtime.handleMessage(
      { type: "exp005.trial.begin", trial: exp005TrialFixture() },
      popupSender,
    )).ok,
    true,
  );

  blockNextReceiptWrite = true;
  const invalidatingEvent = runtime.handleMessage(
    {
      target: "background",
      type: "offscreen.event",
      event: { receipt: { type: "unsupported.test.event" } },
    },
    offscreenSender,
  );
  await writeReached.promise;
  const clearing = runtime.handleMessage({ type: "exp005.trial.clear" }, popupSender);
  pendingWrite.resolve();
  const [eventResult, clearResult] = await Promise.all([invalidatingEvent, clearing]);
  assert.equal(eventResult.ok, true);
  assert.equal(clearResult.ok, true);
  assert.equal(
    harness.sessionStorage.has(sessionStorageKeys.exp005ReceiptState),
    false,
  );
});
