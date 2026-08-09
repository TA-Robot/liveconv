function requireMethod(value, owner, method) {
  if (value === null || typeof value !== "object") {
    throw new TypeError(`${owner} dependency must be an object`);
  }
  if (typeof value[method] !== "function") {
    throw new TypeError(`${owner}.${method} dependency must be a function`);
  }
}

export function createSessionController(dependencies) {
  if (dependencies === null || typeof dependencies !== "object") {
    throw new TypeError("dependencies must be an object");
  }
  requireMethod(dependencies.capture, "capture", "start");
  requireMethod(dependencies.capture, "capture", "stop");

  let capture = "stopped";
  let requestedCapture = "stopped";
  let transition = Promise.resolve();
  let requestedTransition = transition;

  function snapshot() {
    return Object.freeze({ capture, route: "native" });
  }

  function start() {
    if (requestedCapture === "running") {
      return requestedTransition;
    }
    requestedCapture = "running";
    const run = async () => {
      if (capture === "running") {
        return;
      }
      capture = "starting";
      try {
        await dependencies.capture.start();
        capture = "running";
      } catch (error) {
        capture = "stopped";
        if (requestedCapture === "running") {
          requestedCapture = "stopped";
          requestedTransition = Promise.resolve();
        }
        throw error;
      }
    };
    const operation = transition.then(run, run);
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  function stop() {
    if (requestedCapture === "stopped") {
      return requestedTransition;
    }
    requestedCapture = "stopped";
    const run = async () => {
      if (capture === "stopped") {
        return;
      }
      capture = "stopping";
      try {
        await dependencies.capture.stop();
        capture = "stopped";
      } catch (error) {
        capture = "running";
        if (requestedCapture === "stopped") {
          requestedCapture = "running";
          requestedTransition = Promise.resolve();
        }
        throw error;
      }
    };
    const operation = transition.then(run, run);
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  return Object.freeze({ snapshot, start, stop });
}
