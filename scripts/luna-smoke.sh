#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report="$(mktemp)"
sandbox="${LUNA_SANDBOX:-read-only}"
trap 'rm -f "$report"' EXIT

case "$sandbox" in
  read-only | workspace-write) ;;
  danger-full-access)
    if [[ "${LIVECONV_ALLOW_UNSANDBOXED:-0}" != "1" ]]; then
      printf 'danger-full-access requires LIVECONV_ALLOW_UNSANDBOXED=1\n' >&2
      exit 2
    fi
    ;;
  *)
    printf 'invalid LUNA_SANDBOX: %s\n' "$sandbox" >&2
    exit 2
    ;;
esac

cd "$root"

codex exec \
  --strict-config \
  --ephemeral \
  --sandbox "$sandbox" \
  --model gpt-5.6-luna \
  --json \
  'Validation only. Spawn exactly one generic subagent without a custom agent type or model. Ask it to read the first heading in AGENTS.md without opening any ignored file, then answer CHILD_OK only if it read the heading. Wait for it. Independently read the first heading too. Answer exactly LUNA_CHILD_OK only when both reads succeeded, otherwise LUNA_CHILD_FAILED. Do not edit files.' \
  > "$report"

if jq -e 'select(.type == "item.completed" and .item.type == "agent_message" and .item.text == "LUNA_CHILD_OK")' "$report" >/dev/null; then
  printf 'Luna parent and inherited child can read the repository\n'
else
  printf 'Luna repository-read smoke test failed\n' >&2
  tail -n 20 "$report" >&2
  exit 1
fi
