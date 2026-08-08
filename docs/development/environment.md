# Development environment

Status: Active

## Supported starting environment

The repository control plane requires Bash 3.2 or newer, Git, OpenSSH, `jq`, Make,
Python 3, the pinned packages in `requirements-dev.txt`, and Codex. Application
phases add Node.js, pnpm, uv, FFmpeg, and audio libraries through the Dev
Container.

Run:

```bash
make doctor
make check
```

To start the tested Luna parent-and-child workflow:

```bash
make luna PROMPT_FILE=prompts/luna/phase0-kickoff.md
```

Use `make luna-smoke` to verify direct Luna access and inherited generic-child
spawning with a real repository read. The smoke test consumes model tokens and is
intentionally not part of CI or `make check`.

If the test reports that `bwrap` cannot create a user namespace, the host kernel
blocks Codex's local sandbox. Run swarms only on a host that supports the sandbox.
In an already isolated, disposable development container only, `make luna-smoke`
accepts `danger-full-access` when both `LUNA_SANDBOX=danger-full-access` and
`LIVECONV_ALLOW_UNSANDBOXED=1` are explicit. That fallback is only a capability
diagnostic and must not be used for normal agent work.

## Dev Container

Open the repository in a client that supports `.devcontainer/devcontainer.json`.
The container supplies:

- Python 3.12
- Node.js 22 and pnpm
- Git, OpenSSH, jq, Make, FFmpeg, and libsndfile headers
- the repository bootstrap and doctor checks

The base image is pinned by digest and the Node Feature is pinned by
`devcontainer-lock.json`. Update those pins deliberately after reviewing upstream
release notes.

GPU model execution is intentionally not assumed by the base container. Use a
separate authorized GPU runtime and record its image, driver, GPU, precision, and
model revision in the experiment.

## GitHub SSH key in this workspace

Some shared workspace filesystems expose every file as mode `0666`, even after
`chmod`. OpenSSH correctly refuses a private key with that mode. The setup script
copies the provided key to `~/.ssh/liveconv_github`, adds a final newline when the
uploaded file omitted one, applies mode `0600`, validates it, and configures only
this repository to use it.

```bash
make git-auth KEY=/workspace/liveconv/key
```

The source key is ignored by Git. Never commit either copy.

## Local secrets

Use `.env` only for local development and keep a redacted `.env.example` when a
service first needs configuration. Prefer short-lived credentials and secret
managers for deployed environments.

## Artifact storage

Do not use Git LFS as a default dumping ground for private voice data. Store raw
recordings, embeddings, indexes, checkpoints, and generated audio in an
access-controlled artifact store. Git tracks checksums, non-sensitive locators,
aggregate measurements, and retention metadata.
