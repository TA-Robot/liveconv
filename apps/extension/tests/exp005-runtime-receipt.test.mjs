import assert from "node:assert/strict";
import test from "node:test";

import { createExp005RuntimeReceiptRecorder } from "../src/exp005-runtime-receipt.js";

const HASH = (character) => `sha256:${character.repeat(64)}`;
const RECEIPT_ID = "10000000-0000-4000-8000-000000000001";
const SESSION_ID = "20000000-0000-4000-8000-000000000001";
const PIPELINES = Object.freeze([
  "30000000-0000-4000-8000-000000000001",
  "30000000-0000-4000-8000-000000000002",
  "30000000-0000-4000-8000-000000000003",
  "30000000-0000-4000-8000-000000000004",
]);
const ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop";

const entries = Object.freeze([
  {
    model_id: "rvc-v2",
    profile_id: "vc.rvc.synthetic-ja.v1",
    profile_hash: HASH("a"),
    configuration_hash: HASH("1"),
    route_mode: "live",
  },
  {
    model_id: "beatrice-2",
    profile_id: "vc.beatrice.synthetic-ja.v1",
    profile_hash: HASH("b"),
    configuration_hash: HASH("2"),
    route_mode: "live",
  },
  {
    model_id: "x-vc",
    profile_id: "vc.x-vc.synthetic-ja.v1",
    profile_hash: HASH("c"),
    configuration_hash: HASH("3"),
    route_mode: "live",
  },
  {
    model_id: "openvoice-v2",
    profile_id: "vc.openvoice-v2.synthetic-ja.v1",
    profile_hash: HASH("d"),
    configuration_hash: HASH("4"),
    route_mode: "buffered_preview_after_end",
  },
]);

const preflight = Object.freeze({
  schema_version: 1,
  check: "liveconv-ms2-ssh-preflight",
  status: "pass",
  client: {
    host_key_pinned: true,
    strict_host_key_checking: true,
    local_forward: {
      listen_host: "127.0.0.1",
      listen_port: 9765,
      target_host: "127.0.0.1",
      target_port: 8765,
    },
  },
  server: { forwarding_only: true, permitopen_loopback: true },
  gateway: {
    loopback_bound: true,
    bearer_auth_required: true,
    exact_extension_origin: true,
    one_use_ticket: true,
    max_sessions: 1,
  },
});

function createRecorder() {
  return createExp005RuntimeReceiptRecorder({ receiptIdFactory: () => RECEIPT_ID });
}

function begin(recorder, overrides = {}) {
  return recorder.begin({
    roster_revision: HASH("e"),
    plan_revision: HASH("f"),
    roster_entries: entries,
    ssh_preflight: preflight,
    ...overrides,
  });
}

function attach(recorder) {
  assert.equal(
    recorder.observeCaptureStarted({
      tabUrl: "https://chatgpt.com/c/example",
      tabAudible: true,
      userGesture: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeGatewayBoundary({
      protocol_version: 1,
      transport_scope: "loopback",
      max_sessions: 1,
      ticket_one_use: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeGatewaySession({
      gatewayUrl: "http://127.0.0.1:9765",
      sessionId: SESSION_ID,
      ticket: "opaque-one-use-ticket",
      pipelineId: PIPELINES[0],
      profileId: entries[0].profile_id,
      profileHash: entries[0].profile_hash,
      configurationHash: entries[0].configuration_hash,
    }),
    true,
  );
  assert.equal(
    recorder.observeGatewayAttached({
      sessionId: SESSION_ID,
      pipelineId: PIPELINES[0],
      profileId: entries[0].profile_id,
      profileHash: entries[0].profile_hash,
      configurationHash: entries[0].configuration_hash,
      extensionOrigin: ORIGIN,
    }),
    true,
  );
}

function startAttempt(recorder, index) {
  const entry = entries[index];
  assert.equal(
    recorder.startAttempt({
      generationId: index + 1,
      pipelineId: PIPELINES[index],
      profileId: entry.profile_id,
      profileHash: entry.profile_hash,
      configurationHash: entry.configuration_hash,
    }),
    true,
  );
}

function observeRemoteOutput(recorder, index) {
  assert.equal(
    recorder.observeOutput({
      generationId: index + 1,
      pipelineId: PIPELINES[index],
      finite: true,
      changed: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeRemotePlayout({
      generationId: index + 1,
      pipelineId: PIPELINES[index],
      nativeAudible: false,
      remoteAudible: true,
    }),
    true,
  );
}

test("EXP-005 recorder emits only a complete metadata receipt from observed runtime events", () => {
  const recorder = createRecorder();
  assert.deepEqual(begin(recorder), { receiptId: RECEIPT_ID });
  attach(recorder);

  startAttempt(recorder, 0);
  observeRemoteOutput(recorder, 0);
  assert.equal(
    recorder.observeGenerationTerminal({
      generationId: 1,
      pipelineId: PIPELINES[0],
      endTriggered: false,
    }),
    true,
  );

  startAttempt(recorder, 1);
  observeRemoteOutput(recorder, 1);
  assert.equal(
    recorder.observeGenerationTerminal({
      generationId: 2,
      pipelineId: PIPELINES[1],
      endTriggered: false,
    }),
    true,
  );

  startAttempt(recorder, 2);
  observeRemoteOutput(recorder, 2);
  assert.equal(
    recorder.observeGenerationTerminal({
      generationId: 3,
      pipelineId: PIPELINES[2],
      endTriggered: false,
    }),
    true,
  );

  startAttempt(recorder, 3);
  observeRemoteOutput(recorder, 3);
  assert.equal(
    recorder.observeGenerationTerminal({
      generationId: 4,
      pipelineId: PIPELINES[3],
      endTriggered: true,
    }),
    true,
  );

  assert.equal(
    recorder.startAttempt({
      generationId: 5,
      pipelineId: PIPELINES[3],
      profileId: entries[3].profile_id,
      profileHash: entries[3].profile_hash,
      configurationHash: entries[3].configuration_hash,
    }),
    true,
  );
  assert.equal(recorder.authorizeFailureInjection({ generationId: 5 }), true);
  assert.equal(
    recorder.observeForcedFallback({
      generationId: 5,
      pipelineId: PIPELINES[3],
      injected: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeNativeFallback({
      generationId: 5,
      pipelineId: PIPELINES[3],
      nativeAudible: true,
      remoteAudible: false,
    }),
    true,
  );

  const receipt = recorder.exportReceipt();
  assert.equal(receipt.source, "extension_gateway_runtime");
  assert.equal(receipt.receipt_id, RECEIPT_ID);
  assert.deepEqual(receipt.attempts.map((attempt) => attempt.model_id), [
    "rvc-v2",
    "beatrice-2",
    "x-vc",
    "openvoice-v2",
  ]);
  assert.equal(receipt.attempts[2].finite_output_observed, true);
  assert.equal(receipt.attempts[2].exclusive_playout_observed, true);
  assert.equal(receipt.attempts[3].end_triggered, true);
  assert.deepEqual(receipt.forced_failure_event, {
    event_type: "fallback.required",
    model_id: "openvoice-v2",
    profile_id: entries[3].profile_id,
    profile_hash: entries[3].profile_hash,
    configuration_hash: entries[3].configuration_hash,
    pipeline_id: PIPELINES[3],
    generation_id: 5,
    failure_injected: true,
    fallback_required_observed: true,
  });
  assert.deepEqual(receipt.chatgpt_tab, {
    chatgpt_com_audible_tab_observed: true,
    capture_started_after_user_gesture: true,
  });
  assert.deepEqual(receipt.ssh_loopback, {
    configured_local_forward_reached_gateway: true,
    client_loopback_only: true,
    remote_gateway_loopback_only: true,
    pinned_server_identity_configured: true,
  });
  const serialized = JSON.stringify(receipt);
  assert.equal(/ticket|session_id|gatewayUrl|chatgpt\.com\/c|pcm|samples/i.test(serialized), false);
});

test("EXP-005 recorder restores a bounded checkpoint and rejects spontaneous fallback", () => {
  const recorder = createRecorder();
  begin(recorder);
  attach(recorder);
  for (let index = 0; index < entries.length; index += 1) {
    startAttempt(recorder, index);
    observeRemoteOutput(recorder, index);
    assert.equal(
      recorder.observeGenerationTerminal({
        generationId: index + 1,
        pipelineId: PIPELINES[index],
        endTriggered: index === 3,
      }),
      true,
    );
  }
  assert.equal(
    recorder.startAttempt({
      generationId: 5,
      pipelineId: PIPELINES[3],
      profileId: entries[3].profile_id,
      profileHash: entries[3].profile_hash,
      configurationHash: entries[3].configuration_hash,
    }),
    true,
  );

  const restored = createRecorder();
  restored.restore(recorder.checkpoint());
  assert.equal(restored.authorizeFailureInjection({ generationId: 5 }), true);
  assert.equal(
    restored.observeForcedFallback({
      generationId: 5,
      pipelineId: PIPELINES[3],
      injected: false,
    }),
    false,
  );
  assert.throws(() => restored.exportReceipt(), /invalid or forged/i);

  const corrupt = recorder.checkpoint();
  corrupt.attempts[0].profileHash = HASH("9");
  assert.throws(() => createRecorder().restore(corrupt), /identity is invalid/i);
});

test("EXP-005 recorder rejects forged or incomplete source facts and blocks export", () => {
  const forgedPreflight = structuredClone(preflight);
  forgedPreflight.gateway.max_sessions = 2;
  assert.throws(
    () => begin(createRecorder(), { ssh_preflight: forgedPreflight }),
    /constrained route/i,
  );

  const recorder = createRecorder();
  begin(recorder);
  assert.equal(
    recorder.observeCaptureStarted({
      tabUrl: "https://chatgpt.com.evil.example/",
      tabAudible: true,
      userGesture: true,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);

  recorder.clear();
  begin(recorder);
  assert.equal(
    recorder.observeCaptureStarted({
      tabUrl: "https://chatgpt.com/c/example",
      tabAudible: true,
      userGesture: false,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);

  recorder.clear();
  begin(recorder);
  assert.equal(
    recorder.observeCaptureStarted({
      tabUrl: "https://chatgpt.com/c/example",
      tabAudible: false,
      userGesture: true,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);

  recorder.clear();
  begin(recorder);
  assert.equal(
    recorder.observeCaptureStarted({
      tabUrl: "https://chatgpt.com/c/example",
      tabAudible: true,
      userGesture: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeGatewayBoundary({
      protocol_version: 1,
      transport_scope: "loopback",
      max_sessions: 1,
      ticket_one_use: true,
    }),
    true,
  );
  assert.equal(
    recorder.observeGatewaySession({
      gatewayUrl: "http://127.0.0.1:9766",
      sessionId: SESSION_ID,
      ticket: "opaque-one-use-ticket",
      pipelineId: PIPELINES[0],
      profileId: entries[0].profile_id,
      profileHash: entries[0].profile_hash,
      configurationHash: entries[0].configuration_hash,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);

  recorder.clear();
  begin(recorder);
  attach(recorder);
  assert.equal(
    recorder.observeGatewayBoundary({
      protocol_version: 1,
      transport_scope: "network",
      max_sessions: 1,
      ticket_one_use: true,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);
});

test("EXP-005 recorder keeps terminal ordering, stale output, End mode, and reset fail-closed", () => {
  const recorder = createRecorder();
  begin(recorder);
  attach(recorder);
  startAttempt(recorder, 0);

  assert.equal(
    recorder.startAttempt({
      generationId: 2,
      pipelineId: PIPELINES[1],
      profileId: entries[1].profile_id,
      profileHash: entries[1].profile_hash,
      configurationHash: entries[1].configuration_hash,
    }),
    false,
  );
  assert.equal(
    recorder.observeStaleOutputAccepted({
      generationId: 1,
      pipelineId: PIPELINES[0],
      accepted: true,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);

  recorder.clear();
  assert.equal(recorder.active(), false);
  begin(recorder);
  attach(recorder);
  startAttempt(recorder, 0);
  observeRemoteOutput(recorder, 0);
  assert.equal(
    recorder.observeGenerationTerminal({
      generationId: 1,
      pipelineId: PIPELINES[0],
      endTriggered: true,
    }),
    false,
  );
  assert.throws(() => recorder.exportReceipt(), /invalid or forged/i);
});
