import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/capture-orchestrator.js", import.meta.url);

function createHarness({ documentExists = false, connectError = null } = {}) {
  const calls = [];
  let offscreenOpen = documentExists;
  let nativeLoopbackActive = false;
  let selectedRoute = "native";

  const dependencies = {
    tabCapture: {
      async getMediaStreamId() {
        calls.push({ name: "tabCapture.getMediaStreamId" });
        return "synthetic-tab-stream-id";
      },
    },
    offscreen: {
      async hasDocument() {
        calls.push({ name: "offscreen.hasDocument" });
        return offscreenOpen;
      },
      async createDocument(options) {
        calls.push({ name: "offscreen.createDocument", options });
        offscreenOpen = true;
      },
      async closeDocument() {
        calls.push({ name: "offscreen.closeDocument" });
        offscreenOpen = false;
      },
    },
    audioGraph: {
      async startNativeLoopback(options) {
        calls.push({ name: "audioGraph.startNativeLoopback", options });
        nativeLoopbackActive = true;
      },
      async stop() {
        calls.push({ name: "audioGraph.stop" });
        nativeLoopbackActive = false;
      },
    },
    remote: {
      async connect() {
        calls.push({ name: "remote.connect" });
        if (connectError) {
          throw connectError;
        }
      },
      async close() {
        calls.push({ name: "remote.close" });
      },
    },
    selector: {
      select(route) {
        calls.push({ name: "selector.select", route });
        selectedRoute = route;
      },
    },
  };

  return {
    calls,
    dependencies,
    state() {
      return { nativeLoopbackActive, offscreenOpen, selectedRoute };
    },
  };
}

function callNames(harness) {
  return harness.calls.map((call) => call.name);
}

test("capture can start only from an explicit user gesture", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const harness = createHarness();
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await assert.rejects(
    orchestrator.start({ userGesture: false }),
    /user gesture/i,
  );
  await assert.rejects(orchestrator.start({}), /user gesture/i);

  assert.deepEqual(harness.calls, []);
  assert.equal(orchestrator.snapshot().capture, "stopped");
  assert.equal(orchestrator.snapshot().route, "native");
});

test("explicit start creates one Offscreen Document and starts native before remote", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const harness = createHarness();
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await orchestrator.start({ userGesture: true });

  const createCall = harness.calls.find(
    (call) => call.name === "offscreen.createDocument",
  );
  assert(createCall, "an Offscreen Document must be created for the media graph");
  assert.equal(createCall.options.url, "offscreen/offscreen.html");
  assert(createCall.options.reasons.includes("USER_MEDIA"));
  assert.equal(typeof createCall.options.justification, "string");
  assert(createCall.options.justification.length > 0);

  const graphCall = harness.calls.find(
    (call) => call.name === "audioGraph.startNativeLoopback",
  );
  assert.deepEqual(graphCall?.options, { streamId: "synthetic-tab-stream-id" });
  assert(
    callNames(harness).indexOf("audioGraph.startNativeLoopback") <
      callNames(harness).indexOf("remote.connect"),
    "native loopback must be established before the remote attempt",
  );
  assert.deepEqual(harness.state(), {
    nativeLoopbackActive: true,
    offscreenOpen: true,
    selectedRoute: "native",
  });
  assert.deepEqual(orchestrator.snapshot(), {
    capture: "running",
    offscreen: "open",
    remote: "pending",
    route: "native",
  });
});

test("native remains selected until generation-specific remote readiness", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const harness = createHarness();
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await orchestrator.start({ userGesture: true });
  assert.equal(harness.state().selectedRoute, "native");
  assert.equal(
    harness.calls.filter(
      (call) => call.name === "selector.select" && call.route === "remote",
    ).length,
    0,
  );

  orchestrator.remoteReady(7);

  assert.equal(harness.state().selectedRoute, "remote");
  assert.equal(orchestrator.snapshot().route, "remote");
  assert.equal(orchestrator.snapshot().remote, "ready");
  assert.equal(orchestrator.snapshot().generationId, 7);
});

test("start is idempotent and reuses an existing Offscreen Document", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const harness = createHarness({ documentExists: true });
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await Promise.all([
    orchestrator.start({ userGesture: true }),
    orchestrator.start({ userGesture: true }),
  ]);

  assert.equal(
    harness.calls.filter((call) => call.name === "tabCapture.getMediaStreamId")
      .length,
    1,
  );
  assert.equal(
    harness.calls.filter((call) => call.name === "offscreen.createDocument")
      .length,
    0,
  );
  assert.equal(
    harness.calls.filter(
      (call) => call.name === "audioGraph.startNativeLoopback",
    ).length,
    1,
  );
  assert.equal(
    harness.calls.filter((call) => call.name === "remote.connect").length,
    1,
  );
});

test("remote connection failure stays native and releases capture resources", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const failure = new Error("synthetic remote denial");
  const harness = createHarness({ connectError: failure });
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await assert.rejects(
    orchestrator.start({ userGesture: true }),
    (error) => error === failure,
  );

  assert.equal(harness.state().selectedRoute, "native");
  assert.equal(harness.state().nativeLoopbackActive, false);
  assert.equal(harness.state().offscreenOpen, false);
  assert.equal(orchestrator.snapshot().capture, "stopped");
  assert.equal(orchestrator.snapshot().route, "native");
  assert(callNames(harness).includes("audioGraph.stop"));
  assert(callNames(harness).includes("offscreen.closeDocument"));
});

test("stop returns to native before closing remote and Offscreen resources", async () => {
  const { createCaptureOrchestrator } = await import(moduleUrl);
  const harness = createHarness();
  const orchestrator = createCaptureOrchestrator(harness.dependencies);

  await orchestrator.start({ userGesture: true });
  orchestrator.remoteReady(7);
  await orchestrator.stop();

  const nativeSelect = harness.calls.findLastIndex(
    (call) => call.name === "selector.select" && call.route === "native",
  );
  const remoteClose = harness.calls.findLastIndex(
    (call) => call.name === "remote.close",
  );
  assert(nativeSelect < remoteClose);
  assert.deepEqual(harness.state(), {
    nativeLoopbackActive: false,
    offscreenOpen: false,
    selectedRoute: "native",
  });
  assert.deepEqual(orchestrator.snapshot(), {
    capture: "stopped",
    offscreen: "closed",
    remote: "disconnected",
    route: "native",
  });
});
