import assert from "node:assert/strict";
import test from "node:test";

import { createDependencies } from "./support.mjs";

const controllerModuleUrl = new URL("../src/session-controller.js", import.meta.url);

function assertNativeIdle(controller) {
  const state = controller.snapshot();
  assert.equal(state.capture, "stopped");
  assert.equal(state.route, "native");
}

test("construction is side-effect free and native by default", async () => {
  const { createSessionController } = await import(controllerModuleUrl);
  const dependencies = createDependencies();
  const controller = createSessionController(dependencies);

  assertNativeIdle(controller);
  assert.deepEqual(dependencies.calls, []);
});

test("capture starts and stops only through explicit idempotent commands", async () => {
  const { createSessionController } = await import(controllerModuleUrl);
  const dependencies = createDependencies();
  const controller = createSessionController(dependencies);

  await controller.start();
  await controller.start();
  assert.equal(controller.snapshot().capture, "running");
  assert.equal(controller.snapshot().route, "native");
  assert.deepEqual(dependencies.calls, ["capture.start"]);

  await controller.stop();
  await controller.stop();
  assertNativeIdle(controller);
  assert.deepEqual(dependencies.calls, ["capture.start", "capture.stop"]);
});

test("native start never opens a remote route implicitly", async () => {
  const { createSessionController } = await import(controllerModuleUrl);
  const dependencies = createDependencies();
  const controller = createSessionController(dependencies);

  await controller.start();
  assert(!dependencies.calls.includes("remote.connect"));
  assert(!dependencies.calls.includes("remote.close"));
  assert.equal(controller.snapshot().route, "native");
});

test("capture-start failure remains stopped on the native route", async () => {
  const { createSessionController } = await import(controllerModuleUrl);
  const failure = new Error("synthetic capture denial");
  const dependencies = createDependencies({ startError: failure });
  const controller = createSessionController(dependencies);

  await assert.rejects(controller.start(), (error) => error === failure);
  assertNativeIdle(controller);
  assert.deepEqual(dependencies.calls, ["capture.start"]);
});

test("concurrent starts share one capture request", async () => {
  const { createSessionController } = await import(controllerModuleUrl);
  const calls = [];
  let releaseStart;
  const startGate = new Promise((resolve) => {
    releaseStart = resolve;
  });
  const controller = createSessionController({
    capture: {
      async start() {
        calls.push("capture.start");
        await startGate;
      },
      async stop() {
        calls.push("capture.stop");
      },
    },
    remote: {
      async connect() {
        calls.push("remote.connect");
      },
      async close() {
        calls.push("remote.close");
      },
    },
  });

  const first = controller.start();
  const second = controller.start();
  await Promise.resolve();
  assert.deepEqual(calls, ["capture.start"]);
  releaseStart();
  await Promise.all([first, second]);
  assert.equal(controller.snapshot().capture, "running");
  assert.equal(controller.snapshot().route, "native");
});
