const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const HASH = /^sha256:[0-9a-f]{64}$/;
const UINT32_MAX = 0xffff_ffff;
const EXTENSION_ORIGIN = /^chrome-extension:\/\/[a-p]{32}$/;
const CHATGPT_ORIGIN = "https://chatgpt.com";
const MODEL_ORDER = Object.freeze([
  Object.freeze({
    modelId: "rvc-v2",
    routeMode: "live",
    endTriggered: false,
  }),
  Object.freeze({
    modelId: "beatrice-2",
    routeMode: "live",
    endTriggered: false,
  }),
  Object.freeze({
    modelId: "x-vc",
    routeMode: "live",
    endTriggered: false,
  }),
  Object.freeze({
    modelId: "openvoice-v2",
    routeMode: "buffered_preview_after_end",
    endTriggered: true,
  }),
]);

function requireObject(value, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${name} must be an object`);
  }
  return value;
}

function requireExactFields(value, fields, name) {
  const object = requireObject(value, name);
  const expected = new Set(fields);
  if (
    Object.keys(object).length !== expected.size ||
    Object.keys(object).some((field) => !expected.has(field))
  ) {
    throw new TypeError(`${name} has unsupported fields`);
  }
  return object;
}

function requireUuid(value, name) {
  if (typeof value !== "string" || !UUID.test(value)) {
    throw new TypeError(`${name} must be a canonical UUID`);
  }
  return value;
}

function requireHash(value, name) {
  if (typeof value !== "string" || !HASH.test(value)) {
    throw new TypeError(`${name} must be a SHA-256 identity`);
  }
  return value;
}

function requireGenerationId(value, name = "generationId") {
  if (!Number.isSafeInteger(value) || value < 0 || value > UINT32_MAX) {
    throw new TypeError(`${name} must be a uint32`);
  }
  return value;
}

function requireProfileId(value, name = "profileId") {
  if (
    typeof value !== "string" ||
    !/^vc\.[a-z0-9][a-z0-9.-]{0,127}\.v1$/.test(value)
  ) {
    throw new TypeError(`${name} has an invalid format`);
  }
  return value;
}

function requireRevision(value, name) {
  return requireHash(value, name);
}

function requireBoolean(value, name) {
  if (value !== true && value !== false) {
    throw new TypeError(`${name} must be a boolean`);
  }
  return value;
}

function requireLoopbackGatewayUrl(value) {
  if (typeof value !== "string") {
    throw new TypeError("gatewayUrl must be a string");
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError("gatewayUrl must be an absolute loopback URL");
  }
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  ) {
    throw new TypeError("gatewayUrl must be the SSH IPv4 loopback origin");
  }
  const port = url.port === "" ? 80 : Number(url.port);
  if (!Number.isSafeInteger(port) || port < 1 || port > 65_535) {
    throw new TypeError("gatewayUrl must contain a valid loopback port");
  }
  return port;
}

function validatePreflight(value) {
  const preflight = requireExactFields(
    value,
    ["schema_version", "check", "status", "client", "server", "gateway"],
    "sshPreflight",
  );
  if (
    preflight.schema_version !== 1 ||
    preflight.check !== "liveconv-ms2-ssh-preflight" ||
    preflight.status !== "pass"
  ) {
    throw new TypeError("sshPreflight is not an LV-049 pass record");
  }
  const client = requireExactFields(
    preflight.client,
    ["host_key_pinned", "strict_host_key_checking", "local_forward"],
    "sshPreflight.client",
  );
  const localForward = requireExactFields(
    client.local_forward,
    ["listen_host", "listen_port", "target_host", "target_port"],
    "sshPreflight.client.local_forward",
  );
  const server = requireExactFields(
    preflight.server,
    ["forwarding_only", "permitopen_loopback"],
    "sshPreflight.server",
  );
  const gateway = requireExactFields(
    preflight.gateway,
    [
      "loopback_bound",
      "bearer_auth_required",
      "exact_extension_origin",
      "one_use_ticket",
      "max_sessions",
    ],
    "sshPreflight.gateway",
  );
  if (
    client.host_key_pinned !== true ||
    client.strict_host_key_checking !== true ||
    localForward.listen_host !== "127.0.0.1" ||
    localForward.target_host !== "127.0.0.1" ||
    !Number.isSafeInteger(localForward.listen_port) ||
    localForward.listen_port < 1 ||
    localForward.listen_port > 65_535 ||
    !Number.isSafeInteger(localForward.target_port) ||
    localForward.target_port < 1 ||
    localForward.target_port > 65_535 ||
    server.forwarding_only !== true ||
    server.permitopen_loopback !== true ||
    gateway.loopback_bound !== true ||
    gateway.bearer_auth_required !== true ||
    gateway.exact_extension_origin !== true ||
    gateway.one_use_ticket !== true ||
    gateway.max_sessions !== 1
  ) {
    throw new TypeError("sshPreflight does not prove the constrained route");
  }
  return Object.freeze({ listenPort: localForward.listen_port });
}

function validateRosterEntries(value) {
  if (!Array.isArray(value) || value.length !== MODEL_ORDER.length) {
    throw new TypeError("rosterEntries must contain the four frozen models");
  }
  return Object.freeze(
    value.map((candidate, index) => {
      const expected = MODEL_ORDER[index];
      const entry = requireExactFields(
        candidate,
        [
          "model_id",
          "profile_id",
          "profile_hash",
          "configuration_hash",
          "route_mode",
        ],
        `rosterEntries[${index}]`,
      );
      if (
        entry.model_id !== expected.modelId ||
        entry.route_mode !== expected.routeMode
      ) {
        throw new TypeError("rosterEntries are not in the frozen EXP-005 order");
      }
      return Object.freeze({
        modelId: entry.model_id,
        profileId: requireProfileId(entry.profile_id, "roster profile_id"),
        profileHash: requireHash(entry.profile_hash, "roster profile_hash"),
        configurationHash: requireHash(
          entry.configuration_hash,
          "roster configuration_hash",
        ),
        routeMode: entry.route_mode,
        endTriggered: expected.endTriggered,
      });
    }),
  );
}

function publicAttempt(attempt) {
  return Object.freeze({
    model_id: attempt.modelId,
    profile_id: attempt.profileId,
    profile_hash: attempt.profileHash,
    configuration_hash: attempt.configurationHash,
    route_mode: attempt.routeMode,
    pipeline_id: attempt.pipelineId,
    generation_id: attempt.generationId,
    finite_output_observed: attempt.finiteOutputObserved === true,
    changed_output_observed: attempt.changedOutputObserved === true,
    stale_output_accepted: attempt.staleOutputAccepted === true,
    exclusive_playout_observed: attempt.exclusivePlayoutObserved === true,
    end_triggered: attempt.endTriggered === true,
  });
}

function defaultReceiptId() {
  return crypto.randomUUID();
}

/**
 * Produces only the metadata-only runtime receipt defined by EXP-005.  Raw PCM,
 * tickets, tab metadata, and route locations are used transiently for checks and
 * never copied into the exported document.
 */
export function createExp005RuntimeReceiptRecorder(options = {}) {
  const receiptIdFactory = options.receiptIdFactory ?? defaultReceiptId;
  if (typeof receiptIdFactory !== "function") {
    throw new TypeError("receiptIdFactory must be a function");
  }

  let trial = null;

  function requireTrial() {
    if (trial === null) {
      throw new Error("EXP-005 trial has not begun");
    }
    return trial;
  }

  function invalidate(reason) {
    if (trial !== null) {
      trial.invalidReason ??= reason;
    }
  }

  function begin(value) {
    if (trial !== null) {
      throw new Error("EXP-005 trial is already active; clear it first");
    }
    const input = requireExactFields(
      value,
      ["roster_revision", "plan_revision", "roster_entries", "ssh_preflight"],
      "trial.begin",
    );
    const receiptId = requireUuid(receiptIdFactory(), "receiptIdFactory result");
    const rosterRevision = requireRevision(input.roster_revision, "roster_revision");
    const planRevision = requireRevision(input.plan_revision, "plan_revision");
    const entries = validateRosterEntries(input.roster_entries);
    const sshPreflight = validatePreflight(input.ssh_preflight);
    trial = {
      receiptId,
      rosterRevision,
      planRevision,
      entries,
      configuredForwardPort: sshPreflight.listenPort,
      chatgptCapture: false,
      boundary: false,
      gatewaySession: null,
      gatewayAttached: false,
      attempts: [],
      activeAttempt: null,
      failureProbe: null,
      forcedFailure: null,
      nativeFallback: null,
      invalidReason: null,
    };
    return Object.freeze({ receiptId });
  }

  function observeCaptureStarted({ tabUrl, tabAudible, userGesture } = {}) {
    const state = requireTrial();
    if (userGesture !== true) {
      invalidate("capture did not originate from the explicit popup gesture");
      return false;
    }
    try {
      if (new URL(tabUrl).origin !== CHATGPT_ORIGIN) {
        throw new Error("captured tab is not https://chatgpt.com");
      }
    } catch {
      invalidate("captured tab origin could not be asserted as https://chatgpt.com");
      return false;
    }
    if (tabAudible !== true) {
      invalidate("captured ChatGPT tab was not audible at capture start");
      return false;
    }
    state.chatgptCapture = true;
    return true;
  }

  function observeGatewayBoundary(value) {
    const state = requireTrial();
    const boundary = requireExactFields(
      value,
      ["protocol_version", "transport_scope", "max_sessions", "ticket_one_use"],
      "runtime boundary",
    );
    if (
      boundary.protocol_version !== 1 ||
      boundary.transport_scope !== "loopback" ||
      boundary.max_sessions !== 1 ||
      boundary.ticket_one_use !== true
    ) {
      invalidate("Gateway runtime boundary does not prove the MS-2 limits");
      return false;
    }
    state.boundary = true;
    return true;
  }

  function observeGatewaySession({
    gatewayUrl,
    sessionId,
    ticket,
    pipelineId,
    profileId,
    profileHash,
    configurationHash,
  } = {}) {
    const state = requireTrial();
    try {
      const gatewayPort = requireLoopbackGatewayUrl(gatewayUrl);
      if (gatewayPort !== state.configuredForwardPort) {
        throw new TypeError("Gateway session did not use the configured SSH local-forward port");
      }
      requireUuid(sessionId, "sessionId");
      requireUuid(pipelineId, "pipelineId");
      requireProfileId(profileId);
      requireHash(profileHash, "profileHash");
      requireHash(configurationHash, "configurationHash");
      if (
        typeof ticket !== "string" ||
        ticket.length === 0 ||
        new TextEncoder().encode(ticket).byteLength > 4_096
      ) {
        throw new TypeError("ticket must be a non-empty opaque session grant");
      }
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid Gateway session");
      return false;
    }
    state.gatewaySession = Object.freeze({
      sessionId,
      pipelineId,
      profileId,
      profileHash,
      configurationHash,
    });
    return true;
  }

  function observeGatewayAttached({
    sessionId,
    pipelineId,
    profileId,
    profileHash,
    configurationHash,
    extensionOrigin,
  } = {}) {
    const state = requireTrial();
    try {
      requireUuid(sessionId, "sessionId");
      requireUuid(pipelineId, "pipelineId");
      requireProfileId(profileId);
      requireHash(profileHash, "profileHash");
      requireHash(configurationHash, "configurationHash");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid Gateway attach");
      return false;
    }
    if (
      !state.gatewaySession ||
      sessionId !== state.gatewaySession.sessionId ||
      pipelineId !== state.gatewaySession.pipelineId ||
      profileId !== state.gatewaySession.profileId ||
      profileHash !== state.gatewaySession.profileHash ||
      configurationHash !== state.gatewaySession.configurationHash ||
      !EXTENSION_ORIGIN.test(extensionOrigin)
    ) {
      invalidate("Gateway attach did not bind the issued session and Extension Origin");
      return false;
    }
    state.gatewayAttached = true;
    return true;
  }

  function startAttempt({
    generationId,
    pipelineId,
    profileId,
    profileHash,
    configurationHash,
  } = {}) {
    const state = requireTrial();
    if (!state.gatewayAttached || !state.boundary || !state.chatgptCapture) {
      invalidate("attempt began before the required transport facts were observed");
      return false;
    }
    if (state.activeAttempt !== null) {
      invalidate("attempt order is not terminal and sequential");
      return false;
    }
    try {
      requireGenerationId(generationId);
      requireUuid(pipelineId, "pipelineId");
      requireProfileId(profileId);
      requireHash(profileHash, "profileHash");
      requireHash(configurationHash, "configurationHash");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid generation identity");
      return false;
    }
    const previous = state.attempts.at(-1);
    if (state.attempts.length === state.entries.length) {
      if (
        state.failureProbe !== null ||
        !previous?.terminal ||
        previous.modelId !== "openvoice-v2" ||
        generationId <= previous.generationId ||
        pipelineId !== previous.pipelineId ||
        profileId !== previous.profileId ||
        profileHash !== previous.profileHash ||
        configurationHash !== previous.configurationHash
      ) {
        invalidate("failure probe did not bind the post-attempt OpenVoice generation");
        return false;
      }
      state.failureProbe = Object.freeze({
        modelId: previous.modelId,
        profileId,
        profileHash,
        configurationHash,
        pipelineId,
        generationId,
      });
      return true;
    }
    const entry = state.entries[state.attempts.length];
    if (
      profileId !== entry.profileId ||
      profileHash !== entry.profileHash ||
      configurationHash !== entry.configurationHash ||
      (previous && generationId <= previous.generationId) ||
      state.attempts.some((attempt) => attempt.pipelineId === pipelineId)
    ) {
      invalidate("generation identity does not match the frozen ordered roster");
      return false;
    }
    const attempt = {
      ...entry,
      generationId,
      pipelineId,
      finiteOutputObserved: null,
      changedOutputObserved: false,
      staleOutputAccepted: false,
      exclusivePlayoutObserved: false,
      expectedEndTriggered: entry.endTriggered,
      endTriggered: false,
      terminal: false,
    };
    state.attempts.push(attempt);
    state.activeAttempt = attempt;
    return true;
  }

  function activeAttemptFor(generationId, pipelineId = undefined) {
    const state = requireTrial();
    const attempt = state.activeAttempt;
    if (
      !attempt &&
      state.failureProbe?.generationId === generationId &&
      (pipelineId === undefined || state.failureProbe.pipelineId === pipelineId)
    ) {
      return null;
    }
    if (
      !attempt ||
      attempt.generationId !== generationId ||
      (pipelineId !== undefined && attempt.pipelineId !== pipelineId)
    ) {
      invalidate("runtime observation did not bind the active generation");
      return null;
    }
    return attempt;
  }

  function observeOutput({ generationId, pipelineId, finite, changed } = {}) {
    const attempt = activeAttemptFor(generationId, pipelineId);
    if (!attempt) {
      return false;
    }
    try {
      requireBoolean(finite, "finite");
      requireBoolean(changed, "changed");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid PCM observation");
      return false;
    }
    if (finite !== true) {
      attempt.finiteOutputObserved = false;
    } else if (attempt.finiteOutputObserved !== false) {
      attempt.finiteOutputObserved = true;
    }
    attempt.changedOutputObserved ||= changed;
    return true;
  }

  function observeRemotePlayout({ generationId, pipelineId, nativeAudible, remoteAudible } = {}) {
    const attempt = activeAttemptFor(generationId, pipelineId);
    if (!attempt) {
      return false;
    }
    try {
      requireBoolean(nativeAudible, "nativeAudible");
      requireBoolean(remoteAudible, "remoteAudible");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid playout observation");
      return false;
    }
    if (nativeAudible === remoteAudible) {
      invalidate("remote playout was not exclusive");
      return false;
    }
    if (remoteAudible) {
      attempt.exclusivePlayoutObserved = true;
    }
    return true;
  }

  function observeGenerationTerminal({ generationId, pipelineId, endTriggered } = {}) {
    const attempt = activeAttemptFor(generationId, pipelineId);
    if (!attempt) {
      return false;
    }
    try {
      requireBoolean(endTriggered, "endTriggered");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid terminal observation");
      return false;
    }
    if (endTriggered !== attempt.expectedEndTriggered) {
      invalidate("attempt End mode does not match its frozen model route");
      return false;
    }
    attempt.endTriggered = endTriggered;
    attempt.terminal = true;
    stateForAttempt(attempt).activeAttempt = null;
    return true;
  }

  function stateForAttempt(attempt) {
    const state = requireTrial();
    if (!state.attempts.includes(attempt)) {
      throw new Error("attempt is not owned by this receipt");
    }
    return state;
  }

  function observeStaleOutputAccepted({ generationId, pipelineId, accepted } = {}) {
    const attempt = activeAttemptFor(generationId, pipelineId);
    if (!attempt) {
      return false;
    }
    try {
      requireBoolean(accepted, "accepted");
    } catch (error) {
      invalidate(error instanceof Error ? error.message : "invalid stale observation");
      return false;
    }
    attempt.staleOutputAccepted ||= accepted;
    if (accepted) {
      invalidate("stale output was accepted for playout");
    }
    return !accepted;
  }

  function authorizeFailureInjection({ generationId } = {}) {
    const state = requireTrial();
    return (
      state.invalidReason === null &&
      state.activeAttempt === null &&
      state.attempts.length === state.entries.length &&
      state.attempts.every((attempt) => attempt.terminal) &&
      state.failureProbe?.generationId === generationId &&
      state.forcedFailure === null
    );
  }

  function observeForcedFallback({ generationId, pipelineId, injected } = {}) {
    const state = requireTrial();
    const probe = state.failureProbe;
    if (
      injected !== true ||
      !probe ||
      state.forcedFailure !== null ||
      generationId !== probe.generationId ||
      pipelineId !== probe.pipelineId
    ) {
      invalidate("forced fallback was not the explicit post-attempt injection");
      return false;
    }
    state.forcedFailure = probe;
    return true;
  }

  function observeNativeFallback({ generationId, pipelineId, nativeAudible, remoteAudible } = {}) {
    const state = requireTrial();
    const probe = state.failureProbe;
    if (!probe || !state.forcedFailure) {
      invalidate("native fallback was not preceded by fallback.required");
      return false;
    }
    if (
      state.forcedFailure.generationId !== generationId ||
      state.forcedFailure.pipelineId !== pipelineId ||
      nativeAudible !== true ||
      remoteAudible !== false
    ) {
      invalidate("native fallback did not preserve the forced-failure identity");
      return false;
    }
    state.nativeFallback = state.forcedFailure;
    return true;
  }

  function checkpoint() {
    const state = requireTrial();
    const clone = (value) => value === null ? null : structuredClone(value);
    return Object.freeze({
      schema_version: 1,
      receipt_id: state.receiptId,
      roster_revision: state.rosterRevision,
      plan_revision: state.planRevision,
      entries: clone(state.entries),
      configured_forward_port: state.configuredForwardPort,
      chatgpt_capture: state.chatgptCapture,
      boundary: state.boundary,
      gateway_session: clone(state.gatewaySession),
      gateway_attached: state.gatewayAttached,
      attempts: clone(state.attempts),
      active_attempt_index:
        state.activeAttempt === null ? null : state.attempts.indexOf(state.activeAttempt),
      failure_probe: clone(state.failureProbe),
      forced_failure: clone(state.forcedFailure),
      native_fallback: clone(state.nativeFallback),
      invalid_reason: state.invalidReason,
    });
  }

  function restore(value) {
    if (trial !== null) {
      throw new Error("EXP-005 trial is already active; clear it first");
    }
    const saved = requireExactFields(
      value,
      [
        "schema_version",
        "receipt_id",
        "roster_revision",
        "plan_revision",
        "entries",
        "configured_forward_port",
        "chatgpt_capture",
        "boundary",
        "gateway_session",
        "gateway_attached",
        "attempts",
        "active_attempt_index",
        "failure_probe",
        "forced_failure",
        "native_fallback",
        "invalid_reason",
      ],
      "persisted receipt",
    );
    if (saved.schema_version !== 1) {
      throw new TypeError("persisted receipt has an unsupported schema version");
    }
    requireUuid(saved.receipt_id, "persisted receipt_id");
    requireRevision(saved.roster_revision, "persisted roster_revision");
    requireRevision(saved.plan_revision, "persisted plan_revision");
    if (
      !Number.isSafeInteger(saved.configured_forward_port) ||
      saved.configured_forward_port < 1 ||
      saved.configured_forward_port > 65_535
    ) {
      throw new TypeError("persisted forward port is invalid");
    }
    requireBoolean(saved.chatgpt_capture, "persisted chatgpt_capture");
    requireBoolean(saved.boundary, "persisted boundary");
    requireBoolean(saved.gateway_attached, "persisted gateway_attached");
    if (!Array.isArray(saved.entries)) {
      throw new TypeError("persisted entries must be an array");
    }
    const entries = validateRosterEntries(
      saved.entries.map((entry) => ({
        model_id: entry.modelId,
        profile_id: entry.profileId,
        profile_hash: entry.profileHash,
        configuration_hash: entry.configurationHash,
        route_mode: entry.routeMode,
      })),
    );
    const gatewaySession = saved.gateway_session === null
      ? null
      : requireExactFields(
          saved.gateway_session,
          ["sessionId", "pipelineId", "profileId", "profileHash", "configurationHash"],
          "persisted gateway session",
        );
    if (gatewaySession !== null) {
      requireUuid(gatewaySession.sessionId, "persisted sessionId");
      requireUuid(gatewaySession.pipelineId, "persisted gateway pipelineId");
      requireProfileId(gatewaySession.profileId, "persisted gateway profileId");
      requireHash(gatewaySession.profileHash, "persisted gateway profileHash");
      requireHash(
        gatewaySession.configurationHash,
        "persisted gateway configurationHash",
      );
    }
    if (saved.gateway_attached && gatewaySession === null) {
      throw new TypeError("persisted Gateway attach is missing its session identity");
    }
    if (!Array.isArray(saved.attempts) || saved.attempts.length > entries.length) {
      throw new TypeError("persisted attempts are invalid");
    }
    const attempts = saved.attempts.map((attempt, index) => {
      const fields = requireExactFields(
        attempt,
        [
          "modelId", "profileId", "profileHash", "configurationHash", "routeMode",
          "endTriggered", "generationId", "pipelineId", "finiteOutputObserved",
          "changedOutputObserved", "staleOutputAccepted", "exclusivePlayoutObserved",
          "expectedEndTriggered", "terminal",
        ],
        `persisted attempts[${index}]`,
      );
      const entry = entries[index];
      requireGenerationId(fields.generationId, "persisted generationId");
      requireUuid(fields.pipelineId, "persisted pipelineId");
      for (const name of [
        "changedOutputObserved", "staleOutputAccepted", "exclusivePlayoutObserved",
        "expectedEndTriggered", "endTriggered", "terminal",
      ]) {
        requireBoolean(fields[name], `persisted ${name}`);
      }
      if (
        (fields.finiteOutputObserved !== null &&
          typeof fields.finiteOutputObserved !== "boolean") ||
        fields.modelId !== entry.modelId ||
        fields.profileId !== entry.profileId ||
        fields.profileHash !== entry.profileHash ||
        fields.configurationHash !== entry.configurationHash ||
        fields.routeMode !== entry.routeMode ||
        fields.expectedEndTriggered !== entry.endTriggered ||
        (fields.terminal && fields.endTriggered !== entry.endTriggered) ||
        (index > 0 && fields.generationId <= saved.attempts[index - 1].generationId) ||
        saved.attempts.slice(0, index).some(
          (previous) => previous.pipelineId === fields.pipelineId,
        )
      ) {
        throw new TypeError("persisted attempt identity is invalid");
      }
      return { ...fields };
    });
    const activeIndex = saved.active_attempt_index;
    if (
      activeIndex !== null &&
      (!Number.isSafeInteger(activeIndex) ||
        activeIndex !== attempts.length - 1 ||
        attempts[activeIndex]?.terminal)
    ) {
      throw new TypeError("persisted active attempt is invalid");
    }
    if (
      attempts.some((attempt, index) => !attempt.terminal && index !== activeIndex)
    ) {
      throw new TypeError("persisted attempt terminal ordering is invalid");
    }
    const validateProbe = (candidate, name) => {
      if (candidate === null) {
        return null;
      }
      const probe = requireExactFields(
        candidate,
        [
          "modelId", "profileId", "profileHash", "configurationHash",
          "pipelineId", "generationId",
        ],
        name,
      );
      const openvoice = attempts.at(-1);
      requireGenerationId(probe.generationId, `${name}.generationId`);
      if (
        attempts.length !== entries.length ||
        !attempts.every((attempt) => attempt.terminal) ||
        !openvoice ||
        probe.modelId !== "openvoice-v2" ||
        probe.profileId !== openvoice.profileId ||
        probe.profileHash !== openvoice.profileHash ||
        probe.configurationHash !== openvoice.configurationHash ||
        probe.pipelineId !== openvoice.pipelineId ||
        probe.generationId <= openvoice.generationId
      ) {
        throw new TypeError(`${name} does not bind the OpenVoice failure probe`);
      }
      return Object.freeze({ ...probe });
    };
    const failureProbe = validateProbe(saved.failure_probe, "persisted failure probe");
    const forcedFailure = validateProbe(saved.forced_failure, "persisted forced failure");
    const nativeFallback = validateProbe(saved.native_fallback, "persisted native fallback");
    if (
      (forcedFailure !== null &&
        JSON.stringify(forcedFailure) !== JSON.stringify(failureProbe)) ||
      (nativeFallback !== null &&
        JSON.stringify(nativeFallback) !== JSON.stringify(forcedFailure))
    ) {
      throw new TypeError("persisted fallback identity is inconsistent");
    }
    if (
      saved.invalid_reason !== null &&
      (typeof saved.invalid_reason !== "string" || saved.invalid_reason.length > 512)
    ) {
      throw new TypeError("persisted invalid reason is invalid");
    }
    trial = {
      receiptId: saved.receipt_id,
      rosterRevision: saved.roster_revision,
      planRevision: saved.plan_revision,
      entries,
      configuredForwardPort: saved.configured_forward_port,
      chatgptCapture: saved.chatgpt_capture,
      boundary: saved.boundary,
      gatewaySession: gatewaySession === null ? null : Object.freeze({ ...gatewaySession }),
      gatewayAttached: saved.gateway_attached,
      attempts,
      activeAttempt: activeIndex === null ? null : attempts[activeIndex],
      failureProbe,
      forcedFailure,
      nativeFallback,
      invalidReason: saved.invalid_reason,
    };
    return Object.freeze({ receiptId: saved.receipt_id });
  }

  function exportReceipt() {
    const state = requireTrial();
    if (state.invalidReason !== null) {
      throw new Error("EXP-005 receipt contains invalid or forged runtime evidence");
    }
    if (
      !state.chatgptCapture ||
      !state.boundary ||
      !state.gatewaySession ||
      !state.gatewayAttached ||
      state.activeAttempt !== null ||
      state.attempts.length !== state.entries.length ||
      state.attempts.some((attempt) => !attempt.terminal) ||
      state.forcedFailure === null ||
      state.nativeFallback === null
    ) {
      throw new Error("EXP-005 receipt has incomplete terminal evidence");
    }
    return Object.freeze({
      schema_version: 1,
      source: "extension_gateway_runtime",
      receipt_id: state.receiptId,
      roster_revision: state.rosterRevision,
      plan_revision: state.planRevision,
      chatgpt_tab: Object.freeze({
        chatgpt_com_audible_tab_observed: true,
        capture_started_after_user_gesture: true,
      }),
      ssh_loopback: Object.freeze({
        configured_local_forward_reached_gateway: true,
        client_loopback_only: true,
        remote_gateway_loopback_only: true,
        pinned_server_identity_configured: true,
      }),
      gateway_authentication: Object.freeze({
        gateway_session_authenticated: true,
        single_use_session_grant_authenticated: true,
        exact_extension_origin_verified: true,
        max_sessions: 1,
      }),
      attempts: Object.freeze(state.attempts.map(publicAttempt)),
      forced_failure_event: Object.freeze({
        event_type: "fallback.required",
        model_id: state.forcedFailure.modelId,
        profile_id: state.forcedFailure.profileId,
        profile_hash: state.forcedFailure.profileHash,
        configuration_hash: state.forcedFailure.configurationHash,
        pipeline_id: state.forcedFailure.pipelineId,
        generation_id: state.forcedFailure.generationId,
        failure_injected: true,
        fallback_required_observed: true,
      }),
      native_fallback_event: Object.freeze({
        event_type: "extension.native_fallback_activated",
        model_id: state.nativeFallback.modelId,
        profile_id: state.nativeFallback.profileId,
        profile_hash: state.nativeFallback.profileHash,
        configuration_hash: state.nativeFallback.configurationHash,
        pipeline_id: state.nativeFallback.pipelineId,
        generation_id: state.nativeFallback.generationId,
        native_route_active: true,
        remote_route_active: false,
      }),
    });
  }

  function clear() {
    trial = null;
  }

  function active() {
    return trial !== null;
  }

  return Object.freeze({
    active,
    authorizeFailureInjection,
    begin,
    checkpoint,
    clear,
    exportReceipt,
    invalidate,
    observeCaptureStarted,
    observeForcedFallback,
    observeGatewayAttached,
    observeGatewayBoundary,
    observeGatewaySession,
    observeGenerationTerminal,
    observeNativeFallback,
    observeOutput,
    observeRemotePlayout,
    observeStaleOutputAccepted,
    restore,
    startAttempt,
  });
}
