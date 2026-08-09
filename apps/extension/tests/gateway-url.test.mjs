import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL("../src/gateway-url.js", import.meta.url);

test("gateway and WebSocket URLs stay on the explicitly granted origin", async () => {
  const { gatewayPermissionOrigin, normalizeGatewayUrl, websocketUrl } =
    await import(moduleUrl);

  assert.equal(
    normalizeGatewayUrl("https://audio.example.test/"),
    "https://audio.example.test",
  );
  assert.equal(
    gatewayPermissionOrigin("https://audio.example.test"),
    "https://audio.example.test/*",
  );
  assert.equal(
    websocketUrl("https://audio.example.test", "/v1/ws"),
    "wss://audio.example.test/v1/ws",
  );
  assert.equal(
    normalizeGatewayUrl("http://127.0.0.1:8765"),
    "http://127.0.0.1:8765",
  );
  assert.equal(
    gatewayPermissionOrigin("http://127.0.0.1:8765"),
    "http://127.0.0.1/*",
  );
  assert.equal(
    websocketUrl("http://127.0.0.1:8765", "/v1/ws"),
    "ws://127.0.0.1:8765/v1/ws",
  );

  for (const path of [
    "/\\evil.example/ws",
    "/%5cevil.example/ws",
    "//evil.example/ws",
    "https://evil.example/ws",
  ]) {
    assert.throws(
      () => websocketUrl("https://audio.example.test", path),
      /websocket_path|origin/i,
    );
  }
});

test("gateway normalization rejects grant-expanding or header-unsafe forms", async () => {
  const { normalizeGatewayUrl } = await import(moduleUrl);
  for (const url of [
    "http://audio.example.test",
    "https://user@audio.example.test",
    "https://audio.example.test/prefix",
    "https://audio.example.test/?query=1",
  ]) {
    assert.throws(() => normalizeGatewayUrl(url));
  }
});

test("permission replacement removes failed and superseded grants", async () => {
  const { replaceGatewayPermission } = await import(moduleUrl);
  const calls = [];
  const permissions = {
    async contains() {
      return false;
    },
    async request(request) {
      calls.push({ name: "request", request });
      return true;
    },
    async remove(request) {
      calls.push({ name: "remove", request });
      return true;
    },
  };
  const failed = await replaceGatewayPermission({
    permissions,
    nextOrigin: "https://next.example/*",
    previousOrigin: "https://old.example/*",
    commit: async () => {
      calls.push({ name: "commit" });
      return { ok: false };
    },
  });
  assert.equal(failed.response.ok, false);
  assert.deepEqual(calls, [
    { name: "request", request: { origins: ["https://next.example/*"] } },
    { name: "remove", request: { origins: ["https://old.example/*"] } },
    { name: "commit" },
    { name: "request", request: { origins: ["https://old.example/*"] } },
    { name: "remove", request: { origins: ["https://next.example/*"] } },
  ]);

  calls.length = 0;
  const succeeded = await replaceGatewayPermission({
    permissions,
    nextOrigin: "https://next.example/*",
    previousOrigin: "https://old.example/*",
    commit: async () => {
      calls.push({ name: "commit" });
      return { ok: true };
    },
  });
  assert.equal(succeeded.response.ok, true);
  assert.deepEqual(calls, [
    { name: "request", request: { origins: ["https://next.example/*"] } },
    { name: "remove", request: { origins: ["https://old.example/*"] } },
    { name: "commit" },
  ]);
});

for (const [label, removalResult] of [
  ["returns false", false],
  ["rejects", new Error("permission API rejected")],
]) {
  test(`permission replacement rolls back when old grant removal ${label}`, async () => {
    const { replaceGatewayPermission } = await import(moduleUrl);
    const calls = [];
    const permissions = {
      async contains() {
        return false;
      },
      async request(request) {
        calls.push({ name: "request", request });
        return true;
      },
      async remove(request) {
        calls.push({ name: "remove", request });
        if (request.origins[0] === "https://old.example/*") {
          if (removalResult instanceof Error) {
            throw removalResult;
          }
          return removalResult;
        }
        return true;
      },
    };
    let committed = false;

    await assert.rejects(
      replaceGatewayPermission({
        permissions,
        nextOrigin: "https://next.example/*",
        previousOrigin: "https://old.example/*",
        commit: async () => {
          committed = true;
          return { ok: true };
        },
      }),
      label === "returns false" ? /did not remove/ : /permission API rejected/,
    );

    assert.equal(committed, false);
    assert.deepEqual(calls, [
      { name: "request", request: { origins: ["https://next.example/*"] } },
      { name: "remove", request: { origins: ["https://old.example/*"] } },
      { name: "remove", request: { origins: ["https://next.example/*"] } },
    ]);
  });
}
