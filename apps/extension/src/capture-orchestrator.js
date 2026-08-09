const OFFSCREEN_OPTIONS = Object.freeze({
  url: "offscreen/offscreen.html",
  reasons: Object.freeze(["USER_MEDIA"]),
  justification: "Capture and play the selected tab audio with a native fallback.",
});

function requireMethod(value, owner, method) {
  if (value === null || typeof value !== "object") {
    throw new TypeError(`${owner} dependency must be an object`);
  }
  if (typeof value[method] !== "function") {
    throw new TypeError(`${owner}.${method} dependency must be a function`);
  }
}

export function createCaptureOrchestrator(dependencies) {
  if (dependencies === null || typeof dependencies !== "object") {
    throw new TypeError("dependencies must be an object");
  }
  requireMethod(dependencies.tabCapture, "tabCapture", "getMediaStreamId");
  requireMethod(dependencies.offscreen, "offscreen", "hasDocument");
  requireMethod(dependencies.offscreen, "offscreen", "createDocument");
  requireMethod(dependencies.offscreen, "offscreen", "closeDocument");
  requireMethod(dependencies.audioGraph, "audioGraph", "startNativeLoopback");
  requireMethod(dependencies.audioGraph, "audioGraph", "stop");
  requireMethod(dependencies.remote, "remote", "connect");
  requireMethod(dependencies.remote, "remote", "close");
  requireMethod(dependencies.selector, "selector", "select");

  let capture = "stopped";
  let offscreen = "closed";
  let remote = "disconnected";
  let route = "native";
  let generationId = null;
  let startOperation = null;
  let stopOperation = null;
  let graphActive = false;

  function snapshot() {
    const state = { capture, offscreen, remote, route };
    if (generationId !== null) {
      state.generationId = generationId;
    }
    return Object.freeze(state);
  }

  function selectNative() {
    dependencies.selector.select("native");
    route = "native";
    generationId = null;
  }

  async function releaseResources({ closeRemote = true } = {}) {
    let cleanupError = null;
    try {
      selectNative();
    } catch (error) {
      cleanupError = error;
    }
    if (closeRemote) {
      try {
        await dependencies.remote.close();
      } catch (error) {
        cleanupError ??= error;
      } finally {
        remote = "disconnected";
      }
    }
    if (graphActive) {
      try {
        await dependencies.audioGraph.stop();
      } catch (error) {
        cleanupError ??= error;
      } finally {
        graphActive = false;
      }
    }
    if (offscreen === "open") {
      try {
        await dependencies.offscreen.closeDocument();
      } catch (error) {
        cleanupError ??= error;
      } finally {
        offscreen = "closed";
      }
    }
    if (cleanupError) {
      throw cleanupError;
    }
  }

  function start({ userGesture } = {}) {
    if (userGesture !== true) {
      return Promise.reject(
        new TypeError("capture start requires an explicit user gesture"),
      );
    }
    if (capture === "running") {
      return Promise.resolve();
    }
    if (stopOperation) {
      return stopOperation.then(() => start({ userGesture: true }));
    }
    if (startOperation) {
      return startOperation;
    }

    capture = "starting";
    startOperation = (async () => {
      try {
        if (await dependencies.offscreen.hasDocument()) {
          offscreen = "open";
        } else {
          await dependencies.offscreen.createDocument({
            ...OFFSCREEN_OPTIONS,
            reasons: [...OFFSCREEN_OPTIONS.reasons],
          });
          offscreen = "open";
        }

        const streamId = await dependencies.tabCapture.getMediaStreamId();
        await dependencies.audioGraph.startNativeLoopback({ streamId });
        graphActive = true;
        capture = "running";
        remote = "connecting";
        await dependencies.remote.connect();
        if (remote === "connecting") {
          remote = "pending";
        }
      } catch (error) {
        capture = "stopping";
        try {
          await releaseResources();
        } catch {
          // The original start failure is the actionable error.
        }
        capture = "stopped";
        throw error;
      } finally {
        startOperation = null;
      }
    })();
    return startOperation;
  }

  function remoteReady(readyGenerationId) {
    if (
      !Number.isInteger(readyGenerationId) ||
      readyGenerationId < 0 ||
      readyGenerationId > 0xffff_ffff
    ) {
      throw new TypeError("generationId must be a uint32");
    }
    if (capture !== "running" || remote === "disconnected") {
      return false;
    }
    if (generationId !== null && readyGenerationId < generationId) {
      return false;
    }
    generationId = readyGenerationId;
    remote = "ready";
    dependencies.selector.select("remote");
    route = "remote";
    return true;
  }

  function stop() {
    if (stopOperation) {
      return stopOperation;
    }
    if (capture === "stopped" && !startOperation) {
      return Promise.resolve();
    }

    stopOperation = (async () => {
      try {
        if (startOperation) {
          try {
            await startOperation;
          } catch {
            return;
          }
        }
        capture = "stopping";
        await releaseResources();
        capture = "stopped";
      } catch (error) {
        capture = graphActive ? "running" : "stopped";
        throw error;
      } finally {
        stopOperation = null;
      }
    })();
    return stopOperation;
  }

  return Object.freeze({ remoteReady, snapshot, start, stop });
}
