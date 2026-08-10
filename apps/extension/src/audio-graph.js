import { createExclusiveSelector } from "./exclusive-selector.js";

const SAMPLE_RATE = 48_000;
const MAXIMUM_WORKLET_REMOTE_FRAMES = 10;
// A cold Beatrice worker can return several seconds of catch-up audio in one
// browser task. Stage the full negotiated protocol ceiling while the Worklet
// consumes at real time; the old 25-frame ceiling rejected valid catch-up
// bursts before the Worklet could acknowledge its first ten frames.
const MAXIMUM_STAGED_REMOTE_FRAMES = 500;
const DEFAULT_CAPTURE_CREDIT_FRAMES = 4;
const MAXIMUM_CAPTURE_CREDIT_FRAMES = 500;
const REMOTE_TARGET_FRAMES = 4;

function requireFunction(value, name) {
  if (typeof value !== "function") {
    throw new TypeError(`${name} must be a function`);
  }
  return value;
}

function setGain(node, audible, context) {
  const value = audible ? 1 : 0;
  if (typeof node.gain?.setValueAtTime === "function") {
    node.gain.setValueAtTime(value, context.currentTime);
  } else {
    node.gain.value = value;
  }
}

function stopTracks(stream) {
  for (const track of stream?.getTracks?.() ?? []) {
    track.stop();
  }
}

function createDeferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

export function createAudioGraph(options = {}) {
  const mediaDevices = options.mediaDevices ?? globalThis.navigator?.mediaDevices;
  const AudioContextClass = options.AudioContextClass ?? globalThis.AudioContext;
  const AudioWorkletNodeClass =
    options.AudioWorkletNodeClass ?? globalThis.AudioWorkletNode;
  const workletModuleUrl = options.workletModuleUrl;
  const onCaptureFrame = requireFunction(
    options.onCaptureFrame ?? (() => {}),
    "onCaptureFrame",
  );
  const onFallback = requireFunction(
    options.onFallback ?? (() => {}),
    "onFallback",
  );
  const onRemoteReady = requireFunction(
    options.onRemoteReady ?? (() => {}),
    "onRemoteReady",
  );
  const onSourceEnded = requireFunction(
    options.onSourceEnded ?? (() => {}),
    "onSourceEnded",
  );
  if (typeof mediaDevices?.getUserMedia !== "function") {
    throw new TypeError("mediaDevices.getUserMedia must be a function");
  }
  if (typeof AudioContextClass !== "function") {
    throw new TypeError("AudioContextClass must be a constructor");
  }
  if (typeof AudioWorkletNodeClass !== "function") {
    throw new TypeError("AudioWorkletNodeClass must be a constructor");
  }
  if (typeof workletModuleUrl !== "string" || workletModuleUrl.length === 0) {
    throw new TypeError("workletModuleUrl must be a non-empty string");
  }

  let stream = null;
  let context = null;
  let source = null;
  let captureSink = null;
  let captureNode = null;
  let playoutNode = null;
  let selector = null;
  let activeGenerationId = null;
  let stagedRemoteFrames = [];
  let pendingRemoteFrames = 0;
  let workletRemoteDepth = 0;
  let draining = false;
  let playoutEndPosted = false;
  let drainOperation = null;
  let lastPlayoutSourceFrame = null;
  let previewSequenceBase = null;
  let previewSourceFrameBase = null;
  let capture = "stopped";
  let startEpoch = 0;
  let pendingStart = null;

  function snapshot() {
    return Object.freeze({
      capture,
      route: selector?.snapshot().route ?? "native",
      generationId: activeGenerationId,
    });
  }

  function fallback(event = {}) {
    if (activeGenerationId !== null) {
      playoutNode?.port.postMessage({
        type: "playout.audible",
        audible: false,
      });
    }
    selector?.fallback();
    onFallback({ generationId: activeGenerationId, ...event });
  }

  function postRemoteFrame(frame) {
    pendingRemoteFrames += 1;
    playoutNode.port.postMessage(
      {
        type: "playout.enqueue",
        generationId: activeGenerationId,
        sequence: frame.header.sequence,
        sourceFrame: frame.sourceFrame,
        samples: frame.samples,
      },
      [frame.samples.buffer],
    );
  }

  function maybeEndPlayout() {
    if (
      draining &&
      !playoutEndPosted &&
      stagedRemoteFrames.length === 0 &&
      pendingRemoteFrames === 0 &&
      activeGenerationId !== null
    ) {
      playoutEndPosted = true;
      playoutNode.port.postMessage({
        type: "playout.end",
        generationId: activeGenerationId,
      });
    }
  }

  function pumpRemoteFrames() {
    while (
      stagedRemoteFrames.length > 0 &&
      pendingRemoteFrames + workletRemoteDepth < MAXIMUM_WORKLET_REMOTE_FRAMES
    ) {
      postRemoteFrame(stagedRemoteFrames.shift());
    }
    maybeEndPlayout();
  }

  function handlePlayoutMessage({ data }) {
    if (
      data?.generationId !== activeGenerationId ||
      activeGenerationId === null
    ) {
      return;
    }
    if (data.type === "playout.depth") {
      if (data.acknowledged === true) {
        pendingRemoteFrames = Math.max(0, pendingRemoteFrames - 1);
      }
      if (Number.isInteger(data.depth) && data.depth >= 0) {
        workletRemoteDepth = data.depth;
      }
      pumpRemoteFrames();
    } else if (data.type === "playout.ready") {
      playoutNode.port.postMessage({ type: "playout.audible", audible: true });
      selector.select("remote");
      onRemoteReady({ generationId: activeGenerationId });
    } else if (
      data.type === "playout.playhead" &&
      Number.isSafeInteger(data.sourceFrame) &&
      data.sourceFrame >= 0
    ) {
      lastPlayoutSourceFrame = data.sourceFrame;
    } else if (data.type === "playout.drained" && draining) {
      playoutNode.port.postMessage({ type: "playout.audible", audible: false });
      selector.fallback();
      drainOperation?.resolve();
    } else if (data.type === "playout.fallback") {
      fallback({ reasonCode: data.reasonCode });
    }
  }

  function handleCaptureMessage({ data }) {
    if (
      data?.type === "capture.fallback" &&
      data.generationId === activeGenerationId &&
      activeGenerationId !== null
    ) {
      fallback({ reasonCode: data.reasonCode ?? "QUEUE_OVERFLOW" });
      return;
    }
    if (
      data?.type !== "capture.frame" ||
      data.generationId !== activeGenerationId ||
      !(data.samples instanceof Float32Array)
    ) {
      return;
    }
    const accepted = onCaptureFrame({
      generationId: activeGenerationId,
      sourceFrame: data.sourceFrame,
      samples: data.samples,
    }) !== false;
    if (accepted && data.generationId === activeGenerationId) {
      captureNode.port.postMessage({
        type: "capture.credit",
        generationId: activeGenerationId,
        frames: 1,
      });
    }
  }

  async function disposeResources(resources) {
    if (!resources) {
      return;
    }
    resources.selector?.fallback();
    for (const node of [
      resources.source,
      resources.captureSink,
      resources.captureNode,
      resources.playoutNode,
    ]) {
      try {
        node?.disconnect();
      } catch {
        // Nodes may already be disconnected during partial-start cleanup.
      }
    }
    stopTracks(resources.stream);
    if (resources.context && resources.context.state !== "closed") {
      await resources.context.close();
    }
  }

  async function release() {
    fallback({ reasonCode: "SESSION_STOP" });
    activeGenerationId = null;
    stagedRemoteFrames = [];
    pendingRemoteFrames = 0;
    workletRemoteDepth = 0;
    draining = false;
    playoutEndPosted = false;
    drainOperation?.resolve();
    drainOperation = null;
    lastPlayoutSourceFrame = null;
    previewSequenceBase = null;
    previewSourceFrameBase = null;
    const resources = {
      stream,
      context,
      source,
      captureSink,
      captureNode,
      playoutNode,
      selector,
    };
    stream = null;
    context = null;
    source = null;
    captureSink = null;
    captureNode = null;
    playoutNode = null;
    selector = null;
    await disposeResources(resources);
    capture = "stopped";
  }

  function isCurrentStart(candidate) {
    return pendingStart === candidate && candidate.epoch === startEpoch;
  }

  async function startNativeLoopback({ streamId, tabId } = {}) {
    if (capture === "running") {
      return;
    }
    if (typeof streamId !== "string" || streamId.length === 0) {
      throw new TypeError("streamId must be a non-empty string");
    }
    if (!Number.isInteger(tabId) || tabId < 0) {
      throw new TypeError("tabId must be a non-negative integer");
    }
    const candidate = {
      epoch: startEpoch + 1,
      stream: null,
      context: null,
      source: null,
      captureSink: null,
      captureNode: null,
      playoutNode: null,
      selector: null,
    };
    startEpoch = candidate.epoch;
    pendingStart = candidate;
    capture = "starting";
    try {
      candidate.stream = await mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: "tab",
            chromeMediaSourceId: streamId,
          },
        },
        video: false,
      });
      if (!isCurrentStart(candidate)) {
        await disposeResources(candidate);
        return;
      }
      candidate.context = new AudioContextClass({
        latencyHint: "interactive",
        sampleRate: SAMPLE_RATE,
      });
      if (candidate.context.sampleRate !== SAMPLE_RATE) {
        throw new Error(`AudioContext must run at ${SAMPLE_RATE} Hz`);
      }
      await candidate.context.audioWorklet.addModule(workletModuleUrl);
      if (!isCurrentStart(candidate)) {
        await disposeResources(candidate);
        return;
      }
      candidate.source = candidate.context.createMediaStreamSource(
        candidate.stream,
      );
      candidate.captureSink = candidate.context.createGain();
      candidate.captureNode = new AudioWorkletNodeClass(
        candidate.context,
        "liveconv-capture",
        {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          outputChannelCount: [1],
          channelCount: 1,
          channelCountMode: "explicit",
        },
      );
      candidate.playoutNode = new AudioWorkletNodeClass(
        candidate.context,
        "liveconv-playout",
        {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          outputChannelCount: [1],
        },
      );
      candidate.captureNode.port.onmessage = handleCaptureMessage;
      candidate.playoutNode.port.onmessage = handlePlayoutMessage;

      candidate.selector = createExclusiveSelector({
        native: {
          setAudible(audible) {
            if (audible) {
              candidate.playoutNode.port.postMessage({
                type: "playout.audible",
                audible: false,
              });
            }
          },
        },
        remote: {
          setAudible(audible) {
            candidate.playoutNode.port.postMessage({
              type: "playout.audible",
              audible,
            });
          },
        },
      });
      setGain(candidate.captureSink, false, candidate.context);
      candidate.source
        .connect(candidate.captureNode)
        .connect(candidate.captureSink)
        .connect(candidate.context.destination);
      candidate.source
        .connect(candidate.playoutNode)
        .connect(candidate.context.destination);
      for (const track of candidate.stream.getAudioTracks?.() ?? []) {
        track.addEventListener("ended", onSourceEnded, { once: true });
      }
      await candidate.context.resume();
      if (!isCurrentStart(candidate)) {
        await disposeResources(candidate);
        return;
      }

      stream = candidate.stream;
      context = candidate.context;
      source = candidate.source;
      captureSink = candidate.captureSink;
      captureNode = candidate.captureNode;
      playoutNode = candidate.playoutNode;
      selector = candidate.selector;
      pendingStart = null;
      capture = "running";
    } catch (error) {
      const wasCurrent = isCurrentStart(candidate);
      await disposeResources(candidate);
      if (wasCurrent) {
        pendingStart = null;
        capture = "stopped";
      }
      throw error;
    }
  }

  function beginGeneration(
    generationId,
    {
      captureCreditFrames = DEFAULT_CAPTURE_CREDIT_FRAMES,
      maximumCaptureFrames = null,
    } = {},
  ) {
    if (capture !== "running") {
      throw new Error("audio graph is not running");
    }
    if (!Number.isInteger(generationId) || generationId < 0) {
      throw new TypeError("generationId must be a non-negative integer");
    }
    if (activeGenerationId !== null) {
      throw new Error("an audio generation is already active");
    }
    if (
      !Number.isSafeInteger(captureCreditFrames) ||
      captureCreditFrames <= 0 ||
      captureCreditFrames > MAXIMUM_CAPTURE_CREDIT_FRAMES
    ) {
      throw new TypeError("captureCreditFrames must be between 1 and 500");
    }
    if (
      maximumCaptureFrames !== null &&
      (!Number.isSafeInteger(maximumCaptureFrames) ||
        maximumCaptureFrames <= 0 ||
        maximumCaptureFrames > MAXIMUM_CAPTURE_CREDIT_FRAMES)
    ) {
      throw new TypeError("maximumCaptureFrames must be between 1 and 500");
    }
    activeGenerationId = generationId;
    stagedRemoteFrames = [];
    pendingRemoteFrames = 0;
    workletRemoteDepth = 0;
    draining = false;
    playoutEndPosted = false;
    drainOperation = null;
    lastPlayoutSourceFrame = null;
    previewSequenceBase = null;
    previewSourceFrameBase = null;
    selector.fallback();
    const captureBegin = {
      type: "capture.begin",
      generationId,
      maximumCredits: captureCreditFrames,
      ...(maximumCaptureFrames === null
        ? {}
        : { maximumFrames: maximumCaptureFrames }),
    };
    captureNode.port.postMessage(captureBegin);
    captureNode.port.postMessage({
      type: "capture.credit",
      generationId,
      frames: captureCreditFrames,
    });
    playoutNode.port.postMessage({ type: "playout.begin", generationId });
  }

  function endGeneration(generationId) {
    if (generationId !== activeGenerationId) {
      return false;
    }
    captureNode.port.postMessage({ type: "capture.cancel", generationId });
    return true;
  }

  function drainGeneration(generationId) {
    if (generationId !== activeGenerationId) {
      return Promise.reject(new Error("generation is not active"));
    }
    if (drainOperation) {
      return drainOperation.promise;
    }
    draining = true;
    playoutEndPosted = false;
    drainOperation = createDeferred();
    pumpRemoteFrames();
    return drainOperation.promise;
  }

  function completeGeneration(generationId) {
    if (generationId !== activeGenerationId) {
      return false;
    }
    playoutNode.port.postMessage({ type: "playout.cancel", generationId });
    fallback({ reasonCode: "GENERATION_COMPLETE" });
    activeGenerationId = null;
    stagedRemoteFrames = [];
    pendingRemoteFrames = 0;
    workletRemoteDepth = 0;
    draining = false;
    playoutEndPosted = false;
    drainOperation?.resolve();
    drainOperation = null;
    lastPlayoutSourceFrame = null;
    previewSequenceBase = null;
    previewSourceFrameBase = null;
    return true;
  }

  function cancelGeneration(generationId, reasonCode = "GENERATION_CANCELED") {
    if (generationId !== activeGenerationId) {
      return false;
    }
    captureNode.port.postMessage({ type: "capture.cancel", generationId });
    playoutNode.port.postMessage({ type: "playout.cancel", generationId });
    fallback({ reasonCode });
    activeGenerationId = null;
    stagedRemoteFrames = [];
    pendingRemoteFrames = 0;
    workletRemoteDepth = 0;
    draining = false;
    playoutEndPosted = false;
    drainOperation?.resolve();
    drainOperation = null;
    lastPlayoutSourceFrame = null;
    previewSequenceBase = null;
    previewSourceFrameBase = null;
    return true;
  }

  function enqueueRemoteFrame(frame) {
    if (
      activeGenerationId === null ||
      frame?.header?.generation_id !== activeGenerationId ||
      !(frame.samples instanceof Float32Array)
    ) {
      return false;
    }
    if (
      stagedRemoteFrames.length + pendingRemoteFrames + workletRemoteDepth >=
      MAXIMUM_STAGED_REMOTE_FRAMES
    ) {
      fallback({ reasonCode: "QUEUE_OVERFLOW" });
      return false;
    }
    stagedRemoteFrames.push(frame);
    pumpRemoteFrames();
    return true;
  }

  function rebasePreviewFrame(frame) {
    if (
      activeGenerationId === null ||
      frame?.header?.generation_id !== activeGenerationId ||
      !Number.isSafeInteger(frame?.header?.sequence) ||
      !Number.isSafeInteger(frame?.sourceFrame) ||
      frame.sourceFrame < 0
    ) {
      return frame;
    }
    if (
      previewSourceFrameBase === null &&
      lastPlayoutSourceFrame !== null &&
      frame.sourceFrame < lastPlayoutSourceFrame
    ) {
      previewSequenceBase = frame.header.sequence;
      previewSourceFrameBase =
        lastPlayoutSourceFrame + REMOTE_TARGET_FRAMES * 960;
    }
    if (previewSourceFrameBase === null) {
      return frame;
    }
    return {
      ...frame,
      sourceFrame:
        previewSourceFrameBase +
        (frame.header.sequence - previewSequenceBase) * 960,
    };
  }

  async function stop() {
    if (capture === "stopped" && pendingStart === null) {
      return;
    }
    startEpoch += 1;
    const candidate = pendingStart;
    pendingStart = null;
    capture = "stopping";
    await Promise.all([disposeResources(candidate), release()]);
  }

  return Object.freeze({
    beginGeneration,
    cancelGeneration,
    completeGeneration,
    drainGeneration,
    endGeneration,
    enqueueRemoteFrame,
    fallback,
    rebasePreviewFrame,
    snapshot,
    startNativeLoopback,
    stop,
  });
}
