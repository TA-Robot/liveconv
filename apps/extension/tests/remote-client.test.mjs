import assert from "node:assert/strict";
import test from "node:test";

import {
  createSyntheticFrame,
  FakeWebSocket,
  flushMicrotasks,
  readJson,
} from "./support.mjs";

const moduleUrl = new URL("../src/remote-client.js", import.meta.url);
const fixtureUrl = new URL("fixtures/remote-session.json", import.meta.url);

function profileFields(fixture, { selected = false } = {}) {
  return {
    profile_id: selected ? fixture.next_profile_id : fixture.profile_id,
    profile_hash: fixture.profile_hash,
    configuration_hash: fixture.configuration_hash,
    pipeline_id: selected ? fixture.next_pipeline_id : fixture.pipeline_id,
  };
}

function sessionReady(fixture, requestId) {
  return {
    type: "session.ready",
    protocol_version: 1,
    session_id: fixture.session_id,
    request_id: requestId,
    ...profileFields(fixture),
    clock_id: fixture.clock_id,
    limits: fixture.limits,
  };
}

function modelSelected(fixture, requestId) {
  return {
    type: "model.selected",
    protocol_version: 1,
    session_id: fixture.session_id,
    request_id: requestId,
    ...profileFields(fixture, { selected: true }),
  };
}

function generationReady(
  fixture,
  requestId,
  generationId,
  { selected = false } = {},
) {
  return {
    type: "generation.ready",
    protocol_version: 1,
    session_id: fixture.session_id,
    request_id: requestId,
    generation_id: generationId,
    ...profileFields(fixture, { selected }),
  };
}

function generationTerminal(
  fixture,
  type,
  requestId,
  generationId,
  { selected = false } = {},
) {
  return {
    type,
    protocol_version: 1,
    session_id: fixture.session_id,
    request_id: requestId,
    generation_id: generationId,
    pipeline_id: selected ? fixture.next_pipeline_id : fixture.pipeline_id,
  };
}

function createHarness(createRemoteClient, requestIds, clientOptions = {}) {
  let socket;
  let requestIndex = 0;
  const fallbacks = [];
  const outputFrames = [];
  const client = createRemoteClient({
    ...clientOptions,
    socketFactory(url) {
      socket = new FakeWebSocket(url);
      return socket;
    },
    requestIdFactory() {
      const requestId = requestIds[requestIndex];
      requestIndex += 1;
      if (requestId === undefined) {
        throw new Error("synthetic request IDs exhausted");
      }
      return requestId;
    },
    onFallback(event) {
      fallbacks.push(event);
    },
    onOutputFrame(frame) {
      outputFrames.push(frame);
    },
  });
  return {
    client,
    fallbacks,
    outputFrames,
    get socket() {
      return socket;
    },
  };
}

function controls(socket) {
  return socket.sent
    .filter((value) => typeof value === "string")
    .map((value) => JSON.parse(value));
}

async function connectReady(harness, fixture) {
  const pending = harness.client.connect({
    url: fixture.url,
    sessionId: fixture.session_id,
    ticket: fixture.ticket,
  });
  await flushMicrotasks();
  assert(harness.socket, "connect must create a socket");
  assert.equal(harness.socket.url, fixture.url);
  assert.equal(harness.socket.binaryType, "arraybuffer");
  assert.deepEqual(harness.socket.sent, []);

  harness.socket.open();
  const attach = controls(harness.socket).at(-1);
  assert.deepEqual(attach, {
    type: "session.attach",
    protocol_version: 1,
    request_id: "attach-1",
    session_id: fixture.session_id,
    ticket: fixture.ticket,
  });

  harness.socket.receive(JSON.stringify(sessionReady(fixture, attach.request_id)));
  await pending;
  return attach;
}

test("WSS connect sends attach first and resolves only after session.ready", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, ["attach-1"]);

  let connected = false;
  const pending = harness.client
    .connect({
      url: fixture.url,
      sessionId: fixture.session_id,
      ticket: fixture.ticket,
    })
    .then(() => {
      connected = true;
    });
  await flushMicrotasks();
  assert.equal(connected, false);

  harness.socket.open();
  await flushMicrotasks();
  assert.equal(connected, false);
  assert.equal(controls(harness.socket).length, 1);
  assert.equal(controls(harness.socket)[0].type, "session.attach");

  harness.socket.receive(
    JSON.stringify(sessionReady(fixture, controls(harness.socket)[0].request_id)),
  );
  await pending;

  assert.equal(harness.client.snapshot().transport, "ready");
  assert.equal(harness.client.snapshot().profileId, fixture.profile_id);
  assert.equal(harness.client.snapshot().pipelineId, fixture.pipeline_id);
  assert.equal(harness.client.snapshot().generationId, null);
});

test("pre-open WebSocket error and close always settle the connect operation", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);

  for (const failure of ["error", "close"]) {
    const harness = createHarness(createRemoteClient, []);
    const operation = harness.client.connect({
      url: fixture.url,
      sessionId: fixture.session_id,
      ticket: fixture.ticket,
    });
    await flushMicrotasks();
    if (failure === "error") {
      harness.socket.fail(new Error("pre-open failure"));
      await assert.rejects(operation, /pre-open failure/);
    } else {
      harness.socket.close(1006, "pre-open close");
      await assert.rejects(operation, /closed \(1006\)/);
    }
  }
});

test("close aborts a connecting socket without waiting for open", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, []);
  const operation = harness.client.connect({
    url: fixture.url,
    sessionId: fixture.session_id,
    ticket: fixture.ticket,
  });
  await flushMicrotasks();

  await harness.client.close();
  await assert.rejects(operation, /closed by the client/);
  assert.deepEqual(harness.socket.closeCalls, [
    { code: 1000, reason: "client closed" },
  ]);
});

test("attach and control requests have deterministic deadlines", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const timers = new Map();
  let nextTimer = 0;
  const harness = createHarness(createRemoteClient, ["attach-1"], {
    requestTimeoutMilliseconds: 50,
    setTimer(callback) {
      nextTimer += 1;
      timers.set(nextTimer, callback);
      return nextTimer;
    },
    clearTimer(timer) {
      timers.delete(timer);
    },
  });
  const operation = harness.client.connect({
    url: fixture.url,
    sessionId: fixture.session_id,
    ticket: fixture.ticket,
  });
  harness.socket.open();
  assert.equal(timers.size, 1);
  [...timers.values()][0]();
  await assert.rejects(operation, /session\.attach timed out/);
  assert.equal(harness.client.snapshot().transport, "disconnected");
});

test("generation start, end, and cancel use acknowledged v1 controls", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, [
    "attach-1",
    "start-7",
    "end-7",
    "start-8",
    "cancel-8",
  ]);
  await connectReady(harness, fixture);

  const startSeven = harness.client.startGeneration(7);
  assert.deepEqual(controls(harness.socket).at(-1), {
    type: "generation.start",
    protocol_version: 1,
    request_id: "start-7",
    session_id: fixture.session_id,
    generation_id: 7,
  });
  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-7", 7)),
  );
  await startSeven;
  assert.equal(harness.client.snapshot().generationState, "streaming");

  const endSeven = harness.client.endGeneration(7);
  assert.equal(controls(harness.socket).at(-1).type, "generation.end");
  assert.equal(harness.client.snapshot().generationState, "draining");
  harness.socket.receive(
    JSON.stringify(
      generationTerminal(fixture, "generation.completed", "end-7", 7),
    ),
  );
  await endSeven;
  assert.equal(harness.client.snapshot().generationState, "idle");

  const startEight = harness.client.startGeneration(8);
  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-8", 8)),
  );
  await startEight;

  const cancelEight = harness.client.cancelGeneration(8);
  assert.deepEqual(controls(harness.socket).at(-1), {
    type: "generation.cancel",
    protocol_version: 1,
    request_id: "cancel-8",
    session_id: fixture.session_id,
    generation_id: 8,
  });
  harness.socket.receive(
    JSON.stringify(
      generationTerminal(fixture, "generation.canceled", "cancel-8", 8),
    ),
  );
  await cancelEight;
  assert.equal(harness.client.snapshot().generationState, "idle");
  assert.equal(harness.client.snapshot().generationId, null);
});

test("canceling a draining generation rejects its earlier end waiter", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, [
    "attach-1",
    "start-7",
    "end-7",
    "cancel-7",
  ]);
  await connectReady(harness, fixture);
  const start = harness.client.startGeneration(7);
  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-7", 7)),
  );
  await start;

  const endOutcome = harness.client.endGeneration(7).then(
    () => ({ status: "resolved" }),
    (error) => ({ status: "rejected", error }),
  );
  const cancellation = harness.client.cancelGeneration(7);
  const outcome = await endOutcome;
  assert.equal(outcome.status, "rejected");
  assert.equal(outcome.error.name, "AbortError");
  assert.equal(outcome.error.code, "GENERATION_CANCELED");

  harness.socket.receive(
    JSON.stringify(
      generationTerminal(
        fixture,
        "generation.canceled",
        "cancel-7",
        7,
      ),
    ),
  );
  await cancellation;
  assert.equal(harness.client.snapshot().generationState, "idle");
});

test("profile selection is allowed only after a generation is terminal", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, [
    "attach-1",
    "start-7",
    "end-7",
    "select-after-7",
  ]);
  await connectReady(harness, fixture);

  const start = harness.client.startGeneration(7);
  await assert.rejects(
    Promise.resolve().then(() =>
      harness.client.selectProfile(fixture.next_profile_id),
    ),
    /generation boundary/i,
  );
  assert.equal(
    controls(harness.socket).filter((message) => message.type === "model.select")
      .length,
    0,
  );

  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-7", 7)),
  );
  await start;
  const end = harness.client.endGeneration(7);

  await assert.rejects(
    Promise.resolve().then(() =>
      harness.client.selectProfile(fixture.next_profile_id),
    ),
    /generation boundary/i,
  );
  assert.equal(
    controls(harness.socket).filter((message) => message.type === "model.select")
      .length,
    0,
  );

  harness.socket.receive(
    JSON.stringify(
      generationTerminal(fixture, "generation.completed", "end-7", 7),
    ),
  );
  await end;

  const selection = harness.client.selectProfile(fixture.next_profile_id);
  assert.deepEqual(controls(harness.socket).at(-1), {
    type: "model.select",
    protocol_version: 1,
    request_id: "select-after-7",
    session_id: fixture.session_id,
    profile_id: fixture.next_profile_id,
  });
  harness.socket.receive(
    JSON.stringify(modelSelected(fixture, "select-after-7")),
  );
  await selection;

  assert.equal(harness.client.snapshot().profileId, fixture.next_profile_id);
  assert.equal(harness.client.snapshot().pipelineId, fixture.next_pipeline_id);
});

test("server fallback invalidates a generation before later binary output arrives", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(createRemoteClient, ["attach-1", "start-7"]);
  await connectReady(harness, fixture);

  const start = harness.client.startGeneration(7);
  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-7", 7)),
  );
  await start;

  harness.socket.receive(
    JSON.stringify({
      type: "fallback.required",
      protocol_version: 1,
      session_id: fixture.session_id,
      generation_id: 7,
      pipeline_id: fixture.pipeline_id,
      reason_code: "SEQUENCE_GAP",
    }),
  );

  assert.equal(harness.fallbacks.length, 1);
  assert.equal(harness.fallbacks[0].generation_id, 7);
  assert.equal(harness.fallbacks[0].reason_code, "SEQUENCE_GAP");
  assert.equal(harness.client.snapshot().generationState, "failed");

  harness.socket.receive(new ArrayBuffer(3_872));
  assert.deepEqual(
    harness.outputFrames,
    [],
    "late output after fallback must never reach the jitter queue",
  );
});

test("uplink WebSocket buffering is bounded before another PCM frame is accepted", async () => {
  const { createRemoteClient } = await import(moduleUrl);
  const fixture = await readJson(fixtureUrl);
  const harness = createHarness(
    createRemoteClient,
    ["attach-1", "start-7"],
    { maximumBufferedBytes: 4_000 },
  );
  await connectReady(harness, fixture);
  const start = harness.client.startGeneration(7);
  harness.socket.receive(
    JSON.stringify(generationReady(fixture, "start-7", 7)),
  );
  await start;

  harness.socket.bufferedAmount = 200;
  assert.equal(
    harness.client.sendFrame(
      createSyntheticFrame({ direction: "input", generationId: 7 }),
    ),
    false,
  );

  assert.equal(harness.fallbacks.length, 1);
  assert.equal(harness.fallbacks[0].reason_code, "QUEUE_OVERFLOW");
  assert.deepEqual(harness.socket.closeCalls.at(-1), {
    code: 1008,
    reason: "uplink queue overflow",
  });
});
