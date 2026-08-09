export function derivePopupView(
  state,
  { error, statusSynchronized = false } = {},
) {
  const capture = state?.capture ?? "stopped";
  const route = state?.route ?? "native";
  const remote = state?.remote ?? "disconnected";
  const generationActive = Number.isInteger(state?.generationId);
  const canSelectProfile =
    capture === "running" && !generationActive && remote === "ready";
  const status =
    error ??
    state?.lastError ??
    (capture === "starting" || remote === "connecting" || remote === "loading"
      ? "Loading profile…"
      : remote === "selecting"
        ? "Selecting profile…"
        : capture === "running" && route === "remote"
          ? "Remote"
          : capture === "running" && remote === "degraded"
            ? "Native fallback"
            : ({
              stopped: "Stopped",
              starting: "Starting",
              running: "Native",
              stopping: "Stopping",
            }[capture] ?? "Unavailable"));

  return Object.freeze({
    status,
    startDisabled: capture !== "stopped",
    stopDisabled: capture === "stopped",
    configureDisabled: !statusSynchronized || capture !== "stopped",
    gatewayDisabled: capture !== "stopped",
    profileDisabled: capture !== "stopped" && !canSelectProfile,
    tokenDisabled: capture !== "stopped",
    modelsDisabled: capture !== "stopped",
    selectProfileDisabled: !canSelectProfile,
    endDisabled: !generationActive,
    cancelDisabled: !generationActive,
    nextDisabled:
      capture !== "running" ||
      generationActive ||
      remote === "disabled" ||
      remote === "disconnected" ||
      remote === "degraded",
  });
}
