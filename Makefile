SHELL := /usr/bin/env bash

.PHONY: help bootstrap doctor check control-check package-check remote-check remote-check-tools test test-python test-extension lint server git-auth experiment lock-dev luna luna-smoke

help:
	@printf '%s\n' \
	  'make bootstrap                         Run local bootstrap and checks' \
	  'make doctor                            Inspect required and optional tools' \
	  'make check                             Validate controls, lint, and tests' \
	  'make package-check                     Build and smoke public Python packages' \
	  'make remote-check                      Validate remote TLS deployment config' \
	  'make remote-check-tools ENV_FILE=/path Validate with Compose and Caddy' \
	  'make test                              Run Python and Extension tests' \
	  'make test-extension                    Run Chrome Extension Node tests' \
	  'make lint                              Run Ruff checks and format check' \
	  'make server                            Start loopback audio gateway' \
	  'make git-auth KEY=/path/to/key          Configure repository SSH auth' \
	  'make experiment ID=EXP-002 SLUG=name TITLE="Title"' \
	  'make lock-dev                           Refresh hashed Python tool lock' \
	  'make luna PROMPT_FILE=prompts/luna/phase0-kickoff.md' \
	  'make luna-smoke                        Verify a Luna child can be spawned'

bootstrap:
	@bash scripts/bootstrap.sh

doctor:
	@bash scripts/doctor.sh

check:
	@$(MAKE) control-check
	@$(MAKE) lint
	@$(MAKE) package-check
	@$(MAKE) test

control-check:
	@bash scripts/check.sh

package-check:
	@uv run --frozen python scripts/check-packages.py

remote-check:
	@python3 deploy/remote/validate.py

remote-check-tools:
	@test -n "$(ENV_FILE)" || { echo 'ENV_FILE is required'; exit 2; }
	@deploy/remote/check-tools.sh "$(ENV_FILE)"

test:
	@$(MAKE) test-python
	@$(MAKE) test-extension

test-python:
	@uv run --frozen --all-packages pytest

test-extension:
	@node --test apps/extension/tests/*.test.mjs

lint:
	@uv run --frozen ruff check .
	@uv run --frozen ruff format --check .

server:
	@uv run --frozen --all-packages python -m liveconv_audio

git-auth:
	@test -n "$(KEY)" || { echo 'KEY is required'; exit 2; }
	@bash scripts/setup-git-auth.sh "$(KEY)"

experiment:
	@test -n "$(ID)" || { echo 'ID is required'; exit 2; }
	@test -n "$(SLUG)" || { echo 'SLUG is required'; exit 2; }
	@test -n "$(TITLE)" || { echo 'TITLE is required'; exit 2; }
	@bash scripts/new-experiment.sh "$(ID)" "$(SLUG)" "$(TITLE)"

lock-dev:
	@uv pip compile --generate-hashes \
	  --custom-compile-command 'make lock-dev' \
	  requirements-dev.in --output-file requirements-dev.txt

luna:
	@test -n "$(PROMPT_FILE)" || { echo 'PROMPT_FILE is required'; exit 2; }
	@bash scripts/luna-swarm.sh "$(PROMPT_FILE)"

luna-smoke:
	@bash scripts/luna-smoke.sh
