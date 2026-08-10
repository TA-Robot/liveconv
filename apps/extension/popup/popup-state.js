export function derivePopupView(
  state,
  { error, statusSynchronized = false, selectedModelSelectable = true } = {},
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
      ? "接続中…"
      : remote === "selecting"
        ? "声を切替中…"
        : capture === "running" && route === "remote"
          ? "● 音声変換中"
          : capture === "running" && remote === "degraded"
            ? "⚠ 変換失敗・原音"
            : ({
              stopped: "停止中",
              starting: "開始中",
              running: "○ 準備中・原音",
              stopping: "停止中…",
            }[capture] ?? "利用不可"));

  return Object.freeze({
    status,
    startDisabled: capture !== "stopped",
    stopDisabled: capture === "stopped",
    configureDisabled: !statusSynchronized || capture !== "stopped",
    gatewayDisabled: capture !== "stopped",
    profileDisabled: capture !== "stopped" && !canSelectProfile,
    tokenDisabled: capture !== "stopped",
    modelsDisabled: capture !== "stopped",
    selectProfileDisabled: !canSelectProfile || !selectedModelSelectable,
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
