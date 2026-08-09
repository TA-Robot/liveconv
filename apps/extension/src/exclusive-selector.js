function requireRoute(routes, name) {
  const route = routes?.[name];
  if (route === null || typeof route !== "object") {
    throw new TypeError(`${name} route must be an object`);
  }
  if (typeof route.setAudible !== "function") {
    throw new TypeError(`${name}.setAudible must be a function`);
  }
  return route;
}

export function createExclusiveSelector(routes) {
  const native = requireRoute(routes, "native");
  const remote = requireRoute(routes, "remote");
  let selected = "native";

  // Establish a known-safe state even when the route objects retain old state.
  remote.setAudible(false);
  native.setAudible(true);

  function select(route) {
    if (route !== "native" && route !== "remote") {
      throw new TypeError(`unsupported route: ${String(route)}`);
    }
    if (route === selected) {
      return false;
    }

    if (route === "remote") {
      native.setAudible(false);
      remote.setAudible(true);
    } else {
      remote.setAudible(false);
      native.setAudible(true);
    }
    selected = route;
    return true;
  }

  function fallback() {
    return select("native");
  }

  function snapshot() {
    return Object.freeze({
      route: selected,
      nativeAudible: selected === "native",
      remoteAudible: selected === "remote",
    });
  }

  return Object.freeze({ fallback, select, snapshot });
}
