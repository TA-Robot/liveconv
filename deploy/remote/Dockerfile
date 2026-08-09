# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.9.0@sha256:8f926a80debadba6f18442030df316c0e2b28d6af62d1292fb44b1c874173dc0 AS uv

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /build

# All workspace manifests are needed for frozen workspace resolution. Only the
# Gateway and its two local dependencies are installed into the runtime venv.
COPY pyproject.toml uv.lock ./
COPY packages/protocol/pyproject.toml packages/protocol/pyproject.toml
COPY packages/evaluation/pyproject.toml packages/evaluation/pyproject.toml
COPY packages/stt/pyproject.toml packages/stt/pyproject.toml
COPY packages/speaker/pyproject.toml packages/speaker/pyproject.toml
COPY services/audio/pyproject.toml services/audio/pyproject.toml
COPY workers/pyproject.toml workers/pyproject.toml
COPY experiments/EXP-002-remote-router/runner/pyproject.toml experiments/EXP-002-remote-router/runner/pyproject.toml

COPY packages/protocol/liveconv_protocol/*.py packages/protocol/liveconv_protocol/
COPY services/audio/liveconv_audio/*.py services/audio/liveconv_audio/
COPY services/audio/liveconv_audio/default-model-profiles.json services/audio/liveconv_audio/default-model-profiles.json
COPY workers/__init__.py workers/__init__.py
COPY workers/README.md workers/README.md
COPY workers/model-pack.schema.json workers/model-pack.schema.json
COPY workers/packs/*.py workers/packs/
COPY workers/packs/*.json workers/packs/
COPY workers/runtime/*.py workers/runtime/
COPY workers/conformance/*.py workers/conformance/

# The worker distribution currently enumerates each adapter package. Include
# only its importable Python sources so setuptools can build that dependency;
# model libraries, runtime locks, repositories, and weights stay out of this
# deterministic Gateway image.
COPY workers/adapters/__init__.py workers/adapters/__init__.py
COPY workers/adapters/beatrice_2/*.py workers/adapters/beatrice_2/
COPY workers/adapters/openvoice_v2/*.py workers/adapters/openvoice_v2/
COPY workers/adapters/rvc_v2/*.py workers/adapters/rvc_v2/
COPY workers/adapters/rvc_v2/tools/__init__.py workers/adapters/rvc_v2/tools/__init__.py
COPY workers/adapters/x_vc/*.py workers/adapters/x_vc/

RUN uv sync \
    --frozen \
    --no-dev \
    --no-editable \
    --package liveconv-audio \
    && /opt/venv/bin/python -c \
      "from importlib.resources import files; assert files('liveconv_audio').joinpath('default-model-profiles.json').is_file()"

FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7 AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 liveconv \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin liveconv \
    && install -d -o root -g root -m 0755 /etc/liveconv \
    && install -d -o liveconv -g liveconv -m 0750 /opt/liveconv/bin /opt/liveconv/artifacts

COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv
COPY --chown=10001:10001 --chmod=0555 deploy/remote/entrypoint.sh /opt/liveconv/bin/entrypoint.sh

WORKDIR /opt/liveconv
USER 10001:10001
EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
  CMD ["python", "-c", "import os, pathlib, urllib.request; p=os.environ.get('LIVECONV_API_TOKEN_FILE'); t=pathlib.Path(p).read_text(encoding='utf-8').strip() if p else os.environ['LIVECONV_API_TOKEN']; u='http://127.0.0.1:'+os.environ.get('LIVECONV_BIND_PORT','8765')+'/health/ready'; r=urllib.request.urlopen(urllib.request.Request(u, headers={'Authorization': 'Bearer '+t}), timeout=3); raise SystemExit(0 if r.status == 200 else 1)"]

ENTRYPOINT ["/opt/liveconv/bin/entrypoint.sh"]
