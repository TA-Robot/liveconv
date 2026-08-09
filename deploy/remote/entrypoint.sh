#!/bin/sh
set -eu

if [ -n "${LIVECONV_API_TOKEN_FILE:-}" ]; then
  if [ ! -r "$LIVECONV_API_TOKEN_FILE" ]; then
    printf '%s\n' 'LIVECONV_API_TOKEN_FILE is not readable' >&2
    exit 78
  fi
  LIVECONV_API_TOKEN="$(cat "$LIVECONV_API_TOKEN_FILE")"
  export LIVECONV_API_TOKEN
fi

if [ -z "${LIVECONV_API_TOKEN:-}" ]; then
  printf '%s\n' 'LIVECONV_API_TOKEN_FILE or LIVECONV_API_TOKEN is required' >&2
  exit 78
fi

exec python -m liveconv_audio
