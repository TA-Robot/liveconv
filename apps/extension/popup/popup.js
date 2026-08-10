import {
  gatewayPermissionOrigin,
  normalizeGatewayUrl,
  replaceGatewayPermission,
} from "../src/gateway-url.js";
import { derivePopupView } from "./popup-state.js";

const LIVE_VOICES = Object.freeze({
  "vc.rvc.synthetic-ja.v1": Object.freeze({
    name: "RVC v2",
    option: "RVC v2（リアルタイム）",
  }),
  "vc.beatrice.synthetic-ja.v1": Object.freeze({
    name: "Beatrice 2・低めの声",
    option: "Beatrice 2・低め（リアルタイム）",
  }),
  "vc.x-vc.synthetic-ja.v1": Object.freeze({
    name: "X-VC",
    option: "X-VC（リアルタイム）",
  }),
});

const status = document.querySelector('[data-role="session-status"]');
const routeStatus = document.querySelector('[data-role="route-status"]');
const conversionProgress = document.querySelector(
  '[data-role="conversion-progress"]',
);
const tokenStatus = document.querySelector('[data-role="token-status"]');
const startButton = document.querySelector('[data-action="start"]');
const stopButton = document.querySelector('[data-action="stop"]');
const endButton = document.querySelector('[data-action="end"]');
const cancelButton = document.querySelector('[data-action="cancel"]');
const nextButton = document.querySelector('[data-action="next"]');
const configurationForm = document.querySelector('[data-role="configuration"]');
const configureButton = document.querySelector('[data-action="configure"]');
const modelsButton = document.querySelector('[data-action="models"]');
const profileIdentity = document.querySelector('[data-role="profile-identity"]');
const gatewayInput = configurationForm.elements.namedItem("gatewayUrl");
const profileInput = configurationForm.elements.namedItem("profileId");
const tokenInput = configurationForm.elements.namedItem("token");

let currentState = null;
let statusSynchronized = false;
let models = [];
let stopPending = false;
let profileSwitchPending = false;
let pendingProfileId = null;
let progressGenerationId = null;
let outputFrameCount = 0;

function renderProgress() {
  const seconds = (outputFrameCount * 0.02).toFixed(1);
  conversionProgress.textContent = `実変換: ${seconds}秒（${outputFrameCount}フレーム）`;
}

function modelDetail(model) {
  if (model.selectable !== true) {
    return "音声サービスを利用できません";
  }
  if (model.decisionState === "quality-failed") {
    return "リアルタイム · 日本語品質に難あり";
  }
  if (model.profileId === "vc.beatrice.synthetic-ja.v1") {
    return "リアルタイム · 低めのプリセット音声";
  }
  return "リアルタイム変換できます";
}

function voiceFor(profileId) {
  return LIVE_VOICES[profileId] ?? null;
}

function routeDetail(state, error) {
  if (error ?? state?.lastError) {
    return `エラー: ${error ?? state.lastError}`;
  }
  const capture = state?.capture ?? "stopped";
  const route = state?.route ?? "native";
  const remote = state?.remote ?? "disconnected";
  if (capture === "running" && route === "remote") {
    const profileId =
      pendingProfileId ??
      state?.configuration?.profileId ??
      profileInput.value;
    const voice = voiceFor(profileId);
    return `● ${voice?.name ?? "選択した声"}へ変換して再生中`;
  }
  if (capture === "running" && remote === "degraded") {
    return "⚠ 変換に失敗しました。現在は原音を再生しています。";
  }
  if (capture === "running") {
    return "○ 音声変換を準備中です。準備完了までは原音です。";
  }
  if (capture === "starting" || remote === "connecting" || remote === "loading") {
    return "○ リアルタイム音声サービスへ接続中です。";
  }
  return "停止中。GPT Liveタブで「音声変換を開始」を押してください。";
}

function renderModels(nextModels) {
  if (Array.isArray(nextModels)) {
    models = nextModels.filter(
      (model) =>
        model.invocationMode === "live" && voiceFor(model.profileId) !== null,
    );
    const desiredProfileId =
      pendingProfileId ??
      currentState?.configuration?.profileId ??
      profileInput.value ??
      "";
    profileInput.replaceChildren(
      ...models.map((model) => {
        const option = document.createElement("option");
        option.value = model.profileId;
        option.textContent = voiceFor(model.profileId).option;
        option.disabled = model.selectable !== true;
        return option;
      }),
    );
    if (models.some((model) => model.profileId === desiredProfileId)) {
      profileInput.value = desiredProfileId;
    } else {
      profileInput.value =
        models.find((model) => model.selectable === true)?.profileId ??
        models[0]?.profileId ??
        "";
    }
  }
  const selected = models.find(
    (model) => model.profileId === profileInput.value.trim(),
  );
  profileIdentity.textContent = selected
    ? `${voiceFor(selected.profileId).name} · ${modelDetail(selected)}`
    : models.length > 0
      ? "変換先の声を利用できません。"
      : "音声サービスの確認待ちです。";
  return selected;
}

function render(state, error) {
  currentState = state ?? null;
  const capture = state?.capture ?? "stopped";
  const remote = state?.remote ?? "disconnected";
  const configured = state?.configuration?.configured === true;
  if (capture === "stopped" && currentState?.capture !== "running") {
    progressGenerationId = null;
  }
  if (configured) {
    gatewayInput.value = state.configuration.gatewayUrl;
    if (!profileSwitchPending) {
      profileInput.value = state.configuration.profileId;
    }
  }
  const selected = renderModels();
  const view = derivePopupView(state, {
    error,
    statusSynchronized,
    selectedModelSelectable:
      models.length === 0 || selected?.selectable === true,
  });
  status.textContent = view.status;
  routeStatus.textContent = routeDetail(state, error);
  tokenInput.required = !configured;
  tokenInput.placeholder = configured
    ? "保存済み（今後は再入力不要）"
    : "Session tokenを入力";
  tokenStatus.textContent = configured
    ? "接続設定はChromeに保存済みです。空欄表示が正常です。"
    : "Tokenはまだ保存されていません。";
  startButton.disabled = view.startDisabled;
  stopButton.disabled = view.stopDisabled || stopPending;
  configureButton.disabled = view.configureDisabled;
  gatewayInput.disabled = view.gatewayDisabled;
  profileInput.disabled =
    profileSwitchPending ||
    capture === "starting" ||
    capture === "stopping" ||
    remote === "connecting" ||
    remote === "loading" ||
    remote === "selecting";
  tokenInput.disabled = view.tokenDisabled;
  modelsButton.disabled = view.modelsDisabled;
  endButton.disabled = view.endDisabled;
  cancelButton.disabled = view.cancelDisabled;
  nextButton.disabled = view.nextDisabled;

}

async function sendOrThrow(type, fields = {}) {
  const response = await send(type, fields);
  if (!response?.ok) {
    throw new Error(response?.error ?? `${type} failed`);
  }
  return response;
}

async function applyProfile(profileId) {
  const selected = models.find((model) => model.profileId === profileId);
  if (selected && selected.selectable !== true) {
    throw new Error(`${selected.displayName} is unavailable`);
  }
  profileSwitchPending = true;
  pendingProfileId = profileId;
  render(currentState);
  try {
    const capture = currentState?.capture ?? "stopped";
    if (capture === "stopped") {
      if (currentState?.configuration?.configured !== true) {
        profileIdentity.textContent =
          "モデルを選びました。初回だけGatewayとTokenを入力して「設定を保存」を押してください。";
        return;
      }
      await sendOrThrow("session.configure", {
        configuration: {
          gatewayUrl: currentState.configuration.gatewayUrl,
          profileId,
          token: tokenInput.value,
        },
      });
      tokenInput.value = "";
      return;
    }
    if (capture !== "running") {
      throw new Error("モデルは起動完了後に変更してください");
    }
    if (currentState?.remote === "degraded") {
      throw new Error("Stopしてからモデルを選び、Startしてください");
    }
    if (Number.isInteger(currentState?.generationId)) {
      await sendOrThrow("generation.cancel");
    }
    await sendOrThrow("model.select", { profileId });
    await sendOrThrow("generation.start");
  } finally {
    profileSwitchPending = false;
    pendingProfileId = null;
    render(currentState);
  }
}

async function send(type, fields = {}) {
  startButton.disabled = true;
  const isStop = type === "session.stop";
  if (isStop) {
    stopPending = true;
    stopButton.disabled = true;
  }
  let response;
  try {
    response = await chrome.runtime.sendMessage({ type, ...fields });
  } finally {
    if (isStop) {
      stopPending = false;
    }
  }
  renderModels(response?.models);
  render(response?.state, response?.ok ? undefined : response?.error);
  return response;
}

startButton.addEventListener("click", () => {
  progressGenerationId = null;
  outputFrameCount = 0;
  renderProgress();
  render({ ...currentState, capture: "starting", remote: "loading" });
  void send("session.start", { userGesture: true }).catch((error) => {
    render(currentState, error instanceof Error ? error.message : "Start failed");
  });
});

modelsButton.addEventListener("click", () => {
  void (async () => {
    try {
      const storedGateway = currentState?.configuration?.gatewayUrl;
      if (
        !tokenInput.value &&
        storedGateway === normalizeGatewayUrl(gatewayInput.value)
      ) {
        await send("models.list");
        return;
      }
      const gatewayUrl = normalizeGatewayUrl(gatewayInput.value);
      const result = await replaceGatewayPermission({
        permissions: chrome.permissions,
        nextOrigin: gatewayPermissionOrigin(gatewayUrl),
        commit: () =>
          send("models.list", {
            configuration: {
              gatewayUrl,
              profileId: profileInput.value.trim(),
              token: tokenInput.value,
            },
          }),
      });
      if (!result.granted) {
        render(currentState, "Gateway access denied");
      }
    } catch (error) {
      render(
        currentState,
        error instanceof Error ? error.message : "Catalog failed",
      );
    }
  })();
});

profileInput.addEventListener("change", () => {
  const profileId = profileInput.value;
  void applyProfile(profileId).catch((error) => {
    render(
      currentState,
      error instanceof Error ? error.message : "モデル変更に失敗しました",
    );
  });
});

stopButton.addEventListener("click", () => {
  void send("session.stop").catch((error) => {
    render(currentState, error instanceof Error ? error.message : "Stop failed");
  });
});

endButton.addEventListener("click", () => {
  void send("generation.end").catch((error) => {
    render(currentState, error instanceof Error ? error.message : "End failed");
  });
});

cancelButton.addEventListener("click", () => {
  void send("generation.cancel").catch((error) => {
    render(
      currentState,
      error instanceof Error ? error.message : "Interrupt failed",
    );
  });
});

nextButton.addEventListener("click", () => {
  void send("generation.start").catch((error) => {
    render(currentState, error instanceof Error ? error.message : "Next failed");
  });
});

configurationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!statusSynchronized) {
    return;
  }
  void (async () => {
    try {
      configureButton.disabled = true;
      const gatewayUrl = normalizeGatewayUrl(gatewayInput.value);
      const nextPermission = gatewayPermissionOrigin(gatewayUrl);
      const previousGatewayUrl = currentState?.configuration?.gatewayUrl;
      const previousPermission = previousGatewayUrl
        ? gatewayPermissionOrigin(previousGatewayUrl)
        : null;
      const result = await replaceGatewayPermission({
        permissions: chrome.permissions,
        nextOrigin: nextPermission,
        previousOrigin: previousPermission,
        commit: () => send("session.configure", {
          configuration: {
            gatewayUrl,
            profileId: profileInput.value.trim(),
            token: tokenInput.value,
          },
        }),
      });
      if (!result.granted) {
        render(currentState, "Gateway access denied");
        return;
      }
      if (!result.response?.ok) {
        return;
      }
      tokenInput.value = "";
    } catch (error) {
      render(
        currentState,
        error instanceof Error ? error.message : "Configuration failed",
      );
    } finally {
      configureButton.disabled =
        !statusSynchronized || currentState?.capture !== "stopped";
    }
  })();
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (
    sender?.id === chrome.runtime.id &&
    message?.target === "popup" &&
    message?.type === "conversion.progress" &&
    Number.isInteger(message.progress?.generationId) &&
    Number.isSafeInteger(message.progress?.outputFrames) &&
    message.progress.outputFrames >= 0
  ) {
    if (progressGenerationId !== message.progress.generationId) {
      progressGenerationId = message.progress.generationId;
      outputFrameCount = 0;
    }
    outputFrameCount = Math.max(
      outputFrameCount,
      message.progress.outputFrames,
    );
    renderProgress();
    return false;
  }
  if (
    sender?.id !== chrome.runtime.id ||
    message?.target !== "popup" ||
    message?.type !== "session.state" ||
    message.state === null ||
    typeof message.state !== "object"
  ) {
    return false;
  }
  statusSynchronized = true;
  render(message.state);
  return false;
});

chrome.runtime.sendMessage({ type: "session.status" }).then(
  (response) => {
    if (response?.ok && response.state) {
      statusSynchronized = true;
    }
    render(response?.state, response?.ok ? undefined : response?.error);
    if (response?.ok && response.state?.configuration?.configured) {
      void send("models.list").catch(() => {});
    }
  },
  () => render(undefined, "Unavailable"),
);
