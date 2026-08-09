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

function popupHarness({ initialState, pendingType }) {
  const requests = [];
  const pending = deferred();
  const gatewayInput = new FakeElement({ value: "http://127.0.0.1:8765" });
  const profileInput = new FakeElement({ value: "test.passthrough.v1" });
  const tokenInput = new FakeElement();
  const elements = new Map(
    [
      '[data-role="session-status"]',
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
          return Promise.resolve({ ok: true, state: initialState });
        }
        if (message.type === pendingType) {
          return pending.promise;
        }
        if (message.type === "session.stop") {
          return Promise.resolve({
            ok: true,
            state: {
              ...initialState,
              capture: "stopped",
              remote: "disconnected",
              generationId: null,
            },
          });
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
