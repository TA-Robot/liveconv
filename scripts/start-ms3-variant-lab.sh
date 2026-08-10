#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
deployment="${LIVECONV_MS3_DEPLOYMENT:-${repo_root}/artifacts/ms3/current}"
gateway_env="${LIVECONV_GATEWAY_ENV:-${HOME}/.config/liveconv/gateway.env}"
bind_host="${LIVECONV_MS3_BIND_HOST:-127.0.0.1}"
bind_port="${LIVECONV_MS3_BIND_PORT:-8877}"

if [[ ! -f "${gateway_env}" ]]; then
  printf 'MS-3 Gateway configuration is unavailable: %s\n' "${gateway_env}" >&2
  exit 2
fi
if [[ ! -d "${deployment}" ]]; then
  printf 'MS-3 activation is unavailable: %s\n' "${deployment}" >&2
  exit 2
fi

arguments=(
  --deployment "${deployment}"
  --gateway-env "${gateway_env}"
  --bind-host "${bind_host}"
  --bind-port "${bind_port}"
)
if [[ "${1:-}" == "--check" ]]; then
  arguments+=(--check)
elif [[ $# -ne 0 ]]; then
  printf 'usage: %s [--check]\n' "$0" >&2
  exit 2
fi

cd -- "${repo_root}"
exec uv run --frozen --all-packages python scripts/run-ms3-gateway.py "${arguments[@]}"
