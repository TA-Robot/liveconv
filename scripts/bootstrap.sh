#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if command -v corepack >/dev/null 2>&1; then
  corepack enable >/dev/null 2>&1 || true
fi

bash scripts/doctor.sh
uv sync --frozen --all-packages --group dev
make check

printf '\nliveconv bootstrap complete\n'
