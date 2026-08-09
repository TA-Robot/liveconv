import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, relative, resolve, sep } from "node:path";

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH = /^sha256:[0-9a-f]{64}$/;
const EXTENSION_ID = /^[a-p]{32}$/;
const COMMANDS = new Set(["begin", "inject-failure", "export", "clear"]);
const REPOSITORY_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

function requireObject(value, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${name} must be an object`);
  }
  return value;
}

function requireExactFields(value, fields, name) {
  const object = requireObject(value, name);
  if (
    Object.keys(object).length !== fields.length ||
    Object.keys(object).some((field) => !fields.includes(field))
  ) {
    throw new TypeError(`${name} has unsupported fields`);
  }
  return object;
}

function requireLoopbackCdpUrl(value) {
  if (typeof value !== "string") {
    throw new TypeError("--cdp-url must be a URL");
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError("--cdp-url must be a URL");
  }
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    !url.port ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  ) {
    throw new TypeError("--cdp-url must be an IPv4-loopback DevTools origin");
  }
  return url.href.slice(0, -1);
}

function requireExtensionId(value) {
  if (typeof value !== "string" || !EXTENSION_ID.test(value)) {
    throw new TypeError("--extension-id must be a Chrome extension ID");
  }
  return value;
}

export function parseCollectorArguments(argv) {
  const [command, ...rest] = argv;
  if (!COMMANDS.has(command)) {
    throw new TypeError("command must be begin, inject-failure, export, or clear");
  }
  const values = {};
  for (let index = 0; index < rest.length; index += 2) {
    const flag = rest[index];
    const value = rest[index + 1];
    if (typeof flag !== "string" || !flag.startsWith("--") || value === undefined) {
      throw new TypeError("collector arguments must use --name value pairs");
    }
    const name = flag.slice(2);
    if (Object.hasOwn(values, name)) {
      throw new TypeError(`duplicate collector argument: --${name}`);
    }
    values[name] = value;
  }
  const required = {
    begin: ["cdp-url", "extension-id", "trial", "ssh-preflight"],
    "inject-failure": ["cdp-url", "extension-id"],
    export: ["cdp-url", "extension-id", "output"],
    clear: ["cdp-url", "extension-id"],
  }[command];
  if (
    Object.keys(values).length !== required.length ||
    required.some((name) => !Object.hasOwn(values, name))
  ) {
    throw new TypeError(`unsupported arguments for ${command}`);
  }
  return Object.freeze({
    command,
    cdpUrl: requireLoopbackCdpUrl(values["cdp-url"]),
    extensionId: requireExtensionId(values["extension-id"]),
    ...(values.trial ? { trialPath: values.trial } : {}),
    ...(values["ssh-preflight"]
      ? { sshPreflightPath: values["ssh-preflight"] }
      : {}),
    ...(values.output ? { outputPath: values.output } : {}),
  });
}

export function buildTrialBeginMessage(trial, sshPreflight) {
  const input = requireExactFields(
    trial,
    ["roster_revision", "plan_revision", "roster_entries"],
    "trial",
  );
  if (
    typeof input.roster_revision !== "string" ||
    !HASH.test(input.roster_revision) ||
    typeof input.plan_revision !== "string" ||
    !HASH.test(input.plan_revision) ||
    !Array.isArray(input.roster_entries)
  ) {
    throw new TypeError("trial does not contain frozen EXP-005 revisions");
  }
  return Object.freeze({
    type: "exp005.trial.begin",
    trial: Object.freeze({
      roster_revision: input.roster_revision,
      plan_revision: input.plan_revision,
      roster_entries: input.roster_entries,
      ssh_preflight: requireObject(sshPreflight, "ssh preflight"),
    }),
  });
}

function assertSafeReceiptValue(value, field = "receipt") {
  if (typeof value === "string") {
    if (value.length > 512 || /(?:ticket|token|bearer|pcm|samples|audio|path|host)/i.test(value)) {
      throw new TypeError(`${field} contains unsafe runtime material`);
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const [index, item] of value.entries()) {
      assertSafeReceiptValue(item, `${field}[${index}]`);
    }
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if (/(?:ticket|token|bearer|pcm|samples|audio|path|host)/i.test(key)) {
        throw new TypeError(`${field} has an unsafe field`);
      }
      assertSafeReceiptValue(item, `${field}.${key}`);
    }
  }
}

export function validateRuntimeReceipt(value) {
  const receipt = requireExactFields(
    value,
    [
      "schema_version",
      "source",
      "receipt_id",
      "roster_revision",
      "plan_revision",
      "chatgpt_tab",
      "ssh_loopback",
      "gateway_authentication",
      "attempts",
      "forced_failure_event",
      "native_fallback_event",
    ],
    "runtime receipt",
  );
  if (
    receipt.schema_version !== 1 ||
    receipt.source !== "extension_gateway_runtime" ||
    typeof receipt.receipt_id !== "string" ||
    !UUID.test(receipt.receipt_id) ||
    !HASH.test(receipt.roster_revision) ||
    !HASH.test(receipt.plan_revision) ||
    !Array.isArray(receipt.attempts) ||
    receipt.attempts.length !== 4
  ) {
    throw new TypeError("runtime receipt is not schema-compatible EXP-005 evidence");
  }
  const chatgptTab = requireExactFields(
    receipt.chatgpt_tab,
    ["chatgpt_com_audible_tab_observed", "capture_started_after_user_gesture"],
    "runtime receipt.chatgpt_tab",
  );
  const sshLoopback = requireExactFields(
    receipt.ssh_loopback,
    [
      "configured_local_forward_reached_gateway",
      "client_loopback_only",
      "remote_gateway_loopback_only",
      "pinned_server_identity_configured",
    ],
    "runtime receipt.ssh_loopback",
  );
  const gatewayAuthentication = requireExactFields(
    receipt.gateway_authentication,
    [
      "gateway_session_authenticated",
      "single_use_session_grant_authenticated",
      "exact_extension_origin_verified",
      "max_sessions",
    ],
    "runtime receipt.gateway_authentication",
  );
  if (
    chatgptTab.chatgpt_com_audible_tab_observed !== true ||
    chatgptTab.capture_started_after_user_gesture !== true ||
    sshLoopback.configured_local_forward_reached_gateway !== true ||
    sshLoopback.client_loopback_only !== true ||
    sshLoopback.remote_gateway_loopback_only !== true ||
    sshLoopback.pinned_server_identity_configured !== true ||
    gatewayAuthentication.gateway_session_authenticated !== true ||
    gatewayAuthentication.single_use_session_grant_authenticated !== true ||
    gatewayAuthentication.exact_extension_origin_verified !== true ||
    gatewayAuthentication.max_sessions !== 1
  ) {
    throw new TypeError("runtime receipt does not prove the required machine facts");
  }
  assertSafeReceiptValue(receipt);
  return receipt;
}

function popupTargetUrl(extensionId) {
  return `chrome-extension://${extensionId}/popup/popup.html`;
}

async function cdpTargets(cdpUrl, fetchFn) {
  const response = await fetchFn(`${cdpUrl}/json/list`, { cache: "no-store" });
  if (!response?.ok) {
    throw new Error("Chrome DevTools target discovery failed");
  }
  const value = await response.json();
  if (!Array.isArray(value)) {
    throw new Error("Chrome DevTools target discovery returned invalid JSON");
  }
  return value;
}

function evaluateInPopup(webSocketDebuggerUrl, expression, WebSocketClass) {
  return new Promise((resolvePromise, reject) => {
    const socket = new WebSocketClass(webSocketDebuggerUrl);
    let nextId = 1;
    const timer = setTimeout(() => {
      socket.close();
      reject(new Error("Chrome DevTools evaluation timed out"));
    }, 10_000);
    socket.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("Chrome DevTools connection failed"));
    }, { once: true });
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({
        id: nextId,
        method: "Runtime.evaluate",
        params: { expression, awaitPromise: true, returnByValue: true },
      }));
      nextId += 1;
    }, { once: true });
    socket.addEventListener("message", ({ data }) => {
      let message;
      try {
        message = JSON.parse(String(data));
      } catch {
        return;
      }
      if (message.id !== 1) {
        return;
      }
      clearTimeout(timer);
      socket.close();
      const result = message.result?.result;
      if (message.error || result?.type !== "string") {
        reject(new Error("Chrome DevTools evaluation did not return an Extension response"));
        return;
      }
      try {
        resolvePromise(JSON.parse(result.value));
      } catch {
        reject(new Error("Extension response was not JSON"));
      }
    });
  });
}

export async function sendPopupMessage({
  cdpUrl,
  extensionId,
  message,
  fetchFn = globalThis.fetch,
  WebSocketClass = globalThis.WebSocket,
} = {}) {
  if (typeof fetchFn !== "function" || typeof WebSocketClass !== "function") {
    throw new TypeError("CDP fetch and WebSocket dependencies are required");
  }
  const targets = await cdpTargets(cdpUrl, fetchFn);
  const target = targets.find(
    (candidate) =>
      candidate?.url === popupTargetUrl(extensionId) &&
      typeof candidate.webSocketDebuggerUrl === "string",
  );
  if (!target) {
    throw new Error("open the liveconv Extension popup before running the collector");
  }
  const expression = [
    "chrome.runtime.sendMessage(",
    JSON.stringify(message),
    ").then(",
    "(value) => JSON.stringify(value),",
    "(error) => JSON.stringify({ ok: false, error: String(error) })",
    ")",
  ].join("");
  return evaluateInPopup(target.webSocketDebuggerUrl, expression, WebSocketClass);
}

function assertExternalOutput(path) {
  const destination = resolve(path);
  const relativePath = relative(REPOSITORY_ROOT, destination);
  if (
    relativePath === "" ||
    (relativePath !== ".." && !relativePath.startsWith(`..${sep}`))
  ) {
    throw new TypeError("--output must be outside the liveconv repository");
  }
  return destination;
}

async function loadJson(path, name) {
  let value;
  try {
    value = JSON.parse(await readFile(path, "utf8"));
  } catch {
    throw new Error(`${name} is not readable JSON`);
  }
  return value;
}

export async function runCollector(argv, dependencies = {}) {
  const options = parseCollectorArguments(argv);
  let message;
  if (options.command === "begin") {
    message = buildTrialBeginMessage(
      await loadJson(options.trialPath, "trial"),
      await loadJson(options.sshPreflightPath, "SSH preflight"),
    );
  } else if (options.command === "export") {
    message = { type: "exp005.trial.export" };
  } else if (options.command === "inject-failure") {
    message = { type: "exp005.trial.inject-failure" };
  } else {
    message = { type: "exp005.trial.clear" };
  }
  const response = await sendPopupMessage({
    cdpUrl: options.cdpUrl,
    extensionId: options.extensionId,
    message,
    ...dependencies,
  });
  if (response?.ok !== true) {
    throw new Error("Extension rejected the EXP-005 collector command");
  }
  if (options.command === "export") {
    const receipt = validateRuntimeReceipt(response.receipt);
    await writeFile(
      assertExternalOutput(options.outputPath),
      `${JSON.stringify(receipt)}\n`,
      { encoding: "utf8", flag: "wx", mode: 0o600 },
    );
    return Object.freeze({ receiptId: receipt.receipt_id });
  }
  if (options.command === "begin") {
    return Object.freeze({ receiptId: response.receipt?.receiptId });
  }
  return options.command === "inject-failure"
    ? Object.freeze({ injected: true })
    : Object.freeze({ cleared: true });
}

function isMain() {
  return process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
}

if (isMain()) {
  runCollector(process.argv.slice(2)).then(
    (result) => process.stdout.write(`${JSON.stringify(result)}\n`),
    (error) => {
      process.stderr.write(`liveconv EXP-005 collector: ${error.message}\n`);
      process.exitCode = 1;
    },
  );
}
