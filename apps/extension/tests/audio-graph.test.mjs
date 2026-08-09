import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/audio-graph.js", import.meta.url);

function createHarness(createAudioGraph, stageHooks = {}) {
  const calls = [];
  const nodes = [];
  const tracks = [
    {
      stopped: false,
      listeners: new Map(),
      addEventListener(type, listener) {
        this.listeners.set(type, listener);
      },
      stop() {
        calls.push({ name: "track.stop" });
        this.stopped = true;
      },
    },
  ];
  const stream = {
    getTracks() {
      return tracks;
    },
    getAudioTracks() {
      return tracks;
    },
  };

  class FakeNode {
    constructor(name) {
      this.name = name;
      this.connections = [];
      this.disconnected = false;
      nodes.push(this);
    }

    connect(destination) {
      calls.push({ name: "node.connect", source: this.name, destination: destination.name });
      this.connections.push(destination);
      return destination;
    }

    disconnect() {
      calls.push({ name: "node.disconnect", node: this.name });
      this.disconnected = true;
    }
  }

  class FakeGain extends FakeNode {
    constructor(name) {
      super(name);
      this.gain = {
        value: 0,
        setValueAtTime: (value, time) => {
          calls.push({ name: "gain.set", node: this.name, value, time });
          this.gain.value = value;
        },
      };
    }
  }

  let gainIndex = 0;
  let context;
  class FakeContext {
    constructor(options) {
      calls.push({ name: "context.create", options });
      this.sampleRate = 48_000;
      this.currentTime = 1.25;
      this.state = "suspended";
      this.destination = new FakeNode("destination");
      this.audioWorklet = {
        addModule: async (url) => {
          calls.push({ name: "worklet.addModule", url });
          await stageHooks.addModule?.(url);
        },
      };
      context = this;
    }

    createMediaStreamSource(receivedStream) {
      calls.push({ name: "context.createMediaStreamSource", stream: receivedStream });
      return new FakeNode("source");
    }

    createGain() {
      gainIndex += 1;
      return new FakeGain(`captureSink${gainIndex === 1 ? "" : gainIndex}`);
    }

    async resume() {
      calls.push({ name: "context.resume" });
      await stageHooks.resume?.();
      this.state = "running";
    }

    async close() {
      calls.push({ name: "context.close" });
      this.state = "closed";
    }
  }

  class FakePort {
    constructor(owner) {
      this.owner = owner;
      this.messages = [];
      this.onmessage = null;
    }

    postMessage(message, transfer = []) {
      calls.push({ name: "port.postMessage", owner: this.owner, message, transfer });
      this.messages.push(message);
    }

    receive(data) {
      this.onmessage?.({ data });
    }
  }

  class FakeWorkletNode extends FakeNode {
    constructor(_context, name) {
      super(name);
      this.port = new FakePort(name);
    }
  }

  const captureFrames = [];
  const fallbacks = [];
  const ready = [];
  const ended = [];
  const graph = createAudioGraph({
    mediaDevices: {
      async getUserMedia(constraints) {
        calls.push({ name: "media.getUserMedia", constraints });
        await stageHooks.getUserMedia?.(constraints);
        return stream;
      },
    },
    AudioContextClass: FakeContext,
    AudioWorkletNodeClass: FakeWorkletNode,
    workletModuleUrl: "chrome-extension://extension/offscreen/worklets/liveconv-audio.js",
    onCaptureFrame(frame) {
      captureFrames.push(frame);
    },
    onFallback(event) {
      fallbacks.push(event);
    },
    onRemoteReady(event) {
      ready.push(event);
    },
    onSourceEnded() {
      ended.push(true);
    },
  });
  return {
    calls,
    captureFrames,
    ended,
    fallbacks,
    graph,
    nodes,
    ready,
    stream,
    tracks,
    get context() {
      return context;
    },
    node(name) {
      return nodes.find((node) => node.name === name);
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

async function waitForCall(calls, name) {
  for (let turn = 0; turn < 20; turn += 1) {
    if (calls.some((call) => call.name === name)) {
      return;
    }
    await new Promise((resolve) => setImmediate(resolve));
  }
  assert.fail(`expected ${name} to be reached`);
}

async function assertSettlesPromptly(operation) {
  let settled = false;
  operation.finally(() => {
    settled = true;
  });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, true, "audio graph Stop must preempt pending startup");
  await operation;
}

test("AudioGraph consumes the tab stream in Offscreen and establishes native-only playout first", async () => {
  const { createAudioGraph } = await import(moduleUrl);
  const harness = createHarness(createAudioGraph);

  await harness.graph.startNativeLoopback({
    streamId: "synthetic-stream-id",
    tabId: 42,
  });

  const media = harness.calls.find((call) => call.name === "media.getUserMedia");
  assert.deepEqual(media.constraints, {
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: "synthetic-stream-id",
      },
    },
    video: false,
  });
  assert.equal(harness.node("captureSink").gain.value, 0);
  assert.deepEqual(harness.graph.snapshot(), {
    capture: "running",
    route: "native",
    generationId: null,
  });
  assert(harness.tracks[0].listeners.has("ended"));
});

const pendingAudioGraphStages = [
  {
    name: "media.getUserMedia",
    hooks(pending) {
      return { getUserMedia: () => pending };
    },
    forbidden: ["context.create"],
  },
  {
    name: "worklet.addModule",
    hooks(pending) {
      return { addModule: () => pending };
    },
    forbidden: ["context.createMediaStreamSource", "context.resume"],
  },
  {
    name: "context.resume",
    hooks(pending) {
      return { resume: () => pending };
    },
    forbidden: [],
  },
];

for (const stage of pendingAudioGraphStages) {
  test(`AudioGraph Stop invalidates startup while ${stage.name} is pending`, async () => {
    const { createAudioGraph } = await import(moduleUrl);
    const blocker = deferred();
    const harness = createHarness(
      createAudioGraph,
      stage.hooks(blocker.promise),
    );
    const start = harness.graph.startNativeLoopback({
      streamId: "synthetic-stream-id",
      tabId: 42,
    });
    await waitForCall(harness.calls, stage.name);

    await assertSettlesPromptly(harness.graph.stop());
    assert.equal(harness.graph.snapshot().capture, "stopped");

    blocker.resolve();
    await start;

    assert.equal(harness.graph.snapshot().capture, "stopped");
    assert.equal(harness.tracks[0].stopped, true);
    if (harness.context) {
      assert.equal(harness.context.state, "closed");
    }
    for (const forbidden of stage.forbidden) {
      assert.equal(
        harness.calls.some((call) => call.name === forbidden),
        false,
        `canceled startup must not reach ${forbidden}`,
      );
    }
  });
}

test("jitter readiness mutes native before making remote audible and capture frames stay local", async () => {
  const { createAudioGraph } = await import(moduleUrl);
  const harness = createHarness(createAudioGraph);
  await harness.graph.startNativeLoopback({
    streamId: "synthetic-stream-id",
    tabId: 42,
  });
  harness.graph.beginGeneration(7);

  const captureNode = harness.node("liveconv-capture");
  const playoutNode = harness.node("liveconv-playout");
  assert.deepEqual(captureNode.port.messages.at(-2), {
    type: "capture.begin",
    generationId: 7,
  });
  assert.deepEqual(captureNode.port.messages.at(-1), {
    type: "capture.credit",
    generationId: 7,
    frames: 4,
  });
  assert.deepEqual(playoutNode.port.messages.at(-1), {
    type: "playout.begin",
    generationId: 7,
  });

  const samples = new Float32Array(960);
  captureNode.port.receive({
    type: "capture.frame",
    generationId: 7,
    sourceFrame: 128,
    samples,
  });
  assert.equal(harness.captureFrames.length, 1);
  assert.equal(harness.captureFrames[0].samples, samples);
  assert.deepEqual(captureNode.port.messages.at(-1), {
    type: "capture.credit",
    generationId: 7,
    frames: 1,
  });

  const beforeReady = harness.calls.length;
  playoutNode.port.receive({ type: "playout.ready", generationId: 7 });
  const changes = harness.calls
    .slice(beforeReady)
    .filter((call) => call.name === "port.postMessage")
    .map((call) => call.message)
    .filter((message) => message.type === "playout.audible");
  assert.deepEqual(changes.at(-1), { type: "playout.audible", audible: true });
  assert.equal(harness.graph.snapshot().route, "remote");
  assert.deepEqual(harness.ready, [{ generationId: 7 }]);
});

test("generation cancellation restores native synchronously and releases all media resources on stop", async () => {
  const { createAudioGraph } = await import(moduleUrl);
  const harness = createHarness(createAudioGraph);
  await harness.graph.startNativeLoopback({
    streamId: "synthetic-stream-id",
    tabId: 42,
  });
  harness.graph.beginGeneration(7);
  harness.node("liveconv-playout").port.receive({
    type: "playout.ready",
    generationId: 7,
  });

  const beforeCancel = harness.calls.length;
  assert.equal(harness.graph.cancelGeneration(7, "WORKER_CRASH"), true);
  assert.equal(harness.graph.snapshot().route, "native");
  assert(
    harness.calls
      .slice(beforeCancel)
      .filter((call) => call.name === "port.postMessage")
      .some(
        (call) =>
          call.message.type === "playout.audible" &&
          call.message.audible === false,
      ),
  );
  assert.equal(harness.fallbacks.at(-1).reasonCode, "WORKER_CRASH");

  await harness.graph.stop();
  assert.equal(harness.tracks[0].stopped, true);
  assert.equal(harness.context.state, "closed");
  assert.equal(harness.graph.snapshot().capture, "stopped");
});

test("main-to-Worklet downlink messages are bounded at the 200 ms jitter maximum", async () => {
  const { createAudioGraph } = await import(moduleUrl);
  const harness = createHarness(createAudioGraph);
  await harness.graph.startNativeLoopback({
    streamId: "synthetic-stream-id",
    tabId: 42,
  });
  harness.graph.beginGeneration(7);

  for (let sequence = 0; sequence < 10; sequence += 1) {
    assert.equal(
      harness.graph.enqueueRemoteFrame({
        header: { generation_id: 7, sequence },
        sourceFrame: sequence * 960,
        samples: new Float32Array(960),
      }),
      true,
    );
  }
  assert.equal(
    harness.graph.enqueueRemoteFrame({
      header: { generation_id: 7, sequence: 10 },
      sourceFrame: 10 * 960,
      samples: new Float32Array(960),
    }),
    false,
  );
  assert.equal(harness.fallbacks.at(-1).reasonCode, "QUEUE_OVERFLOW");
  assert.equal(harness.graph.snapshot().route, "native");
});

test("server completion drains already-accepted Worklet audio before returning to native", async () => {
  const { createAudioGraph } = await import(moduleUrl);
  const harness = createHarness(createAudioGraph);
  await harness.graph.startNativeLoopback({
    streamId: "synthetic-stream-id",
    tabId: 42,
  });
  harness.graph.beginGeneration(7);
  const playout = harness.node("liveconv-playout");
  playout.port.receive({ type: "playout.ready", generationId: 7 });
  assert.equal(harness.graph.snapshot().route, "remote");

  let drained = false;
  const operation = harness.graph.drainGeneration(7).then(() => {
    drained = true;
  });
  await Promise.resolve();
  assert.equal(drained, false);
  assert.deepEqual(playout.port.messages.at(-1), {
    type: "playout.end",
    generationId: 7,
  });

  playout.port.receive({ type: "playout.drained", generationId: 7 });
  await operation;
  assert.equal(drained, true);
  assert.equal(harness.graph.snapshot().route, "native");
});
