#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

required=(bash git ssh jq make python3)
optional=(codex node pnpm uv ffmpeg docker)
missing=0

printf 'liveconv environment doctor\n\n'

for tool in "${required[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf 'ok       %-12s %s\n' "$tool" "$(command -v "$tool")"
  else
    printf 'missing  %-12s required\n' "$tool"
    missing=$((missing + 1))
  fi
done

if python3 -c 'import jsonschema' >/dev/null 2>&1; then
  printf 'ok       %-12s available\n' 'jsonschema'
else
  printf 'missing  %-12s install requirements-dev.txt\n' 'jsonschema'
  missing=$((missing + 1))
fi

for tool in "${optional[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf 'ok       %-12s %s\n' "$tool" "$(command -v "$tool")"
  else
    printf 'optional %-12s needed by a later application phase\n' "$tool"
  fi
done

printf '\nrepository\n'
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'ok       git root     %s\n' "$(git rev-parse --show-toplevel)"
  printf 'info     branch       %s\n' "$(git branch --show-current || true)"
  printf 'info     origin       %s\n' "$(git remote get-url origin 2>/dev/null || echo 'not configured')"
else
  printf 'missing  git repository\n'
  missing=$((missing + 1))
fi

if [[ -f "$HOME/.ssh/liveconv_github" ]]; then
  mode="$(stat -c '%a' "$HOME/.ssh/liveconv_github" 2>/dev/null || stat -f '%Lp' "$HOME/.ssh/liveconv_github")"
  if [[ "$mode" == "600" ]]; then
    printf 'ok       git key      installed with mode 600\n'
  else
    printf 'warning  git key      unexpected mode %s\n' "$mode"
  fi
else
  printf 'optional git key      run make git-auth KEY=/path/to/key\n'
fi

if command -v unshare >/dev/null 2>&1; then
  if unshare --user --map-root-user true >/dev/null 2>&1; then
    printf 'ok       sandbox      user namespaces are available\n'
  else
    printf 'warning  sandbox      user namespaces are blocked; Codex read/write sandboxes may fail\n'
  fi
fi

printf '\n'
if ((missing > 0)); then
  printf '%s required item(s) missing\n' "$missing" >&2
  exit 1
fi

printf 'required environment is ready\n'
