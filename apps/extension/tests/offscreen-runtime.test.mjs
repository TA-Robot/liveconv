import assert from "node:assert/strict";
import test from "node:test";

import { createDeferred, flushMicrotasks } from "./support.mjs";

const moduleUrl = new URL("../src/offscreen-runtime.js", import.meta.url);

function createHarness(createOffscreenRuntime) {
  const calls = [];
  const notifications = [];
  let graphCallbacks;
  let remoteCallbacks;
  let drainGate = null;
  const graph = {
    async startNativeLoopback(options) {
      calls.push({ name: "graph.startNativeLoopback", options });
    },
    beginGeneration(generationId, options) {
      calls.push({ name: "graph.beginGeneration", generationId, options });
    },
    endGeneration(generationId) {
      calls.push({ name: "graph.endGeneration", generationId });
    },
    drainGeneration(generationId) {
      calls.push({ name: "graph.drainGeneration", generationId });
      return drainGate?.promise ?? Promise.resolve();
    },
    completeGeneration(generationId) {
      calls.push({ name: "graph.completeGeneration", generationId });
    },
    cancelGeneration(generationId, reasonCode) {
      calls.push({ name: "graph.cancelGeneration", generationId, reasonCode });
    },
    enqueueRemoteFrame(frame) {
      calls.push({ name: "graph.enqueueRemoteFrame", frame });
      return true;
    },
    fallback(event) {
      calls.push({ name: "graph.fallback", event });
    },
    async stop() {
      calls.push({ name: "graph.stop" });
    },
  };
  const client = {
    async connect(options) {
      calls.push({ name: "client.connect", options });
    },
    async startGeneration(generationId) {
      calls.push({ name: "client.startGeneration", generationId });
    },
    async selectProfile(profileId, expectedProfile) {
      calls.push({ name: "client.selectProfile", profileId, expectedProfile });
    },
    sendFrame(frame) {
      calls.push({ name: "client.sendFrame", frame });
      return true;
    },
    endGeneration(generationId) {
      calls.push({ name: "client.endGeneration", generationId });
      return Promise.resolve();
    },
    cancelGeneration(generationId) {
      calls.push({ name: "client.cancelGeneration", generationId });
      return Promise.resolve();
    },
    close() {
      calls.push({ name: "client.close" });
      return Promise.resolve();
    },
  };
  const runtime = createOffscreenRuntime({
    audioGraphFactory(callbacks) {
      graphCallbacks = callbacks;
      return graph;
    },
    remoteClientFactory(callbacks) {
      remoteCallbacks = callbacks;
      return client;
    },
    async sendMessage(message) {
      calls.push({ name: "runtime.sendMessage", message });
      notifications.push(message);
    },
    nowNanoseconds() {
      return 5_000_000_000n;
    },
  });
  return {
    calls,
    client,
    graph,
    notifications,
    runtime,
    get graphCallbacks() {
      return graphCallbacks;
    },
    get remoteCallbacks() {
      return remoteCallbacks;
    },
    setDrainGate(value) {
      drainGate = value;
    },
  };
}

async function startConnected(harness, invocationMode = "live") {
  const sender = {
    id: "extension-id",
    url: "chrome-extension://extension-id/src/background.js",
  };
  let response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.native.start",
      streamId: "tab-stream-id",
      tabId: 42,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.remote.connect",
      url: "wss://audio.example.test/v1/ws",
      sessionId: "11111111-1111-4111-8111-111111111111",
      ticket: "one-use-ticket",
      generationId: 7,
      expectedProfile: {
        profileId: "vc.synthetic.v1",
        profileHash:
          "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        configurationHash:
          "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        pipelineId: "22222222-2222-4222-8222-222222222222",
      },
      expectedLimits: { ingressBudgetMs: 1_000, maxIngressFrames: 50 },
      invocationMode,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  return sender;
}

async function configureReceipt(harness, enabled) {
  const response = await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.receipt.configure", enabled },
    {
      id: "extension-id",
      url: "chrome-extension://extension-id/src/background.js",
    },
    "extension-id",
  );
  assert.equal(response.ok, true);
}

test("Offscreen status binds a UUID epoch to only the current capture graph", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = {
    id: "extension-id",
    url: "chrome-extension://extension-id/src/background.js",
  };
  const started = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.native.start",
      streamId: "tab-stream-id",
      tabId: 42,
    },
    sender,
    "extension-id",
  );
  assert.equal(started.ok, true);
  assert.match(
    started.state.offscreenEpoch,
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  );

  const runningStatus = await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.status" },
    sender,
    "extension-id",
  );
  assert.equal(runningStatus.state.offscreenEpoch, started.state.offscreenEpoch);

  await harness.runtime.stop();
  const stoppedStatus = await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.status" },
    sender,
    "extension-id",
  );
  assert.equal(Object.hasOwn(stoppedStatus.state, "offscreenEpoch"), false);
});

test("Offscreen owns tab media, remote transport, and timestamped uplink without messaging PCM through the service worker", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  await startConnected(harness);

  assert.deepEqual(
    harness.calls.filter((call) =>
      [
        "graph.startNativeLoopback",
        "client.connect",
        "client.startGeneration",
        "graph.beginGeneration",
      ].includes(call.name),
    ).slice(0, 4),
    [
    {
      name: "graph.startNativeLoopback",
      options: { streamId: "tab-stream-id", tabId: 42 },
    },
    {
      name: "client.connect",
      options: {
        url: "wss://audio.example.test/v1/ws",
        sessionId: "11111111-1111-4111-8111-111111111111",
        ticket: "one-use-ticket",
        expectedProfile: {
          profileId: "vc.synthetic.v1",
          profileHash:
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          configurationHash:
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          pipelineId: "22222222-2222-4222-8222-222222222222",
        },
        expectedLimits: { ingressBudgetMs: 1_000, maxIngressFrames: 50 },
      },
    },
    { name: "client.startGeneration", generationId: 7 },
    {
      name: "graph.beginGeneration",
      generationId: 7,
      options: { captureCreditFrames: 50 },
    },
  ]);

  assert.equal(harness.graphCallbacks.onCaptureFrame({
    generationId: 7,
    sourceFrame: 100,
    samples: new Float32Array(960),
  }), true);
  assert.equal(harness.graphCallbacks.onCaptureFrame({
    generationId: 7,
    sourceFrame: 1_060,
    samples: new Float32Array(960),
  }), true);
  const sent = harness.calls.filter((call) => call.name === "client.sendFrame");
  assert.equal(sent.length, 2);
  assert.equal(sent[0].frame.header.sequence, 0);
  assert.equal(sent[0].frame.header.source_monotonic_ns, 5_000_000_000n);
  assert.equal(sent[1].frame.header.sequence, 1);
  assert.equal(sent[1].frame.header.source_monotonic_ns, 5_020_000_000n);
  assert.equal(
    harness.notifications.some((message) => Object.hasOwn(message, "samples")),
    false,
  );

  const output = {
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960),
  };
  harness.remoteCallbacks.onOutputFrame(output);
  assert.equal(harness.calls.at(-1).name, "graph.enqueueRemoteFrame");
  assert.equal(harness.calls.at(-1).frame.sourceFrame, 100);
});

test("offscreen emits bounded EXP-005 facts only after real protocol responses and local PCM comparison", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const identity = {
    profile_id: "vc.synthetic.v1",
    profile_hash:
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    configuration_hash:
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
  };
  harness.client.connect = async (options) => {
    harness.calls.push({ name: "client.connect", options });
    return {
      session_id: options.sessionId,
      ...identity,
    };
  };
  harness.client.startGeneration = async (generationId) => {
    harness.calls.push({ name: "client.startGeneration", generationId });
    return { generation_id: generationId, ...identity };
  };
  await configureReceipt(harness, true);
  const sender = await startConnected(harness);
  const input = new Float32Array(960);
  assert.equal(harness.graphCallbacks.onCaptureFrame({
    generationId: 7,
    sourceFrame: 100,
    samples: input,
  }), true);
  harness.remoteCallbacks.onOutputFrame({
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960).fill(0.25),
  });
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });
  await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.generation.end", generationId: 7 },
    sender,
    "extension-id",
  );

  const receipts = harness.notifications
    .map((message) => message.event.receipt)
    .filter(Boolean);
  assert.deepEqual(receipts.map((event) => event.type), [
    "gateway.attached",
    "generation.ready",
    "remote.playout",
    "generation.output",
    "generation.stale-output",
    "generation.terminal",
  ]);
  assert.deepEqual(receipts[3], {
    type: "generation.output",
    generationId: 7,
    pipelineId: identity.pipeline_id,
    finite: true,
    changed: true,
  });
  assert.deepEqual(receipts[2], {
    type: "remote.playout",
    generationId: 7,
    pipelineId: identity.pipeline_id,
    nativeAudible: false,
    remoteAudible: true,
  });
  assert.equal(receipts[4].accepted, false);
  assert.equal(receipts[5].endTriggered, false);
  assert.equal(/samples|pcm|ticket/i.test(JSON.stringify(receipts)), false);
});

test("receipt comparison precedes AudioGraph transfer of remote PCM", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const identity = {
    profile_id: "vc.synthetic.v1",
    profile_hash:
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    configuration_hash:
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
  };
  harness.client.connect = async () => identity;
  harness.client.startGeneration = async (generationId) => ({
    generation_id: generationId,
    ...identity,
  });
  harness.graph.enqueueRemoteFrame = (frame) => {
    harness.calls.push({ name: "graph.enqueueRemoteFrame.transfer" });
    structuredClone(frame.samples, { transfer: [frame.samples.buffer] });
    assert.equal(frame.samples.byteLength, 0);
    return true;
  };
  await configureReceipt(harness, true);
  const sender = await startConnected(harness);
  assert.equal(harness.graphCallbacks.onCaptureFrame({
    generationId: 7,
    sourceFrame: 100,
    samples: new Float32Array(960),
  }), true);
  const output = {
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960).fill(0.25),
  };
  harness.remoteCallbacks.onOutputFrame(output);
  assert.equal(output.samples.byteLength, 0);
  await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.generation.end", generationId: 7 },
    sender,
    "extension-id",
  );

  const receipt = harness.notifications
    .map((message) => message.event.receipt)
    .find((event) => event?.type === "generation.output");
  assert.deepEqual(receipt, {
    type: "generation.output",
    generationId: 7,
    pipelineId: identity.pipeline_id,
    finite: true,
    changed: true,
  });
});

test("inactive high-rate output emits no receipt and active output stays O(1)", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const identity = {
    profile_id: "vc.synthetic.v1",
    profile_hash:
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    configuration_hash:
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
  };
  harness.client.connect = async () => identity;
  harness.client.startGeneration = async (generationId) => ({
    generation_id: generationId,
    ...identity,
  });
  const sender = await startConnected(harness);
  const sendFrames = () => {
    for (let index = 0; index < 100; index += 1) {
      const sourceFrame = 100 + index * 960;
      harness.graphCallbacks.onCaptureFrame({
        generationId: 7,
        sourceFrame,
        samples: new Float32Array(960),
      });
      harness.remoteCallbacks.onOutputFrame({
        header: {
          generation_id: 7,
          sequence: index,
          source_monotonic_ns: 5_000_000_000n + BigInt(index * 20_000_000),
        },
        samples: new Float32Array(960).fill(0.25),
      });
    }
  };
  sendFrames();
  assert.equal(
    harness.notifications.some((message) => message.event.receipt),
    false,
  );
  await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.generation.cancel", generationId: 7 },
    sender,
    "extension-id",
  );

  await configureReceipt(harness, true);
  await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.generation.start", generationId: 8 },
    sender,
    "extension-id",
  );
  for (let index = 0; index < 100; index += 1) {
    const sourceFrame = 100 + index * 960;
    harness.graphCallbacks.onCaptureFrame({
      generationId: 8,
      sourceFrame,
      samples: new Float32Array(960),
    });
    harness.remoteCallbacks.onOutputFrame({
      header: {
        generation_id: 8,
        sequence: index,
        source_monotonic_ns: 5_000_000_000n + BigInt(index * 20_000_000),
      },
      samples: new Float32Array(960).fill(0.5),
    });
  }
  await harness.runtime.handleMessage(
    { target: "offscreen", type: "offscreen.generation.end", generationId: 8 },
    sender,
    "extension-id",
  );
  const generationEightReceipts = harness.notifications
    .map((message) => message.event.receipt)
    .filter((event) => event?.generationId === 8);
  assert.equal(
    generationEightReceipts.filter((event) => event.type === "generation.output").length,
    1,
  );
  assert(generationEightReceipts.length <= 4);
});

test("explicit EXP-005 injection is native-first and cannot be forged by Gateway fallback", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const identity = {
    profile_id: "vc.openvoice-v2.synthetic-ja.v1",
    profile_hash:
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    configuration_hash:
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    pipeline_id: "22222222-2222-4222-8222-222222222222",
  };
  harness.client.connect = async () => identity;
  harness.client.startGeneration = async (generationId) => ({
    generation_id: generationId,
    ...identity,
  });
  await configureReceipt(harness, true);
  const sender = await startConnected(harness, "buffered_end");
  const response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.exp005.inject-failure",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  const cancelIndex = harness.calls.findIndex(
    (call) => call.name === "graph.cancelGeneration" && call.generationId === 7,
  );
  const fallbackReceiptIndex = harness.calls.findIndex(
    (call) => call.name === "runtime.sendMessage" &&
      call.message.event.receipt?.type === "fallback.required",
  );
  assert(cancelIndex >= 0 && cancelIndex < fallbackReceiptIndex);
  const receipts = harness.notifications
    .map((message) => message.event.receipt)
    .filter((event) => ["fallback.required", "native.fallback"].includes(event?.type));
  assert.equal(receipts[0].injected, true);
  assert.equal(receipts[0].profileId, identity.profile_id);
  assert.equal(receipts[1].configurationHash, identity.configuration_hash);

  const naturalHarness = createHarness(createOffscreenRuntime);
  naturalHarness.client.connect = harness.client.connect;
  naturalHarness.client.startGeneration = harness.client.startGeneration;
  await configureReceipt(naturalHarness, true);
  await startConnected(naturalHarness, "buffered_end");
  await naturalHarness.remoteCallbacks.onFallback({ type: "fallback.required" });
  const natural = naturalHarness.notifications
    .map((message) => message.event.receipt)
    .find((event) => event?.type === "fallback.required");
  assert.equal(natural.injected, false);
});

test("remote playout becomes exclusive only after the graph reports its jitter target ready", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  await startConnected(harness);

  assert.equal(harness.runtime.snapshot().route, "native");
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });
  await flushMicrotasks();

  assert.deepEqual(harness.runtime.snapshot(), {
    capture: "running",
    route: "remote",
    remote: "ready",
    generationId: 7,
  });
  assert.deepEqual(harness.notifications.at(-1).event, {
    route: "remote",
    remote: "ready",
    generationId: 7,
  });
});

test("buffered preview captures at most 25 frames and cannot enqueue or select remote before End", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness, "buffered_end");
  const begin = harness.calls.find((call) => call.name === "graph.beginGeneration");
  assert.deepEqual(begin.options, {
    captureCreditFrames: 25,
    maximumCaptureFrames: 25,
  });
  assert.equal(
    harness.calls.some((call) => call.name === "client.endGeneration"),
    false,
  );

  const output = {
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960),
  };
  harness.remoteCallbacks.onOutputFrame(output);
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });
  assert.equal(
    harness.calls.some((call) => call.name === "graph.enqueueRemoteFrame"),
    false,
    "a buffered profile must discard early remote output",
  );
  assert.equal(harness.runtime.snapshot().route, "native");
  assert.equal(harness.runtime.snapshot().remote, "pending");

  assert.equal(
    harness.graphCallbacks.onCaptureFrame({
      generationId: 7,
      sourceFrame: 100,
      samples: new Float32Array(960),
    }),
    true,
  );
  const endGate = createDeferred();
  const drainGate = createDeferred();
  harness.setDrainGate(drainGate);
  harness.client.endGeneration = (generationId) => {
    harness.calls.push({ name: "client.endGeneration.blocked", generationId });
    return endGate.promise;
  };

  const ending = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.end",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();

  harness.remoteCallbacks.onOutputFrame(output);
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });
  assert.equal(
    harness.calls.filter((call) => call.name === "graph.enqueueRemoteFrame").length,
    1,
  );
  assert.equal(harness.runtime.snapshot().route, "remote");
  assert.equal(
    harness.runtime.snapshot().remote,
    "draining",
    "after-End playout remains accepted throughout the local drain",
  );

  endGate.resolve();
  await flushMicrotasks();
  const graphEnd = harness.calls.findIndex(
    (call) => call.name === "graph.endGeneration",
  );
  const remoteEnd = harness.calls.findIndex(
    (call) => call.name === "client.endGeneration.blocked",
  );
  const localDrain = harness.calls.findIndex(
    (call) => call.name === "graph.drainGeneration",
  );
  assert(graphEnd >= 0 && graphEnd < remoteEnd && remoteEnd < localDrain);
  drainGate.resolve();
  const response = await ending;
  assert.equal(response.ok, true);
});

test("fallback and explicit cancellation invalidate local playout before waiting for a server acknowledgement", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });

  const cancelGate = createDeferred();
  harness.client.cancelGeneration = (generationId) => {
    harness.calls.push({ name: "client.cancelGeneration.blocked", generationId });
    return cancelGate.promise;
  };
  const operation = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.cancel",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();

  assert.equal(harness.runtime.snapshot().route, "native");
  assert.equal(harness.runtime.snapshot().generationId, null);
  const localCancel = harness.calls.findIndex(
    (call) => call.name === "graph.cancelGeneration",
  );
  const remoteCancel = harness.calls.findIndex(
    (call) => call.name === "client.cancelGeneration.blocked",
  );
  assert(localCancel >= 0 && localCancel < remoteCancel);

  cancelGate.resolve();
  const response = await operation;
  assert.equal(response.ok, true);
  assert.equal(response.state.remote, "ready");
});

test("canceled or stale output cannot reclaim native playout", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  const canceled = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.cancel",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  assert.equal(canceled.ok, true);
  const enqueueCount = harness.calls.filter(
    (call) => call.name === "graph.enqueueRemoteFrame",
  ).length;
  const cancelCount = harness.calls.filter(
    (call) => call.name === "graph.cancelGeneration",
  ).length;
  harness.remoteCallbacks.onOutputFrame({
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960),
  });
  assert.equal(
    harness.calls.filter((call) => call.name === "graph.enqueueRemoteFrame").length,
    enqueueCount,
  );
  assert.equal(
    harness.calls.filter((call) => call.name === "graph.cancelGeneration").length,
    cancelCount,
  );
  assert.deepEqual(harness.runtime.snapshot(), {
    capture: "running",
    route: "native",
    remote: "ready",
    generationId: null,
  });
});

test("Offscreen applies a catalog-bound profile selection only after cancellation", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  let response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.model.select",
      expectedProfile: { profileId: "vc.next.v1" },
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, false);
  assert.match(response.error, /idle ready remote session/i);

  response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.cancel",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.model.select",
      expectedProfile: {
        profileId: "vc.next.v1",
        profileHash:
          "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        configurationHash:
          "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      },
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  assert.deepEqual(
    harness.calls.find((call) => call.name === "client.selectProfile"),
    {
      name: "client.selectProfile",
      profileId: "vc.next.v1",
      expectedProfile: {
        profileId: "vc.next.v1",
        profileHash:
          "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        configurationHash:
          "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      },
    },
  );
});

test("normal generation end waits for local Worklet playout drain before clearing the generation", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });
  const drainGate = createDeferred();
  harness.setDrainGate(drainGate);

  const operation = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.end",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();

  assert.equal(harness.runtime.snapshot().generationId, 7);
  assert.equal(harness.runtime.snapshot().remote, "draining");
  assert.equal(
    harness.calls.some((call) => call.name === "graph.completeGeneration"),
    false,
  );

  drainGate.resolve();
  const response = await operation;
  assert.equal(response.ok, true);
  assert.equal(response.state.generationId, null);
  assert.equal(response.state.route, "native");
  assert(
    harness.calls.findIndex((call) => call.name === "graph.drainGeneration") <
      harness.calls.findIndex((call) => call.name === "graph.completeGeneration"),
  );
});

test("a queued capture frame after End cannot cancel normal playout drain", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  const initialFrame = {
    generationId: 7,
    sourceFrame: 100,
    samples: new Float32Array(960),
  };
  assert.equal(harness.graphCallbacks.onCaptureFrame(initialFrame), true);

  const endGate = createDeferred();
  const drainGate = createDeferred();
  harness.setDrainGate(drainGate);
  let clientDraining = false;
  harness.client.endGeneration = (generationId) => {
    harness.calls.push({ name: "client.endGeneration.blocked", generationId });
    clientDraining = true;
    return endGate.promise;
  };
  harness.client.sendFrame = (frame) => {
    harness.calls.push({ name: "client.sendFrame", frame });
    return !clientDraining;
  };

  const ending = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.end",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();

  const sentBeforeLateFrame = harness.calls.filter(
    (call) => call.name === "client.sendFrame",
  ).length;
  assert.equal(
    harness.graphCallbacks.onCaptureFrame({
      ...initialFrame,
      sourceFrame: 1_060,
    }),
    false,
  );
  assert.equal(
    harness.calls.filter((call) => call.name === "client.sendFrame").length,
    sentBeforeLateFrame,
  );
  assert.equal(
    harness.calls.some((call) => call.name === "graph.cancelGeneration"),
    false,
  );
  assert.equal(
    harness.calls.some((call) => call.name === "client.cancelGeneration"),
    false,
  );
  assert.equal(
    harness.calls.some((call) => call.name === "graph.fallback"),
    false,
  );

  harness.remoteCallbacks.onOutputFrame({
    header: {
      generation_id: 7,
      sequence: 0,
      source_monotonic_ns: 5_000_000_000n,
    },
    samples: new Float32Array(960),
  });
  assert.equal(harness.calls.at(-1).name, "graph.enqueueRemoteFrame");

  endGate.resolve();
  await flushMicrotasks();
  assert.equal(
    harness.calls.some((call) => call.name === "graph.drainGeneration"),
    true,
  );
  assert.equal(
    harness.calls.some((call) => call.name === "graph.completeGeneration"),
    false,
  );

  drainGate.resolve();
  const response = await ending;
  assert.equal(response.ok, true);
  assert.deepEqual(response.state, {
    capture: "running",
    route: "native",
    remote: "ready",
    generationId: null,
  });
  assert.equal(
    harness.calls.some((call) => call.name === "graph.completeGeneration"),
    true,
  );
});

test("interrupting a draining generation retires the older end operation", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  const endGate = createDeferred();
  harness.client.endGeneration = () => endGate.promise;
  harness.client.cancelGeneration = () => {
    const error = new Error("superseded by cancellation");
    error.name = "AbortError";
    endGate.reject(error);
    return Promise.resolve();
  };

  const ending = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.end",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();
  const canceling = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.cancel",
      generationId: 7,
    },
    sender,
    "extension-id",
  );

  const [endResponse, cancelResponse] = await Promise.all([ending, canceling]);
  assert.equal(endResponse.ok, true);
  assert.equal(cancelResponse.ok, true);
  assert.deepEqual(harness.runtime.snapshot(), {
    capture: "running",
    route: "native",
    remote: "ready",
    generationId: null,
  });
});

test("worker fallback is native-first and Offscreen stop never waits for remote close", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  await startConnected(harness);
  harness.graphCallbacks.onRemoteReady({ generationId: 7 });

  harness.remoteCallbacks.onFallback({
    generation_id: 7,
    reason_code: "WORKER_CRASH",
  });
  assert.equal(harness.runtime.snapshot().route, "native");
  assert.equal(harness.runtime.snapshot().remote, "degraded");
  assert.equal(harness.runtime.snapshot().generationId, null);

  const closeGate = createDeferred();
  harness.client.close = () => {
    harness.calls.push({ name: "client.close.blocked" });
    return closeGate.promise;
  };
  const state = await harness.runtime.stop();
  assert.deepEqual(state, {
    capture: "stopped",
    route: "native",
    remote: "disconnected",
    generationId: null,
  });
  assert(harness.calls.some((call) => call.name === "graph.stop"));
  closeGate.resolve();
});

test("idle transport loss retires its epoch and requires Stop before remote recovery", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const sender = await startConnected(harness);
  let response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.end",
      generationId: 7,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, true);
  assert.equal(response.state.generationId, null);
  assert.equal(response.state.remote, "ready");
  harness.graph.fallback = (event) => {
    harness.calls.push({ name: "graph.fallback", event });
    harness.graphCallbacks.onFallback(event);
  };

  harness.remoteCallbacks.onTransportClosed({
    connectionEpoch: 1,
    reasonCode: "TRANSPORT_CLOSED",
    message: "remote WebSocket closed (1006)",
  });
  harness.remoteCallbacks.onTransportClosed({
    connectionEpoch: 1,
    reasonCode: "TRANSPORT_CLOSED",
    message: "duplicate close",
  });
  await flushMicrotasks();

  assert.deepEqual(harness.runtime.snapshot(), {
    capture: "running",
    route: "native",
    remote: "degraded",
    generationId: null,
  });
  assert.equal(
    harness.calls.filter((call) => call.name === "graph.fallback").length,
    1,
  );
  assert.equal(
    harness.calls.filter((call) => call.name === "client.close").length,
    1,
  );
  assert.deepEqual(harness.notifications.at(-1).event, {
    capture: "running",
    route: "native",
    remote: "degraded",
    generationId: null,
    transportClosed: true,
    requiresFreshSession: true,
    error:
      "remote WebSocket closed (1006). Stop and Start to create a fresh authenticated session.",
  });

  response = await harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.generation.start",
      generationId: 8,
    },
    sender,
    "extension-id",
  );
  assert.equal(response.ok, false);
  assert.match(response.error, /not ready/i);
  assert.equal(
    harness.calls.filter(
      (call) => call.name === "client.startGeneration" && call.generationId === 8,
    ).length,
    0,
  );
});

test("Offscreen Stop keeps a pending native start from committing running", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  const startGate = createDeferred();
  harness.graph.startNativeLoopback = async (options) => {
    harness.calls.push({ name: "graph.startNativeLoopback.blocked", options });
    await startGate.promise;
  };
  const sender = {
    id: "extension-id",
    url: "chrome-extension://extension-id/src/background.js",
  };
  const starting = harness.runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.native.start",
      streamId: "tab-stream-id",
      tabId: 42,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();

  assert.deepEqual(await harness.runtime.stop(), {
    capture: "stopped",
    route: "native",
    remote: "disconnected",
    generationId: null,
  });

  startGate.resolve();
  const response = await starting;
  assert.equal(response.ok, true);
  assert.deepEqual(harness.runtime.snapshot(), {
    capture: "stopped",
    route: "native",
    remote: "disconnected",
    generationId: null,
  });
});

test("an older native-start rejection cannot clear a newer graph", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const oldStartGate = createDeferred();
  const calls = [];
  let graphIndex = 0;
  const graphs = [
    {
      async startNativeLoopback() {
        calls.push("old.start");
        await oldStartGate.promise;
        throw new Error("old start failed late");
      },
      async stop() {
        calls.push("old.stop");
      },
    },
    {
      async startNativeLoopback() {
        calls.push("new.start");
      },
      async stop() {
        calls.push("new.stop");
      },
    },
  ];
  const runtime = createOffscreenRuntime({
    audioGraphFactory() {
      const candidate = graphs[graphIndex];
      graphIndex += 1;
      return candidate;
    },
    remoteClientFactory() {
      return {};
    },
    async sendMessage() {},
  });
  const sender = {
    id: "extension-id",
    url: "chrome-extension://extension-id/src/background.js",
  };
  const oldStart = runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.native.start",
      streamId: "old-stream-id",
      tabId: 42,
    },
    sender,
    "extension-id",
  );
  await flushMicrotasks();
  await runtime.stop();

  const newStart = await runtime.handleMessage(
    {
      target: "offscreen",
      type: "offscreen.native.start",
      streamId: "new-stream-id",
      tabId: 42,
    },
    sender,
    "extension-id",
  );
  assert.equal(newStart.ok, true);
  assert.equal(newStart.state.capture, "running");

  oldStartGate.resolve();
  const oldResponse = await oldStart;
  assert.equal(oldResponse.ok, false);
  assert.match(oldResponse.error, /failed late/);
  assert.equal(runtime.snapshot().capture, "running");
  assert.deepEqual(calls, ["old.start", "old.stop", "new.start"]);
});

test("a late remote connect A cannot disturb client or graph B", async () => {
  const { createOffscreenRuntime } = await import(moduleUrl);
  const connectA = createDeferred();
  const calls = [];
  let graphIndex = 0;
  let clientIndex = 0;
  function createGraph(label) {
    return {
      async startNativeLoopback() {
        calls.push(`${label}.start`);
      },
      beginGeneration(generationId) {
        calls.push(`${label}.begin.${generationId}`);
      },
      cancelGeneration(generationId) {
        calls.push(`${label}.cancel.${generationId}`);
      },
      fallback() {
        calls.push(`${label}.fallback`);
      },
      async stop() {
        calls.push(`${label}.stop`);
      },
    };
  }
  function createClient(label, connectGate = null) {
    return {
      async connect() {
        calls.push(`${label}.connect`);
        await connectGate?.promise;
      },
      async startGeneration(generationId) {
        calls.push(`${label}.startGeneration.${generationId}`);
      },
      close() {
        calls.push(`${label}.close`);
        return Promise.resolve();
      },
    };
  }
  const graphs = [createGraph("graphA"), createGraph("graphB")];
  const clients = [createClient("clientA", connectA), createClient("clientB")];
  const runtime = createOffscreenRuntime({
    audioGraphFactory() {
      const candidate = graphs[graphIndex];
      graphIndex += 1;
      return candidate;
    },
    remoteClientFactory() {
      const candidate = clients[clientIndex];
      clientIndex += 1;
      return candidate;
    },
    async sendMessage() {},
  });
  const sender = {
    id: "extension-id",
    url: "chrome-extension://extension-id/src/background.js",
  };
  async function startNative(streamId) {
    const response = await runtime.handleMessage(
      {
        target: "offscreen",
        type: "offscreen.native.start",
        streamId,
        tabId: 42,
      },
      sender,
      "extension-id",
    );
    assert.equal(response.ok, true);
  }
  function connectRemote(sessionId, generationId) {
    return runtime.handleMessage(
      {
        target: "offscreen",
        type: "offscreen.remote.connect",
        url: "wss://audio.example.test/v1/ws",
        sessionId,
        ticket: `ticket-${sessionId}`,
        generationId,
      },
      sender,
      "extension-id",
    );
  }

  await startNative("stream-a");
  const remoteA = connectRemote("session-a", 11);
  await flushMicrotasks();
  await runtime.stop();
  await startNative("stream-b");
  const remoteB = await connectRemote("session-b", 22);
  assert.equal(remoteB.ok, true);
  assert.equal(remoteB.state.generationId, 22);

  connectA.resolve();
  const staleResponse = await remoteA;

  assert.equal(staleResponse.ok, true);
  assert.deepEqual(runtime.snapshot(), {
    capture: "running",
    route: "native",
    remote: "pending",
    generationId: 22,
  });
  assert.equal(calls.includes("clientA.startGeneration.11"), false);
  assert.equal(calls.includes("graphA.begin.11"), false);
  assert.equal(calls.includes("clientB.close"), false);
  assert.equal(calls.includes("graphB.fallback"), false);
  assert(calls.filter((call) => call === "clientA.close").length >= 1);
  assert(calls.includes("clientB.startGeneration.22"));
  assert(calls.includes("graphB.begin.22"));
});

test("Offscreen listener ignores popup and background-targeted messages", async () => {
  const { createOffscreenRuntime, installOffscreenMessageListener } =
    await import(moduleUrl);
  const harness = createHarness(createOffscreenRuntime);
  let installed;
  const chromeApi = {
    runtime: {
      id: "extension-id",
      getURL(path) {
        return `chrome-extension://extension-id/${path}`;
      },
      onMessage: {
        addListener(listener) {
          installed = listener;
        },
      },
    },
  };
  installOffscreenMessageListener(harness.runtime, chromeApi);

  let responded = false;
  assert.equal(
    installed(
      { type: "session.status" },
      { id: "extension-id" },
      () => {
        responded = true;
      },
    ),
    false,
  );
  assert.equal(responded, false);
});
