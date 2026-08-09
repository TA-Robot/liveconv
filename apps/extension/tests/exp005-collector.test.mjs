import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildTrialBeginMessage,
  parseCollectorArguments,
  runCollector,
  sendPopupMessage,
  validateRuntimeReceipt,
} from "../scripts/collect-exp005-receipt.mjs";

const EXTENSION_ID = "abcdefghijklmnopabcdefghijklmnop";
const HASH = (character) => `sha256:${character.repeat(64)}`;
const RECEIPT_ID = "10000000-0000-4000-8000-000000000001";

const trial = Object.freeze({
  roster_revision: HASH("a"),
  plan_revision: HASH("b"),
  roster_entries: [
    {
      model_id: "rvc-v2",
      profile_id: "vc.rvc.synthetic-ja.v1",
      profile_hash: HASH("c"),
      configuration_hash: HASH("1"),
      route_mode: "live",
    },
    {
      model_id: "beatrice-2",
      profile_id: "vc.beatrice.synthetic-ja.v1",
      profile_hash: HASH("d"),
      configuration_hash: HASH("2"),
      route_mode: "live",
    },
    {
      model_id: "x-vc",
      profile_id: "vc.x-vc.synthetic-ja.v1",
      profile_hash: HASH("e"),
      configuration_hash: HASH("3"),
      route_mode: "live",
    },
    {
      model_id: "openvoice-v2",
      profile_id: "vc.openvoice-v2.synthetic-ja.v1",
      profile_hash: HASH("f"),
      configuration_hash: HASH("4"),
      route_mode: "buffered_preview_after_end",
    },
  ],
});

const preflight = Object.freeze({ status: "pass" });

function receipt() {
  const attempts = trial.roster_entries.map((entry, index) => ({
    model_id: entry.model_id,
    profile_id: entry.profile_id,
    profile_hash: entry.profile_hash,
    configuration_hash: entry.configuration_hash,
    route_mode: entry.route_mode,
    pipeline_id: `20000000-0000-4000-8000-00000000000${index + 1}`,
    generation_id: index + 1,
    finite_output_observed: index !== 2,
    changed_output_observed: index !== 2,
    stale_output_accepted: false,
    exclusive_playout_observed: true,
    end_triggered: index === 3,
  }));
  return {
    schema_version: 1,
    source: "extension_gateway_runtime",
    receipt_id: RECEIPT_ID,
    roster_revision: trial.roster_revision,
    plan_revision: trial.plan_revision,
    chatgpt_tab: {
      chatgpt_com_audible_tab_observed: true,
      capture_started_after_user_gesture: true,
    },
    ssh_loopback: {
      configured_local_forward_reached_gateway: true,
      client_loopback_only: true,
      remote_gateway_loopback_only: true,
      pinned_server_identity_configured: true,
    },
    gateway_authentication: {
      gateway_session_authenticated: true,
      single_use_session_grant_authenticated: true,
      exact_extension_origin_verified: true,
      max_sessions: 1,
    },
    attempts,
    forced_failure_event: {
      event_type: "fallback.required",
      model_id: attempts[3].model_id,
      profile_id: attempts[3].profile_id,
      profile_hash: attempts[3].profile_hash,
      configuration_hash: attempts[3].configuration_hash,
      pipeline_id: attempts[3].pipeline_id,
      generation_id: 5,
      failure_injected: true,
      fallback_required_observed: true,
    },
    native_fallback_event: {
      event_type: "extension.native_fallback_activated",
      model_id: attempts[3].model_id,
      profile_id: attempts[3].profile_id,
      profile_hash: attempts[3].profile_hash,
      configuration_hash: attempts[3].configuration_hash,
      pipeline_id: attempts[3].pipeline_id,
      generation_id: 5,
      native_route_active: true,
      remote_route_active: false,
    },
  };
}

class FakeWebSocket {
  constructor() {
    this.listeners = new Map();
    queueMicrotask(() => this.emit("open", {}));
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  close() {}

  send(value) {
    const request = JSON.parse(value);
    const message = JSON.parse(
      /sendMessage\((.*?)\)\.then/u.exec(request.params.expression)[1],
    );
    const response = message.type === "exp005.trial.export"
      ? { ok: true, receipt: receipt() }
      : { ok: true, receipt: { receiptId: RECEIPT_ID } };
    queueMicrotask(() => this.emit("message", {
      data: JSON.stringify({
        id: request.id,
        result: { result: { type: "string", value: JSON.stringify(response) } },
      }),
    }));
  }

  emit(type, value) {
    this.listeners.get(type)?.(value);
  }
}

const fakeFetch = async () => ({
  ok: true,
  async json() {
    return [{
      url: `chrome-extension://${EXTENSION_ID}/popup/popup.html`,
      webSocketDebuggerUrl: "ws://127.0.0.1:9337/devtools/page/popup",
    }];
  },
});

test("collector accepts only loopback CDP commands and creates the explicit popup begin payload", () => {
  assert.deepEqual(
    parseCollectorArguments([
      "begin",
      "--cdp-url",
      "http://127.0.0.1:9337",
      "--extension-id",
      EXTENSION_ID,
      "--trial",
      "/secure/trial.json",
      "--ssh-preflight",
      "/secure/preflight.json",
    ]),
    {
      command: "begin",
      cdpUrl: "http://127.0.0.1:9337",
      extensionId: EXTENSION_ID,
      trialPath: "/secure/trial.json",
      sshPreflightPath: "/secure/preflight.json",
    },
  );
  assert.throws(
    () => parseCollectorArguments(["clear", "--cdp-url", "http://localhost:9337", "--extension-id", EXTENSION_ID]),
    /IPv4-loopback/i,
  );
  assert.deepEqual(
    parseCollectorArguments([
      "inject-failure",
      "--cdp-url",
      "http://127.0.0.1:9337",
      "--extension-id",
      EXTENSION_ID,
    ]),
    {
      command: "inject-failure",
      cdpUrl: "http://127.0.0.1:9337",
      extensionId: EXTENSION_ID,
    },
  );
  assert.deepEqual(buildTrialBeginMessage(trial, preflight), {
    type: "exp005.trial.begin",
    trial: { ...trial, ssh_preflight: preflight },
  });
});

test("collector uses the open popup CDP target and only accepts a safe runtime receipt", async () => {
  const response = await sendPopupMessage({
    cdpUrl: "http://127.0.0.1:9337",
    extensionId: EXTENSION_ID,
    message: { type: "exp005.trial.export" },
    fetchFn: fakeFetch,
    WebSocketClass: FakeWebSocket,
  });
  assert.equal(response.ok, true);
  assert.equal(validateRuntimeReceipt(response.receipt).receipt_id, RECEIPT_ID);
  const unsafe = receipt();
  unsafe.gateway_authentication.ticket = "forbidden";
  assert.throws(
    () => validateRuntimeReceipt(unsafe),
    /unsupported fields|unsafe field/i,
  );

  const unsupportedMachineClaim = receipt();
  delete unsupportedMachineClaim.ssh_loopback.pinned_server_identity_configured;
  unsupportedMachineClaim.ssh_loopback.pinned_server_identity_verified = true;
  assert.throws(
    () => validateRuntimeReceipt(unsupportedMachineClaim),
    /unsupported fields/i,
  );
});

test("collector writes only producer output to a new external receipt path", async () => {
  const directory = await mkdtemp(join(tmpdir(), "liveconv-exp005-"));
  const trialPath = join(directory, "trial.json");
  const preflightPath = join(directory, "preflight.json");
  const outputPath = join(directory, "receipt.json");
  await writeFile(trialPath, JSON.stringify(trial));
  await writeFile(preflightPath, JSON.stringify(preflight));
  const result = await runCollector([
    "export",
    "--cdp-url",
    "http://127.0.0.1:9337",
    "--extension-id",
    EXTENSION_ID,
    "--output",
    outputPath,
  ], { fetchFn: fakeFetch, WebSocketClass: FakeWebSocket });
  assert.deepEqual(result, { receiptId: RECEIPT_ID });
  assert.equal(JSON.parse(await readFile(outputPath, "utf8")).receipt_id, RECEIPT_ID);
});

test("collector sends the popup-only explicit failure injection command", async () => {
  const result = await runCollector([
    "inject-failure",
    "--cdp-url",
    "http://127.0.0.1:9337",
    "--extension-id",
    EXTENSION_ID,
  ], { fetchFn: fakeFetch, WebSocketClass: FakeWebSocket });
  assert.deepEqual(result, { injected: true });
});
