#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  printf '%s\n' 'usage: check-tools.sh /absolute/path/liveconv.env' >&2
  exit 2
fi

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE=$1
CADDY_IMAGE='caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d'

python3 "$HERE/validate.py" --env-file "$ENV_FILE"
python3 "$HERE/validate-build-context.py"
docker compose --env-file "$ENV_FILE" -f "$HERE/compose.yaml" config --quiet

if grep -Eq '^LIVECONV_PROFILE_CONFIG_FILE=.+$' "$ENV_FILE"; then
  docker compose --env-file "$ENV_FILE" \
    -f "$HERE/compose.yaml" \
    -f "$HERE/compose.profile-registry.yaml" config --quiet
fi

docker run --rm \
  --env-file "$ENV_FILE" \
  --mount "type=bind,src=$HERE/Caddyfile,dst=/etc/caddy/Caddyfile,readonly" \
  "$CADDY_IMAGE" \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
