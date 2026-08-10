import assert from "node:assert/strict";
import test from "node:test";

const popupModuleUrl = new URL("../popup/popup.js", import.meta.url);

function deferred() {
  let resolve;
  const promise = new Promise((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

class FakeElement {
  constructor({ value = "" } = {}) {
    this.children = [];
    this.disabled = false;
    this.label = "";
    this.listeners = new Map();
    this.textContent = "";
    this.value = value;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  dispatch(type) {
    const event = { preventDefault() {} };
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  click() {
    this.dispatch("click");
  }

  replaceChildren(...children) {
    this.children = children;
  }
}

function popupHarness({ initialState, models = [], pendingType }) {
  const requests = [];
  const pending = deferred();
  let runtimeState = initialState;
  const gatewayInput = new FakeElement({ value: "http://127.0.0.1:8765" });
  const profileInput = new FakeElement({ value: "test.passthrough.v1" });
  const tokenInput = new FakeElement();
  const elements = new Map(
    [
      '[data-role="session-status"]',
      '[data-role="route-status"]',
      '[data-role="conversion-progress"]',
      '[data-role="token-status"]',
      '[data-action="start"]',
      '[data-action="stop"]',
      '[data-action="end"]',
      '[data-action="cancel"]',
      '[data-action="next"]',
      '[data-action="configure"]',
      '[data-action="models"]',
      '[data-action="select-profile"]',
      "#profile-options",
      '[data-role="profile-identity"]',
      '[data-role="model-roster"]',
    ].map((selector) => [selector, new FakeElement()]),
  );
  const form = new FakeElement();
  form.elements = {
    namedItem(name) {
      return { gatewayUrl: gatewayInput, profileId: profileInput, token: tokenInput }[
        name
      ];
    },
  };
  elements.set('[data-role="configuration"]', form);
  let popupMessageListener = null;
  const chromeApi = {
    permissions: {},
    runtime: {
      id: "abcdefghijklmnopabcdefghijklmnop",
      onMessage: {
        addListener(listener) {
          popupMessageListener = listener;
        },
      },
      sendMessage(message) {
        requests.push(message);
        if (message.type === "session.status") {
          return Promise.resolve({ ok: true, state: runtimeState });
        }
        if (message.type === "models.list") {
          return Promise.resolve({ ok: true, state: runtimeState, models });
        }
        if (message.type === "variants.list") {
          return Promise.resolve({ ok: true, state: runtimeState, variants: models });
        }
        if (message.type === pendingType) {
          return pending.promise;
        }
        if (message.type === "session.stop") {
          runtimeState = {
            ...runtimeState,
            capture: "stopped",
            remote: "disconnected",
            generationId: null,
          };
          return Promise.resolve({
            ok: true,
            state: runtimeState,
          });
        }
        if (message.type === "generation.cancel") {
          runtimeState = {
            ...runtimeState,
            route: "native",
            remote: "ready",
            generationId: null,
          };
          return Promise.resolve({ ok: true, state: runtimeState });
        }
        if (message.type === "model.select") {
          runtimeState = {
            ...runtimeState,
            configuration: {
              ...runtimeState.configuration,
              profileId: message.profileId,
            },
          };
          return Promise.resolve({ ok: true, state: runtimeState });
        }
        if (message.type === "generation.start") {
          runtimeState = {
            ...runtimeState,
            route: "native",
            remote: "pending",
            generationId: 10,
          };
          return Promise.resolve({ ok: true, state: runtimeState });
        }
        throw new Error(`unexpected popup message: ${message.type}`);
      },
    },
  };
  const document = {
    createElement() {
      return new FakeElement();
    },
    querySelector(selector) {
      return elements.get(selector) ?? null;
    },
  };
  return {
    chromeApi,
    document,
    elements,
    pending,
    popupMessageListener: () => popupMessageListener,
    requests,
  };
}

async function loadPopup(t, harness, caseName) {
  const previousChrome = globalThis.chrome;
  const previousDocument = globalThis.document;
  globalThis.chrome = harness.chromeApi;
  globalThis.document = harness.document;
  t.after(() => {
    globalThis.chrome = previousChrome;
    globalThis.document = previousDocument;
  });
  await import(`${popupModuleUrl.href}?case=${caseName}`);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(typeof harness.popupMessageListener(), "function");
}

const stoppedState = {
  capture: "stopped",
  route: "native",
  remote: "disconnected",
  generationId: null,
  configuration: { configured: false, gatewayUrl: null, profileId: null },
};

test("popup DOM keeps Stop reachable while Start is unresolved", async (t) => {
  const harness = popupHarness({
    initialState: stoppedState,
    pendingType: "session.start",
  });
  await loadPopup(t, harness, "unresolved-start");
  const start = harness.elements.get('[data-action="start"]');
  const stop = harness.elements.get('[data-action="stop"]');

  start.click();

  assert.equal(start.disabled, true);
  assert.equal(stop.disabled, false, "Stop must remain reachable during Start");
  stop.click();
  assert.equal(stop.disabled, true, "only the pending Stop operation disables Stop");
  assert(harness.requests.some((message) => message.type === "session.stop"));
});

test("popup DOM keeps Stop reachable while End is unresolved", async (t) => {
  const harness = popupHarness({
    initialState: {
      ...stoppedState,
      capture: "running",
      remote: "pending",
      generationId: 9,
    },
    pendingType: "generation.end",
  });
  await loadPopup(t, harness, "unresolved-end");
  const end = harness.elements.get('[data-action="end"]');
  const stop = harness.elements.get('[data-action="stop"]');

  end.click();

  assert.equal(stop.disabled, false, "Stop must remain reachable during End");
  stop.click();
  assert.equal(stop.disabled, true, "only the pending Stop operation disables Stop");
  assert(harness.requests.some((message) => message.type === "session.stop"));
});

test("popup exposes every route-qualified voice including buffered preview", async (t) => {
  const models = [
    {
      modelId: "rvc-v2",
      displayName: "RVC v2",
      profileId: "vc.rvc.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "quality-failed",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
    {
      modelId: "beatrice-2",
      displayName: "Beatrice 2",
      profileId: "vc.beatrice.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "technical-only",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
    {
      modelId: "x-vc",
      displayName: "X-VC",
      profileId: "vc.x-vc.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "quality-failed",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
    {
      modelId: "openvoice-v2",
      displayName: "OpenVoice V2",
      profileId: "vc.openvoice-v2.synthetic-ja.v1",
      invocationMode: "buffered_end",
      executionState: "buffered-preview",
      decisionState: "unassessed",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
  ];
  const harness = popupHarness({
    initialState: {
      ...stoppedState,
      configuration: {
        configured: true,
        gatewayUrl: "https://audio.example.test",
        profileId: "vc.beatrice.synthetic-ja.v1",
      },
    },
    models,
  });
  await loadPopup(t, harness, "all-roster-models");

  const profile = harness.document
    .querySelector('[data-role="configuration"]')
    .elements.namedItem("profileId");
  const options = profile.children;
  assert.equal(options.length, 4);
  assert.deepEqual(
    options.map((option) => option.value),
    [
      "vc.rvc.synthetic-ja.v1",
      "vc.beatrice.synthetic-ja.v1",
      "vc.x-vc.synthetic-ja.v1",
      "vc.openvoice-v2.synthetic-ja.v1",
    ],
  );
  assert.deepEqual(
    options.map((option) => option.textContent),
    [
      "RVC v2",
      "Beatrice 2",
      "X-VC",
      "OpenVoice V2（区間終了後）",
    ],
  );
  assert(options.every((option) => option.disabled === false));
  assert.equal(profile.value, "vc.beatrice.synthetic-ja.v1");
});

test("popup selector applies immediately at a running generation boundary", async (t) => {
  const models = [
    {
      modelId: "rvc-v2",
      displayName: "RVC v2",
      profileId: "vc.rvc.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "quality-failed",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
  ];
  const harness = popupHarness({
    initialState: {
      ...stoppedState,
      capture: "running",
      remote: "ready",
      generationId: null,
      configuration: {
        configured: true,
        gatewayUrl: "http://127.0.0.1:18765",
        profileId: "vc.beatrice.synthetic-ja.v1",
      },
    },
    models,
    pendingType: "model.select",
  });
  await loadPopup(t, harness, "row-live-select");

  const profile = harness.document
    .querySelector('[data-role="configuration"]')
    .elements.namedItem("profileId");
  profile.value = "vc.rvc.synthetic-ja.v1";
  profile.dispatch("change");

  assert(
    harness.requests.some(
      (message) =>
        message.type === "model.select" &&
        message.profileId === "vc.rvc.synthetic-ja.v1",
    ),
  );
});

test("popup selector automatically interrupts, switches, and resumes an active model", async (t) => {
  const models = [
    {
      modelId: "rvc-v2",
      displayName: "RVC v2",
      profileId: "vc.rvc.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "quality-failed",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
    {
      modelId: "beatrice-2",
      displayName: "Beatrice 2",
      profileId: "vc.beatrice.synthetic-ja.v1",
      invocationMode: "live",
      executionState: "live-trial",
      decisionState: "technical-only",
      voiceRequirement: "pretrained_voice",
      reasonCode: null,
      selectable: true,
    },
  ];
  const harness = popupHarness({
    initialState: {
      ...stoppedState,
      capture: "running",
      remote: "pending",
      generationId: 9,
      configuration: {
        configured: true,
        gatewayUrl: "http://127.0.0.1:18765",
        profileId: "vc.beatrice.synthetic-ja.v1",
      },
    },
    models,
  });
  await loadPopup(t, harness, "selector-active-switch");

  const profile = harness.document
    .querySelector('[data-role="configuration"]')
    .elements.namedItem("profileId");
  profile.value = "vc.rvc.synthetic-ja.v1";
  profile.dispatch("change");
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(
    harness.requests.slice(-3).map((message) => message.type),
    ["generation.cancel", "model.select", "generation.start"],
  );
  assert.equal(harness.requests.at(-2).profileId, "vc.rvc.synthetic-ja.v1");
});

test("popup makes saved-token and active remote playout visible after reopen", async (t) => {
  const harness = popupHarness({
    initialState: {
      ...stoppedState,
      capture: "running",
      route: "remote",
      remote: "ready",
      generationId: 7,
      configuration: {
        configured: true,
        gatewayUrl: "http://127.0.0.1:18765",
        profileId: "vc.beatrice.synthetic-ja.v1",
      },
    },
    models: [
      {
        modelId: "beatrice-2",
        displayName: "Beatrice 2・低めの声",
        profileId: "vc.beatrice.synthetic-ja.v1",
        invocationMode: "live",
        executionState: "live-trial",
        decisionState: "technical-only",
        voiceRequirement: "pretrained_voice",
        reasonCode: null,
        selectable: true,
      },
    ],
  });
  await loadPopup(t, harness, "saved-token-remote-route");

  const token = harness.document
    .querySelector('[data-role="configuration"]')
    .elements.namedItem("token");
  assert.equal(token.required, false);
  assert.match(token.placeholder, /保存済み/);
  assert.match(
    harness.elements.get('[data-role="token-status"]').textContent,
    /空欄表示が正常/,
  );
  assert.match(
    harness.elements.get('[data-role="route-status"]').textContent,
    /Beatrice 2・低めの声へ変換して再生中/,
  );
  harness.popupMessageListener()(
    {
      target: "popup",
      type: "conversion.progress",
      progress: { generationId: 7, inputFrames: 75, outputFrames: 50 },
    },
    { id: harness.chromeApi.runtime.id },
  );
  assert.equal(
    harness.elements.get('[data-role="conversion-progress"]').textContent,
    "実変換: 1.0秒（50フレーム）",
  );
});
