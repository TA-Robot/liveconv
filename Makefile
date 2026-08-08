SHELL := /usr/bin/env bash

.PHONY: help bootstrap doctor check git-auth experiment lock-dev luna luna-smoke

help:
	@printf '%s\n' \
	  'make bootstrap                         Run local bootstrap and checks' \
	  'make doctor                            Inspect required and optional tools' \
	  'make check                             Validate repository control files' \
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
	@bash scripts/check.sh

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
