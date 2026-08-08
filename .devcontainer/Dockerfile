FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ffmpeg \
        jq \
        libsndfile1-dev \
        make \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt /tmp/liveconv-requirements-dev.txt
RUN python -m pip install --no-cache-dir --require-hashes \
      -r /tmp/liveconv-requirements-dev.txt
