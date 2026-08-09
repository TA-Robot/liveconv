import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { asBytes, protocolFixtures, readJson } from "./support.mjs";

const frameModuleUrl = new URL("../src/protocol/frame.js", import.meta.url);
const controlModuleUrl = new URL("../src/protocol/control.js", import.meta.url);

function sha256(value) {
  return createHash("sha256").update(asBytes(value)).digest("hex");
}

function normalizedHeader(header) {
  return {
    ...header,
    source_monotonic_ns: Number(header.source_monotonic_ns),
  };
}

test("PCM encoder matches the canonical v1 header and payload golden", async () => {
  const { encodePcmFrame } = await import(frameModuleUrl);
  const fixture = await readJson(new URL("pcm_frame_v1.json", protocolFixtures));
  const samples = Float32Array.from(
    { length: fixture.header.samples_per_channel },
    (_, index) => ((index % 32) - 16) / 16,
  );

  const frame = asBytes(encodePcmFrame(fixture.header, samples));
  assert.equal(frame.byteLength, fixture.frame_length);
  assert.equal(Buffer.from(frame.subarray(0, 32)).toString("hex"), fixture.encoded_header_hex);
  assert.equal(sha256(frame.subarray(32)), fixture.payload_sha256);
  assert.equal(sha256(frame), fixture.frame_sha256);
});

test("PCM decoder round-trips the canonical v1 frame without losing u64 time", async () => {
  const { decodePcmFrame, encodePcmFrame } = await import(frameModuleUrl);
  const fixture = await readJson(new URL("pcm_frame_v1.json", protocolFixtures));
  const samples = Float32Array.from(
    { length: fixture.header.samples_per_channel },
    (_, index) => ((index % 32) - 16) / 16,
  );

  const decoded = decodePcmFrame(encodePcmFrame(fixture.header, samples));
  assert.deepEqual(normalizedHeader(decoded.header), fixture.header);
  assert(decoded.samples instanceof Float32Array);
  assert.equal(sha256(decoded.samples), fixture.payload_sha256);

  const largeTimestamp = (1n << 63n) + 17n;
  const encoded = encodePcmFrame(
    { ...fixture.header, source_monotonic_ns: largeTimestamp },
    samples,
  );
  assert.equal(decodePcmFrame(encoded).header.source_monotonic_ns, largeTimestamp);
});

test("PCM codec rejects malformed headers, lengths, and unsafe samples", async () => {
  const { decodePcmFrame, encodePcmFrame } = await import(frameModuleUrl);
  const fixture = await readJson(new URL("pcm_frame_v1.json", protocolFixtures));
  const samples = Float32Array.from(
    { length: fixture.header.samples_per_channel },
    (_, index) => ((index % 32) - 16) / 16,
  );
  const valid = asBytes(encodePcmFrame(fixture.header, samples));

  for (const [offset, value] of [
    [0, 0],
    [2, 2],
    [7, 31],
  ]) {
    const malformed = valid.slice();
    malformed[offset] = value;
    assert.throws(() => decodePcmFrame(malformed));
  }
  const trailing = new Uint8Array(valid.byteLength + 1);
  trailing.set(valid);
  assert.throws(() => decodePcmFrame(trailing));

  const nonFinitePayload = valid.slice();
  new DataView(nonFinitePayload.buffer).setFloat32(32, Number.NaN, true);
  assert.throws(() => decodePcmFrame(nonFinitePayload));
  assert.throws(() => encodePcmFrame(fixture.header, samples.subarray(1)));

  const nonFiniteSamples = samples.slice();
  nonFiniteSamples[0] = Number.POSITIVE_INFINITY;
  assert.throws(() => encodePcmFrame(fixture.header, nonFiniteSamples));
  const outOfRangeSamples = samples.slice();
  outOfRangeSamples[0] = 1.01;
  assert.throws(() => encodePcmFrame(fixture.header, outOfRangeSamples));
});

test("client controls and server events consume the canonical JSON goldens", async () => {
  const { decodeServerEvent, encodeControlMessage } = await import(controlModuleUrl);
  const controls = await readJson(new URL("control_messages.json", protocolFixtures));
  const serverEvents = await readJson(new URL("server_events.json", protocolFixtures));

  for (const control of controls) {
    assert.deepEqual(JSON.parse(encodeControlMessage(control)), control);
  }
  for (const event of serverEvents) {
    assert.deepEqual(decodeServerEvent(JSON.stringify(event)), event);
  }
});

test("JSON codec is strict about versions, fields, message types, and size", async () => {
  const { decodeServerEvent, encodeControlMessage } = await import(controlModuleUrl);
  const controls = await readJson(new URL("control_messages.json", protocolFixtures));
  const serverEvents = await readJson(new URL("server_events.json", protocolFixtures));

  assert.throws(() => encodeControlMessage({ ...controls[2], protocol_version: 2 }));
  assert.throws(() => encodeControlMessage({ ...controls[2], unexpected: true }));
  const missingRequest = { ...controls[2] };
  delete missingRequest.request_id;
  assert.throws(() => encodeControlMessage(missingRequest));

  assert.throws(() =>
    decodeServerEvent(JSON.stringify({ ...serverEvents[0], type: "unknown" })),
  );
  assert.throws(() =>
    decodeServerEvent(JSON.stringify({ ...serverEvents[0], unexpected: true })),
  );
  assert.throws(() => decodeServerEvent(" ".repeat(16_385)));

  const pongJson = JSON.stringify(serverEvents.at(-1));
  assert.equal(serverEvents.at(-1).type, "pong");
  assert.throws(() => decodeServerEvent(`{"type":"pong",${pongJson.slice(1)}`));
});
