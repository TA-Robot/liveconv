#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

failures=0

pass() {
  printf 'ok   %s\n' "$1"
}

fail() {
  printf 'fail %s\n' "$1" >&2
  failures=$((failures + 1))
}

required_files=(
  AGENTS.md
  README.md
  .codex/config.toml
  .devcontainer/devcontainer-lock.json
  docs/product/brief.md
  docs/product/requirements.md
  docs/architecture/overview.md
  docs/architecture/adr/0001-evaluation-first-hybrid.md
  docs/experiments/evaluation.md
  docs/planning/roadmap.md
  docs/planning/backlog.md
  docs/development/agent-playbook.md
  experiments/registry.json
  schemas/experiment-registry.schema.json
  schemas/experiment.schema.json
  requirements-dev.in
  requirements-dev.txt
)

for path in "${required_files[@]}"; do
  if [[ -f "$path" ]]; then
    pass "required file: $path"
  else
    fail "missing required file: $path"
  fi
done

while IFS= read -r script; do
  if bash -n "$script"; then
    pass "shell syntax: $script"
  else
    fail "shell syntax: $script"
  fi
done < <(find scripts -type f -name '*.sh' -print | sort)

if ! command -v jq >/dev/null 2>&1; then
  fail "jq is required for JSON validation"
else
  while IFS= read -r json_file; do
    if jq empty "$json_file" >/dev/null; then
      pass "JSON syntax: $json_file"
    else
      fail "JSON syntax: $json_file"
    fi
  done < <(find experiments schemas .devcontainer .github -type f -name '*.json' -print 2>/dev/null | sort)

  if [[ "$(jq -r '[.experiments[].id] | length == (unique | length)' experiments/registry.json)" == "true" ]]; then
    pass "experiment registry IDs are unique"
  else
    fail "experiment registry contains duplicate IDs"
  fi

  while IFS=$'\t' read -r experiment_id experiment_path registry_status; do
    if [[ ! -f "$experiment_path" ]]; then
      fail "$experiment_id registry path does not exist: $experiment_path"
      continue
    fi

    file_id="$(jq -r '.id' "$experiment_path")"
    file_status="$(jq -r '.status' "$experiment_path")"
    directory_id="$(basename "$(dirname "$experiment_path")" | cut -d- -f1-2)"

    [[ "$file_id" == "$experiment_id" ]] \
      && pass "$experiment_id registry ID matches file" \
      || fail "$experiment_id registry ID does not match file ID $file_id"
    [[ "$directory_id" == "$experiment_id" ]] \
      && pass "$experiment_id directory matches ID" \
      || fail "$experiment_id directory does not match ID"
    [[ "$file_status" == "$registry_status" ]] \
      && pass "$experiment_id registry status matches file" \
      || fail "$experiment_id registry status $registry_status differs from $file_status"

    if jq -e '
      .schema_version == 1 and
      (.id | test("^EXP-[0-9]{3}$")) and
      (.status | IN("draft", "approved", "running", "analyzed", "decided", "invalidated", "archived")) and
      (.question | length >= 10) and
      (.hypothesis | length >= 10) and
      (.variants | length >= 1) and
      (.metrics | length >= 1) and
      (.procedure.invalidation_conditions | length >= 1)
    ' "$experiment_path" >/dev/null; then
      pass "$experiment_id required experiment fields"
    else
      fail "$experiment_id required experiment fields"
    fi
  done < <(jq -r '.experiments[] | [.id, .path, .status] | @tsv' experiments/registry.json)

  while IFS= read -r experiment_path; do
    if jq -e --arg path "$experiment_path" \
      'any(.experiments[]; .path == $path)' experiments/registry.json >/dev/null; then
      pass "$experiment_path is registered"
    else
      fail "$experiment_path is not listed in experiments/registry.json"
    fi
  done < <(find experiments -mindepth 2 -maxdepth 2 -name experiment.json -print | sort)
fi

if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 is required for JSON Schema validation"
elif ! python3 -c 'import jsonschema' >/dev/null 2>&1; then
  fail "Python package jsonschema is required; install requirements-dev.txt"
else
  if python3 scripts/validate-json.py \
    schemas/experiment-registry.schema.json \
    experiments/registry.json; then
    pass "experiment registry matches its full JSON Schema"
  else
    fail "experiment registry JSON Schema validation"
  fi

  experiment_files=()
  while IFS= read -r experiment_file; do
    experiment_files+=("$experiment_file")
  done < <(find experiments -mindepth 2 -maxdepth 2 -name experiment.json -print | sort)

  if ((${#experiment_files[@]} == 0)); then
    fail "at least one experiment file is required"
  elif python3 scripts/validate-json.py \
      schemas/experiment.schema.json \
      "${experiment_files[@]}"; then
    pass "experiments match the full JSON Schema"
  else
    fail "experiment JSON Schema validation"
  fi
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  tracked_secrets="$(git ls-files | grep -E '(^|/)(key|id_(rsa|dsa|ecdsa|ed25519)|\.env($|\.)|.*\.(pem|key|p12|pfx|jks|keystore))$' || true)"
  if [[ -z "$tracked_secrets" ]]; then
    pass "no obvious secret filenames are tracked"
  else
    fail "possible secret files are tracked: $tracked_secrets"
  fi

  tracked_sensitive_artifacts="$(git ls-files | grep -E '(^|/)(artifacts|checkpoints|embeddings|indexes|models|weights|data/private|data/raw)/|\.(aac|aif|aiff|ann|bin|caf|ckpt|emb|faiss|flac|hnsw|index|m4a|mp3|npy|npz|ogg|onnx|opus|pcm|pt|pth|raw|safetensors|wav|webm|wma)$' || true)"
  if [[ -z "$tracked_sensitive_artifacts" ]]; then
    pass "no sensitive audio, model, embedding, or index artifact is tracked"
  else
    fail "sensitive artifact paths are tracked: $tracked_sensitive_artifacts"
  fi

  secret_pattern='BEGIN (OPENSSH|RSA|EC|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}'
  if git grep --cached -I -n -E -- "$secret_pattern" -- . >/dev/null 2>&1; then
    fail "staged content contains a credential-like value"
  else
    pass "staged content has no private-key or common credential marker"
  fi
fi

if command -v codex >/dev/null 2>&1; then
  codex_report="$(mktemp)"
  codex --strict-config doctor --json > "$codex_report" 2>/dev/null || true
  if jq -e '.checks["config.load"].status == "ok"' "$codex_report" >/dev/null 2>&1; then
    pass "Codex accepts project config in strict mode"
  else
    fail "Codex rejected project config in strict mode"
  fi
  rm -f "$codex_report"
else
  printf 'skip Codex is unavailable; strict project config check not run\n'
fi

if ((failures > 0)); then
  printf '\n%s repository check(s) failed\n' "$failures" >&2
  exit 1
fi

printf '\nall repository checks passed\n'
