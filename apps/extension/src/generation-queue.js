const UINT32_MAX = 0xffff_ffff;

function requirePositiveInteger(value, name) {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new TypeError(`${name} must be a positive safe integer`);
  }
  return value;
}

function requireGenerationId(value) {
  if (!Number.isInteger(value) || value < 0 || value > UINT32_MAX) {
    throw new TypeError("generationId must be a uint32");
  }
  return value;
}

function frameIdentity(frame) {
  const header = frame?.header;
  if (header === null || typeof header !== "object") {
    throw new TypeError("frame.header must be an object");
  }
  const generationId = requireGenerationId(header.generation_id);
  const sequence = header.sequence;
  if (!Number.isInteger(sequence) || sequence < 0 || sequence > UINT32_MAX) {
    throw new TypeError("frame.header.sequence must be a uint32");
  }
  return { generationId, sequence };
}

export function createGenerationQueue(options) {
  if (options === null || typeof options !== "object") {
    throw new TypeError("options must be an object");
  }
  const { direction } = options;
  if (direction !== "uplink" && direction !== "jitter") {
    throw new TypeError("direction must be uplink or jitter");
  }
  const frameDurationMs = requirePositiveInteger(
    options.frameDurationMs,
    "frameDurationMs",
  );
  const maxBufferedMs = requirePositiveInteger(
    options.maxBufferedMs,
    "maxBufferedMs",
  );
  if (maxBufferedMs < frameDurationMs) {
    throw new TypeError("maxBufferedMs must hold at least one frame");
  }
  if (typeof options.onFallback !== "function") {
    throw new TypeError("onFallback must be a function");
  }

  const maximumDepth = Math.floor(maxBufferedMs / frameDurationMs);
  let frames = [];
  let generationId = null;
  let accepting = false;
  let nextSequence = 0;

  function discard() {
    const discarded = frames.length;
    frames = [];
    return discarded;
  }

  function invalidate(reasonCode, details = {}) {
    discard();
    accepting = false;
    options.onFallback({
      direction,
      generationId,
      reasonCode,
      ...details,
    });
    return false;
  }

  function beginGeneration(nextGenerationId) {
    requireGenerationId(nextGenerationId);
    if (generationId !== null && nextGenerationId < generationId) {
      throw new RangeError("generationId cannot move backwards");
    }
    const discarded = discard();
    generationId = nextGenerationId;
    accepting = true;
    nextSequence = 0;
    return discarded;
  }

  function enqueue(frame) {
    if (!accepting || generationId === null) {
      return false;
    }
    const identity = frameIdentity(frame);
    if (identity.generationId !== generationId) {
      return invalidate("STALE_GENERATION", {
        receivedGenerationId: identity.generationId,
      });
    }
    if (identity.sequence !== nextSequence) {
      return invalidate("SEQUENCE_GAP", {
        expectedSequence: nextSequence,
        receivedSequence: identity.sequence,
      });
    }
    if (frames.length >= maximumDepth) {
      return invalidate("QUEUE_OVERFLOW");
    }
    frames.push(frame);
    nextSequence += 1;
    return true;
  }

  function dequeue() {
    return frames.shift();
  }

  function cancelGeneration(canceledGenerationId) {
    requireGenerationId(canceledGenerationId);
    if (generationId !== canceledGenerationId) {
      return 0;
    }
    const discarded = discard();
    accepting = false;
    return discarded;
  }

  function snapshot() {
    return Object.freeze({
      direction,
      generationId,
      depth: frames.length,
      bufferedMs: frames.length * frameDurationMs,
      accepting,
    });
  }

  return Object.freeze({
    beginGeneration,
    cancelGeneration,
    dequeue,
    enqueue,
    snapshot,
  });
}
