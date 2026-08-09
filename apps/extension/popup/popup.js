import {
  gatewayPermissionOrigin,
  normalizeGatewayUrl,
  replaceGatewayPermission,
} from "../src/gateway-url.js";

const status = document.querySelector('[data-role="session-status"]');
const startButton = document.querySelector('[data-action="start"]');
const stopButton = document.querySelector('[data-action="stop"]');
const endButton = document.querySelector('[data-action="end"]');
const cancelButton = document.querySelector('[data-action="cancel"]');
const nextButton = document.querySelector('[data-action="next"]');
const configurationForm = document.querySelector('[data-role="configuration"]');
const configureButton = document.querySelector('[data-action="configure"]');
const gatewayInput = configurationForm.elements.namedItem("gatewayUrl");
const profileInput = configurationForm.elements.namedItem("profileId");
const tokenInput = configurationForm.elements.namedItem("token");

let currentState = null;
let statusSynchronized = false;

function render(state, error) {
  const capture = state?.capture ?? "stopped";
  const route = state?.route ?? "native";
  const remote = state?.remote ?? "disconnected";
  currentState = state ?? null;
  status.textContent =
    error ??
    state?.lastError ??
    (capture === "running" && route === "remote"
      ? "Remote"
      : capture === "running" && remote === "degraded"
        ? "Native fallback"
        : {
            stopped: "Stopped",
            starting: "Starting",
            running: "Native",
            stopping: "Stopping",
          }[capture] ?? "Unavailable");
  startButton.disabled = capture !== "stopped";
  stopButton.disabled = capture === "stopped";
  configureButton.disabled = !statusSynchronized || capture !== "stopped";
  gatewayInput.disabled = capture !== "stopped";
  profileInput.disabled = capture !== "stopped";
  tokenInput.disabled = capture !== "stopped";
  const generationActive = Number.isInteger(state?.generationId);
  endButton.disabled = !generationActive;
  cancelButton.disabled = !generationActive;
  nextButton.disabled =
    capture !== "running" ||
    generationActive ||
    remote === "disabled" ||
    remote === "disconnected" ||
    remote === "degraded";

  if (state?.configuration?.configured) {
    gatewayInput.value = state.configuration.gatewayUrl;
    profileInput.value = state.configuration.profileId;
  }
}

async function send(type, fields = {}) {
  startButton.disabled = true;
  stopButton.disabled = true;
  const response = await chrome.runtime.sendMessage({ type, ...fields });
  render(response?.state, response?.ok ? undefined : response?.error);
  return response;
}

startButton.addEventListener("click", () => {
  void send("session.start", { userGesture: true }).catch((error) => {
    render(currentState, error instanceof Error ? error.message : "Start failed");
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

chrome.runtime.sendMessage({ type: "session.status" }).then(
  (response) => {
    if (response?.ok && response.state) {
      statusSynchronized = true;
    }
    render(response?.state, response?.ok ? undefined : response?.error);
  },
  () => render(undefined, "Unavailable"),
);
