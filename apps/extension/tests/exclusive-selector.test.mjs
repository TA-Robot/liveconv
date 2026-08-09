import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/exclusive-selector.js", import.meta.url);

function createRoutes() {
  const state = { native: false, remote: false };
  const observations = [];
  const calls = [];

  function setter(name) {
    return {
      setAudible(audible) {
        calls.push({ route: name, audible });
        state[name] = audible;
        observations.push({ ...state });
      },
    };
  }

  return {
    calls,
    observations,
    routes: {
      native: setter("native"),
      remote: setter("remote"),
    },
    state,
  };
}

function assertExclusive(observations) {
  for (const observation of observations) {
    assert.equal(
      observation.native && observation.remote,
      false,
      `native and remote became audible together: ${JSON.stringify(observation)}`,
    );
  }
}

test("selector initializes to an explicit native-only route", async () => {
  const { createExclusiveSelector } = await import(moduleUrl);
  const harness = createRoutes();
  const selector = createExclusiveSelector(harness.routes);

  assert.deepEqual(harness.state, { native: true, remote: false });
  assert.equal(selector.snapshot().route, "native");
  assert.equal(selector.snapshot().nativeAudible, true);
  assert.equal(selector.snapshot().remoteAudible, false);
  assertExclusive(harness.observations);
});

test("route changes mute the old route before exposing the new one", async () => {
  const { createExclusiveSelector } = await import(moduleUrl);
  const harness = createRoutes();
  const selector = createExclusiveSelector(harness.routes);

  selector.select("remote");
  selector.select("native");
  selector.select("remote");

  assert.deepEqual(harness.state, { native: false, remote: true });
  assertExclusive(harness.observations);

  const transitionCalls = harness.calls.slice(-2);
  assert.deepEqual(transitionCalls, [
    { route: "native", audible: false },
    { route: "remote", audible: true },
  ]);
});

test("fallback synchronously restores native-only playout and is idempotent", async () => {
  const { createExclusiveSelector } = await import(moduleUrl);
  const harness = createRoutes();
  const selector = createExclusiveSelector(harness.routes);

  selector.select("remote");
  selector.fallback();
  const callsAfterFirstFallback = harness.calls.length;

  assert.deepEqual(harness.state, { native: true, remote: false });
  assert.equal(selector.snapshot().route, "native");
  assertExclusive(harness.observations);

  selector.fallback();
  assert.equal(harness.calls.length, callsAfterFirstFallback);
  assert.deepEqual(harness.state, { native: true, remote: false });
});

test("an invalid route cannot disturb the native safety path", async () => {
  const { createExclusiveSelector } = await import(moduleUrl);
  const harness = createRoutes();
  const selector = createExclusiveSelector(harness.routes);

  assert.throws(() => selector.select("comparison"), /route/i);
  assert.deepEqual(harness.state, { native: true, remote: false });
  assertExclusive(harness.observations);
});
