import { readFile, readdir } from "node:fs/promises";

export const extensionRoot = new URL("../", import.meta.url);
export const protocolFixtures = new URL(
  "../../../packages/protocol/fixtures/",
  import.meta.url,
);

export async function readJson(url) {
  return JSON.parse(await readFile(url, "utf8"));
}

export function asBytes(value) {
  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  throw new TypeError("Expected an ArrayBuffer or an ArrayBuffer view");
}

export async function walkFiles(directory, { exclude = new Set() } = {}) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (exclude.has(entry.name)) {
      continue;
    }
    const url = new URL(entry.name + (entry.isDirectory() ? "/" : ""), directory);
    if (entry.isDirectory()) {
      files.push(...(await walkFiles(url, { exclude })));
    } else if (entry.isFile()) {
      files.push(url);
    }
  }
  return files;
}

export function createDependencies({ startError } = {}) {
  const calls = [];
  return {
    calls,
    capture: {
      async start() {
        calls.push("capture.start");
        if (startError) {
          throw startError;
        }
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
  };
}

export function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return Object.freeze({ promise, resolve, reject });
}

export function createFakeClock(initialNanoseconds = 1_000_000_000n) {
  let current = BigInt(initialNanoseconds);
  return Object.freeze({
    nowNanoseconds() {
      return current;
    },
    advanceMilliseconds(milliseconds) {
      if (!Number.isSafeInteger(milliseconds) || milliseconds < 0) {
        throw new TypeError("milliseconds must be a non-negative safe integer");
      }
      current += BigInt(milliseconds) * 1_000_000n;
      return current;
    },
  });
}

export class FakeWebSocket {
  static CONNECTING = 0;

  static OPEN = 1;

  static CLOSING = 2;

  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.CONNECTING;
    this.binaryType = "blob";
    this.sent = [];
    this.closeCalls = [];
    this.bufferedAmount = 0;
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }

  send(value) {
    if (this.readyState !== FakeWebSocket.OPEN) {
      throw new Error("synthetic socket is not open");
    }
    this.sent.push(value);
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.#dispatch("open", {});
  }

  receive(data) {
    this.#dispatch("message", { data });
  }

  fail(error = new Error("synthetic WebSocket failure")) {
    this.#dispatch("error", { error });
  }

  close(code = 1000, reason = "") {
    this.closeCalls.push({ code, reason });
    this.readyState = FakeWebSocket.CLOSED;
    this.#dispatch("close", { code, reason, wasClean: code === 1000 });
  }

  #dispatch(type, properties) {
    const event = Object.freeze({ type, target: this, ...properties });
    const propertyListener = this[`on${type}`];
    if (typeof propertyListener === "function") {
      propertyListener(event);
    }
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

export function createSyntheticFrame({
  direction = "output",
  generationId = 7,
  sequence = 0,
  sourceMonotonicNs = 1_000_000_000n,
} = {}) {
  if (direction !== "input" && direction !== "output") {
    throw new TypeError("direction must be input or output");
  }
  return Object.freeze({
    header: Object.freeze({
      kind: direction === "input" ? 1 : 2,
      flags: 0,
      generation_id: generationId,
      sequence,
      sample_rate: 48_000,
      channels: 1,
      samples_per_channel: 960,
      source_monotonic_ns: sourceMonotonicNs,
    }),
    samples: new Float32Array(960),
  });
}

export async function flushMicrotasks(turns = 3) {
  for (let index = 0; index < turns; index += 1) {
    await Promise.resolve();
  }
}
