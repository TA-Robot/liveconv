import {
  CaptureFrameAssembler,
  GenerationPlayoutBuffer,
} from "../../src/worklet-buffers.js";

const FRAME_SAMPLES = 960;
const MAXIMUM_CAPTURE_CREDITS = 4;
const NATIVE_DELAY_SAMPLES = 9_600;
const NATIVE_RING_SAMPLES = 16_384;

class LiveconvCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.assembler = new CaptureFrameAssembler(FRAME_SAMPLES);
    this.generationId = null;
    this.credits = 0;
    this.overflowed = false;
    this.port.onmessage = ({ data }) => {
      if (data?.type === "capture.begin") {
        this.generationId = data.generationId;
        this.credits = 0;
        this.overflowed = false;
        this.assembler.reset();
      } else if (
        data?.type === "capture.credit" &&
        data.generationId === this.generationId &&
        Number.isSafeInteger(data.frames) &&
        data.frames > 0
      ) {
        this.credits = Math.min(
          MAXIMUM_CAPTURE_CREDITS,
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
      this.port.postMessage(
        {
          type: "capture.frame",
          generationId: this.generationId,
          sourceFrame: frame.sourceFrame,
          samples: frame.samples,
        },
        [frame.samples.buffer],
      );
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
    this.nativeRing = new Float32Array(NATIVE_RING_SAMPLES);
    this.remoteScratch = new Float32Array(128);
    this.port.onmessage = ({ data }) => {
      if (data?.type === "playout.begin") {
        this.buffer.begin(data.generationId);
        this.ending = false;
        this.drained = false;
        this.remoteRequested = false;
        this.readySent = false;
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
        if (!this.buffer.snapshot().audible) {
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
    const previousDepth = this.buffer.snapshot().depth;
    if (
      !this.remoteRequested &&
      !this.readySent &&
      this.buffer.hasTargetFrom(outputSourceFrame)
    ) {
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
    if (result.aligned && result.rendered > 0) {
      output.set(remote.subarray(0, result.rendered));
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
    } else if (result.underflow && result.aligned) {
      this.port.postMessage({
        type: "playout.fallback",
        generationId: this.buffer.generationId,
        reasonCode: "QUEUE_OVERFLOW",
      });
    }
    return true;
  }
}

registerProcessor("liveconv-capture", LiveconvCaptureProcessor);
registerProcessor("liveconv-playout", LiveconvPlayoutProcessor);
