import {
  normalizeGatewayUrl,
  websocketUrl,
} from "./gateway-url.js";
import { createExp005RuntimeReceiptRecorder } from "./exp005-runtime-receipt.js";

const CONFIGURATION_KEY = "liveconv.session-configuration.v1";
const ACTIVE_SESSION_KEY = "liveconv.active-session.v1";
const EXP005_RECEIPT_STATE_KEY = "liveconv.exp005-receipt-state.v1";
const OFFSCREEN_PATH = "offscreen/offscreen.html";
const PROFILE_ID = /^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HASH = /^sha256:[0-9a-f]{64}$/;
const MAXIMUM_CATALOG_PROFILES = 128;
const MAXIMUM_INGRESS_FRAMES = 500;
const MAXIMUM_ROSTER_MODELS = 4;
const MINIMUM_DEPLOYMENT_VARIANTS = 1;
const MAXIMUM_DEPLOYMENT_VARIANTS = 12;
const ROSTER_ID = /^[a-z0-9][a-z0-9.-]{1,63}$/;
const MODEL_ID = /^[a-z0-9][a-z0-9-]{1,63}$/;
const REASON_CODE = /^[a-z0-9][a-z0-9_]{0,127}$/;
const MS2_MODEL_IDS = new Set([
  "rvc-v2",
  "beatrice-2",
  "x-vc",
  "openvoice-v2",
]);
const MS2_MODEL_SEMANTICS = Object.freeze({
  "rvc-v2": Object.freeze({
    profileId: "vc.rvc.synthetic-ja.v1",
    invocationMode: "live",
    voiceRequirement: "pretrained_voice",
  }),
  "beatrice-2": Object.freeze({
    profileId: "vc.beatrice.synthetic-ja.v1",
    invocationMode: "live",
    voiceRequirement: "pretrained_voice",
  }),
  "x-vc": Object.freeze({
    profileId: "vc.x-vc.synthetic-ja.v1",
    invocationMode: "live",
    voiceRequirement: "pretrained_voice",
  }),
  "openvoice-v2": Object.freeze({
    profileId: "vc.openvoice-v2.synthetic-ja.v1",
    invocationMode: "buffered_end",
    voiceRequirement: "pretrained_voice",
  }),
});
const PROFILE_KINDS = new Set([
  "deterministic_test",
  "voice_conversion",
  "text_to_speech",
]);

function requireMethod(value, owner, method) {
  if (value === null || typeof value !== "object") {
    throw new TypeError(`${owner} dependency must be an object`);
  }
  if (typeof value[method] !== "function") {
    throw new TypeError(`${owner}.${method} dependency must be a function`);
  }
}

function errorMessage(error) {
  return error instanceof Error ? error.message : "Extension operation failed";
}

function normalizeConfiguration(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("configuration must be an object");
  }
  const gatewayUrl = normalizeGatewayUrl(value.gatewayUrl);
  if (typeof value.profileId !== "string" || !PROFILE_ID.test(value.profileId)) {
    throw new TypeError("profileId has an invalid format");
  }
  const tokenBytes =
    typeof value.token === "string"
      ? new TextEncoder().encode(value.token).length
      : 0;
  if (tokenBytes < 32 || tokenBytes > 4_096) {
    throw new TypeError("session token must contain between 32 and 4096 bytes");
  }
  if (![...value.token].every((character) => {
    const code = character.charCodeAt(0);
    return code >= 0x21 && code <= 0x7e;
  })) {
    throw new TypeError("session token must contain printable ASCII only");
  }
  return Object.freeze({ gatewayUrl, profileId: value.profileId, token: value.token });
}

function publicConfiguration(configuration) {
  if (!configuration) {
    return Object.freeze({ configured: false, gatewayUrl: null, profileId: null });
  }
  return Object.freeze({
    configured: true,
    gatewayUrl: configuration.gatewayUrl,
    profileId: configuration.profileId,
  });
}

function requireString(value, name, { pattern, maximumLength = 256 } = {}) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > maximumLength ||
    (pattern && !pattern.test(value))
  ) {
    throw new Error(`gateway returned an invalid ${name}`);
  }
  return value;
}

function requireCatalogProfile(value, index) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`gateway returned an invalid profile at index ${index}`);
  }
  const profileId = requireString(value.profile_id, "profile_id", {
    pattern: PROFILE_ID,
    maximumLength: 128,
  });
  if (!PROFILE_KINDS.has(value.kind) || value.adapter_api_version !== 1) {
    throw new Error(`gateway returned incompatible metadata for ${profileId}`);
  }
  if (value.readiness !== "ready") {
    throw new Error(`gateway catalog included non-ready profile ${profileId}`);
  }
  const integerArray = (candidate, name) => {
    if (
      !Array.isArray(candidate) ||
      candidate.length === 0 ||
      !candidate.every((entry) => Number.isSafeInteger(entry) && entry > 0)
    ) {
      throw new Error(`gateway returned invalid ${name} for ${profileId}`);
    }
    return [...candidate];
  };
  const inputSampleRates = integerArray(
    value.input_sample_rates,
    "input_sample_rates",
  );
  const outputSampleRates = integerArray(
    value.output_sample_rates,
    "output_sample_rates",
  );
  if (
    typeof value.streaming !== "boolean" ||
    !Number.isSafeInteger(value.frame_ms) ||
    value.frame_ms <= 0 ||
    !Number.isSafeInteger(value.minimum_context_ms) ||
    value.minimum_context_ms < 0
  ) {
    throw new Error(`gateway returned invalid streaming metadata for ${profileId}`);
  }
  const profile = {
    profileId,
    kind: value.kind,
    promotion:
      value.kind === "voice_conversion"
        ? requireCatalogPromotion(value.promotion, profileId)
        : null,
    readiness: value.readiness,
    implementationRevision: requireString(
      value.implementation_revision,
      "implementation_revision",
    ),
    weightRevision:
      value.weight_revision === null
        ? null
        : requireString(value.weight_revision, "weight_revision"),
    streaming: value.streaming,
    cancellation: requireString(value.cancellation, "cancellation"),
    inputSampleRates,
    outputSampleRates,
    frameMs: value.frame_ms,
    minimumContextMs: value.minimum_context_ms,
    voiceRequirement: requireString(
      value.voice_requirement,
      "voice_requirement",
    ),
    warmupPolicy: requireString(value.warmup_policy, "warmup_policy"),
    resourceClass: requireString(value.resource_class, "resource_class"),
    profileHash: requireString(value.profile_hash, "profile_hash", {
      pattern: HASH,
    }),
    configurationHash: requireString(
      value.configuration_hash,
      "configuration_hash",
      { pattern: HASH },
    ),
  };
  profile.compatible =
    profile.frameMs === 20 &&
    profile.inputSampleRates.includes(48_000) &&
    profile.outputSampleRates.includes(48_000);
  return Object.freeze(profile);
}

function requireCatalogPromotion(value, profileId) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`gateway returned invalid promotion for ${profileId}`);
  }
  requireExactFields(
    value,
    [
      "status",
      "pack_id",
      "pack_sha256",
      "evidence_sha256",
      "endpoint_sha256",
    ],
    `promotion for ${profileId}`,
  );
  if (!["technical_validation", "approved"].includes(value.status)) {
    throw new Error(`gateway returned invalid promotion status for ${profileId}`);
  }
  return Object.freeze({
    status: value.status,
    packId: requireString(value.pack_id, `promotion.pack_id for ${profileId}`, {
      pattern: MODEL_ID,
      maximumLength: 64,
    }),
    packHash: requireString(value.pack_sha256, `promotion.pack_sha256 for ${profileId}`, {
      pattern: HASH,
      maximumLength: 71,
    }),
    evidenceHash: requireString(
      value.evidence_sha256,
      `promotion.evidence_sha256 for ${profileId}`,
      { pattern: HASH, maximumLength: 71 },
    ),
    endpointHash: requireString(
      value.endpoint_sha256,
      `promotion.endpoint_sha256 for ${profileId}`,
      { pattern: HASH, maximumLength: 71 },
    ),
  });
}

function requireCatalogResponse(value) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    value.protocol_version !== 1 ||
    !Array.isArray(value.profiles) ||
    value.profiles.length === 0 ||
    value.profiles.length > MAXIMUM_CATALOG_PROFILES
  ) {
    throw new Error("gateway returned an invalid model catalog");
  }
  const profiles = value.profiles.map(requireCatalogProfile);
  if (new Set(profiles.map((profile) => profile.profileId)).size !== profiles.length) {
    throw new Error("gateway returned duplicate profile IDs");
  }
  return Object.freeze(profiles);
}

function requireExactFields(value, fields, owner) {
  const actual = Object.keys(value);
  if (
    actual.length !== fields.length ||
    actual.some((field) => !fields.includes(field))
  ) {
    throw new Error(`gateway returned unexpected fields in ${owner}`);
  }
}

function requireNullableReasonCode(value, modelId) {
  if (value === null) {
    return null;
  }
  return requireString(value, `reason_code for ${modelId}`, {
    pattern: REASON_CODE,
    maximumLength: 128,
  });
}

function requireRosterModel(value, index) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`gateway returned an invalid roster model at index ${index}`);
  }
  requireExactFields(
    value,
    [
      "model_id",
      "display_name",
      "profile_id",
      "invocation_mode",
      "execution_state",
      "decision_state",
      "voice_requirement",
      "reason_code",
      "profile",
    ],
    `roster model ${index}`,
  );
  const modelId = requireString(value.model_id, "model_id", {
    pattern: MODEL_ID,
    maximumLength: 64,
  });
  const profileId = requireString(value.profile_id, "profile_id", {
    pattern: PROFILE_ID,
    maximumLength: 128,
  });
  if (!["live", "buffered_end"].includes(value.invocation_mode)) {
    throw new Error(`gateway returned an invalid invocation mode for ${modelId}`);
  }
  if (
    !["live-trial", "buffered-preview", "unavailable"].includes(
      value.execution_state,
    )
  ) {
    throw new Error(`gateway returned an invalid execution state for ${modelId}`);
  }
  if (
    !["technical-only", "quality-failed", "unassessed", "selected"].includes(
      value.decision_state,
    )
  ) {
    throw new Error(`gateway returned an invalid decision state for ${modelId}`);
  }
  if (
    !["none", "authorized_target_required", "pretrained_voice"].includes(
      value.voice_requirement,
    )
  ) {
    throw new Error(`gateway returned an invalid voice requirement for ${modelId}`);
  }
  const reasonCode = requireNullableReasonCode(value.reason_code, modelId);
  const enabled = value.execution_state !== "unavailable";
  if (
    (value.invocation_mode === "live" &&
      value.execution_state === "buffered-preview") ||
    (value.invocation_mode === "buffered_end" &&
      value.execution_state === "live-trial")
  ) {
    throw new Error(`gateway returned inconsistent execution mode for ${modelId}`);
  }
  if (
    (enabled && (reasonCode !== null || value.profile === null)) ||
    (!enabled && (reasonCode === null || value.profile !== null))
  ) {
    throw new Error(`gateway returned inconsistent availability for ${modelId}`);
  }
  const profile = enabled ? requireCatalogProfile(value.profile, index) : null;
  if (profile !== null && profile.profileId !== profileId) {
    throw new Error(`gateway roster profile_id does not match profile for ${modelId}`);
  }
  return Object.freeze({
    modelId,
    displayName: requireString(value.display_name, "display_name", {
      maximumLength: 80,
    }),
    profileId,
    invocationMode: value.invocation_mode,
    executionState: value.execution_state,
    decisionState: value.decision_state,
    voiceRequirement: value.voice_requirement,
    reasonCode,
    profile,
  });
}

function requireFixedMs2ModelSemantics(model) {
  const expected = MS2_MODEL_SEMANTICS[model.modelId];
  if (
    !expected ||
    model.profileId !== expected.profileId ||
    model.invocationMode !== expected.invocationMode ||
    model.voiceRequirement !== expected.voiceRequirement
  ) {
    throw new Error(
      `gateway roster violates fixed MS-2 semantics for ${model.modelId}`,
    );
  }
}

function requireModelRosterResponse(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway returned an invalid model roster");
  }
  requireExactFields(
    value,
    ["schema_version", "roster_id", "roster_hash", "models"],
    "model roster",
  );
  if (
    value.schema_version !== 1 ||
    !Array.isArray(value.models) ||
    value.models.length !== MAXIMUM_ROSTER_MODELS
  ) {
    throw new Error("gateway returned an invalid model roster");
  }
  const models = value.models.map(requireRosterModel);
  const modelIds = new Set(models.map((model) => model.modelId));
  if (
    modelIds.size !== MAXIMUM_ROSTER_MODELS ||
    modelIds.size !== MS2_MODEL_IDS.size ||
    [...MS2_MODEL_IDS].some((modelId) => !modelIds.has(modelId))
  ) {
    throw new Error("gateway roster must include each prepared MS-2 model once");
  }
  if (new Set(models.map((model) => model.profileId)).size !== models.length) {
    throw new Error("gateway roster returned duplicate profile IDs");
  }
  for (const model of models) {
    requireFixedMs2ModelSemantics(model);
  }
  return Object.freeze({
    schemaVersion: value.schema_version,
    rosterId: requireString(value.roster_id, "roster_id", {
      pattern: ROSTER_ID,
      maximumLength: 64,
    }),
    rosterHash: requireString(value.roster_hash, "roster_hash", {
      pattern: HASH,
      maximumLength: 71,
    }),
    models,
  });
}

function bindRosterToCatalog(roster, catalog) {
  const catalogByProfileId = new Map(
    catalog.map((profile) => [profile.profileId, profile]),
  );
  return Object.freeze(
    roster.models.map((model) => {
      if (model.executionState === "unavailable") {
        return Object.freeze({ ...model, selectable: false });
      }
      const catalogProfile = catalogByProfileId.get(model.profileId);
      if (!catalogProfile) {
        throw new Error(
          `enabled roster profile ${model.profileId} is absent from /v1/models`,
        );
      }
      if (
        catalogProfile.kind !== "voice_conversion" ||
        catalogProfile.promotion?.packId !== model.modelId
      ) {
        throw new Error(
          `enabled roster profile ${model.profileId} is not promoted for ${model.modelId}`,
        );
      }
      if (
        model.voiceRequirement !== catalogProfile.voiceRequirement ||
        catalogProfile.streaming !== (model.invocationMode === "live")
      ) {
        throw new Error(
          `enabled roster invocation or voice requirement does not match /v1/models for ${model.modelId}`,
        );
      }
      if (
        model.profile.profileHash !== catalogProfile.profileHash ||
        model.profile.configurationHash !== catalogProfile.configurationHash ||
        model.profile.voiceRequirement !== catalogProfile.voiceRequirement ||
        model.profile.streaming !== catalogProfile.streaming ||
        model.profile.profileId !== catalogProfile.profileId
      ) {
        throw new Error(
          `enabled roster profile identity does not match /v1/models for ${model.modelId}`,
        );
      }
      if (!catalogProfile.compatible) {
        throw new Error(`roster profile ${model.profileId} is not compatible with audio route v1`);
      }
      return Object.freeze({
        ...model,
        profile: catalogProfile,
        selectable: model.voiceRequirement !== "authorized_target_required",
      });
    }),
  );
}

function requireDeploymentVariant(value, index, catalogByProfileId) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`gateway returned an invalid deployment variant at index ${index}`);
  }
  requireExactFields(
    value,
    [
      "variant_id",
      "family_id",
      "display_order",
      "display_name",
      "target_presentation",
      "lane",
      "invocation_mode",
      "profile_id",
      "profile_hash",
      "configuration_hash",
      "pack_id",
      "promotion_evidence_sha256",
      "authorization_record_sha256",
      "variant_manifest_sha256",
    ],
    `deployment variant ${index}`,
  );
  const variantId = requireString(value.variant_id, "variant_id", {
    pattern: ROSTER_ID,
    maximumLength: 96,
  });
  const familyId = requireString(value.family_id, `family_id for ${variantId}`, {
    pattern: ROSTER_ID,
    maximumLength: 64,
  });
  const profileId = requireString(value.profile_id, `profile_id for ${variantId}`, {
    pattern: PROFILE_ID,
    maximumLength: 128,
  });
  const packId = requireString(value.pack_id, `pack_id for ${variantId}`, {
    pattern: MODEL_ID,
    maximumLength: 64,
  });
  const displayName = requireString(value.display_name, `display_name for ${variantId}`, {
    maximumLength: 100,
  });
  if (/[\\/\r\n]/u.test(displayName)) {
    throw new Error(`gateway returned an invalid display name for ${variantId}`);
  }
  if (
    !Number.isSafeInteger(value.display_order) ||
    value.display_order !== index + 1 ||
    value.lane !== "voice-conversion" ||
    !["live", "buffered_end"].includes(value.invocation_mode) ||
    ![
      "youthful-feminine",
      "bright-youthful-feminine",
      "soft-youthful-feminine",
      "relaxed-youthful-feminine",
    ].includes(value.target_presentation) ||
    familyId !== packId
  ) {
    throw new Error(`gateway returned incompatible deployment metadata for ${variantId}`);
  }
  const profileHash = requireString(value.profile_hash, `profile_hash for ${variantId}`, {
    pattern: HASH,
    maximumLength: 71,
  });
  const configurationHash = requireString(
    value.configuration_hash,
    `configuration_hash for ${variantId}`,
    { pattern: HASH, maximumLength: 71 },
  );
  const promotionEvidenceHash = requireString(
    value.promotion_evidence_sha256,
    `promotion evidence for ${variantId}`,
    { pattern: HASH, maximumLength: 71 },
  );
  const profile = catalogByProfileId.get(profileId);
  if (
    !profile ||
    profile.kind !== "voice_conversion" ||
    !profile.compatible ||
    profile.profileHash !== profileHash ||
    profile.configurationHash !== configurationHash ||
    profile.promotion?.packId !== packId ||
    profile.promotion?.evidenceHash !== promotionEvidenceHash ||
    (value.invocation_mode === "live" && !profile.streaming)
  ) {
    throw new Error(`deployment identity does not match catalog for ${variantId}`);
  }
  return Object.freeze({
    variantId,
    familyId,
    displayOrder: value.display_order,
    displayName,
    targetPresentation: value.target_presentation,
    invocationMode: value.invocation_mode,
    profileId,
    profileHash,
    configurationHash,
    packId,
    promotionEvidenceHash,
    authorizationRecordHash: requireString(
      value.authorization_record_sha256,
      `authorization record for ${variantId}`,
      { pattern: HASH, maximumLength: 71 },
    ),
    variantManifestHash: requireString(
      value.variant_manifest_sha256,
      `variant manifest for ${variantId}`,
      { pattern: HASH, maximumLength: 71 },
    ),
    profile,
  });
}

function requireDeploymentManifestResponse(value, catalog) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway returned an invalid deployment manifest");
  }
  requireExactFields(
    value,
    [
      "schema_version",
      "bundle_id",
      "bundle_revision",
      "protocol_version",
      "transport_scope",
      "max_sessions",
      "variants",
    ],
    "deployment manifest",
  );
  if (
    value.schema_version !== 1 ||
    value.protocol_version !== 1 ||
    value.transport_scope !== "loopback-ssh" ||
    value.max_sessions !== 1 ||
    !Array.isArray(value.variants) ||
    value.variants.length < MINIMUM_DEPLOYMENT_VARIANTS ||
    value.variants.length > MAXIMUM_DEPLOYMENT_VARIANTS
  ) {
    throw new Error("gateway returned an incompatible deployment manifest");
  }
  const catalogByProfileId = new Map(
    catalog.map((profile) => [profile.profileId, profile]),
  );
  const variants = value.variants.map((variant, index) =>
    requireDeploymentVariant(variant, index, catalogByProfileId));
  if (
    new Set(variants.map((variant) => variant.variantId)).size !== variants.length ||
    new Set(variants.map((variant) => variant.profileId)).size !== variants.length
  ) {
    throw new Error("gateway deployment manifest variants are not unique");
  }
  return Object.freeze({
    schemaVersion: value.schema_version,
    bundleId: requireString(value.bundle_id, "bundle_id", {
      pattern: ROSTER_ID,
      maximumLength: 96,
    }),
    bundleRevision: requireString(value.bundle_revision, "bundle_revision", {
      pattern: HASH,
      maximumLength: 71,
    }),
    protocolVersion: value.protocol_version,
    transportScope: value.transport_scope,
    maxSessions: value.max_sessions,
    variants,
  });
}

function expectedProfileIdentity(profile, pipelineId) {
  return Object.freeze({
    profileId: profile.profileId,
    profileHash: profile.profileHash,
    configurationHash: profile.configurationHash,
    ...(pipelineId ? { pipelineId } : {}),
  });
}

function requireSessionResponse(value, expectedProfile) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway returned an invalid session response");
  }
  if (typeof value.session_id !== "string" || !UUID.test(value.session_id)) {
    throw new Error("gateway returned an invalid session_id");
  }
  if (
    value.protocol_version !== 1 ||
    typeof value.pipeline_id !== "string" ||
    !UUID.test(value.pipeline_id) ||
    value.profile_id !== expectedProfile.profileId ||
    value.profile_hash !== expectedProfile.profileHash ||
    value.configuration_hash !== expectedProfile.configurationHash
  ) {
    throw new Error("gateway session identity does not match the selected catalog profile");
  }
  if (
    value.limits === null ||
    typeof value.limits !== "object" ||
    !Number.isSafeInteger(value.limits.ingress_budget_ms) ||
    value.limits.ingress_budget_ms <= 0 ||
    !Number.isSafeInteger(value.limits.max_ingress_frames) ||
    value.limits.max_ingress_frames <= 0 ||
    value.limits.max_ingress_frames > MAXIMUM_INGRESS_FRAMES ||
    value.limits.max_ingress_frames !==
      Math.floor(value.limits.ingress_budget_ms / 20)
  ) {
    throw new Error("gateway returned invalid ingress limits");
  }
  if (
    typeof value.ticket !== "string" ||
    value.ticket.length === 0 ||
    new TextEncoder().encode(value.ticket).length > 4_096
  ) {
    throw new Error("gateway returned an invalid one-use ticket");
  }
  if (
    typeof value.websocket_path !== "string" ||
    value.websocket_path.length > 2_048 ||
    !value.websocket_path.startsWith("/") ||
    value.websocket_path.startsWith("//") ||
    /[\\\u0000-\u001f\u007f]/u.test(value.websocket_path) ||
    /%5c/iu.test(value.websocket_path)
  ) {
    throw new Error("gateway returned an invalid websocket_path");
  }
  return value;
}

function requireRuntimeBoundaryResponse(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway returned an invalid runtime boundary response");
  }
  requireExactFields(
    value,
    ["protocol_version", "transport_scope", "max_sessions", "ticket_one_use"],
    "runtime boundary",
  );
  if (
    value.protocol_version !== 1 ||
    !["loopback", "network"].includes(value.transport_scope) ||
    !Number.isSafeInteger(value.max_sessions) ||
    value.max_sessions < 1 ||
    value.ticket_one_use !== true
  ) {
    throw new Error("gateway returned an invalid runtime boundary response");
  }
  return Object.freeze({
    protocolVersion: value.protocol_version,
    transportScope: value.transport_scope,
    maxSessions: value.max_sessions,
    ticketOneUse: value.ticket_one_use,
  });
}

function authorizedHeaders(token) {
  return Object.freeze({
    "content-type": "application/json",
    authorization: ["Bearer", token].join(" "),
  });
}

async function jsonResponse(response, operation) {
  if (!response?.ok) {
    const status = Number.isInteger(response?.status) ? response.status : "unknown";
    throw new Error(`${operation} failed with HTTP ${status}`);
  }
  try {
    return await response.json();
  } catch {
    throw new Error(`${operation} returned invalid JSON`);
  }
}

export function createBrowserRuntime(options = {}) {
  const chromeApi = options.chromeApi;
  const fetchFn = options.fetchFn ?? globalThis.fetch;
  const receiptRecorder =
    options.receiptRecorder ?? createExp005RuntimeReceiptRecorder();
  requireMethod(chromeApi?.runtime, "chrome.runtime", "getURL");
  requireMethod(chromeApi?.runtime, "chrome.runtime", "getContexts");
  requireMethod(chromeApi?.runtime, "chrome.runtime", "sendMessage");
  requireMethod(chromeApi?.offscreen, "chrome.offscreen", "createDocument");
  requireMethod(chromeApi?.offscreen, "chrome.offscreen", "closeDocument");
  requireMethod(chromeApi?.tabCapture, "chrome.tabCapture", "getMediaStreamId");
  requireMethod(chromeApi?.tabs, "chrome.tabs", "query");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "get");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "set");
  requireMethod(chromeApi?.storage?.session, "chrome.storage.session", "remove");
  requireMethod(chromeApi?.storage?.local, "chrome.storage.local", "get");
  requireMethod(chromeApi?.storage?.local, "chrome.storage.local", "set");
  if (typeof fetchFn !== "function") {
    throw new TypeError("fetchFn must be a function");
  }
  for (const method of [
    "active",
    "authorizeFailureInjection",
    "begin",
    "checkpoint",
    "clear",
    "exportReceipt",
    "invalidate",
    "observeCaptureStarted",
    "observeForcedFallback",
    "observeGatewayAttached",
    "observeGatewayBoundary",
    "observeGatewaySession",
    "observeGenerationTerminal",
    "observeNativeFallback",
    "observeOutput",
    "observeRemotePlayout",
    "observeStaleOutputAccepted",
    "restore",
    "startAttempt",
  ]) {
    if (typeof receiptRecorder?.[method] !== "function") {
      throw new TypeError(`receiptRecorder.${method} must be a function`);
    }
  }
  const requestTimeoutMilliseconds = options.requestTimeoutMilliseconds ?? 5_000;
  if (
    !Number.isSafeInteger(requestTimeoutMilliseconds) ||
    requestTimeoutMilliseconds <= 0
  ) {
    throw new TypeError(
      "requestTimeoutMilliseconds must be a positive safe integer",
    );
  }
  const setTimer = options.setTimer ?? globalThis.setTimeout;
  const clearTimer = options.clearTimer ?? globalThis.clearTimeout;
  if (typeof setTimer !== "function" || typeof clearTimer !== "function") {
    throw new TypeError("timer dependencies must be functions");
  }

  let capture = "stopped";
  let requestedCapture = "stopped";
  let route = "native";
  let remote = "disconnected";
  let generationId = null;
  let lastError = null;
  let transition = Promise.resolve();
  let cleanupBarrier = Promise.resolve();
  let requestedTransition = transition;
  let creatingOffscreen = null;
  let capturedTabId = null;
  let capturedOffscreenEpoch = null;
  let activeStartController = null;
  let stopOperation = null;
  let sessionMetadataKnown = false;
  let currentSession = null;
  let sessionMetadataEpoch = 0;
  let catalogProfiles = [];
  let rosterModels = [];
  let deploymentVariants = [];
  let profileSelectionEpoch = 0;
  let activeProfileSelection = null;
  let generationControlEpoch = 0;
  const activeGenerationControls = new Set();
  let receiptStateKnown = false;
  let receiptRestoreError = null;
  let receiptPersistenceEpoch = 0;
  let receiptPersistence = Promise.resolve();
  const requestControllers = new Set();

  async function ensureReceiptState() {
    if (receiptStateKnown) {
      return;
    }
    const readEpoch = receiptPersistenceEpoch;
    const stored = await chromeApi.storage.session.get(EXP005_RECEIPT_STATE_KEY);
    if (receiptStateKnown || readEpoch !== receiptPersistenceEpoch) {
      return;
    }
    const value = stored?.[EXP005_RECEIPT_STATE_KEY];
    if (value !== undefined) {
      try {
        receiptRecorder.restore(value);
      } catch {
        receiptRestoreError = "persisted EXP-005 receipt state is corrupt";
      }
    }
    receiptStateKnown = true;
  }

  function queueReceiptPersistence(value, { remove = false } = {}) {
    const epoch = receiptPersistenceEpoch + 1;
    receiptPersistenceEpoch = epoch;
    const operation = receiptPersistence.then(async () => {
      if (epoch !== receiptPersistenceEpoch) {
        return;
      }
      if (remove) {
        await chromeApi.storage.session.remove(EXP005_RECEIPT_STATE_KEY);
      } else {
        await chromeApi.storage.session.set({
          [EXP005_RECEIPT_STATE_KEY]: value,
        });
      }
    });
    receiptPersistence = operation.catch(() => {});
    return operation;
  }

  function persistReceiptState() {
    return queueReceiptPersistence(receiptRecorder.checkpoint());
  }

  async function receiptTransition(method, value) {
    await ensureReceiptState();
    if (receiptRestoreError !== null) {
      throw new Error(receiptRestoreError);
    }
    const result = receiptRecorder[method](value);
    await persistReceiptState();
    return result;
  }

  function receiptIsActive() {
    return receiptRestoreError === null && receiptRecorder.active();
  }

  function generationControlIdentity() {
    if (
      !sessionMetadataKnown ||
      currentSession === null ||
      typeof currentSession.sessionId !== "string" ||
      typeof capturedOffscreenEpoch !== "string" ||
      generationId === null ||
      !Number.isInteger(capturedTabId)
    ) {
      return null;
    }
    return Object.freeze({
      sessionId: currentSession.sessionId,
      pipelineEpoch: capturedOffscreenEpoch,
      generationId,
      capturedTabId,
    });
  }

  function nextGenerationControlIdentity() {
    if (
      !sessionMetadataKnown ||
      currentSession === null ||
      typeof currentSession.sessionId !== "string" ||
      typeof capturedOffscreenEpoch !== "string" ||
      generationId !== null ||
      !Number.isInteger(capturedTabId)
    ) {
      return null;
    }
    return Object.freeze({
      sessionId: currentSession.sessionId,
      pipelineEpoch: capturedOffscreenEpoch,
      generationId: currentSession.generationId,
      capturedTabId,
      profileId: currentSession.profileId,
      modelId: currentSession.modelId,
      invocationMode: currentSession.invocationMode,
    });
  }

  function beginGenerationControl() {
    const control = {
      epoch: generationControlEpoch,
      canceled: false,
      identity: generationControlIdentity(),
    };
    activeGenerationControls.add(control);
    return control;
  }

  function beginNextGenerationControl() {
    const control = {
      epoch: generationControlEpoch,
      canceled: false,
      identity: nextGenerationControlIdentity(),
    };
    activeGenerationControls.add(control);
    return control;
  }

  function invalidateGenerationControls() {
    generationControlEpoch += 1;
    for (const control of activeGenerationControls) {
      control.canceled = true;
    }
  }

  function generationControlIsActive(control) {
    return (
      activeGenerationControls.has(control) &&
      !control.canceled &&
      control.epoch === generationControlEpoch
    );
  }

  function canceledGenerationControl() {
    const error = new Error("generation control was canceled by Stop");
    error.name = "AbortError";
    return error;
  }

  function requireActiveGenerationControl(control) {
    if (!generationControlIsActive(control)) {
      throw canceledGenerationControl();
    }
  }

  function bindGenerationControl(control) {
    requireActiveGenerationControl(control);
    const identity = generationControlIdentity();
    if (identity === null) {
      if (
        sessionMetadataKnown &&
        typeof currentSession?.sessionId === "string"
      ) {
        throw new Error("captured tab session binding is unavailable");
      }
      throw new Error("remote session identity is unavailable");
    }
    if (control.identity === null) {
      control.identity = identity;
    }
    return control.identity;
  }

  function requireCurrentGenerationControl(
    control,
    { terminalGenerationId } = {},
  ) {
    requireActiveGenerationControl(control);
    const identity = control.identity;
    const currentGenerationMatches =
      generationId === identity.generationId ||
      (terminalGenerationId !== undefined &&
        generationId === terminalGenerationId);
    if (
      capture !== "running" ||
      currentSession?.sessionId !== identity.sessionId ||
      currentSession?.generationId !== identity.generationId ||
      capturedOffscreenEpoch !== identity.pipelineEpoch ||
      capturedTabId !== identity.capturedTabId ||
      !currentGenerationMatches
    ) {
      throw canceledGenerationControl();
    }
  }

  function bindNextGenerationControl(control) {
    requireActiveGenerationControl(control);
    const identity = nextGenerationControlIdentity();
    if (identity === null) {
      throw new Error("next generation session identity is unavailable");
    }
    if (control.identity === null) {
      control.identity = identity;
    }
    return control.identity;
  }

  function requireCurrentNextGenerationIdentity(control) {
    requireActiveGenerationControl(control);
    const identity = control.identity;
    if (
      capture !== "running" ||
      currentSession?.sessionId !== identity.sessionId ||
      currentSession?.generationId !== identity.generationId ||
      currentSession?.profileId !== identity.profileId ||
      currentSession?.modelId !== identity.modelId ||
      currentSession?.invocationMode !== identity.invocationMode ||
      capturedOffscreenEpoch !== identity.pipelineEpoch ||
      capturedTabId !== identity.capturedTabId ||
      activeProfileSelection !== null
    ) {
      throw canceledGenerationControl();
    }
  }

  function requireCurrentNextGenerationControl(
    control,
    { nextGenerationId = null } = {},
  ) {
    requireCurrentNextGenerationIdentity(control);
    const atReadyBoundary = remote === "ready" && generationId === null;
    const loadingNext = remote === "loading" && generationId === null;
    const runningNext =
      (remote === "pending" || remote === "ready") &&
      generationId === nextGenerationId;
    if (
      nextGenerationId === null
        ? !atReadyBoundary
        : !(atReadyBoundary || loadingNext || runningNext)
    ) {
      throw canceledGenerationControl();
    }
  }

  function requireNextGenerationResponse(state, nextGenerationId) {
    if (
      state?.capture !== "running" ||
      state.route !== "native" ||
      state.remote !== "pending" ||
      state.generationId !== nextGenerationId
    ) {
      throw new Error("Offscreen returned an invalid next generation identity");
    }
  }

  function finishGenerationControl(control) {
    activeGenerationControls.delete(control);
  }

  function beginProfileSelection() {
    if (activeProfileSelection !== null) {
      throw new Error("profile selection is still in progress");
    }
    if (activeGenerationControls.size > 0) {
      throw new Error("generation control is still in progress");
    }
    let resolveCleanup;
    const cleanup = new Promise((resolve) => {
      resolveCleanup = resolve;
    });
    const selection = {
      epoch: profileSelectionEpoch + 1,
      canceled: false,
      resolveCleanup,
    };
    profileSelectionEpoch = selection.epoch;
    activeProfileSelection = selection;
    const precedingCleanup = cleanupBarrier;
    cleanupBarrier = Promise.allSettled([precedingCleanup, cleanup]).then(
      () => undefined,
    );
    return selection;
  }

  function invalidateProfileSelection() {
    profileSelectionEpoch += 1;
    if (activeProfileSelection !== null) {
      activeProfileSelection.canceled = true;
    }
  }

  function profileSelectionIsCurrent(selection) {
    return (
      activeProfileSelection === selection &&
      !selection.canceled &&
      selection.epoch === profileSelectionEpoch
    );
  }

  function requireCurrentProfileSelection(selection) {
    if (!profileSelectionIsCurrent(selection)) {
      const error = new Error("profile selection was canceled by Stop");
      error.name = "AbortError";
      throw error;
    }
  }

  function finishProfileSelection(selection) {
    if (activeProfileSelection === selection) {
      activeProfileSelection = null;
    }
    selection.resolveCleanup();
  }

  function createStartController() {
    const canceledMarker = Object.freeze({});
    let canceled = false;
    let cancel;
    const cancellation = new Promise((resolve) => {
      cancel = () => {
        if (!canceled) {
          canceled = true;
          resolve(canceledMarker);
        }
      };
    });
    return Object.freeze({
      cancel,
      get canceled() {
        return canceled;
      },
      async wait(operation) {
        return Promise.race([Promise.resolve(operation), cancellation]);
      },
      canceledMarker,
    });
  }

  async function waitForStart(controller, operation) {
    const result = await controller.wait(operation);
    if (result === controller.canceledMarker) {
      const error = new Error("capture start was canceled");
      error.name = "AbortError";
      throw error;
    }
    return result;
  }

  async function fetchWithDeadline(url, requestOptions, operation) {
    const controller = new AbortController();
    requestControllers.add(controller);
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimer(() => {
        controller.abort();
        const error = new Error(`${operation} timed out`);
        error.name = "TimeoutError";
        reject(error);
      }, requestTimeoutMilliseconds);
    });
    const aborted = new Promise((_, reject) => {
      controller.signal.addEventListener(
        "abort",
        () => {
          const error = new Error(`${operation} was canceled`);
          error.name = "AbortError";
          reject(error);
        },
        { once: true },
      );
    });
    try {
      return await Promise.race([
        Promise.resolve(fetchFn(url, { ...requestOptions, signal: controller.signal })),
        timeout,
        aborted,
      ]);
    } finally {
      clearTimer(timer);
      requestControllers.delete(controller);
    }
  }

  function abortRequests() {
    for (const controller of requestControllers) {
      controller.abort();
    }
  }

  async function activeTab(startController = null) {
    const operation = chromeApi.tabs.query({ active: true, currentWindow: true });
    const tabs = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const tab = tabs?.[0];
    const tabId = tab?.id;
    if (!Number.isInteger(tabId) || tabId < 0) {
      throw new Error("the active tab is unavailable");
    }
    return Object.freeze({ id: tabId, url: tab.url, audible: tab.audible });
  }

  async function activeTabId(startController = null) {
    return (await activeTab(startController)).id;
  }

  async function storedConfiguration(startController = null) {
    const sessionOperation = chromeApi.storage.session.get(CONFIGURATION_KEY);
    const sessionStored = startController
      ? await waitForStart(startController, sessionOperation)
      : await sessionOperation;
    const sessionConfiguration = sessionStored?.[CONFIGURATION_KEY] ?? null;
    if (sessionConfiguration) {
      await chromeApi.storage.local.set({
        [CONFIGURATION_KEY]: sessionConfiguration,
      });
      return sessionConfiguration;
    }
    const localOperation = chromeApi.storage.local.get(CONFIGURATION_KEY);
    const localStored = startController
      ? await waitForStart(startController, localOperation)
      : await localOperation;
    const localConfiguration = localStored?.[CONFIGURATION_KEY] ?? null;
    if (localConfiguration) {
      await chromeApi.storage.session.set({
        [CONFIGURATION_KEY]: localConfiguration,
      });
    }
    return localConfiguration;
  }

  async function persistConfiguration(configuration) {
    await chromeApi.storage.session.set({ [CONFIGURATION_KEY]: configuration });
    await chromeApi.storage.local.set({ [CONFIGURATION_KEY]: configuration });
  }

  async function activeSession(startController = null) {
    if (sessionMetadataKnown) {
      return currentSession;
    }
    const readEpoch = sessionMetadataEpoch;
    const operation = chromeApi.storage.session.get(ACTIVE_SESSION_KEY);
    const stored = startController
      ? await waitForStart(startController, operation)
      : await operation;
    if (!sessionMetadataKnown && sessionMetadataEpoch === readEpoch) {
      const recovered = stored?.[ACTIVE_SESSION_KEY] ?? null;
      currentSession = recovered ? Object.freeze({ ...recovered }) : null;
      sessionMetadataKnown = true;
    }
    return currentSession;
  }

  function persistSessionMetadata(session, epoch) {
    const operation = session
      ? chromeApi.storage.session.set({ [ACTIVE_SESSION_KEY]: session })
      : chromeApi.storage.session.remove(ACTIVE_SESSION_KEY);
    Promise.resolve(operation).then(
      () => {
        if (epoch !== sessionMetadataEpoch) {
          void reconcileSessionMetadata();
        }
      },
      () => {},
    );
    return operation;
  }

  function commitActiveSession(session) {
    currentSession = session ? Object.freeze({ ...session }) : null;
    sessionMetadataKnown = true;
    sessionMetadataEpoch += 1;
    return currentSession;
  }

  function setActiveSession(session) {
    const committedSession = commitActiveSession(session);
    return persistSessionMetadata(committedSession, sessionMetadataEpoch);
  }

  function clearActiveSession() {
    capturedTabId = null;
    capturedOffscreenEpoch = null;
    return setActiveSession(null);
  }

  async function restoreCapturedTab(state, startController = null) {
    if (state?.capture !== "running") {
      capturedTabId = null;
      capturedOffscreenEpoch = null;
      return;
    }
    if (
      Number.isInteger(capturedTabId) &&
      capturedTabId >= 0 &&
      typeof capturedOffscreenEpoch === "string" &&
      UUID.test(capturedOffscreenEpoch) &&
      capturedOffscreenEpoch === state.offscreenEpoch
    ) {
      return;
    }
    capturedTabId = null;
    capturedOffscreenEpoch = null;
    const session = await activeSession(startController);
    if (
      Number.isInteger(session?.capturedTabId) &&
      session.capturedTabId >= 0 &&
      typeof session?.offscreenEpoch === "string" &&
      UUID.test(session?.offscreenEpoch) &&
      session.offscreenEpoch === state.offscreenEpoch
    ) {
      capturedTabId = session.capturedTabId;
      capturedOffscreenEpoch = session.offscreenEpoch;
    }
  }

  async function reconcileSessionMetadata() {
    if (!sessionMetadataKnown) {
      return;
    }
    const epoch = sessionMetadataEpoch;
    const session = currentSession;
    try {
      await persistSessionMetadata(session, epoch);
    } catch {
      // The foreground mutation reports its own failure; stale repair is best effort.
    }
  }

  async function hasOffscreenDocument(startController = null) {
    const operation = chromeApi.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [chromeApi.runtime.getURL(OFFSCREEN_PATH)],
    });
    const contexts = startController
      ? await waitForStart(startController, operation)
      : await operation;
    return Array.isArray(contexts) && contexts.length > 0;
  }

  function cleanupCanceledStart(controller) {
    if (!controller.canceled || requestedCapture !== "stopped") {
      return;
    }
    const cleanup = async () => {
      if (!controller.canceled || requestedCapture !== "stopped") {
        return;
      }
      try {
        const operation = chromeApi.runtime.sendMessage({
          type: "offscreen.stop",
          target: "offscreen",
        });
        Promise.resolve(operation).catch(() => {});
      } catch {
        // A canceled start may settle after its Offscreen Document was closed.
      }
      if (!controller.canceled || requestedCapture !== "stopped") {
        return;
      }
      try {
        await chromeApi.offscreen.closeDocument();
      } catch {
        // Late cleanup is best effort when no Offscreen Document remains.
      }
    };
    const operation = cleanupBarrier.then(cleanup, cleanup);
    cleanupBarrier = operation;
  }

  async function waitForCleanupBarrier() {
    let pending;
    do {
      pending = cleanupBarrier;
      await pending;
    } while (pending !== cleanupBarrier);
  }

  async function ensureOffscreenDocument(startController) {
    if (await hasOffscreenDocument(startController)) {
      return;
    }
    if (!creatingOffscreen) {
      const creation = Promise.resolve(
        chromeApi.offscreen.createDocument({
          url: OFFSCREEN_PATH,
          reasons: ["USER_MEDIA"],
          justification:
            "Capture the selected tab and provide exclusive native or converted playout.",
        }),
      );
      creatingOffscreen = creation;
      creation.then(
        () => {
          if (creatingOffscreen === creation) {
            creatingOffscreen = null;
          }
          cleanupCanceledStart(startController);
        },
        () => {
          if (creatingOffscreen === creation) {
            creatingOffscreen = null;
          }
        },
      );
    }
    await waitForStart(startController, creatingOffscreen);
  }

  async function sendOffscreen(message, startController = null) {
    const operation = chromeApi.runtime.sendMessage({
      ...message,
      target: "offscreen",
    });
    if (startController && message.type === "offscreen.native.start") {
      Promise.resolve(operation).then(
        () => cleanupCanceledStart(startController),
        () => {},
      );
    }
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    if (!response?.ok) {
      throw new Error(response?.error ?? "Offscreen command failed");
    }
    return response.state;
  }

  async function fetchModelCatalog(configuration, startController = null) {
    const operation = fetchWithDeadline(
      `${configuration.gatewayUrl}/v1/models`,
      {
        method: "GET",
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        referrerPolicy: "no-referrer",
        headers: authorizedHeaders(configuration.token),
      },
      "model catalog",
    );
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const document = startController
      ? await waitForStart(
          startController,
          jsonResponse(response, "model catalog"),
        )
      : await jsonResponse(response, "model catalog");
    catalogProfiles = [...requireCatalogResponse(document)];
    return catalogProfiles;
  }

  async function fetchModelRoster(configuration, startController = null) {
    const operation = fetchWithDeadline(
      `${configuration.gatewayUrl}/v1/model-roster`,
      {
        method: "GET",
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        referrerPolicy: "no-referrer",
        headers: authorizedHeaders(configuration.token),
      },
      "model roster",
    );
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const document = startController
      ? await waitForStart(
          startController,
          jsonResponse(response, "model roster"),
        )
      : await jsonResponse(response, "model roster");
    return requireModelRosterResponse(document);
  }

  async function fetchDeploymentManifest(
    configuration,
    catalog,
    startController = null,
  ) {
    const operation = fetchWithDeadline(
      `${configuration.gatewayUrl}/v1/deployment-manifest`,
      {
        method: "GET",
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        referrerPolicy: "no-referrer",
        headers: authorizedHeaders(configuration.token),
      },
      "deployment manifest",
    );
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const document = startController
      ? await waitForStart(
          startController,
          jsonResponse(response, "deployment manifest"),
        )
      : await jsonResponse(response, "deployment manifest");
    return requireDeploymentManifestResponse(document, catalog);
  }

  async function fetchModelInventory(configuration, startController = null) {
    const catalog = await fetchModelCatalog(configuration, startController);
    const roster = await fetchModelRoster(configuration, startController);
    rosterModels = [...bindRosterToCatalog(roster, catalog)];
    return Object.freeze({ catalog, models: rosterModels, roster });
  }

  async function fetchRuntimeBoundary(configuration, startController = null) {
    const operation = fetchWithDeadline(
      `${configuration.gatewayUrl}/v1/runtime-boundary`,
      {
        method: "GET",
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        referrerPolicy: "no-referrer",
        headers: authorizedHeaders(configuration.token),
      },
      "runtime boundary",
    );
    const response = startController
      ? await waitForStart(startController, operation)
      : await operation;
    const document = startController
      ? await waitForStart(
          startController,
          jsonResponse(response, "runtime boundary"),
        )
      : await jsonResponse(response, "runtime boundary");
    return requireRuntimeBoundaryResponse(document);
  }

  function selectedRosterModel(profileId) {
    const model = rosterModels.find(
      (candidate) => candidate.profileId === profileId,
    );
    if (!model) {
      throw new Error(`profile ${profileId} is not in the current Gateway roster`);
    }
    if (model.executionState === "unavailable") {
      throw new Error(
        `model ${model.displayName} is unavailable: ${model.reasonCode}`,
      );
    }
    if (model.voiceRequirement === "authorized_target_required") {
      throw new Error(
        `model ${model.displayName} requires an authorized target voice`,
      );
    }
    if (!model.selectable || !model.profile?.compatible) {
      throw new Error(`profile ${profileId} is not compatible with audio route v1`);
    }
    return model;
  }

  function deploymentVariantModel(variant) {
    return Object.freeze({
      modelId: variant.variantId,
      variantId: variant.variantId,
      familyId: variant.familyId,
      displayName: variant.displayName,
      targetPresentation: variant.targetPresentation,
      profileId: variant.profileId,
      invocationMode: variant.invocationMode,
      executionState:
        variant.invocationMode === "live" ? "live-trial" : "buffered-preview",
      decisionState: "unassessed",
      voiceRequirement: variant.profile.voiceRequirement,
      reasonCode: null,
      selectable: true,
      profile: variant.profile,
    });
  }

  function selectedVoiceModel(profileId) {
    const variant = deploymentVariants.find(
      (candidate) => candidate.profileId === profileId,
    );
    return variant ?? selectedRosterModel(profileId);
  }

  async function listModels(configurationValue = null) {
    const configuration = configurationValue
      ? normalizeConfiguration(configurationValue)
      : await storedConfiguration();
    if (!configuration) {
      throw new Error("configure Gateway credentials before loading profiles");
    }
    return fetchModelInventory(configuration);
  }

  async function listVariants(configurationValue = null) {
    const configuration = configurationValue
      ? normalizeConfiguration(configurationValue)
      : await storedConfiguration();
    if (!configuration) {
      throw new Error("configure Gateway credentials before loading variants");
    }
    const catalog = await fetchModelCatalog(configuration);
    const deployment = await fetchDeploymentManifest(configuration, catalog);
    deploymentVariants = deployment.variants.map(deploymentVariantModel);
    return Object.freeze({
      catalog,
      deployment,
      variants: deploymentVariants,
    });
  }

  async function createGatewaySession(
    configuration,
    profile,
    startController,
  ) {
    const response = await waitForStart(
      startController,
      fetchWithDeadline(
        `${configuration.gatewayUrl}/v1/sessions`,
        {
          method: "POST",
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          referrerPolicy: "no-referrer",
          headers: authorizedHeaders(configuration.token),
          body: JSON.stringify({
            protocol_version: 1,
            profile_id: configuration.profileId,
            input: {
              sample_rate: 48_000,
              channels: 1,
              sample_format: "f32le",
              frame_ms: 20,
            },
            voice_id: null,
          }),
        },
        "session creation",
      ),
    );
    return requireSessionResponse(
      await waitForStart(
        startController,
        jsonResponse(response, "session creation"),
      ),
      profile,
    );
  }

  async function deleteGatewaySession(session, knownConfiguration = null) {
    if (!session) {
      return;
    }
    const configuration =
      knownConfiguration ?? (await storedConfiguration());
    if (!configuration || configuration.gatewayUrl !== session.gatewayUrl) {
      return;
    }
    try {
      await fetchWithDeadline(
        `${session.gatewayUrl}/v1/sessions/${encodeURIComponent(session.sessionId)}`,
        {
          method: "DELETE",
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          referrerPolicy: "no-referrer",
          headers: authorizedHeaders(configuration.token),
        },
        "session deletion",
      );
    } catch {
      // The local stop path remains authoritative when remote cleanup is unavailable.
    }
  }

  async function compensateCanceledGatewaySession(
    configuration,
    gatewaySession,
  ) {
    if (!gatewaySession) {
      return;
    }
    const session = {
      gatewayUrl: configuration.gatewayUrl,
      sessionId: gatewaySession.session_id,
    };
    await Promise.all([
      deleteGatewaySession(session, configuration),
      reconcileSessionMetadata(),
    ]);
  }

  async function synchronize(startController = null) {
    if (!(await hasOffscreenDocument(startController))) {
      if (capture !== "starting" && capture !== "stopping") {
        capture = "stopped";
        route = "native";
        remote = "disconnected";
        generationId = null;
        capturedTabId = null;
        capturedOffscreenEpoch = null;
      }
      return;
    }
    try {
      const state = await sendOffscreen(
        { type: "offscreen.status" },
        startController,
      );
      capture = state.capture;
      route = state.route;
      remote = state.remote;
      generationId = state.generationId ?? null;
      await restoreCapturedTab(state, startController);
    } catch (error) {
      if (startController?.canceled) {
        throw error;
      }
      route = "native";
    }
  }

  async function snapshot({ synchronizeState = false, knownConfiguration } = {}) {
    if (synchronizeState) {
      await synchronize();
    }
    const configuration =
      knownConfiguration === undefined
        ? await storedConfiguration()
        : knownConfiguration;
    const state = {
      capture,
      route,
      remote,
      generationId,
      configuration: publicConfiguration(configuration),
    };
    if (lastError !== null) {
      state.lastError = lastError;
    }
    return Object.freeze(state);
  }

  async function notifyPopup(state) {
    try {
      await chromeApi.runtime.sendMessage({
        target: "popup",
        type: "session.state",
        state,
      });
    } catch {
      // The popup is usually closed; its next status request resynchronizes state.
    }
  }

  async function notifyConversionProgress(progress) {
    try {
      await chromeApi.runtime.sendMessage({
        target: "popup",
        type: "conversion.progress",
        progress,
      });
    } catch {
      // The popup is usually closed; the next progress event updates it.
    }
  }

  async function configure(value) {
    let candidate = value;
    if (
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      value.token === ""
    ) {
      const existing = await storedConfiguration();
      const requestedGateway = normalizeGatewayUrl(value.gatewayUrl);
      if (!existing || existing.gatewayUrl !== requestedGateway) {
        throw new Error("a token is required for a new Gateway");
      }
      candidate = { ...value, token: existing.token };
    }
    const configuration = normalizeConfiguration(candidate);
    await waitForCleanupBarrier();
    await synchronize();
    if (capture !== "stopped") {
      throw new Error("configuration can change only while capture is stopped");
    }
    if (rosterModels.length > 0 || deploymentVariants.length > 0) {
      selectedVoiceModel(configuration.profileId);
    }
    await persistConfiguration(configuration);
    lastError = null;
    // The successful storage write is the authoritative configuration commit.
    // Avoid a second read turning that committed result into an ambiguous failure
    // for the optional-host-permission transaction in the popup.
    return snapshot({ knownConfiguration: configuration });
  }

  async function performStart(startController, { userGesture }) {
    capture = "starting";
    lastError = null;
    try {
      await ensureReceiptState();
      if (receiptRestoreError !== null) {
        throw new Error(receiptRestoreError);
      }
      await ensureOffscreenDocument(startController);
      if (receiptIsActive()) {
        await sendOffscreen(
          { type: "offscreen.receipt.configure", enabled: true },
          startController,
        );
      }
      const tab = await activeTab(startController);
      const tabId = tab.id;
      const streamId = await waitForStart(
        startController,
        chromeApi.tabCapture.getMediaStreamId({ targetTabId: tabId }),
      );
      if (typeof streamId !== "string" || streamId.length === 0) {
        throw new Error("tabCapture returned an invalid stream ID");
      }
      const nativeState = await sendOffscreen(
        {
          type: "offscreen.native.start",
          streamId,
          tabId,
        },
        startController,
      );
      if (!UUID.test(nativeState?.offscreenEpoch)) {
        throw new Error("Offscreen returned an invalid capture epoch");
      }
      capturedTabId = tabId;
      capturedOffscreenEpoch = nativeState.offscreenEpoch;
      capture = "running";
      route = "native";
      if (receiptIsActive()) {
        await receiptTransition("observeCaptureStarted", {
          tabUrl: tab.url,
          tabAudible: tab.audible,
          userGesture,
        });
      }

      const configuration = await storedConfiguration(startController);
      if (!configuration) {
        remote = "disabled";
        return;
      }

      remote = "connecting";
      let gatewaySession = null;
      try {
        const inventory = await fetchModelInventory(configuration, startController);
        if (
          !rosterModels.some(
            (candidate) => candidate.profileId === configuration.profileId,
          )
        ) {
          const deployment = await fetchDeploymentManifest(
            configuration,
            inventory.catalog,
            startController,
          );
          deploymentVariants = deployment.variants.map(deploymentVariantModel);
        }
        if (receiptIsActive()) {
          const boundary = await fetchRuntimeBoundary(configuration, startController);
          await receiptTransition("observeGatewayBoundary", {
            protocol_version: boundary.protocolVersion,
            transport_scope: boundary.transportScope,
            max_sessions: boundary.maxSessions,
            ticket_one_use: boundary.ticketOneUse,
          });
        }
        const model = selectedVoiceModel(configuration.profileId);
        const profile = model.profile;
        gatewaySession = await createGatewaySession(
          configuration,
          profile,
          startController,
        );
        if (receiptIsActive()) {
          await receiptTransition("observeGatewaySession", {
            gatewayUrl: configuration.gatewayUrl,
            sessionId: gatewaySession.session_id,
            ticket: gatewaySession.ticket,
            pipelineId: gatewaySession.pipeline_id,
            profileId: gatewaySession.profile_id,
            profileHash: gatewaySession.profile_hash,
            configurationHash: gatewaySession.configuration_hash,
          });
        }
        const previous = await activeSession(startController);
        const nextGenerationId = Math.max(previous?.generationId ?? 0, 0) + 1;
        const session = {
          gatewayUrl: configuration.gatewayUrl,
          sessionId: gatewaySession.session_id,
          generationId: nextGenerationId,
          profileId: profile.profileId,
          modelId: model.modelId,
          invocationMode: model.invocationMode,
          capturedTabId: tabId,
          offscreenEpoch: capturedOffscreenEpoch,
        };
        const sessionWrite = setActiveSession(session);
        await waitForStart(
          startController,
          sessionWrite,
        );
        generationId = nextGenerationId;
        await sendOffscreen(
          {
            type: "offscreen.remote.connect",
            url: websocketUrl(
              configuration.gatewayUrl,
              gatewaySession.websocket_path,
            ),
            sessionId: gatewaySession.session_id,
            ticket: gatewaySession.ticket,
            generationId: nextGenerationId,
            expectedProfile: expectedProfileIdentity(
              profile,
              gatewaySession.pipeline_id,
            ),
            expectedLimits: {
              ingressBudgetMs: gatewaySession.limits.ingress_budget_ms,
              maxIngressFrames: gatewaySession.limits.max_ingress_frames,
            },
            invocationMode: model.invocationMode,
          },
          startController,
        );
        remote = "pending";
      } catch (error) {
        if (startController.canceled) {
          await compensateCanceledGatewaySession(
            configuration,
            gatewaySession,
          );
          throw error;
        }
        route = "native";
        remote = "degraded";
        generationId = null;
        lastError = errorMessage(error);
        const session = gatewaySession
          ? {
              gatewayUrl: configuration.gatewayUrl,
              sessionId: gatewaySession.session_id,
            }
          : null;
        await deleteGatewaySession(session);
        await clearActiveSession();
      }
    } catch (error) {
      if (startController.canceled) {
        return;
      }
      capture = "stopped";
      route = "native";
      remote = "disconnected";
      generationId = null;
      try {
        await clearActiveSession();
      } catch {
        // Preserve the capture failure while the metadata epoch prevents stale repair.
      }
      lastError = errorMessage(error);
      if (await hasOffscreenDocument()) {
        try {
          await sendOffscreen({ type: "offscreen.stop" });
        } catch {
          // Preserve the original capture failure.
        }
        await chromeApi.offscreen.closeDocument();
      }
      throw error;
    }
  }

  function start({ userGesture = false } = {}) {
    if (userGesture !== true) {
      return Promise.reject(
        new TypeError("capture start requires an explicit user gesture"),
      );
    }
    if (requestedCapture === "running") {
      return requestedTransition;
    }
    requestedCapture = "running";
    const startController = createStartController();
    activeStartController = startController;
    const run = async () => {
      try {
        if (startController.canceled || requestedCapture !== "running") {
          return;
        }
        await synchronize(startController);
        if (startController.canceled || requestedCapture !== "running") {
          return;
        }
        if (capture === "running") {
          return;
        }
        await performStart(startController, { userGesture });
      } catch (error) {
        if (startController.canceled) {
          return;
        }
        if (requestedCapture === "running") {
          requestedCapture = "stopped";
        }
        throw error;
      } finally {
        if (activeStartController === startController) {
          activeStartController = null;
        }
      }
    };
    const runAfterCleanup = async () => {
      await waitForCleanupBarrier();
      return run();
    };
    const operation = transition.then(runAfterCleanup, runAfterCleanup);
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  async function stopOffscreenDocument() {
    if (!(await hasOffscreenDocument())) {
      return;
    }
    let stopError = null;
    try {
      await sendOffscreen({ type: "offscreen.stop" });
    } catch (error) {
      stopError = error;
    }
    try {
      await chromeApi.offscreen.closeDocument();
    } catch (error) {
      if (stopError === null) {
        stopError = error;
      }
    }
    if (stopError !== null) {
      throw stopError;
    }
  }

  async function performStop() {
    capture = "stopping";
    route = "native";
    remote = "disconnected";
    generationId = null;
    let session = null;
    const failures = [];
    const recordFailure = async (operation) => {
      try {
        return await operation();
      } catch (error) {
        failures.push(error);
        return undefined;
      }
    };
    try {
      // Local native fallback and teardown are authoritative. Never serialize
      // them behind best-effort metadata recovery after an MV3 restart.
      await recordFailure(stopOffscreenDocument);
      session = await recordFailure(activeSession);
      await recordFailure(() => deleteGatewaySession(session));
    } finally {
      await recordFailure(clearActiveSession);
      capture = "stopped";
      route = "native";
      remote = "disconnected";
      generationId = null;
      lastError = null;
    }
    if (failures.length > 0) {
      throw failures[0];
    }
  }

  function stop() {
    requestedCapture = "stopped";
    activeStartController?.cancel();
    invalidateProfileSelection();
    invalidateGenerationControls();
    if (stopOperation) {
      return stopOperation;
    }
    abortRequests();
    const operation = performStop().finally(() => {
      stopOperation = null;
    });
    stopOperation = operation;
    transition = operation;
    requestedTransition = operation;
    return operation;
  }

  async function generationCommand(type) {
    const control = beginGenerationControl();
    try {
      await synchronize();
      requireActiveGenerationControl(control);
      if (capture !== "running" || generationId === null) {
        throw new Error("no remote generation is active");
      }
      const identity = bindGenerationControl(control);
      requireCurrentGenerationControl(control);
      const selectedTabId = await activeTabId();
      requireCurrentGenerationControl(control);
      if (selectedTabId !== identity.capturedTabId) {
        throw new Error("generation commands must originate from the captured tab");
      }
      const state = await sendOffscreen({
        type,
        generationId: identity.generationId,
      });
      requireCurrentGenerationControl(control, {
        terminalGenerationId: state.generationId ?? null,
      });
      route = state.route;
      remote = state.remote;
      generationId = state.generationId ?? null;
      return state;
    } finally {
      finishGenerationControl(control);
    }
  }

  async function injectExp005Failure() {
    await ensureReceiptState();
    if (receiptRestoreError !== null || !receiptIsActive()) {
      throw new Error(receiptRestoreError ?? "EXP-005 trial has not begun");
    }
    const control = beginGenerationControl();
    try {
      await synchronize();
      requireActiveGenerationControl(control);
      if (capture !== "running" || generationId === null) {
        throw new Error("no remote generation is active");
      }
      const identity = bindGenerationControl(control);
      requireCurrentGenerationControl(control);
      const selectedTabId = await activeTabId();
      requireCurrentGenerationControl(control);
      if (selectedTabId !== identity.capturedTabId) {
        throw new Error("failure injection must originate from the captured tab");
      }
      if (!receiptRecorder.authorizeFailureInjection({
        generationId: identity.generationId,
      })) {
        throw new Error("EXP-005 failure probe is not ready for explicit injection");
      }
      const state = await sendOffscreen({
        type: "offscreen.exp005.inject-failure",
        generationId: identity.generationId,
      });
      requireCurrentGenerationControl(control, {
        terminalGenerationId: state.generationId ?? null,
      });
      route = state.route;
      remote = state.remote;
      generationId = state.generationId ?? null;
      return state;
    } finally {
      finishGenerationControl(control);
    }
  }

  async function startNextGeneration() {
    if (activeProfileSelection !== null) {
      throw new Error("profile selection is still in progress");
    }
    const control = beginNextGenerationControl();
    try {
      await synchronize();
      requireActiveGenerationControl(control);
      if (
        capture !== "running" ||
        remote !== "ready" ||
        generationId !== null
      ) {
        throw new Error(
          "remote transport is not available; remote is not ready for the next generation",
        );
      }
      const identity = bindNextGenerationControl(control);
      requireCurrentNextGenerationControl(control);
      if ((await activeTabId()) !== identity.capturedTabId) {
        throw new Error("generation commands must originate from the captured tab");
      }
      requireCurrentNextGenerationControl(control);
      const session = await activeSession();
      requireCurrentNextGenerationControl(control);
      const configuration = await storedConfiguration();
      requireCurrentNextGenerationControl(control);
      if (
        !configuration ||
        session.gatewayUrl !== configuration.gatewayUrl ||
        session.profileId !== configuration.profileId
      ) {
        throw new Error("remote session metadata does not match the selected configuration");
      }
      if (rosterModels.length === 0) {
        await fetchModelInventory(configuration);
        requireCurrentNextGenerationControl(control);
      }
      const model = selectedVoiceModel(configuration.profileId);
      if (
        session.modelId !== model.modelId ||
        session.invocationMode !== model.invocationMode ||
        identity.profileId !== model.profileId ||
        identity.modelId !== model.modelId ||
        identity.invocationMode !== model.invocationMode
      ) {
        throw new Error("remote session metadata does not match the selected model");
      }
      const nextGenerationId = identity.generationId + 1;
      const nextSession = Object.freeze({
        ...session,
        generationId: nextGenerationId,
      });

      const compensateStartedGeneration = async () => {
        try {
          requireCurrentNextGenerationIdentity(control);
        } catch {
          await reconcileSessionMetadata();
          return;
        }
        let canceledState;
        try {
          canceledState = await sendOffscreen({
            type: "offscreen.generation.cancel",
            generationId: nextGenerationId,
          });
        } catch {
          try {
            requireCurrentNextGenerationIdentity(control);
          } catch {
            await reconcileSessionMetadata();
            return;
          }
          try {
            await stop();
          } catch {
            // Stop remains authoritative even when remote cleanup reports failure.
          }
          return;
        }
        try {
          requireCurrentNextGenerationIdentity(control);
        } catch {
          await reconcileSessionMetadata();
          return;
        }
        if (
          canceledState?.capture !== "running" ||
          canceledState.route !== "native" ||
          canceledState.remote !== "ready" ||
          canceledState.generationId !== null
        ) {
          try {
            await stop();
          } catch {
            // An invalid compensation response cannot leave remote playout trusted.
          }
          return;
        }
        route = canceledState.route;
        remote = canceledState.remote;
        generationId = null;
        await reconcileSessionMetadata();
      };

      let startDispatched = false;
      let state;
      try {
        startDispatched = true;
        state = await sendOffscreen({
          type: "offscreen.generation.start",
          generationId: nextGenerationId,
          invocationMode: identity.invocationMode,
        });
        requireCurrentNextGenerationControl(control, { nextGenerationId });
        requireNextGenerationResponse(state, nextGenerationId);
        await chromeApi.storage.session.set({
          [ACTIVE_SESSION_KEY]: nextSession,
        });
        requireCurrentNextGenerationControl(control, { nextGenerationId });
      } catch (error) {
        if (startDispatched) {
          await compensateStartedGeneration();
        }
        throw error;
      }
      commitActiveSession(nextSession);
      if (
        generationId === null &&
        (remote === "ready" || remote === "loading")
      ) {
        route = state.route;
        remote = state.remote;
        generationId = state.generationId;
      }
      return state;
    } finally {
      finishGenerationControl(control);
    }
  }

  async function selectProfile(profileId) {
    if (typeof profileId !== "string" || !PROFILE_ID.test(profileId)) {
      throw new TypeError("profileId has an invalid format");
    }
    const selection = beginProfileSelection();
    let configuration = null;
    let previousSession = null;
    let storageMutationStarted = false;
    let cancellationCompensated = false;

    const compensateCanceledSelection = async () => {
      if (cancellationCompensated || !storageMutationStarted) {
        return;
      }
      cancellationCompensated = true;
      const failures = [];
      try {
        await persistConfiguration(configuration);
      } catch (error) {
        failures.push(error);
      }
      if (sessionMetadataKnown) {
        const metadataEpoch = sessionMetadataEpoch;
        try {
          await persistSessionMetadata(currentSession, metadataEpoch);
        } catch (error) {
          failures.push(error);
        }
      }
      if (failures.length > 0) {
        throw new Error(
          `canceled profile selection cleanup failed: ${failures
            .map(errorMessage)
            .join("; ")}`,
        );
      }
    };

    const throwIfCanceled = async () => {
      if (profileSelectionIsCurrent(selection)) {
        return;
      }
      await compensateCanceledSelection();
      requireCurrentProfileSelection(selection);
    };

    try {
      await synchronize();
      requireCurrentProfileSelection(selection);
      if (
        capture !== "running" ||
        remote !== "ready" ||
        generationId !== null
      ) {
        throw new Error(
          "profile selection is allowed only at a ready generation boundary",
        );
      }
      const selectedTabId = await activeTabId();
      requireCurrentProfileSelection(selection);
      if (selectedTabId !== capturedTabId) {
        throw new Error("profile selection must originate from the captured tab");
      }
      configuration = await storedConfiguration();
      requireCurrentProfileSelection(selection);
      if (!configuration) {
        throw new Error("session configuration is unavailable");
      }
      if (rosterModels.length === 0) {
        await fetchModelInventory(configuration);
        requireCurrentProfileSelection(selection);
      }
      const previousModel = selectedVoiceModel(configuration.profileId);
      previousSession = await activeSession();
      requireCurrentProfileSelection(selection);
      if (
        !previousSession ||
        previousSession.gatewayUrl !== configuration.gatewayUrl ||
        previousSession.profileId !== previousModel.profileId ||
        previousSession.modelId !== previousModel.modelId ||
        previousSession.invocationMode !== previousModel.invocationMode
      ) {
        throw new Error("remote session metadata does not match the active model");
      }
      const model = selectedVoiceModel(profileId);
      const profile = model.profile;
      const nextConfiguration = Object.freeze({
        ...configuration,
        profileId: profile.profileId,
      });
      const nextSession = Object.freeze({
        ...previousSession,
        profileId: profile.profileId,
        modelId: model.modelId,
        invocationMode: model.invocationMode,
      });

      remote = "selecting";
      let selectedState;
      try {
        selectedState = await sendOffscreen({
          type: "offscreen.model.select",
          expectedProfile: expectedProfileIdentity(profile),
          invocationMode: model.invocationMode,
        });
        await throwIfCanceled();
        if (
          selectedState.capture !== "running" ||
          selectedState.remote !== "ready" ||
          selectedState.generationId !== null
        ) {
          throw new Error("Offscreen did not confirm a ready profile selection");
        }
        storageMutationStarted = true;
        await chromeApi.storage.session.set({
          [CONFIGURATION_KEY]: nextConfiguration,
          [ACTIVE_SESSION_KEY]: nextSession,
        });
        await chromeApi.storage.local.set({
          [CONFIGURATION_KEY]: nextConfiguration,
        });
        await throwIfCanceled();
      } catch (error) {
        if (!profileSelectionIsCurrent(selection)) {
          await compensateCanceledSelection();
          requireCurrentProfileSelection(selection);
        }
        const rollbackFailures = [];
        try {
          const rollbackState = await sendOffscreen({
            type: "offscreen.model.select",
            expectedProfile: expectedProfileIdentity(previousModel.profile),
            invocationMode: previousModel.invocationMode,
          });
          await throwIfCanceled();
          if (
            rollbackState.capture !== "running" ||
            rollbackState.remote !== "ready" ||
            rollbackState.generationId !== null
          ) {
            throw new Error("Offscreen did not confirm rollback to the active profile");
          }
          capture = rollbackState.capture;
          route = rollbackState.route;
          remote = rollbackState.remote;
          generationId = null;
        } catch (rollbackError) {
          rollbackFailures.push(rollbackError);
        }
        try {
          await chromeApi.storage.session.set({
            [CONFIGURATION_KEY]: configuration,
            [ACTIVE_SESSION_KEY]: previousSession,
          });
          await chromeApi.storage.local.set({
            [CONFIGURATION_KEY]: configuration,
          });
          await throwIfCanceled();
        } catch (rollbackError) {
          if (!profileSelectionIsCurrent(selection)) {
            await compensateCanceledSelection();
            requireCurrentProfileSelection(selection);
          }
          rollbackFailures.push(rollbackError);
        }
        if (rollbackFailures.length > 0) {
          try {
            await stop();
          } catch (stopError) {
            rollbackFailures.push(stopError);
          }
          throw new Error(
            `profile selection failed and rollback was incomplete: ${rollbackFailures
              .map(errorMessage)
              .join("; ")}`,
          );
        }
        throw error;
      }

      requireCurrentProfileSelection(selection);
      capture = selectedState.capture;
      route = selectedState.route;
      remote = selectedState.remote;
      generationId = null;
      commitActiveSession(nextSession);
      lastError = null;
      return Object.freeze({
        state: selectedState,
        configuration: nextConfiguration,
      });
    } finally {
      finishProfileSelection(selection);
    }
  }

  async function observeReceiptRuntimeEvent(value) {
    await ensureReceiptState();
    if (!receiptIsActive() || value === null || typeof value !== "object") {
      return;
    }
    try {
      const extensionUrl = chromeApi.runtime.getURL("");
      const extensionOrigin = extensionUrl.match(
        /^(chrome-extension:\/\/[a-p]{32})(?:\/|$)/,
      )?.[1];
      switch (value.type) {
        case "gateway.attached":
          await receiptTransition("observeGatewayAttached", {
            sessionId: value.sessionId,
            pipelineId: value.pipelineId,
            profileId: value.profileId,
            profileHash: value.profileHash,
            configurationHash: value.configurationHash,
            extensionOrigin,
          });
          break;
        case "generation.ready":
          await receiptTransition("startAttempt", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            profileId: value.profileId,
            profileHash: value.profileHash,
            configurationHash: value.configurationHash,
          });
          break;
        case "generation.output":
          await receiptTransition("observeOutput", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            finite: value.finite,
            changed: value.changed,
          });
          break;
        case "remote.playout":
          await receiptTransition("observeRemotePlayout", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            nativeAudible: value.nativeAudible,
            remoteAudible: value.remoteAudible,
          });
          break;
        case "generation.terminal":
          await receiptTransition("observeGenerationTerminal", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            endTriggered: value.endTriggered,
          });
          break;
        case "generation.stale-output":
          await receiptTransition("observeStaleOutputAccepted", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            accepted: value.accepted,
          });
          break;
        case "fallback.required":
          await receiptTransition("observeForcedFallback", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            injected: value.injected,
          });
          break;
        case "native.fallback":
          await receiptTransition("observeNativeFallback", {
            generationId: value.generationId,
            pipelineId: value.pipelineId,
            nativeAudible: value.nativeAudible,
            remoteAudible: value.remoteAudible,
          });
          break;
        default:
          await receiptTransition(
            "invalidate",
            "offscreen emitted an unsupported EXP-005 receipt event",
          );
      }
    } catch {
      if (receiptIsActive()) {
        try {
          await receiptTransition(
            "invalidate",
            "offscreen receipt event could not be validated",
          );
        } catch {
          // A corrupt or unpersistable receipt remains fail-closed.
        }
      }
    }
  }

  async function handleMessage(message, sender) {
    if (sender?.id !== chromeApi.runtime.id) {
      return null;
    }
    const popupUrl = chromeApi.runtime.getURL("popup/popup.html");
    const offscreenUrl = chromeApi.runtime.getURL(OFFSCREEN_PATH);
    const isOffscreenEvent =
      message?.target === "background" && message?.type === "offscreen.event";
    if (
      (isOffscreenEvent && sender.url !== offscreenUrl) ||
      (!isOffscreenEvent && message?.target !== "offscreen" && sender.url !== popupUrl)
    ) {
      return null;
    }
    if (message?.target === "offscreen") {
      return null;
    }
    if (message?.target === "background" && message.type === "offscreen.event") {
      const event = message.event ?? {};
      await observeReceiptRuntimeEvent(event.receipt);
      if (
        event.progress !== null &&
        typeof event.progress === "object" &&
        Number.isInteger(event.progress.generationId) &&
        Number.isSafeInteger(event.progress.inputFrames) &&
        event.progress.inputFrames >= 0 &&
        Number.isSafeInteger(event.progress.outputFrames) &&
        event.progress.outputFrames >= 0
      ) {
        await notifyConversionProgress({
          generationId: event.progress.generationId,
          inputFrames: event.progress.inputFrames,
          outputFrames: event.progress.outputFrames,
        });
      }
      if (event.route === "native" || event.route === "remote") {
        route = event.route;
      }
      if (typeof event.remote === "string") {
        remote = event.remote;
      }
      if (event.generationId === null || Number.isInteger(event.generationId)) {
        generationId = event.generationId;
      }
      if (typeof event.error === "string") {
        lastError = event.error;
      }
      if (event.sourceEnded === true) {
        await stop();
      }
      const state = await snapshot();
      await notifyPopup(state);
      return { ok: true, state };
    }

    try {
      if (message?.type === "exp005.trial.begin") {
        await ensureReceiptState();
        if (receiptRestoreError !== null) {
          throw new Error(`${receiptRestoreError}; clear it before beginning a new trial`);
        }
        await synchronize();
        if (capture !== "stopped") {
          throw new Error("EXP-005 trial must begin before capture starts");
        }
        const receipt = receiptRecorder.begin(message.trial);
        receiptStateKnown = true;
        await persistReceiptState();
        if (await hasOffscreenDocument()) {
          await sendOffscreen({ type: "offscreen.receipt.configure", enabled: true });
        }
        return {
          ok: true,
          receipt,
          state: await snapshot(),
        };
      }
      if (message?.type === "exp005.trial.export") {
        await ensureReceiptState();
        if (receiptRestoreError !== null) {
          throw new Error(receiptRestoreError);
        }
        const receipt = receiptRecorder.exportReceipt();
        if (await hasOffscreenDocument()) {
          await sendOffscreen({ type: "offscreen.receipt.configure", enabled: false });
        }
        return { ok: true, receipt };
      }
      if (message?.type === "exp005.trial.clear") {
        await ensureReceiptState();
        if (await hasOffscreenDocument()) {
          await sendOffscreen({ type: "offscreen.receipt.configure", enabled: false });
        }
        if (receiptRecorder.active()) {
          receiptRecorder.clear();
        }
        receiptRestoreError = null;
        receiptStateKnown = true;
        await queueReceiptPersistence(null, { remove: true });
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "exp005.trial.inject-failure") {
        await injectExp005Failure();
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "session.status") {
        return { ok: true, state: await snapshot({ synchronizeState: true }) };
      }
      if (message?.type === "models.list") {
        const inventory = await listModels(message.configuration ?? null);
        return {
          ok: true,
          state: await snapshot(),
          models: inventory.models,
          profiles: inventory.catalog,
        };
      }
      if (message?.type === "variants.list") {
        const inventory = await listVariants(message.configuration ?? null);
        return {
          ok: true,
          state: await snapshot(),
          bundle: {
            bundleId: inventory.deployment.bundleId,
            bundleRevision: inventory.deployment.bundleRevision,
          },
          variants: inventory.variants,
          profiles: inventory.catalog,
        };
      }
      if (message?.type === "session.configure") {
        return {
          ok: true,
          state: await configure(message.configuration),
          models: rosterModels,
          profiles: catalogProfiles,
        };
      }
      if (message?.type === "session.start") {
        await start({ userGesture: message.userGesture === true });
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "session.stop") {
        await stop();
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.start") {
        await startNextGeneration();
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.end") {
        await generationCommand("offscreen.generation.end");
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "generation.cancel") {
        await generationCommand("offscreen.generation.cancel");
        return { ok: true, state: await snapshot() };
      }
      if (message?.type === "model.select") {
        const selection = await selectProfile(message.profileId);
        return {
          ok: true,
          state: await snapshot({ knownConfiguration: selection.configuration }),
          models: rosterModels,
          profiles: catalogProfiles,
        };
      }
      return null;
    } catch (error) {
      const message = errorMessage(error);
      if (error?.name !== "AbortError") {
        lastError = message;
      }
      return { ok: false, state: await snapshot(), error: message };
    }
  }

  return Object.freeze({ configure, handleMessage, snapshot, start, stop });
}

export function installBrowserMessageListener(runtime, chromeApi) {
  requireMethod(
    chromeApi?.runtime?.onMessage,
    "chrome.runtime.onMessage",
    "addListener",
  );
  const listener = (message, sender, sendResponse) => {
    const popupUrl = chromeApi.runtime.getURL("popup/popup.html");
    const offscreenUrl = chromeApi.runtime.getURL(OFFSCREEN_PATH);
    const expectedUrl =
      message?.target === "background" && message?.type === "offscreen.event"
        ? offscreenUrl
        : popupUrl;
    if (
      sender?.id !== chromeApi.runtime.id ||
      sender.url !== expectedUrl ||
      message?.target === "offscreen" ||
      (message?.target === "background" && message?.type !== "offscreen.event")
    ) {
      return false;
    }
    Promise.resolve(runtime.handleMessage(message, sender)).then(
      (response) => sendResponse(response),
      (error) => sendResponse({ ok: false, error: errorMessage(error) }),
    );
    return true;
  };
  chromeApi.runtime.onMessage.addListener(listener);
  return listener;
}

export const sessionStorageKeys = Object.freeze({
  activeSession: ACTIVE_SESSION_KEY,
  configuration: CONFIGURATION_KEY,
  exp005ReceiptState: EXP005_RECEIPT_STATE_KEY,
});
