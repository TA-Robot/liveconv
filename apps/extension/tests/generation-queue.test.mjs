import assert from "node:assert/strict";
import test from "node:test";

import { createSyntheticFrame } from "./support.mjs";

const moduleUrl = new URL("../src/generation-queue.js", import.meta.url);

function createHarness(createGenerationQueue, direction, maxBufferedMs = 40) {
  const fallbacks = [];
  const queue = createGenerationQueue({
    direction,
    frameDurationMs: 20,
    maxBufferedMs,
    onFallback(event) {
      fallbacks.push(event);
    },
  });
  return { fallbacks, queue };
}

function frame(direction, generationId, sequence) {
  return createSyntheticFrame({
    direction: direction === "uplink" ? "input" : "output",
    generationId,
    sequence,
    sourceMonotonicNs: 1_000_000_000n + BigInt(sequence) * 20_000_000n,
  });
}

for (const direction of ["uplink", "jitter"]) {
  test(`${direction} queue is generation-aware and bounded by buffered time`, async () => {
    const { createGenerationQueue } = await import(moduleUrl);
    const { fallbacks, queue } = createHarness(
      createGenerationQueue,
      direction,
    );

    queue.beginGeneration(7);
    assert.equal(queue.enqueue(frame(direction, 7, 0)), true);
    assert.equal(queue.enqueue(frame(direction, 7, 1)), true);
    assert.equal(queue.snapshot().generationId, 7);
    assert.equal(queue.snapshot().depth, 2);
    assert.equal(queue.snapshot().bufferedMs, 40);
    assert.deepEqual(fallbacks, []);

    assert.equal(queue.dequeue().header.sequence, 0);
    assert.equal(queue.snapshot().bufferedMs, 20);
    assert.equal(queue.enqueue(frame(direction, 7, 2)), true);
    assert.equal(queue.dequeue().header.sequence, 1);
    assert.equal(queue.dequeue().header.sequence, 2);
    assert.equal(queue.dequeue(), undefined);
  });
}

for (const direction of ["uplink", "jitter"]) {
  test(`${direction} overflow invalidates the generation and requests fallback synchronously`, async () => {
    const { createGenerationQueue } = await import(moduleUrl);
    const { fallbacks, queue } = createHarness(
      createGenerationQueue,
      direction,
    );

    queue.beginGeneration(7);
    queue.enqueue(frame(direction, 7, 0));
    queue.enqueue(frame(direction, 7, 1));

    assert.equal(queue.enqueue(frame(direction, 7, 2)), false);
    assert.equal(fallbacks.length, 1, "fallback must fire before enqueue returns");
    assert.equal(fallbacks[0].direction, direction);
    assert.equal(fallbacks[0].generationId, 7);
    assert.equal(fallbacks[0].reasonCode, "QUEUE_OVERFLOW");
    assert.equal(queue.snapshot().depth, 0);
    assert.equal(queue.snapshot().bufferedMs, 0);
    assert.equal(queue.snapshot().accepting, false);
    assert.equal(queue.dequeue(), undefined);
  });
}

test("a sequence gap clears jitter output and requires immediate native fallback", async () => {
  const { createGenerationQueue } = await import(moduleUrl);
  const { fallbacks, queue } = createHarness(createGenerationQueue, "jitter", 80);

  queue.beginGeneration(7);
  assert.equal(queue.enqueue(frame("jitter", 7, 0)), true);
  assert.equal(queue.enqueue(frame("jitter", 7, 2)), false);

  assert.equal(fallbacks.length, 1);
  assert.equal(fallbacks[0].generationId, 7);
  assert.equal(fallbacks[0].reasonCode, "SEQUENCE_GAP");
  assert.equal(queue.snapshot().depth, 0);
  assert.equal(queue.snapshot().accepting, false);
});

test("a duplicate sequence is rejected instead of replaying audio", async () => {
  const { createGenerationQueue } = await import(moduleUrl);
  const { fallbacks, queue } = createHarness(createGenerationQueue, "jitter", 80);

  queue.beginGeneration(7);
  assert.equal(queue.enqueue(frame("jitter", 7, 0)), true);
  assert.equal(queue.enqueue(frame("jitter", 7, 0)), false);

  assert.equal(fallbacks.length, 1);
  assert.equal(fallbacks[0].reasonCode, "SEQUENCE_GAP");
  assert.equal(queue.snapshot().depth, 0);
});

test("a stale generation frame invalidates remote output immediately", async () => {
  const { createGenerationQueue } = await import(moduleUrl);
  const { fallbacks, queue } = createHarness(createGenerationQueue, "jitter", 80);

  queue.beginGeneration(8);
  assert.equal(queue.enqueue(frame("jitter", 7, 0)), false);

  assert.equal(fallbacks.length, 1);
  assert.equal(fallbacks[0].generationId, 8);
  assert.equal(fallbacks[0].receivedGenerationId, 7);
  assert.equal(fallbacks[0].reasonCode, "STALE_GENERATION");
  assert.equal(queue.snapshot().accepting, false);
});

test("cancel drops all not-yet-played output without waiting for a server ack", async () => {
  const { createGenerationQueue } = await import(moduleUrl);
  const { fallbacks, queue } = createHarness(createGenerationQueue, "jitter", 80);

  queue.beginGeneration(8);
  queue.enqueue(frame("jitter", 8, 0));
  queue.enqueue(frame("jitter", 8, 1));

  assert.equal(queue.cancelGeneration(8), 2);
  assert.equal(queue.snapshot().depth, 0);
  assert.equal(queue.snapshot().bufferedMs, 0);
  assert.equal(queue.snapshot().accepting, false);
  assert.equal(queue.dequeue(), undefined);
  assert.deepEqual(fallbacks, []);
});

test("beginning a newer generation discards queued frames from the old one", async () => {
  const { createGenerationQueue } = await import(moduleUrl);
  const { fallbacks, queue } = createHarness(createGenerationQueue, "uplink", 80);

  queue.beginGeneration(7);
  queue.enqueue(frame("uplink", 7, 0));
  queue.enqueue(frame("uplink", 7, 1));

  assert.equal(queue.beginGeneration(8), 2);
  assert.equal(queue.snapshot().generationId, 8);
  assert.equal(queue.snapshot().depth, 0);
  assert.equal(queue.enqueue(frame("uplink", 8, 0)), true);
  assert.deepEqual(fallbacks, []);
});
