# Remote Gateway deployment

This directory exposes the liveconv Gateway only through Caddy TLS/WSS. The
Gateway has no published host port and shares an internal Docker network with
Caddy. Its root filesystem, profile/model mounts, and container capabilities
are read-only or removed. Caddy stores only ACME state in named volumes and does
not enable HTTP access logging.

## Host requirements

- Docker Engine with Compose v2
- the repository bootstrap toolchain, including locked `jsonschema`
- public DNS `A`/`AAAA` records for one dedicated hostname
- inbound TCP 80/443 and UDP 443; outbound access for ACME
- an absolute, host-local model artifact directory outside Git
- an API-token file outside Git, readable by container UID `10001`
- the exact unpacked/installed Chrome Extension ID

The token must be visible ASCII, at least 32 bytes long, and contain at least 16
distinct characters. The allowlist value must contain only exact origins such as
`chrome-extension://abcdefghijklmnopabcdefghijklmnop`; wildcards, Web origins,
paths, and trailing slashes are rejected by Gateway readiness.

The artifact directory must be searchable and readable by container UID/GID
`10001:10001`; it is never writable from the Gateway container.
Make the token readable without making it public: keep the deployment operator
as owner, use numeric group `10001`, and mode `0440`:

```bash
sudo chgrp 10001 /secure/liveconv-api-token
sudo chmod 0440 /secure/liveconv-api-token
```

This lets both the operator's preflight and the container read it. The
preflight checks the numeric container permissions before Compose starts.

## Start

Create a private environment file from `.env.example`, fill every value without
a default, and keep the file outside Git. Validate the deployment before making
it reachable:

```bash
python deploy/remote/validate.py --env-file /absolute/path/liveconv.env
docker compose --env-file /absolute/path/liveconv.env \
  -f deploy/remote/compose.yaml config --quiet
docker compose --env-file /absolute/path/liveconv.env \
  -f deploy/remote/compose.yaml up --build -d
```

`deploy/remote/check-tools.sh /absolute/path/liveconv.env` combines the
preflight with authoritative Docker Compose and pinned-Caddy parsing. When the
optional profile path is populated, it validates the merged override too.

Caddy obtains and renews the public certificate automatically. The external
base URL is `https://<LIVECONV_PUBLIC_HOST>` and the WebSocket URL is
`wss://<LIVECONV_PUBLIC_HOST>/v1/ws`. `/health/live` is public; all readiness,
model, and session routes still require the Bearer token. Caddy forwards the
original `Origin` header, and the Gateway compares it against the exact
`LIVECONV_ALLOWED_ORIGINS` set.

## Profiles and artifacts

The base deployment uses the `default-model-profiles.json` bundled in the
installed `liveconv-audio` wheel. It contains only deterministic passthrough and
gain profiles, so it works without a host registry file.

Real model artifacts remain external and are mounted read-only at
`/opt/liveconv/artifacts`. To use a separately reviewed registry, add the
override and set `LIVECONV_PROFILE_CONFIG_FILE` to an absolute host path:

```bash
docker compose --env-file /absolute/path/liveconv.env \
  -f deploy/remote/compose.yaml \
  -f deploy/remote/compose.profile-registry.yaml up --build -d
```

A registry or artifact mount does not approve a model. Real profiles still need
artifact provenance, licensing, adapter conformance, frozen evaluation, and an
explicit readiness decision. The current Gateway selects only its implemented
adapters.

## Operations

Check status without printing credentials:

```bash
docker compose --env-file /absolute/path/liveconv.env \
  -f deploy/remote/compose.yaml ps
docker compose --env-file /absolute/path/liveconv.env \
  -f deploy/remote/compose.yaml logs --since=10m gateway caddy
```

Rotate the API-token file atomically, then recreate the Gateway. Existing
in-memory sessions are intentionally lost on restart. Back up the `caddy_data`
volume; do not back up raw user audio because the deployment does not persist it.
