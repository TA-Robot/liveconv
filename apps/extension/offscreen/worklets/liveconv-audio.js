import {
  CaptureFrameAssembler,
  GenerationPlayoutBuffer,
} from "../../src/worklet-buffers.js";

const FRAME_SAMPLES = 960;
const DEFAULT_MAXIMUM_CAPTURE_CREDITS = 4;
const MAXIMUM_NEGOTIATED_CAPTURE_CREDITS = 500;
const MAXIMUM_NEGOTIATED_CAPTURE_FRAMES = 500;
// A cold Beatrice session takes about 4.5 seconds to return its first 500 ms
// batch, then catches up in a burst. Keep native and converted audio on the
// same six-second delayed timeline so the burst is still ahead of the audible
// playhead. 288,000 is divisible by both the 960-sample protocol frame and
// Chrome's 128-sample render quantum.
const NATIVE_DELAY_SAMPLES = 288_000;
const NATIVE_RING_SAMPLES = 524_288;

class LiveconvCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.assembler = new CaptureFrameAssembler(FRAME_SAMPLES);
    this.generationId = null;
    this.credits = 0;
    this.maximumCredits = DEFAULT_MAXIMUM_CAPTURE_CREDITS;
    this.maximumFrames = null;
    this.emittedFrames = 0;
    this.overflowed = false;
    this.port.onmessage = ({ data }) => {
      if (data?.type === "capture.begin") {
        this.generationId = data.generationId;
        this.credits = 0;
        this.maximumCredits =
          Number.isSafeInteger(data.maximumCredits) &&
          data.maximumCredits > 0 &&
          data.maximumCredits <= MAXIMUM_NEGOTIATED_CAPTURE_CREDITS
            ? data.maximumCredits
            : DEFAULT_MAXIMUM_CAPTURE_CREDITS;
        this.maximumFrames =
          Number.isSafeInteger(data.maximumFrames) &&
          data.maximumFrames > 0 &&
          data.maximumFrames <= MAXIMUM_NEGOTIATED_CAPTURE_FRAMES
            ? data.maximumFrames
            : null;
        this.emittedFrames = 0;
        this.overflowed = false;
        this.assembler.reset();
      } else if (
        data?.type === "capture.credit" &&
        data.generationId === this.generationId &&
        Number.isSafeInteger(data.frames) &&
        data.frames > 0
      ) {
        this.credits = Math.min(
          this.maximumCredits,
          this.credits + data.frames,
        );
      } else if (data?.type === "capture.cancel") {
        if (data.generationId === this.generationId) {
          this.generationId = null;
          this.credits = 0;
          this.assembler.reset();
        }
      }
    };
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (this.generationId === null || !(channel instanceof Float32Array)) {
      return true;
    }
    for (const frame of this.assembler.push(channel, globalThis.currentFrame)) {
      if (this.credits === 0) {
        if (!this.overflowed) {
          this.overflowed = true;
          this.port.postMessage({
            type: "capture.fallback",
            generationId: this.generationId,
            reasonCode: "QUEUE_OVERFLOW",
          });
        }
        this.generationId = null;
        this.assembler.reset();
        break;
      }
      this.credits -= 1;
      this.emittedFrames += 1;
      this.port.postMessage(
        {
          type: "capture.frame",
          generationId: this.generationId,
          sourceFrame: frame.sourceFrame,
          samples: frame.samples,
        },
        [frame.samples.buffer],
      );
      if (
        this.maximumFrames !== null &&
        this.emittedFrames >= this.maximumFrames
      ) {
        this.port.postMessage({
          type: "capture.complete",
          generationId: this.generationId,
          capturedFrames: this.emittedFrames,
        });
        this.generationId = null;
        this.credits = 0;
        this.assembler.reset();
        break;
      }
    }
    return true;
  }
}

class LiveconvPlayoutProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new GenerationPlayoutBuffer({
      frameSamples: FRAME_SAMPLES,
      targetFrames: 4,
      maximumFrames: 10,
    });
    this.ending = false;
    this.drained = false;
    this.remoteRequested = false;
    this.readySent = false;
    this.lastReportedSourceFrame = null;
    this.nativeRing = new Float32Array(NATIVE_RING_SAMPLES);
    this.remoteScratch = new Float32Array(128);
    this.port.onmessage = ({ data }) => {
      if (data?.type === "playout.begin") {
        this.buffer.begin(data.generationId);
        this.ending = false;
        this.drained = false;
        this.remoteRequested = false;
        this.readySent = false;
        this.lastReportedSourceFrame = null;
        return;
      }
      if (data?.type === "playout.cancel") {
        this.buffer.cancel(data.generationId);
        this.ending = false;
        this.drained = false;
        this.remoteRequested = false;
        this.readySent = false;
        return;
      }
      if (data?.type === "playout.end") {
        if (data.generationId !== this.buffer.generationId) {
          return;
        }
        this.ending = true;
        if (this.buffer.snapshot().depth === 0) {
          this.markDrained();
        }
        return;
      }
      if (data?.type === "playout.audible") {
        this.buffer.setAudible(data.audible);
        this.remoteRequested = data.audible;
        return;
      }
      if (data?.type !== "playout.enqueue") {
        return;
      }
      if (this.ending) {
        this.port.postMessage({
          type: "playout.fallback",
          generationId: data.generationId,
          reasonCode: "INVALID_STATE",
        });
        return;
      }
      let result;
      try {
        result = this.buffer.enqueue(data);
      } catch {
        result = { ok: false, reasonCode: "UNSUPPORTED_AUDIO" };
      }
      this.port.postMessage({
        type: "playout.depth",
        generationId: data.generationId,
        acknowledged: true,
        depth: this.buffer.snapshot().depth,
      });
      if (!result.ok) {
        this.port.postMessage({
          type: "playout.fallback",
          generationId: data.generationId,
          reasonCode: result.reasonCode,
        });
      }
    };
  }

  markDrained() {
    if (this.drained) {
      return;
    }
    const generationId = this.buffer.generationId;
    this.buffer.cancel(generationId);
    this.drained = true;
    this.port.postMessage({ type: "playout.drained", generationId });
  }

  failClosed(reasonCode) {
    const generationId = this.buffer.generationId;
    this.buffer.rebuffer();
    this.remoteRequested = false;
    this.readySent = false;
    this.port.postMessage({
      type: "playout.fallback",
      generationId,
      reasonCode,
    });
  }

  renderNative(inputChannels, output, quantumStartFrame) {
    for (let index = 0; index < output.length; index += 1) {
      let sample = 0;
      let channelCount = 0;
      for (const channel of inputChannels) {
        if (channel instanceof Float32Array) {
          sample += channel[index] ?? 0;
          channelCount += 1;
        }
      }
      this.nativeRing[(quantumStartFrame + index) % NATIVE_RING_SAMPLES] =
        channelCount === 0 ? 0 : sample / channelCount;
    }
    const outputSourceFrame = quantumStartFrame - NATIVE_DELAY_SAMPLES;
    output.fill(0);
    if (outputSourceFrame < 0) {
      return outputSourceFrame;
    }
    for (let index = 0; index < output.length; index += 1) {
      output[index] =
        this.nativeRing[(outputSourceFrame + index) % NATIVE_RING_SAMPLES];
    }
    return outputSourceFrame;
  }

  process(inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!(output instanceof Float32Array)) {
      return true;
    }
    const inputChannels = inputs[0] ?? [];
    const quantumStartFrame = globalThis.currentFrame;
    const outputSourceFrame = this.renderNative(
      inputChannels,
      output,
      quantumStartFrame,
    );
    if (outputSourceFrame < 0) {
      return true;
    }
    if (
      this.lastReportedSourceFrame === null ||
      outputSourceFrame - this.lastReportedSourceFrame >= FRAME_SAMPLES
    ) {
      this.lastReportedSourceFrame = outputSourceFrame;
      this.port.postMessage({
        type: "playout.playhead",
        generationId: this.buffer.generationId,
        sourceFrame: outputSourceFrame,
      });
    }
    const previousDepth = this.buffer.snapshot().depth;
    const ready = this.ending
      ? this.buffer.hasAvailableFrom(outputSourceFrame)
      : this.buffer.hasTargetFrom(outputSourceFrame);
    if (!this.remoteRequested && !this.readySent && ready) {
      this.readySent = true;
      this.port.postMessage({
        type: "playout.ready",
        generationId: this.buffer.generationId,
        sourceFrame: outputSourceFrame,
      });
    }
    if (this.remoteScratch.length !== output.length) {
      this.remoteScratch = new Float32Array(output.length);
    }
    const remote = this.remoteScratch;
    const result = this.remoteRequested
      ? this.buffer.renderAligned(remote, outputSourceFrame)
      : { aligned: false, underflow: false, rendered: 0 };
    if (
      result.aligned &&
      !result.underflow &&
      result.rendered === output.length
    ) {
      output.set(remote);
    }
    const depth = this.buffer.snapshot().depth;
    if (depth !== previousDepth) {
      this.port.postMessage({
        type: "playout.depth",
        generationId: this.buffer.generationId,
        acknowledged: false,
        depth,
      });
    }
    if (this.ending && (result.underflow || depth === 0)) {
      this.markDrained();
    } else if (this.remoteRequested && (result.underflow || !result.aligned)) {
      // Never splice a remote prefix into a native quantum. Drop the stale
      // jitter window and make a fresh 80 ms readiness decision before remote
      // playout can be selected again.
      this.failClosed("QUEUE_OVERFLOW");
    }
    return true;
  }
}

registerProcessor("liveconv-capture", LiveconvCaptureProcessor);
registerProcessor("liveconv-playout", LiveconvPlayoutProcessor);
