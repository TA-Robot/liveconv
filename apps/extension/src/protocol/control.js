const PROTOCOL_VERSION = 1;
const MAX_MESSAGE_BYTES = 16_384;
const UINT32_MAX = 0xffff_ffff;

const REQUEST_ID = /^[A-Za-z0-9._:-]{1,128}$/;
const PROFILE_ID = /^[a-z0-9][a-z0-9._-]{0,127}$/;
const CLOCK_ID = /^[A-Za-z0-9._:-]{1,128}$/;
const FIELD = /^[A-Za-z0-9._:-]{1,128}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH = /^sha256:[0-9a-f]{64}$/;

const COMMON_CONTROL = ["type", "protocol_version", "request_id", "session_id"];
const CONTROL_FIELDS = Object.freeze({
  "session.attach": [...COMMON_CONTROL, "ticket"],
  "model.select": [...COMMON_CONTROL, "profile_id"],
  "generation.start": [...COMMON_CONTROL, "generation_id"],
  "generation.end": [...COMMON_CONTROL, "generation_id"],
  "generation.cancel": [...COMMON_CONTROL, "generation_id"],
  ping: [...COMMON_CONTROL, "client_monotonic_ns", "clock_id"],
  "session.close": COMMON_CONTROL,
});

const COMMON_SERVER = ["type", "protocol_version", "session_id"];
const REQUEST_SERVER = [...COMMON_SERVER, "request_id"];
const PROFILE_FIELDS = [
  "profile_id",
  "profile_hash",
  "configuration_hash",
  "pipeline_id",
];
const GENERATION_FIELDS = ["generation_id", "pipeline_id"];
const SERVER_FIELDS = Object.freeze({
  "session.ready": [
    ...REQUEST_SERVER,
    ...PROFILE_FIELDS,
    "clock_id",
    "limits",
  ],
  "model.selected": [...REQUEST_SERVER, ...PROFILE_FIELDS],
  "generation.ready": [
    ...REQUEST_SERVER,
    ...PROFILE_FIELDS,
    "generation_id",
  ],
  "generation.completed": [...REQUEST_SERVER, ...GENERATION_FIELDS],
  "generation.canceled": [...REQUEST_SERVER, ...GENERATION_FIELDS],
  "session.closed": REQUEST_SERVER,
  "fallback.required": [
    ...COMMON_SERVER,
    ...GENERATION_FIELDS,
    "reason_code",
  ],
  error: [
    "type",
    "protocol_version",
    "code",
    "recoverable",
    "required_action",
    "message",
  ],
  pong: [
    ...REQUEST_SERVER,
    "client_clock_id",
    "client_monotonic_ns",
    "clock_id",
    "server_monotonic_ns",
  ],
});
const OPTIONAL_SERVER_FIELDS = Object.freeze({
  error: ["session_id", "request_id", "generation_id", "field"],
});

const ERROR_CODES = new Set([
  "AUTH_FAILED",
  "UNSUPPORTED_PROTOCOL",
  "INVALID_STATE",
  "MODEL_UNAVAILABLE",
  "MODEL_TIMEOUT",
  "QUEUE_OVERFLOW",
  "SEQUENCE_GAP",
  "STALE_GENERATION",
  "UNSUPPORTED_AUDIO",
  "WORKER_CRASH",
]);
const REQUIRED_ACTIONS = new Set([
  "none",
  "retry",
  "fallback",
  "close_session",
]);

const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });

function fail(message) {
  throw new TypeError(message);
}

function byteLength(value) {
  return encoder.encode(value).byteLength;
}

function requireObject(value, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(`${name} must be a JSON object`);
  }
  return value;
}

function requireFields(value, required, optional = []) {
  const requiredSet = new Set(required);
  const allowed = new Set([...required, ...optional]);
  for (const field of requiredSet) {
    if (!Object.hasOwn(value, field)) {
      fail(`missing required field ${field}`);
    }
  }
  for (const field of Object.keys(value)) {
    if (!allowed.has(field)) {
      fail(`unknown field ${field}`);
    }
  }
}

function requireVersion(value) {
  if (!Number.isInteger(value) || value !== PROTOCOL_VERSION) {
    fail(`unsupported protocol version ${String(value)}`);
  }
  return value;
}

function requireText(value, name, { pattern, maximumBytes = 1024 } = {}) {
  if (typeof value !== "string" || value.length === 0) {
    fail(`${name} must be a non-empty string`);
  }
  if (byteLength(value) > maximumBytes) {
    fail(`${name} is too long`);
  }
  if (pattern && !pattern.test(value)) {
    fail(`${name} has an invalid format`);
  }
  return value;
}

function requireUint(value, name, maximum) {
  if (!Number.isSafeInteger(value) || value < 0 || value > maximum) {
    fail(`${name} must be an unsigned safe integer in its wire range`);
  }
  return value;
}

function requireUuid(value, name, { normalize = false } = {}) {
  const text = requireText(value, name, { maximumBytes: 36 });
  const canonical = text.toLowerCase();
  if (!UUID.test(canonical)) {
    fail(`${name} must be a UUID`);
  }
  if (!normalize && canonical !== text) {
    fail(`${name} must use canonical UUID form`);
  }
  return canonical;
}

function requireEnum(value, name, options) {
  if (typeof value !== "string" || !options.has(value)) {
    fail(`${name} is not a version 1 value`);
  }
  return value;
}

function normalizedControl(value) {
  const message = requireObject(value, "control message");
  const type = message.type;
  if (typeof type !== "string" || !Object.hasOwn(CONTROL_FIELDS, type)) {
    fail("unsupported control message type");
  }
  requireFields(message, CONTROL_FIELDS[type]);
  requireVersion(message.protocol_version);

  const normalized = {
    ...message,
    request_id: requireText(message.request_id, "request_id", {
      pattern: REQUEST_ID,
      maximumBytes: 128,
    }),
    session_id: requireUuid(message.session_id, "session_id", {
      normalize: true,
    }),
  };

  if (type === "session.attach") {
    normalized.ticket = requireText(message.ticket, "ticket", {
      maximumBytes: 4096,
    });
  } else if (type === "model.select") {
    normalized.profile_id = requireText(message.profile_id, "profile_id", {
      pattern: PROFILE_ID,
      maximumBytes: 128,
    });
  } else if (type.startsWith("generation.")) {
    normalized.generation_id = requireUint(
      message.generation_id,
      "generation_id",
      UINT32_MAX,
    );
  } else if (type === "ping") {
    normalized.client_monotonic_ns = requireUint(
      message.client_monotonic_ns,
      "client_monotonic_ns",
      Number.MAX_SAFE_INTEGER,
    );
    normalized.clock_id = requireText(message.clock_id, "clock_id", {
      pattern: CLOCK_ID,
      maximumBytes: 128,
    });
  }
  return normalized;
}

function requireServerCommon(event) {
  requireVersion(event.protocol_version);
  requireUuid(event.session_id, "session_id");
}

function requireRequest(event) {
  requireServerCommon(event);
  requireText(event.request_id, "request_id", {
    pattern: REQUEST_ID,
    maximumBytes: 128,
  });
}

function requireProfile(event) {
  requireText(event.profile_id, "profile_id", {
    pattern: PROFILE_ID,
    maximumBytes: 128,
  });
  requireText(event.profile_hash, "profile_hash", { pattern: HASH });
  requireText(event.configuration_hash, "configuration_hash", {
    pattern: HASH,
  });
  requireUuid(event.pipeline_id, "pipeline_id");
}

function requireGeneration(event) {
  requireUint(event.generation_id, "generation_id", UINT32_MAX);
  requireUuid(event.pipeline_id, "pipeline_id");
}

function requireLimits(value) {
  const limits = requireObject(value, "limits");
  requireFields(limits, ["ingress_budget_ms", "max_ingress_frames"]);
  const ingressBudget = requireUint(
    limits.ingress_budget_ms,
    "limits.ingress_budget_ms",
    UINT32_MAX,
  );
  const maxFrames = requireUint(
    limits.max_ingress_frames,
    "limits.max_ingress_frames",
    UINT32_MAX,
  );
  if (ingressBudget === 0 || maxFrames === 0) {
    fail("limits must be greater than zero");
  }
}

function normalizedServerEvent(value) {
  const event = requireObject(value, "server event");
  const type = event.type;
  if (typeof type !== "string" || !Object.hasOwn(SERVER_FIELDS, type)) {
    fail("unsupported server event type");
  }
  requireFields(
    event,
    SERVER_FIELDS[type],
    OPTIONAL_SERVER_FIELDS[type] ?? [],
  );

  if (type === "error") {
    requireVersion(event.protocol_version);
    requireEnum(event.code, "code", ERROR_CODES);
    if (typeof event.recoverable !== "boolean") {
      fail("recoverable must be a boolean");
    }
    requireEnum(event.required_action, "required_action", REQUIRED_ACTIONS);
    requireText(event.message, "message");
    if (Object.hasOwn(event, "session_id")) {
      requireUuid(event.session_id, "session_id");
    }
    if (Object.hasOwn(event, "request_id")) {
      requireText(event.request_id, "request_id", {
        pattern: REQUEST_ID,
        maximumBytes: 128,
      });
    }
    if (Object.hasOwn(event, "generation_id")) {
      requireUint(event.generation_id, "generation_id", UINT32_MAX);
    }
    if (Object.hasOwn(event, "field")) {
      requireText(event.field, "field", {
        pattern: FIELD,
        maximumBytes: 128,
      });
    }
    return { ...event };
  }

  if (type === "fallback.required") {
    requireServerCommon(event);
    requireGeneration(event);
    requireEnum(event.reason_code, "reason_code", ERROR_CODES);
  } else {
    requireRequest(event);
  }

  if (
    type === "session.ready" ||
    type === "model.selected" ||
    type === "generation.ready"
  ) {
    requireProfile(event);
  }
  if (
    type === "generation.ready" ||
    type === "generation.completed" ||
    type === "generation.canceled"
  ) {
    requireUint(event.generation_id, "generation_id", UINT32_MAX);
  }
  if (type === "generation.completed" || type === "generation.canceled") {
    requireGeneration(event);
  }
  if (type === "session.ready") {
    requireText(event.clock_id, "clock_id", {
      pattern: CLOCK_ID,
      maximumBytes: 128,
    });
    requireLimits(event.limits);
    return { ...event, limits: { ...event.limits } };
  }
  if (type === "pong") {
    requireText(event.client_clock_id, "client_clock_id", {
      pattern: CLOCK_ID,
      maximumBytes: 128,
    });
    requireUint(
      event.client_monotonic_ns,
      "client_monotonic_ns",
      Number.MAX_SAFE_INTEGER,
    );
    requireText(event.clock_id, "clock_id", {
      pattern: CLOCK_ID,
      maximumBytes: 128,
    });
    requireUint(
      event.server_monotonic_ns,
      "server_monotonic_ns",
      Number.MAX_SAFE_INTEGER,
    );
  }
  return { ...event };
}

function textInput(value) {
  if (typeof value === "string") {
    return value;
  }
  if (value instanceof ArrayBuffer) {
    return decoder.decode(new Uint8Array(value));
  }
  if (ArrayBuffer.isView(value)) {
    return decoder.decode(
      new Uint8Array(value.buffer, value.byteOffset, value.byteLength),
    );
  }
  fail("server event must be a string or bytes-like value");
}

function assertNoDuplicateJsonKeys(source) {
  let index = 0;

  function skipWhitespace() {
    while (/^[\u0009\u000a\u000d\u0020]$/.test(source[index] ?? "")) {
      index += 1;
    }
  }

  function parseString() {
    const start = index;
    if (source[index] !== '"') {
      fail("JSON object keys must be strings");
    }
    index += 1;
    while (index < source.length) {
      const character = source[index];
      if (character === '"') {
        index += 1;
        try {
          return JSON.parse(source.slice(start, index));
        } catch {
          fail("server event must be valid JSON");
        }
      }
      if (character === "\\") {
        index += 2;
      } else {
        index += 1;
      }
    }
    fail("server event must be valid JSON");
  }

  function parseValue() {
    skipWhitespace();
    const character = source[index];
    if (character === "{") {
      parseObject();
      return;
    }
    if (character === "[") {
      parseArray();
      return;
    }
    if (character === '"') {
      parseString();
      return;
    }
    for (const literal of ["true", "false", "null"]) {
      if (source.startsWith(literal, index)) {
        index += literal.length;
        return;
      }
    }
    const number = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(
      source.slice(index),
    )?.[0];
    if (!number) {
      fail("server event must be valid JSON");
    }
    index += number.length;
  }

  function parseObject() {
    index += 1;
    skipWhitespace();
    const keys = new Set();
    if (source[index] === "}") {
      index += 1;
      return;
    }
    while (index < source.length) {
      const key = parseString();
      if (keys.has(key)) {
        fail(`duplicate server event field ${key}`);
      }
      keys.add(key);
      skipWhitespace();
      if (source[index] !== ":") {
        fail("server event must be valid JSON");
      }
      index += 1;
      parseValue();
      skipWhitespace();
      if (source[index] === "}") {
        index += 1;
        return;
      }
      if (source[index] !== ",") {
        fail("server event must be valid JSON");
      }
      index += 1;
      skipWhitespace();
    }
    fail("server event must be valid JSON");
  }

  function parseArray() {
    index += 1;
    skipWhitespace();
    if (source[index] === "]") {
      index += 1;
      return;
    }
    while (index < source.length) {
      parseValue();
      skipWhitespace();
      if (source[index] === "]") {
        index += 1;
        return;
      }
      if (source[index] !== ",") {
        fail("server event must be valid JSON");
      }
      index += 1;
    }
    fail("server event must be valid JSON");
  }

  parseValue();
  skipWhitespace();
  if (index !== source.length) {
    fail("server event must contain exactly one JSON value");
  }
}

export function encodeControlMessage(value) {
  const encoded = JSON.stringify(normalizedControl(value));
  if (byteLength(encoded) > MAX_MESSAGE_BYTES) {
    fail("control message exceeds the version 1 size limit");
  }
  return encoded;
}

export function decodeServerEvent(value) {
  let text;
  try {
    text = textInput(value);
  } catch (error) {
    fail(error instanceof Error ? error.message : "server event is not UTF-8");
  }
  if (byteLength(text) > MAX_MESSAGE_BYTES) {
    fail("server event exceeds the version 1 size limit");
  }
  assertNoDuplicateJsonKeys(text);
  let decoded;
  try {
    decoded = JSON.parse(text);
  } catch {
    fail("server event must be valid JSON");
  }
  return normalizedServerEvent(decoded);
}
