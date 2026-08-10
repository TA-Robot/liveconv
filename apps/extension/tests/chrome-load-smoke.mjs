import assert from "node:assert/strict";

const endpoint = new URL(process.argv[2] ?? "http://127.0.0.1:9337");

async function readJson(path, options) {
  const response = await fetch(new URL(path, endpoint), options);
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return response.json();
}

const targets = await readJson("/json/list");
const worker = targets.find(
  (target) =>
    target.type === "service_worker" &&
    /^chrome-extension:\/\/[^/]+\/src\/background\.js$/.test(target.url),
);
assert(worker, "GPT Live Voice Converter service worker was not registered");
const extensionId = new URL(worker.url).hostname;
const popupUrl = `chrome-extension://${extensionId}/popup/popup.html`;
const popup = await readJson(`/json/new?${encodeURIComponent(popupUrl)}`, {
  method: "PUT",
});

const socket = new WebSocket(popup.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();
const exceptions = [];
const errorLogs = [];

socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  if (message.method === "Runtime.exceptionThrown") {
    exceptions.push(message.params.exceptionDetails.text);
  } else if (
    message.method === "Log.entryAdded" &&
    ["error", "warning"].includes(message.params.entry.level)
  ) {
    errorLogs.push(message.params.entry.text);
  }
  if (message.id && pending.has(message.id)) {
    const operation = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      operation.reject(new Error(message.error.message));
    } else {
      operation.resolve(message.result);
    }
  }
};

await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});

function command(method, params = {}) {
  const id = nextId;
  nextId += 1;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
  });
}

await command("Runtime.enable");
await command("Log.enable");
await new Promise((resolve) => setTimeout(resolve, 500));
const result = await command("Runtime.evaluate", {
  expression: `({
    readyState: document.readyState,
    status: document.querySelector('[data-role="session-status"]')?.textContent,
    startLabel: document.querySelector('[data-action="start"]')?.getAttribute('aria-label'),
    stopLabel: document.querySelector('[data-action="stop"]')?.getAttribute('aria-label'),
    tokenType: document.querySelector('input[name="token"]')?.type,
    manifestName: chrome.runtime.getManifest().name
  })`,
  returnByValue: true,
  awaitPromise: true,
});
const state = result.result.value;
assert.deepEqual(state, {
  readyState: "complete",
  status: "停止中",
  startLabel: "Start voice conversion",
  stopLabel: "Stop voice conversion",
  tokenType: "password",
  manifestName: "GPT Live Voice Converter",
});
assert.deepEqual(exceptions, []);
assert.deepEqual(errorLogs, []);

socket.close();
const closeResponse = await fetch(new URL(`/json/close/${popup.id}`, endpoint), {
  method: "PUT",
});
assert(closeResponse.ok, "Chrome did not close the popup smoke target");
process.stdout.write(
  `${JSON.stringify({ extensionId, popup: state, exceptions, errorLogs })}\n`,
);
