import assert from "node:assert/strict";
import test from "node:test";

const bufferModuleUrl = new URL("../src/worklet-buffers.js", import.meta.url);
const processorModuleUrl = new URL(
  "../offscreen/worklets/liveconv-audio.js?node-test",
  import.meta.url,
);
const PLAYOUT_DELAY_SAMPLES = 288_000;
const PLAYOUT_DELAY_QUANTA = PLAYOUT_DELAY_SAMPLES / 128;

test("capture assembler emits exact 20 ms frames across 128-sample render quanta", async () => {
  const { CaptureFrameAssembler } = await import(bufferModuleUrl);
  const assembler = new CaptureFrameAssembler(960);
  const frames = [];

  for (let block = 0; block < 8; block += 1) {
    const samples = new Float32Array(128).fill(block + 1);
    frames.push(...assembler.push(samples, block * 128));
  }

  assert.equal(frames.length, 1);
  assert.equal(frames[0].sourceFrame, 0);
  assert.equal(frames[0].samples.length, 960);
  assert.equal(frames[0].samples[0], 1);
  assert.equal(frames[0].samples[127], 1);
  assert.equal(frames[0].samples[128], 2);
  assert.equal(frames[0].samples[959], 8);

  const next = assembler.push(new Float32Array(896).fill(9), 1_024);
  assert.equal(next.length, 1);
  assert.equal(next[0].sourceFrame, 960);
});

test("playout buffer waits for 80 ms, rejects gaps, and invalidates on underflow", async () => {
  const { GenerationPlayoutBuffer } = await import(bufferModuleUrl);
  const buffer = new GenerationPlayoutBuffer({
    frameSamples: 960,
    targetFrames: 4,
    maximumFrames: 10,
  });
  buffer.begin(7);
  for (let sequence = 0; sequence < 4; sequence += 1) {
    const result = buffer.enqueue({
      generationId: 7,
      sequence,
      samples: new Float32Array(960).fill(sequence + 1),
    });
    assert.equal(result.ok, true);
    assert.equal(result.ready, sequence === 3);
  }
  buffer.setAudible(true);
  const output = new Float32Array(128);
  assert.deepEqual(buffer.render(output), { underflow: false, rendered: 128 });
  assert(output.every((sample) => sample === 1));

  const gap = new GenerationPlayoutBuffer();
  gap.begin(8);
  assert.equal(
    gap.enqueue({
      generationId: 8,
      sequence: 1,
      samples: new Float32Array(960),
    }).reasonCode,
    "SEQUENCE_GAP",
  );
  assert.equal(gap.snapshot().accepting, false);

  const short = new GenerationPlayoutBuffer({
    frameSamples: 4,
    targetFrames: 1,
    maximumFrames: 2,
  });
  short.begin(9);
  short.enqueue({ generationId: 9, sequence: 0, samples: new Float32Array(4) });
  short.setAudible(true);
  const shortOutput = new Float32Array(8);
  assert.deepEqual(short.render(shortOutput), {
    underflow: true,
    rendered: 0,
  });
  assert(
    shortOutput.every((sample) => sample === 0),
    "an incomplete remote quantum must not render a partial prefix",
  );
  assert.equal(short.snapshot().accepting, false);
  assert.equal(short.snapshot().depth, 0);
});

test("registered AudioWorklets forward capture, downmix stereo native playout, and silence canceled playout", async () => {
  const registered = new Map();
  class FakePort {
    constructor() {
      this.onmessage = null;
      this.sent = [];
    }

    postMessage(message, transfer = []) {
      this.sent.push({ message, transfer });
    }

    receive(data) {
      this.onmessage?.({ data });
    }
  }
  class FakeAudioWorkletProcessor {
    constructor() {
      this.port = new FakePort();
    }
  }
  globalThis.AudioWorkletProcessor = FakeAudioWorkletProcessor;
  globalThis.registerProcessor = (name, Processor) => {
    registered.set(name, Processor);
  };
  globalThis.currentFrame = 0;
  try {
    await import(processorModuleUrl);
    const CaptureProcessor = registered.get("liveconv-capture");
    const PlayoutProcessor = registered.get("liveconv-playout");
    assert.equal(typeof CaptureProcessor, "function");
    assert.equal(typeof PlayoutProcessor, "function");

    const capture = new CaptureProcessor();
    capture.port.receive({
      type: "capture.begin",
      generationId: 7,
      maximumCredits: 50,
    });
    capture.port.receive({ type: "capture.credit", generationId: 7, frames: 50 });
    assert.equal(capture.credits, 50);
    for (let block = 0; block < 8; block += 1) {
      globalThis.currentFrame = block * 128;
      capture.process([[new Float32Array(128).fill(0.25)]], [[new Float32Array(128)]]);
    }
    assert.equal(capture.port.sent.length, 1);
    assert.equal(capture.port.sent[0].message.type, "capture.frame");
    assert.equal(capture.port.sent[0].message.generationId, 7);
    assert.equal(capture.port.sent[0].message.samples.length, 960);
    assert.equal(capture.port.sent[0].transfer.length, 1);

    const exhaustedCapture = new CaptureProcessor();
    exhaustedCapture.port.receive({ type: "capture.begin", generationId: 8 });
    exhaustedCapture.port.receive({
      type: "capture.credit",
      generationId: 8,
      frames: 4,
    });
    for (let block = 0; block < 40; block += 1) {
      globalThis.currentFrame = 2_000 + block * 128;
      exhaustedCapture.process(
        [[new Float32Array(128).fill(0.25)]],
        [[new Float32Array(128)]],
      );
    }
    assert.equal(
      exhaustedCapture.port.sent.filter(
        (entry) => entry.message.type === "capture.frame",
      ).length,
      4,
    );
    assert.deepEqual(exhaustedCapture.port.sent.at(-1).message, {
      type: "capture.fallback",
      generationId: 8,
      reasonCode: "QUEUE_OVERFLOW",
    });

    const boundedPreviewCapture = new CaptureProcessor();
    boundedPreviewCapture.port.receive({
      type: "capture.begin",
      generationId: 9,
      maximumCredits: 25,
      maximumFrames: 25,
    });
    boundedPreviewCapture.port.receive({
      type: "capture.credit",
      generationId: 9,
      frames: 25,
    });
    for (let block = 0; block < 25 * 8; block += 1) {
      globalThis.currentFrame = 10_000 + block * 128;
      boundedPreviewCapture.process(
        [[new Float32Array(128).fill(0.25)]],
        [[new Float32Array(128)]],
      );
    }
    const previewFrames = boundedPreviewCapture.port.sent.filter(
      (entry) => entry.message.type === "capture.frame",
    );
    assert.equal(previewFrames.length, 25);
    assert.deepEqual(boundedPreviewCapture.port.sent.at(-1).message, {
      type: "capture.complete",
      generationId: 9,
      capturedFrames: 25,
    });
    for (let block = 0; block < 16; block += 1) {
      globalThis.currentFrame = 50_000 + block * 128;
      boundedPreviewCapture.process(
        [[new Float32Array(128).fill(0.25)]],
        [[new Float32Array(128)]],
      );
    }
    assert.equal(
      boundedPreviewCapture.port.sent.filter(
        (entry) => entry.message.type === "capture.frame",
      ).length,
      25,
    );
    assert.equal(
      boundedPreviewCapture.port.sent.some(
        (entry) => entry.message.type === "capture.fallback",
      ),
      false,
    );

    const stereoPlayout = new PlayoutProcessor();
    for (let quantum = 0; quantum < PLAYOUT_DELAY_QUANTA; quantum += 1) {
      globalThis.currentFrame = quantum * 128;
      stereoPlayout.process(
        [[new Float32Array(128), new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    const rightOnlyNative = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES;
    stereoPlayout.process(
      [[new Float32Array(128), new Float32Array(128).fill(1)]],
      [[rightOnlyNative]],
    );
    assert(
      rightOnlyNative.every((sample) => sample === 0.5),
      "native shadow playout must downmix both stereo channels",
    );

    const playout = new PlayoutProcessor();
    playout.port.receive({ type: "playout.begin", generationId: 7 });
    for (let sequence = 0; sequence < 4; sequence += 1) {
      playout.port.receive({
        type: "playout.enqueue",
        generationId: 7,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.5),
      });
    }
    for (let quantum = 0; quantum < PLAYOUT_DELAY_QUANTA; quantum += 1) {
      globalThis.currentFrame = quantum * 128;
      playout.process(
        [[new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES;
    const lastNative = new Float32Array(128);
    playout.process(
      [[new Float32Array(128).fill(1)]],
      [[lastNative]],
    );
    assert.equal(playout.port.sent.at(-1).message.type, "playout.ready");
    assert.equal(playout.port.sent.at(-1).message.sourceFrame, 0);
    assert(lastNative.every((sample) => sample === 1));
    playout.port.receive({ type: "playout.audible", audible: true });
    const audible = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 128;
    playout.process([[new Float32Array(128).fill(1)]], [[audible]]);
    assert(audible.every((sample) => sample === 0.5));

    playout.port.receive({ type: "playout.cancel", generationId: 7 });
    const canceled = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 256;
    playout.process([], [[canceled]]);
    assert(
      canceled.every((sample) => sample === 1),
      "fallback must continue at the native shadow playhead, not replay its prefix",
    );

    const draining = new PlayoutProcessor();
    draining.port.receive({ type: "playout.begin", generationId: 8 });
    for (let sequence = 0; sequence < 4; sequence += 1) {
      draining.port.receive({
        type: "playout.enqueue",
        generationId: 8,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.25),
      });
    }
    for (let quantum = 0; quantum <= PLAYOUT_DELAY_QUANTA; quantum += 1) {
      globalThis.currentFrame = quantum * 128;
      draining.process(
        [[new Float32Array(128)]],
        [[new Float32Array(128)]],
      );
    }
    draining.port.receive({ type: "playout.audible", audible: true });
    draining.port.receive({ type: "playout.end", generationId: 8 });
    for (let quantum = 0; quantum < 30; quantum += 1) {
      globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 128 + quantum * 128;
      draining.process([], [[new Float32Array(128)]]);
    }
    const drainEvents = draining.port.sent.map((entry) => entry.message.type);
    assert(drainEvents.includes("playout.drained"));
    assert.equal(drainEvents.includes("playout.fallback"), false);

    const preAudibleFinal = new PlayoutProcessor();
    preAudibleFinal.port.receive({ type: "playout.begin", generationId: 9 });
    for (let sequence = 0; sequence < 4; sequence += 1) {
      preAudibleFinal.port.receive({
        type: "playout.enqueue",
        generationId: 9,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.75),
      });
    }
    preAudibleFinal.port.receive({ type: "playout.end", generationId: 9 });
    assert.equal(
      preAudibleFinal.port.sent.some(
        (entry) => entry.message.type === "playout.drained",
      ),
      false,
      "End must not cancel queued final PCM before it becomes audible",
    );
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES;
    preAudibleFinal.process(
      [[new Float32Array(128).fill(1)]],
      [[new Float32Array(128)]],
    );
    assert.equal(preAudibleFinal.port.sent.at(-1).message.type, "playout.ready");
    preAudibleFinal.port.receive({ type: "playout.audible", audible: true });
    let renderedRemoteSamples = 0;
    for (let quantum = 1; quantum < 32; quantum += 1) {
      globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + quantum * 128;
      const output = new Float32Array(128);
      preAudibleFinal.process([], [[output]]);
      renderedRemoteSamples += output.filter((sample) => sample === 0.75).length;
    }
    assert(renderedRemoteSamples > 0);
    assert(
      preAudibleFinal.port.sent.some(
        (entry) => entry.message.type === "playout.drained",
      ),
    );

    const partialUnderflow = new PlayoutProcessor();
    partialUnderflow.port.receive({ type: "playout.begin", generationId: 10 });
    for (let sequence = 0; sequence < 5; sequence += 1) {
      partialUnderflow.port.receive({
        type: "playout.enqueue",
        generationId: 10,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.5),
      });
    }
    for (let quantum = 0; quantum < PLAYOUT_DELAY_QUANTA; quantum += 1) {
      globalThis.currentFrame = quantum * 128;
      partialUnderflow.process(
        [[new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES;
    partialUnderflow.process(
      [[new Float32Array(128).fill(1)]],
      [[new Float32Array(128)]],
    );
    partialUnderflow.port.receive({ type: "playout.audible", audible: true });
    for (let quantum = 1; quantum <= 36; quantum += 1) {
      globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + quantum * 128;
      partialUnderflow.process(
        [[new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    const partialOutput = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 37 * 128;
    partialUnderflow.process(
      [[new Float32Array(128).fill(1)]],
      [[partialOutput]],
    );
    assert(
      partialOutput.every((sample) => sample === 1),
      "a partial remote quantum must leave the native quantum intact",
    );
    assert.deepEqual(partialUnderflow.port.sent.at(-1).message, {
      type: "playout.fallback",
      generationId: 10,
      reasonCode: "QUEUE_OVERFLOW",
    });

    const exactBoundary = new PlayoutProcessor();
    exactBoundary.port.receive({ type: "playout.begin", generationId: 11 });
    for (let sequence = 0; sequence < 4; sequence += 1) {
      exactBoundary.port.receive({
        type: "playout.enqueue",
        generationId: 11,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.75),
      });
    }
    for (let quantum = 0; quantum < PLAYOUT_DELAY_QUANTA; quantum += 1) {
      globalThis.currentFrame = quantum * 128;
      exactBoundary.process(
        [[new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES;
    exactBoundary.process(
      [[new Float32Array(128).fill(1)]],
      [[new Float32Array(128)]],
    );
    exactBoundary.port.receive({ type: "playout.audible", audible: true });
    for (let quantum = 1; quantum < 30; quantum += 1) {
      globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + quantum * 128;
      exactBoundary.process(
        [[new Float32Array(128).fill(1)]],
        [[new Float32Array(128)]],
      );
    }
    const exactUnderflowOutput = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 30 * 128;
    exactBoundary.process(
      [[new Float32Array(128).fill(1)]],
      [[exactUnderflowOutput]],
    );
    assert(exactUnderflowOutput.every((sample) => sample === 1));
    assert.deepEqual(exactBoundary.port.sent.at(-1).message, {
      type: "playout.fallback",
      generationId: 11,
      reasonCode: "QUEUE_OVERFLOW",
    });

    exactBoundary.port.receive({
      type: "playout.enqueue",
      generationId: 11,
      sequence: 4,
      sourceFrame: 3_840,
      samples: new Float32Array(960).fill(0.75),
    });
    const beforeFreshReady = exactBoundary.port.sent.filter(
      (entry) => entry.message.type === "playout.ready",
    ).length;
    const insufficientOutput = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 31 * 128;
    exactBoundary.process(
      [[new Float32Array(128).fill(1)]],
      [[insufficientOutput]],
    );
    assert(
      insufficientOutput.every((sample) => sample === 1),
      "one post-underflow frame must not resume remote playout",
    );
    assert.equal(
      exactBoundary.port.sent.filter(
        (entry) => entry.message.type === "playout.ready",
      ).length,
      beforeFreshReady,
    );
    for (let sequence = 5; sequence < 9; sequence += 1) {
      exactBoundary.port.receive({
        type: "playout.enqueue",
        generationId: 11,
        sequence,
        sourceFrame: sequence * 960,
        samples: new Float32Array(960).fill(0.75),
      });
    }
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 32 * 128;
    exactBoundary.process(
      [[new Float32Array(128).fill(1)]],
      [[new Float32Array(128)]],
    );
    assert.equal(
      exactBoundary.port.sent.filter(
        (entry) => entry.message.type === "playout.ready",
      ).length,
      beforeFreshReady + 1,
      "remote playout must receive a fresh 80 ms readiness signal",
    );
    exactBoundary.port.receive({ type: "playout.audible", audible: true });
    const recoveredRemote = new Float32Array(128);
    globalThis.currentFrame = PLAYOUT_DELAY_SAMPLES + 33 * 128;
    exactBoundary.process(
      [[new Float32Array(128).fill(1)]],
      [[recoveredRemote]],
    );
    assert(recoveredRemote.every((sample) => sample === 0.75));
  } finally {
    delete globalThis.AudioWorkletProcessor;
    delete globalThis.registerProcessor;
    delete globalThis.currentFrame;
  }
});
