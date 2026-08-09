const MAGIC = 0x4c56;
const PROTOCOL_VERSION = 1;
const HEADER_LENGTH = 32;
const SAMPLE_RATE = 48_000;
const CHANNELS = 1;
const SAMPLES_PER_CHANNEL = 960;
const SAMPLE_WIDTH_BYTES = 4;
const FRAME_LENGTH =
  HEADER_LENGTH + CHANNELS * SAMPLES_PER_CHANNEL * SAMPLE_WIDTH_BYTES;

const UINT32_MAX = 0xffff_ffff;
const UINT64_MAX = (1n << 64n) - 1n;
const SAFE_INTEGER_MAX = BigInt(Number.MAX_SAFE_INTEGER);
const HEADER_FIELDS = new Set([
  "kind",
  "flags",
  "generation_id",
  "sequence",
  "sample_rate",
  "channels",
  "samples_per_channel",
  "source_monotonic_ns",
]);

function fail(message) {
  throw new TypeError(message);
}

function requireObject(value, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(`${name} must be an object`);
  }
  return value;
}

function requireUint(value, name, maximum) {
  if (!Number.isInteger(value) || value < 0 || value > maximum) {
    fail(`${name} must be an unsigned integer in its wire range`);
  }
  return value;
}

function requireTimestamp(value) {
  let timestamp;
  if (typeof value === "bigint") {
    timestamp = value;
  } else if (Number.isSafeInteger(value)) {
    timestamp = BigInt(value);
  } else {
    fail("source_monotonic_ns must be a safe integer or bigint");
  }
  if (timestamp < 0n || timestamp > UINT64_MAX) {
    fail("source_monotonic_ns is outside the uint64 wire range");
  }
  return timestamp;
}

function normalizeHeader(value) {
  const header = requireObject(value, "header");
  for (const field of Object.keys(header)) {
    if (!HEADER_FIELDS.has(field)) {
      fail(`unknown frame header field ${field}`);
    }
  }
  for (const field of [
    "kind",
    "generation_id",
    "sequence",
    "source_monotonic_ns",
  ]) {
    if (!Object.hasOwn(header, field)) {
      fail(`missing frame header field ${field}`);
    }
  }

  const normalized = {
    kind: requireUint(header.kind, "kind", 0xff),
    flags: requireUint(header.flags ?? 0, "flags", 0xffff),
    generation_id: requireUint(
      header.generation_id,
      "generation_id",
      UINT32_MAX,
    ),
    sequence: requireUint(header.sequence, "sequence", UINT32_MAX),
    sample_rate: requireUint(
      header.sample_rate ?? SAMPLE_RATE,
      "sample_rate",
      UINT32_MAX,
    ),
    channels: requireUint(header.channels ?? CHANNELS, "channels", 0xffff),
    samples_per_channel: requireUint(
      header.samples_per_channel ?? SAMPLES_PER_CHANNEL,
      "samples_per_channel",
      0xffff,
    ),
    source_monotonic_ns: requireTimestamp(header.source_monotonic_ns),
  };

  if (normalized.kind !== 1 && normalized.kind !== 2) {
    fail("kind must be 1 (input) or 2 (output)");
  }
  if (normalized.flags !== 0) {
    fail("version 1 does not define non-zero frame flags");
  }
  if (normalized.sample_rate !== SAMPLE_RATE) {
    fail(`version 1 requires sample_rate=${SAMPLE_RATE}`);
  }
  if (normalized.channels !== CHANNELS) {
    fail(`version 1 requires channels=${CHANNELS}`);
  }
  if (normalized.samples_per_channel !== SAMPLES_PER_CHANNEL) {
    fail(`version 1 requires samples_per_channel=${SAMPLES_PER_CHANNEL}`);
  }
  return normalized;
}

function requireSamples(value) {
  if (!(value instanceof Float32Array)) {
    fail("samples must be a Float32Array");
  }
  if (value.length !== CHANNELS * SAMPLES_PER_CHANNEL) {
    fail(`samples must contain exactly ${SAMPLES_PER_CHANNEL} values`);
  }
  for (const sample of value) {
    if (!Number.isFinite(sample) || sample < -1 || sample > 1) {
      fail("PCM samples must be finite and normalized to [-1, 1]");
    }
  }
  return value;
}

function byteView(value) {
  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  fail("frame must be an ArrayBuffer or ArrayBuffer view");
}

function publicTimestamp(timestamp) {
  return timestamp <= SAFE_INTEGER_MAX ? Number(timestamp) : timestamp;
}

export function encodePcmFrame(header, samples) {
  const normalizedHeader = normalizeHeader(header);
  const normalizedSamples = requireSamples(samples);
  const frame = new ArrayBuffer(FRAME_LENGTH);
  const view = new DataView(frame);

  view.setUint16(0, MAGIC, false);
  view.setUint8(2, PROTOCOL_VERSION);
  view.setUint8(3, normalizedHeader.kind);
  view.setUint16(4, normalizedHeader.flags, false);
  view.setUint16(6, HEADER_LENGTH, false);
  view.setUint32(8, normalizedHeader.generation_id, false);
  view.setUint32(12, normalizedHeader.sequence, false);
  view.setUint32(16, normalizedHeader.sample_rate, false);
  view.setUint16(20, normalizedHeader.channels, false);
  view.setUint16(22, normalizedHeader.samples_per_channel, false);
  view.setBigUint64(24, normalizedHeader.source_monotonic_ns, false);

  for (let index = 0; index < normalizedSamples.length; index += 1) {
    view.setFloat32(
      HEADER_LENGTH + index * SAMPLE_WIDTH_BYTES,
      normalizedSamples[index],
      true,
    );
  }
  return frame;
}

export function decodePcmFrame(value) {
  const bytes = byteView(value);
  if (bytes.byteLength < HEADER_LENGTH) {
    fail(`frame must contain at least ${HEADER_LENGTH} header bytes`);
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint16(0, false) !== MAGIC) {
    fail("frame magic is not LV");
  }
  if (view.getUint8(2) !== PROTOCOL_VERSION) {
    fail("unsupported frame protocol version");
  }
  if (view.getUint16(6, false) !== HEADER_LENGTH) {
    fail(`version 1 header_length must be ${HEADER_LENGTH}`);
  }

  const normalizedHeader = normalizeHeader({
    kind: view.getUint8(3),
    flags: view.getUint16(4, false),
    generation_id: view.getUint32(8, false),
    sequence: view.getUint32(12, false),
    sample_rate: view.getUint32(16, false),
    channels: view.getUint16(20, false),
    samples_per_channel: view.getUint16(22, false),
    source_monotonic_ns: view.getBigUint64(24, false),
  });
  if (bytes.byteLength !== FRAME_LENGTH) {
    fail(`frame length must be exactly ${FRAME_LENGTH} bytes`);
  }

  const samples = new Float32Array(SAMPLES_PER_CHANNEL * CHANNELS);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = view.getFloat32(
      HEADER_LENGTH + index * SAMPLE_WIDTH_BYTES,
      true,
    );
    if (!Number.isFinite(sample) || sample < -1 || sample > 1) {
      fail("PCM samples must be finite and normalized to [-1, 1]");
    }
    samples[index] = sample;
  }

  return {
    header: {
      ...normalizedHeader,
      source_monotonic_ns: publicTimestamp(
        normalizedHeader.source_monotonic_ns,
      ),
    },
    samples,
  };
}

export const frameV1 = Object.freeze({
  magic: MAGIC,
  protocolVersion: PROTOCOL_VERSION,
  headerLength: HEADER_LENGTH,
  frameLength: FRAME_LENGTH,
  sampleRate: SAMPLE_RATE,
  channels: CHANNELS,
  samplesPerChannel: SAMPLES_PER_CHANNEL,
});
