#!/usr/bin/env bash
set -euo pipefail

if (($# != 1)); then
  printf 'usage: %s prompt-file|-\n' "$0" >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prompt_file="$1"
sandbox="${LUNA_SANDBOX:-read-only}"

case "$sandbox" in
  read-only | workspace-write) ;;
  *)
    printf 'LUNA_SANDBOX must be read-only or workspace-write\n' >&2
    exit 2
    ;;
esac

if ! command -v codex >/dev/null 2>&1; then
  printf 'codex is required\n' >&2
  exit 1
fi

if [[ "$prompt_file" == "-" ]]; then
  prompt="$(cat)"
else
  [[ -f "$prompt_file" ]] || {
    printf 'prompt file not found: %s\n' "$prompt_file" >&2
    exit 1
  }
  prompt="$(<"$prompt_file")"
fi

if [[ "$(basename "$prompt_file")" == "phase0-kickoff.md" ]] \
  && [[ "$sandbox" != "read-only" ]]; then
  printf 'phase0-kickoff.md requires the read-only sandbox\n' >&2
  exit 2
fi

cd "$root"
exec codex exec \
  --strict-config \
  --model gpt-5.6-luna \
  --sandbox "$sandbox" \
  "$prompt"
