const UINT32_MAX = 0xffff_ffff;

function requireGenerationId(value) {
  if (!Number.isInteger(value) || value < 0 || value > UINT32_MAX) {
    throw new TypeError("generationId must be a uint32");
  }
  return value;
}

function requireSequence(value) {
  if (!Number.isInteger(value) || value < 0 || value > UINT32_MAX) {
    throw new TypeError("sequence must be a uint32");
  }
  return value;
}

function requireSamples(value, length = null) {
  if (!(value instanceof Float32Array)) {
    throw new TypeError("samples must be a Float32Array");
  }
  if (length !== null && value.length !== length) {
    throw new TypeError(`samples must contain exactly ${length} values`);
  }
  return value;
}

function requireSourceFrame(value) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new TypeError("sourceFrame must be a non-negative safe integer");
  }
  return value;
}

export class CaptureFrameAssembler {
  constructor(frameSamples = 960) {
    if (!Number.isSafeInteger(frameSamples) || frameSamples <= 0) {
      throw new TypeError("frameSamples must be a positive safe integer");
    }
    this.frameSamples = frameSamples;
    this.buffer = new Float32Array(frameSamples);
    this.length = 0;
    this.sourceFrame = 0;
  }

  reset() {
    this.buffer = new Float32Array(this.frameSamples);
    this.length = 0;
    this.sourceFrame = 0;
  }

  push(samples, sourceFrame) {
    requireSamples(samples);
    if (!Number.isSafeInteger(sourceFrame) || sourceFrame < 0) {
      throw new TypeError("sourceFrame must be a non-negative safe integer");
    }
    const frames = [];
    let offset = 0;
    while (offset < samples.length) {
      if (this.length === 0) {
        this.sourceFrame = sourceFrame + offset;
      }
      const count = Math.min(
        samples.length - offset,
        this.frameSamples - this.length,
      );
      this.buffer.set(samples.subarray(offset, offset + count), this.length);
      this.length += count;
      offset += count;
      if (this.length === this.frameSamples) {
        frames.push(
          Object.freeze({ samples: this.buffer, sourceFrame: this.sourceFrame }),
        );
        this.buffer = new Float32Array(this.frameSamples);
        this.length = 0;
      }
    }
    return frames;
  }
}

export class GenerationPlayoutBuffer {
  constructor({ frameSamples = 960, targetFrames = 4, maximumFrames = 10 } = {}) {
    for (const [name, value] of Object.entries({
      frameSamples,
      targetFrames,
      maximumFrames,
    })) {
      if (!Number.isSafeInteger(value) || value <= 0) {
        throw new TypeError(`${name} must be a positive safe integer`);
      }
    }
    if (targetFrames > maximumFrames) {
      throw new TypeError("targetFrames cannot exceed maximumFrames");
    }
    this.frameSamples = frameSamples;
    this.targetFrames = targetFrames;
    this.maximumFrames = maximumFrames;
    this.generationId = null;
    this.expectedSequence = 0;
    this.queue = [];
    this.offset = 0;
    this.accepting = false;
    this.audible = false;
    this.readyNotified = false;
  }

  begin(generationId) {
    requireGenerationId(generationId);
    this.clear();
    this.generationId = generationId;
    this.expectedSequence = 0;
    this.accepting = true;
    this.readyNotified = false;
  }

  clear() {
    this.queue = [];
    this.offset = 0;
    this.audible = false;
  }

  rebuffer() {
    this.clear();
    this.readyNotified = false;
  }

  bufferedSamples() {
    if (this.queue.length === 0) {
      return 0;
    }
    return this.queue.length * this.frameSamples - this.offset;
  }

  cancel(generationId) {
    requireGenerationId(generationId);
    if (generationId !== this.generationId) {
      return false;
    }
    this.clear();
    this.accepting = false;
    return true;
  }

  invalidate(reasonCode) {
    this.clear();
    this.accepting = false;
    return Object.freeze({ ok: false, reasonCode });
  }

  enqueue({ generationId, sequence, sourceFrame, samples } = {}) {
    requireGenerationId(generationId);
    requireSequence(sequence);
    requireSamples(samples, this.frameSamples);
    const normalizedSourceFrame = requireSourceFrame(
      sourceFrame ?? sequence * this.frameSamples,
    );
    if (!this.accepting || generationId !== this.generationId) {
      return this.invalidate("STALE_GENERATION");
    }
    if (sequence !== this.expectedSequence) {
      return this.invalidate("SEQUENCE_GAP");
    }
    if (this.queue.length >= this.maximumFrames) {
      return this.invalidate("QUEUE_OVERFLOW");
    }
    const previous = this.queue.at(-1);
    if (
      previous &&
      normalizedSourceFrame !== previous.sourceFrame + this.frameSamples
    ) {
      return this.invalidate("SEQUENCE_GAP");
    }
    this.queue.push({ samples, sourceFrame: normalizedSourceFrame });
    this.expectedSequence += 1;
    const ready =
      !this.readyNotified &&
      this.bufferedSamples() >= this.targetFrames * this.frameSamples;
    if (ready) {
      this.readyNotified = true;
    }
    return Object.freeze({ ok: true, ready });
  }

  setAudible(value) {
    if (typeof value !== "boolean") {
      throw new TypeError("audible must be a boolean");
    }
    this.audible = value && this.accepting;
  }

  trimBeforeSourceFrame(sourceFrame) {
    requireSourceFrame(sourceFrame);
    while (this.queue.length > 0) {
      const frame = this.queue[0];
      const firstAvailable = frame.sourceFrame + this.offset;
      if (sourceFrame <= firstAvailable) {
        break;
      }
      const discard = sourceFrame - firstAvailable;
      const remaining = this.frameSamples - this.offset;
      if (discard < remaining) {
        this.offset += discard;
        break;
      }
      this.queue.shift();
      this.offset = 0;
    }
    if (this.bufferedSamples() < this.targetFrames * this.frameSamples) {
      this.readyNotified = false;
    }
    return this.queue.length === 0
      ? null
      : this.queue[0].sourceFrame + this.offset;
  }

  hasTargetFrom(sourceFrame) {
    const firstAvailable = this.trimBeforeSourceFrame(sourceFrame);
    return (
      firstAvailable === sourceFrame &&
      this.bufferedSamples() >= this.targetFrames * this.frameSamples
    );
  }

  hasAvailableFrom(sourceFrame) {
    const firstAvailable = this.trimBeforeSourceFrame(sourceFrame);
    return firstAvailable === sourceFrame && this.bufferedSamples() > 0;
  }

  renderAligned(output, sourceFrame) {
    requireSamples(output);
    requireSourceFrame(sourceFrame);
    output.fill(0);
    if (!this.audible) {
      return Object.freeze({ aligned: false, underflow: false, rendered: 0 });
    }
    const firstAvailable = this.trimBeforeSourceFrame(sourceFrame);
    if (firstAvailable !== sourceFrame) {
      return Object.freeze({ aligned: false, underflow: true, rendered: 0 });
    }
    if (this.bufferedSamples() < output.length) {
      return Object.freeze({ aligned: true, underflow: true, rendered: 0 });
    }
    const result = this.render(output);
    return Object.freeze({ aligned: true, ...result });
  }

  render(output) {
    requireSamples(output);
    output.fill(0);
    if (!this.audible) {
      return Object.freeze({ underflow: false, rendered: 0 });
    }
    if (this.bufferedSamples() < output.length) {
      this.audible = false;
      this.accepting = false;
      this.clear();
      return Object.freeze({ underflow: true, rendered: 0 });
    }
    let rendered = 0;
    while (rendered < output.length && this.queue.length > 0) {
      const frame = this.queue[0].samples;
      const count = Math.min(output.length - rendered, frame.length - this.offset);
      output.set(frame.subarray(this.offset, this.offset + count), rendered);
      rendered += count;
      this.offset += count;
      if (this.offset === frame.length) {
        this.queue.shift();
        this.offset = 0;
      }
    }
    const underflow = rendered < output.length;
    if (underflow) {
      this.audible = false;
      this.accepting = false;
      this.clear();
    }
    return Object.freeze({ underflow, rendered });
  }

  snapshot() {
    return Object.freeze({
      generationId: this.generationId,
      depth: this.queue.length,
      bufferedSamples: this.bufferedSamples(),
      firstSourceFrame:
        this.queue.length === 0
          ? null
          : this.queue[0].sourceFrame + this.offset,
      accepting: this.accepting,
      audible: this.audible,
      expectedSequence: this.expectedSequence,
    });
  }
}
