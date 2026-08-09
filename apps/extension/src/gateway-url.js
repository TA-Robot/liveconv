export function normalizeGatewayUrl(value) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new TypeError("gatewayUrl must be a non-empty URL");
  }
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new TypeError("gatewayUrl must be an absolute URL");
  }
  const loopback = url.hostname === "127.0.0.1" || url.hostname === "localhost";
  if (url.protocol !== "https:" && !(loopback && url.protocol === "http:")) {
    throw new TypeError("gatewayUrl must use HTTPS outside loopback");
  }
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (url.pathname !== "/" && url.pathname !== "")
  ) {
    throw new TypeError(
      "gatewayUrl cannot contain credentials, path, query, or fragment",
    );
  }
  return url.origin;
}

export function gatewayPermissionOrigin(value) {
  const url = new URL(normalizeGatewayUrl(value));
  return `${url.protocol}//${url.hostname}/*`;
}

export function websocketUrl(gatewayValue, path) {
  const gatewayUrl = normalizeGatewayUrl(gatewayValue);
  if (
    typeof path !== "string" ||
    path.length === 0 ||
    path.length > 2_048 ||
    !path.startsWith("/") ||
    path.startsWith("//") ||
    /[\\\u0000-\u001f\u007f]/u.test(path) ||
    /%5c/iu.test(path)
  ) {
    throw new Error("gateway returned an invalid websocket_path");
  }
  const url = new URL(path, gatewayUrl);
  if (url.origin !== gatewayUrl || url.username || url.password) {
    throw new Error("gateway websocket_path escaped the configured origin");
  }
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

async function requirePermissionRemoval(permissions, request, operation) {
  const removed = await permissions.remove(request);
  if (removed !== true) {
    throw new Error(`${operation} did not remove the permission`);
  }
}

async function rollbackPermissionChanges({
  permissions,
  nextRequest,
  newlyGranted,
  previousRequest,
  previousRemoved,
}) {
  const failures = [];
  if (previousRemoved) {
    try {
      if ((await permissions.request(previousRequest)) !== true) {
        throw new Error("permission rollback did not restore the previous grant");
      }
    } catch (error) {
      failures.push(error);
    }
  }
  if (newlyGranted) {
    try {
      await requirePermissionRemoval(
        permissions,
        nextRequest,
        "permission rollback",
      );
    } catch (error) {
      failures.push(error);
    }
  }
  if (failures.length > 0) {
    throw new Error("permission rollback failed", { cause: failures[0] });
  }
}

export async function replaceGatewayPermission({
  permissions,
  nextOrigin,
  previousOrigin = null,
  commit,
}) {
  for (const method of ["contains", "request", "remove"]) {
    if (typeof permissions?.[method] !== "function") {
      throw new TypeError(`permissions.${method} must be a function`);
    }
  }
  if (typeof commit !== "function") {
    throw new TypeError("commit must be a function");
  }
  const nextRequest = { origins: [nextOrigin] };
  const alreadyGranted = await permissions.contains(nextRequest);
  const granted = alreadyGranted || await permissions.request(nextRequest);
  if (!granted) {
    return Object.freeze({ granted: false, response: null });
  }
  const newlyGranted = !alreadyGranted;
  const previousRequest =
    previousOrigin && previousOrigin !== nextOrigin
      ? { origins: [previousOrigin] }
      : null;
  let previousRemoved = false;
  let response;
  try {
    if (previousRequest) {
      await requirePermissionRemoval(
        permissions,
        previousRequest,
        "previous gateway cleanup",
      );
      previousRemoved = true;
    }
    response = await commit();
  } catch (error) {
    await rollbackPermissionChanges({
      permissions,
      nextRequest,
      newlyGranted,
      previousRequest,
      previousRemoved,
    });
    throw error;
  }
  if (!response?.ok) {
    await rollbackPermissionChanges({
      permissions,
      nextRequest,
      newlyGranted,
      previousRequest,
      previousRemoved,
    });
    return Object.freeze({ granted: true, response });
  }
  return Object.freeze({ granted: true, response });
}
