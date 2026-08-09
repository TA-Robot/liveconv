import {
  gatewayPermissionOrigin,
  normalizeGatewayUrl,
  replaceGatewayPermission,
} from "../src/gateway-url.js";
import { derivePopupView } from "./popup-state.js";

const status = document.querySelector('[data-role="session-status"]');
const startButton = document.querySelector('[data-action="start"]');
const stopButton = document.querySelector('[data-action="stop"]');
const endButton = document.querySelector('[data-action="end"]');
const cancelButton = document.querySelector('[data-action="cancel"]');
const nextButton = document.querySelector('[data-action="next"]');
const configurationForm = document.querySelector('[data-role="configuration"]');
const configureButton = document.querySelector('[data-action="configure"]');
const modelsButton = document.querySelector('[data-action="models"]');
const selectProfileButton = document.querySelector(
  '[data-action="select-profile"]',
);
const profileOptions = document.querySelector("#profile-options");
const profileIdentity = document.querySelector('[data-role="profile-identity"]');
const modelRoster = document.querySelector('[data-role="model-roster"]');
const gatewayInput = configurationForm.elements.namedItem("gatewayUrl");
const profileInput = configurationForm.elements.namedItem("profileId");
const tokenInput = configurationForm.elements.namedItem("token");

let currentState = null;
let statusSynchronized = false;
let models = [];
let stopPending = false;

function humanize(value) {
  return String(value).replaceAll("_", " ").replaceAll("-", " ");
}

function modelDetail(model) {
  const availability =
    model.executionState === "unavailable"
      ? `Unavailable: ${humanize(model.reasonCode)}`
      : model.executionState === "buffered-preview"
        ? "Buffered preview"
        : "Live trial";
  const voice =
    model.voiceRequirement === "pretrained_voice"
      ? "Pretrained voice"
      : model.voiceRequirement === "authorized_target_required"
        ? "Authorized target required"
        : "No target voice";
  return `${availability} · ${humanize(model.decisionState)} · ${voice}`;
}

function renderModels(nextModels) {
  if (Array.isArray(nextModels)) {
    models = nextModels;
  }
  profileOptions.replaceChildren(
    ...models.map((model) => {
        const option = document.createElement("option");
        option.value = model.profileId;
        option.label = `${model.displayName} · ${modelDetail(model)}`;
        option.disabled = model.selectable !== true;
        return option;
      }),
  );
  modelRoster?.replaceChildren(
    ...models.map((model) => {
      const row = document.createElement("div");
      row.className = "model-row";
      const name = document.createElement("strong");
      name.textContent = model.displayName;
      const detail = document.createElement("span");
      detail.textContent = modelDetail(model);
      row.replaceChildren(name, detail);
      return row;
    }),
  );
  const selected = models.find(
    (model) => model.profileId === profileInput.value.trim(),
  );
  profileIdentity.textContent = selected
    ? `${selected.displayName} · ${modelDetail(selected)}`
    : models.length > 0
      ? "Choose a prepared model."
      : "Load the Gateway roster to verify a profile.";
  endButton.textContent =
    selected?.invocationMode === "buffered_end" ? "End & preview" : "End";
  endButton.setAttribute?.(
    "aria-label",
    selected?.invocationMode === "buffered_end"
      ? "End generation and invoke buffered preview"
      : "End generation",
  );
  return selected;
}

function render(state, error) {
  currentState = state ?? null;
  if (state?.configuration?.configured) {
    gatewayInput.value = state.configuration.gatewayUrl;
    profileInput.value = state.configuration.profileId;
  }
  const selected = renderModels();
  const view = derivePopupView(state, {
    error,
    statusSynchronized,
    selectedModelSelectable:
      models.length === 0 || selected?.selectable === true,
  });
  status.textContent = view.status;
  startButton.disabled = view.startDisabled;
  stopButton.disabled = view.stopDisabled || stopPending;
  configureButton.disabled = view.configureDisabled;
  gatewayInput.disabled = view.gatewayDisabled;
  profileInput.disabled = view.profileDisabled;
  tokenInput.disabled = view.tokenDisabled;
  modelsButton.disabled = view.modelsDisabled;
  selectProfileButton.disabled = view.selectProfileDisabled;
  endButton.disabled = view.endDisabled;
  cancelButton.disabled = view.cancelDisabled;
  nextButton.disabled = view.nextDisabled;

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

selectProfileButton.addEventListener("click", () => {
  void send("model.select", { profileId: profileInput.value.trim() }).catch(
    (error) => {
      render(
        currentState,
        error instanceof Error ? error.message : "Profile selection failed",
      );
    },
  );
});

profileInput.addEventListener("input", () => renderModels());

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
