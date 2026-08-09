#!/usr/bin/env bash
set -euo pipefail

umask 077

script_path="$(realpath -e -- "${BASH_SOURCE[0]}")"
repo_root="$(cd "$(dirname "$script_path")/.." && pwd -P)"

usage() {
  cat >&2 <<'EOF'
usage: codex-pool.sh [--dry-run] [--state-dir DIR] COMMAND MANIFEST [TASK ...]

Commands:
  validate  Validate the manifest, prompt paths, and ownership declarations.
  start     Start all tasks, or only the named tasks, in detached tmux sessions.
  status    Show the latest state of all tasks, or only the named tasks.
  logs      Print the latest combined JSONL/error log for exactly one task.
  final     Print the latest final assistant message for exactly one task.
  stop      Stop all tasks, or only the named tasks, and release their claims.

Environment:
  CODEX_POOL_MAX_PROCESSES  Repository-wide hard ceiling (default: 4, maximum: 32).
  CODEX_POOL_STATE_DIR      State root (default: $TMPDIR/liveconv-codex-pool).
  CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY
                            Set to 1 only on a trusted isolated host whose
                            read-only OS sandbox cannot start.
EOF
  exit 2
}

die() {
  printf 'codex-pool: %s\n' "$*" >&2
  exit 2
}

operational_error() {
  printf 'codex-pool: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || operational_error "$1 is required"
}

hash_text() {
  local value="$1"
  local length="$2"
  printf '%s' "$value" | sha256sum | cut -c "1-$length"
}

hash_file() {
  local digest ignored
  IFS=' ' read -r digest ignored < <(sha256sum -- "$1")
  [[ "$digest" =~ ^[a-f0-9]{64}$ ]] || return 1
  printf '%s' "$digest"
}

valid_run_token() {
  [[ "$1" =~ ^[a-f0-9]{32}$ ]]
}

has_control_characters() {
  [[ "$1" =~ [[:cntrl:]] ]]
}

is_within() {
  local child="$1"
  local parent="$2"
  [[ "$child" == "$parent" || "$child" == "$parent/"* ]]
}

paths_overlap() {
  local first="$1"
  local second="$2"
  [[ "$first" == "$second" || "$first" == "$second/"* || "$second" == "$first/"* ]]
}

is_sensitive_path() {
  local path="${1,,}"
  local component
  local old_ifs="$IFS"
  IFS='/'
  read -r -a components <<<"$path"
  IFS="$old_ifs"

  for component in "${components[@]}"; do
    case "$component" in
      key | .env | .env.* | credentials | secrets | id_rsa | id_dsa | id_ecdsa | id_ed25519)
        return 0
        ;;
      *.pem | *.key | *.p12 | *.pfx | *.jks | *.keystore)
        return 0
        ;;
    esac
  done
  return 1
}

shell_quote() {
  local value="${1//\'/\'\\\'\'}"
  printf "'%s'" "$value"
}

tmux_has_session() {
  tmux has-session -t "=$1" >/dev/null 2>&1
}

timestamp() {
  date -u +'%Y-%m-%dT%H:%M:%SZ'
}

atomic_replace() {
  local source="$1"
  local destination="$2"
  chmod 600 "$source"
  mv -f -- "$source" "$destination"
}

snapshot_file() {
  local source="$1"
  local destination="$2"
  [[ -f "$source" && ! -L "$source" ]] || return 1
  cp -- "$source" "$destination"
  chmod 600 "$destination"
}

update_current_state() (
  local current_file="$1"
  local run_token="$2"
  local next_state="$3"
  local exit_code="${4:-}"
  local lock_file claim_file temporary current_state

  valid_run_token "$run_token" || return 0
  [[ -f "$current_file" && ! -L "$current_file" ]] || return 0
  lock_file="$(jq -er '.lock_file' "$current_file")" || return 0
  claim_file="$(jq -r '.claim_file' "$current_file")" || return 0
  [[ -f "$lock_file" && ! -L "$lock_file" ]] || return 0

  exec 8>"$lock_file"
  flock -x 8
  [[ -f "$current_file" && ! -L "$current_file" ]] || return 0
  [[ "$(jq -r '.run_token' "$current_file")" == "$run_token" ]] || return 0

  current_state="$(jq -r '.state' "$current_file")"
  if [[ "$next_state" == "running" ]]; then
    [[ "$current_state" == "starting" ]] || return 0
    temporary="${current_file}.tmp.$$"
    jq --arg state running --arg at "$(timestamp)" \
      '.state = $state | .started_at = $at' "$current_file" >"$temporary"
    atomic_replace "$temporary" "$current_file"
    return 0
  fi

  case "$current_state" in
    completed | failed | stopped | launch-failed)
      ;;
    *)
      temporary="${current_file}.tmp.$$"
      jq --arg state "$next_state" --arg at "$(timestamp)" \
        --argjson code "$exit_code" \
        '.state = $state | .finished_at = $at | .exit_code = $code' \
        "$current_file" >"$temporary"
      atomic_replace "$temporary" "$current_file"
      ;;
  esac

  if [[ -n "$claim_file" && -f "$claim_file" && ! -L "$claim_file" ]] \
    && [[ "$(jq -r '.run_token // empty' "$claim_file" 2>/dev/null)" == "$run_token" ]]; then
    rm -f -- "$claim_file"
  fi
)

run_task() {
  (($# == 1)) || exit 2
  local current_file="$1"
  local expected_token
  local stored_token model reasoning mode sandbox prompt_file prompt_snapshot prompt_sha256
  local manifest_snapshot manifest_sha256 task_id owns_json
  local log_file final_file final_temporary finish_state finish_code run_finished
  local task_state_dir expected_runs_dir run_dir pool_state_dir repo_state_dir
  local claim_file lock_file

  require_command jq
  require_command codex
  require_command flock
  require_command date
  require_command sha256sum
  [[ -f "$current_file" && ! -L "$current_file" ]] || operational_error "invalid task state"
  current_file="$(realpath -e -- "$current_file")"
  stored_token="$(jq -er '.run_token' "$current_file")" || operational_error "invalid task token"
  valid_run_token "$stored_token" || operational_error "invalid task token"
  expected_token="$stored_token"

  jq -e --arg repo "$repo_root" '
    type == "object" and .schema_version == 1 and .repo_root == $repo and
    (.task | type == "string") and (.owns | type == "array") and
    (.sandbox | type == "string") and
    (.manifest_snapshot | type == "string") and
    (.manifest_sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
    (.prompt_snapshot | type == "string") and
    (.prompt_sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
    (.run_token | type == "string" and test("^[a-f0-9]{32}$")) and
    (.run_dir | type == "string") and (.log_file | type == "string") and
    (.final_file | type == "string") and (.claim_file | type == "string") and
    (.lock_file | type == "string")
  ' "$current_file" >/dev/null || operational_error "invalid task state contract"

  model="$(jq -er '.model' "$current_file")"
  reasoning="$(jq -er '.reasoning' "$current_file")"
  mode="$(jq -er '.mode' "$current_file")"
  sandbox="$(jq -er '.sandbox' "$current_file")"
  prompt_file="$(jq -er '.prompt_file' "$current_file")"
  prompt_snapshot="$(jq -er '.prompt_snapshot' "$current_file")"
  prompt_sha256="$(jq -er '.prompt_sha256' "$current_file")"
  manifest_snapshot="$(jq -er '.manifest_snapshot' "$current_file")"
  manifest_sha256="$(jq -er '.manifest_sha256' "$current_file")"
  task_id="$(jq -er '.task' "$current_file")"
  owns_json="$(jq -c '.owns' "$current_file")"
  log_file="$(jq -er '.log_file' "$current_file")"
  final_file="$(jq -er '.final_file' "$current_file")"
  run_dir="$(jq -er '.run_dir' "$current_file")"
  claim_file="$(jq -r '.claim_file' "$current_file")"
  lock_file="$(jq -er '.lock_file' "$current_file")"
  final_temporary="${final_file}.tmp"

  task_state_dir="$(dirname "$current_file")"
  expected_runs_dir="$task_state_dir/runs"
  pool_state_dir="$(dirname "$(dirname "$task_state_dir")")"
  repo_state_dir="$(dirname "$(dirname "$pool_state_dir")")"
  is_within "$(realpath -m -- "$run_dir")" "$expected_runs_dir" \
    || operational_error "run directory escaped task state"
  [[ "$log_file" == "$run_dir/run.log" && "$final_file" == "$run_dir/final.txt" ]] \
    || operational_error "artifact path does not match task state"
  [[ "$manifest_snapshot" == "$run_dir/manifest.json" \
    && "$prompt_snapshot" == "$run_dir/prompt.md" ]] \
    || operational_error "snapshot path does not match task state"
  [[ -f "$manifest_snapshot" && ! -L "$manifest_snapshot" \
    && -f "$prompt_snapshot" && ! -L "$prompt_snapshot" ]] \
    || operational_error "run input snapshot is unavailable"
  [[ "$(hash_file "$manifest_snapshot")" == "$manifest_sha256" \
    && "$(hash_file "$prompt_snapshot")" == "$prompt_sha256" ]] \
    || operational_error "run input snapshot hash mismatch"
  jq -e --arg task "$task_id" --arg model "$model" \
    --arg reasoning "$reasoning" --arg mode "$mode" '
      type == "object" and .schema_version == 1 and
      (.tasks | type == "array") and
      ([.tasks[] | select(
        .id == $task and .model == $model and .reasoning == $reasoning and .mode == $mode
      )] | length == 1)
    ' "$manifest_snapshot" >/dev/null \
    || operational_error "manifest snapshot does not match task state"
  [[ "$lock_file" == "$repo_state_dir/claims.lock" && -f "$lock_file" && ! -L "$lock_file" ]] \
    || operational_error "invalid task lock"
  if [[ -n "$claim_file" ]]; then
    is_within "$(realpath -m -- "$claim_file")" "$repo_state_dir/claims" \
      || operational_error "ownership claim escaped repository state"
  fi

  case "$model" in
    gpt-5.6-sol | gpt-5.6-terra) ;;
    *) operational_error "invalid model in task state" ;;
  esac
  case "$reasoning" in
    low | medium | high | xhigh | max | ultra) ;;
    *) operational_error "invalid reasoning level in task state" ;;
  esac
  case "$mode" in
    read-only)
      case "$sandbox" in
        read-only | danger-full-access) ;;
        *) operational_error "invalid read-only task sandbox" ;;
      esac
      ;;
    owned-write)
      [[ "$sandbox" == "workspace-write" ]] \
        || operational_error "invalid owned-write task sandbox"
      ;;
    *) operational_error "invalid mode in task state" ;;
  esac
  mkdir -p -m 700 -- "$(dirname "$log_file")"
  : >"$log_file"
  chmod 600 "$log_file"
  rm -f -- "$final_temporary"

  finish_state=failed
  finish_code=125
  run_finished=0
  finish_run() {
    if ((run_finished == 0)); then
      run_finished=1
      update_current_state "$current_file" "$expected_token" "$finish_state" "$finish_code" || true
    fi
  }
  stop_run() {
    finish_state=stopped
    finish_code=143
    exit 143
  }
  trap finish_run EXIT
  trap stop_run HUP INT TERM

  update_current_state "$current_file" "$expected_token" running

  set +e
  {
    printf '%s\n' 'External Codex pool safety contract (higher priority than the task below):'
    printf '%s\n' '- Do not spawn, delegate to, or invoke subagents.'
    printf '%s\n' '- Use only the model selected by the launcher; never invoke another model.'
    printf '%s\n' '- Never read a file or symlink named key, .env, credentials, secrets, or a private-key file.'
    printf '%s\n' '- Never inspect authentication stores or print credential-like environment variables.'
    printf '%s\n' '- Never commit, push, reset, clean, stash, or rewrite Git history.'
    printf '%s\n' '- Preserve unrelated and pre-existing working-tree changes.'
    if [[ "$mode" == "read-only" ]]; then
      printf '%s\n' '- This is read-only work. Do not modify repository or filesystem content.'
      if [[ "$sandbox" == "danger-full-access" ]]; then
        printf '%s\n' '- The host OS sandbox is unavailable. Full access is a transport fallback only; the read-only contract remains mandatory.'
      fi
    else
      printf '%s\n' '- Modify only the exclusive ownership paths listed below.'
      jq -r '.[] | "  - " + .' <<<"$owns_json"
    fi
    printf '\nTask %s from prompt file %s:\n\n' "$task_id" "${prompt_file#"$repo_root"/}"
    cat -- "$prompt_snapshot"
  } | codex exec \
    --strict-config \
    --ephemeral \
    --json \
    --color never \
    --cd "$repo_root" \
    --model "$model" \
    --sandbox "$sandbox" \
    --config "model_reasoning_effort=\"$reasoning\"" \
    --config 'approval_policy="never"' \
    --config 'agents.enabled=false' \
    --config "agents.default_subagent_model=\"$model\"" \
    --config 'shell_environment_policy.inherit="core"' \
    --config 'shell_environment_policy.ignore_default_excludes=false' \
    --config 'sandbox_workspace_write.exclude_slash_tmp=true' \
    --config 'sandbox_workspace_write.exclude_tmpdir_env_var=true' \
    --disable multi_agent \
    --output-last-message "$final_temporary" \
    - >>"$log_file" 2>&1
  finish_code=$?

  if [[ -f "$final_temporary" && ! -L "$final_temporary" ]]; then
    chmod 600 "$final_temporary" || finish_code=125
    mv -f -- "$final_temporary" "$final_file" || finish_code=125
  fi
  if ((finish_code == 0)); then
    finish_state=completed
  else
    finish_state=failed
  fi
  set -e
  exit "$finish_code"
}

if (($# > 0)) && [[ "$1" == "__run" ]]; then
  shift
  run_task "$@"
fi

dry_run=0
state_override=""
while (($# > 0)); do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    --state-dir)
      (($# >= 2)) || usage
      state_override="$2"
      shift 2
      ;;
    --help | -h)
      usage
      ;;
    --)
      shift
      break
      ;;
    -*)
      usage
      ;;
    *)
      break
      ;;
  esac
done

(($# >= 2)) || usage
command_name="$1"
manifest_argument="$2"
shift 2
requested_tasks=("$@")

case "$command_name" in
  validate | start | status | logs | final | stop) ;;
  *) usage ;;
esac
if ((dry_run == 1)) && [[ "$command_name" != "start" && "$command_name" != "stop" ]]; then
  die "--dry-run is supported only by start and stop"
fi
if [[ "$command_name" == "logs" || "$command_name" == "final" ]]; then
  ((${#requested_tasks[@]} == 1)) || die "$command_name requires exactly one task"
fi

require_command jq
require_command realpath
require_command sha256sum

is_sensitive_path "$manifest_argument" && die "manifest uses a sensitive path"
[[ -f "$manifest_argument" && ! -L "$manifest_argument" ]] \
  || die "manifest must be a regular, non-symlink file: $manifest_argument"
manifest_file="$(realpath -e -- "$manifest_argument")"
is_sensitive_path "$manifest_file" && die "manifest uses a sensitive path"

hard_limit="${CODEX_POOL_MAX_PROCESSES:-4}"
[[ "$hard_limit" =~ ^[1-9][0-9]*$ ]] || die "CODEX_POOL_MAX_PROCESSES must be an integer"
((hard_limit <= 32)) || die "CODEX_POOL_MAX_PROCESSES cannot exceed 32"
unsandboxed_read_only="${CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY:-0}"
[[ "$unsandboxed_read_only" == 0 || "$unsandboxed_read_only" == 1 ]] \
  || die "CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY must be 0 or 1"

jq -e '
  type == "object" and
  (keys | sort) == (["max_processes", "pool", "schema_version", "tasks"] | sort) and
  .schema_version == 1 and
  (.pool | type == "string" and test("^[a-z][a-z0-9-]{0,47}$")) and
  (.max_processes | type == "number" and . == floor and . >= 1 and . <= 32) and
  (.tasks | type == "array" and length >= 1 and length <= 128) and
  (all(.tasks[];
    type == "object" and
    (keys | sort) == (["id", "mode", "model", "owns", "prompt", "reasoning"] | sort) and
    (.id | type == "string" and test("^[a-z][a-z0-9-]{0,47}$")) and
    (.model | IN("gpt-5.6-sol", "gpt-5.6-terra")) and
    (.reasoning | IN("low", "medium", "high", "xhigh", "max", "ultra")) and
    (.mode | IN("read-only", "owned-write")) and
    (.prompt | type == "string" and length >= 1 and test("^[^\u0000-\u001f\u007f]+$")) and
    (.owns | type == "array") and
    (all(.owns[];
      type == "string" and length >= 1 and test("^[^\u0000-\u001f\u007f]+$"))) and
    (if .mode == "read-only" then (.owns | length == 0) else (.owns | length >= 1) end)
  )) and
  ([.tasks[].id] | length == (unique | length))
' "$manifest_file" >/dev/null || die "manifest does not match schema version 1"

pool_name="$(jq -r '.pool' "$manifest_file")"
manifest_limit="$(jq -r '.max_processes' "$manifest_file")"
((manifest_limit <= hard_limit)) \
  || die "manifest max_processes $manifest_limit exceeds hard ceiling $hard_limit"

declare -a task_ids=()
declare -A task_models=()
declare -A task_reasoning=()
declare -A task_modes=()
declare -A task_sandboxes=()
declare -A task_prompts=()
declare -A task_owns=()
declare -a all_claim_paths=()
declare -a all_claim_owners=()

while IFS= read -r task_json; do
  task_id="$(jq -r '.id' <<<"$task_json")"
  model="$(jq -r '.model' <<<"$task_json")"
  reasoning="$(jq -r '.reasoning' <<<"$task_json")"
  mode="$(jq -r '.mode' <<<"$task_json")"
  prompt_relative="$(jq -r '.prompt' <<<"$task_json")"

  [[ "$prompt_relative" != /* ]] || die "task $task_id prompt must be repository-relative"
  is_sensitive_path "$prompt_relative" && die "task $task_id prompt uses a sensitive path"
  prompt_input="$repo_root/$prompt_relative"
  [[ -f "$prompt_input" && ! -L "$prompt_input" ]] \
    || die "task $task_id prompt must be a regular, non-symlink file: $prompt_relative"
  prompt_resolved="$(realpath -e -- "$prompt_input")"
  is_within "$prompt_resolved" "$repo_root" || die "task $task_id prompt escapes the repository"
  is_sensitive_path "${prompt_resolved#"$repo_root"/}" \
    && die "task $task_id prompt resolves to a sensitive path: $prompt_relative"

  normalized_owns=()
  while IFS= read -r ownership_path; do
    [[ "$ownership_path" != /* ]] || die "task $task_id ownership must be repository-relative"
    is_sensitive_path "$ownership_path" && die "task $task_id cannot own a sensitive path"
    ownership_resolved="$(realpath -m -- "$repo_root/$ownership_path")"
    is_within "$ownership_resolved" "$repo_root" \
      || die "task $task_id ownership escapes the repository: $ownership_path"
    [[ "$ownership_resolved" != "$repo_root" ]] || die "task $task_id cannot own the repository root"
    ownership_relative="${ownership_resolved#"$repo_root"/}"
    is_sensitive_path "$ownership_relative" \
      && die "task $task_id ownership resolves to a sensitive path: $ownership_path"
    [[ "$ownership_relative" != .git && "$ownership_relative" != .git/* ]] \
      || die "task $task_id cannot own Git metadata"

    for index in "${!all_claim_paths[@]}"; do
      if paths_overlap "$ownership_relative" "${all_claim_paths[$index]}"; then
        die "ownership collision in manifest: $task_id:$ownership_relative overlaps ${all_claim_owners[$index]}:${all_claim_paths[$index]}"
      fi
    done
    normalized_owns+=("$ownership_relative")
    all_claim_paths+=("$ownership_relative")
    all_claim_owners+=("$task_id")
  done < <(jq -r '.owns[]' <<<"$task_json")

  task_ids+=("$task_id")
  task_models["$task_id"]="$model"
  task_reasoning["$task_id"]="$reasoning"
  task_modes["$task_id"]="$mode"
  if [[ "$mode" == "read-only" ]]; then
    task_sandboxes["$task_id"]=read-only
    [[ "$unsandboxed_read_only" == 1 ]] \
      && task_sandboxes["$task_id"]=danger-full-access
  else
    task_sandboxes["$task_id"]=workspace-write
  fi
  task_prompts["$task_id"]="$prompt_resolved"
  task_owns["$task_id"]="$(jq -cn --args '$ARGS.positional' "${normalized_owns[@]}")"
done < <(jq -c '.tasks[]' "$manifest_file")

if ((${#requested_tasks[@]} == 0)); then
  selected_tasks=("${task_ids[@]}")
else
  selected_tasks=("${requested_tasks[@]}")
fi
declare -A selected_seen=()
for task_id in "${selected_tasks[@]}"; do
  [[ -n "${task_models[$task_id]+present}" ]] || die "unknown task: $task_id"
  [[ -z "${selected_seen[$task_id]+present}" ]] || die "task selected more than once: $task_id"
  selected_seen["$task_id"]=1
done

if [[ "$command_name" == "validate" ]]; then
  printf 'valid\tpool=%s\ttasks=%d\tmax_processes=%d\n' \
    "$pool_name" "${#task_ids[@]}" "$manifest_limit"
  exit 0
fi

state_base_input="${state_override:-${CODEX_POOL_STATE_DIR:-${TMPDIR:-/tmp}/liveconv-codex-pool}}"
has_control_characters "$state_base_input" && die "state directory contains control characters"
state_base="$(realpath -m -- "$state_base_input")"
[[ "$state_base" != / ]] || die "state directory cannot be the filesystem root"
is_within "$state_base" "$repo_root" && die "state directory must be outside the repository"
is_within "$repo_root" "$state_base" && die "state directory cannot contain the repository"

repo_hash="$(hash_text "$repo_root" 16)"
canonical_lock_hash="$(hash_text "$repo_root" 64)"
pool_hash="$(hash_text "$manifest_file|$pool_name" 16)"
repo_state="$state_base/repos/$repo_hash"
pool_state="$repo_state/pools/$pool_hash"
claims_dir="$repo_state/claims"
lock_file="$repo_state/claims.lock"
canonical_lock_root="/tmp/liveconv-codex-pool-locks-${UID}"
canonical_process_lock="$canonical_lock_root/$canonical_lock_hash.processes.lock"
session_prefix="lcp-${repo_hash:0:10}-"

require_command tmux

current_file_for() {
  printf '%s/tasks/%s/current.json' "$pool_state" "$1"
}

read_current_field() {
  local current_file="$1"
  local field="$2"
  jq -r "$field" "$current_file" 2>/dev/null
}

validate_current_file() {
  local current_file="$1"
  local expected_task="$2"
  [[ -f "$current_file" && ! -L "$current_file" ]] || return 1
  jq -e --arg repo "$repo_root" --arg manifest "$manifest_file" \
    --arg pool "$pool_name" --arg task "$expected_task" '
      type == "object" and .schema_version == 1 and
      .repo_root == $repo and .manifest == $manifest and
      .pool == $pool and .task == $task and
      (.session | type == "string") and
      (.run_token | type == "string" and test("^[a-f0-9]{32}$")) and
      (.manifest_snapshot | type == "string") and
      (.manifest_sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
      (.prompt_snapshot | type == "string") and
      (.prompt_sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
      (.state | IN("starting", "running", "completed", "failed", "stopped", "launch-failed"))
    ' "$current_file" >/dev/null 2>&1
}

effective_state() {
  local current_file="$1"
  local stored_state session
  stored_state="$(read_current_field "$current_file" '.state')" || {
    printf invalid-state
    return
  }
  session="$(read_current_field "$current_file" '.session')" || {
    printf invalid-state
    return
  }
  case "$stored_state" in
    starting | running)
      tmux_has_session "$session" && printf '%s' "$stored_state" || printf stale
      ;;
    *) printf '%s' "$stored_state" ;;
  esac
}

active_repo_sessions() {
  local count=0 session
  while IFS= read -r session; do
    [[ "$session" == "$session_prefix"* ]] && count=$((count + 1))
  done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null || true)
  printf '%d' "$count"
}

active_pool_sessions() {
  local count=0 task current_file session
  for task in "${task_ids[@]}"; do
    current_file="$(current_file_for "$task")"
    validate_current_file "$current_file" "$task" || continue
    session="$(read_current_field "$current_file" '.session')"
    tmux_has_session "$session" && count=$((count + 1))
  done
  printf '%d' "$count"
}

check_selected_states() {
  local task current_file state
  for task in "${selected_tasks[@]}"; do
    current_file="$(current_file_for "$task")"
    [[ -e "$current_file" ]] || continue
    validate_current_file "$current_file" "$task" \
      || operational_error "invalid state for task $task"
    state="$(effective_state "$current_file")"
    case "$state" in
      starting | running)
        operational_error "task $task is already $state"
        ;;
      stale)
        operational_error "task $task has stale state; run stop before restarting"
        ;;
      invalid-state)
        operational_error "task $task has $state state; run stop before restarting"
        ;;
    esac
  done
}

check_process_limits() {
  local repo_active pool_active requested_count
  repo_active="$(active_repo_sessions)"
  pool_active="$(active_pool_sessions)"
  requested_count="${#selected_tasks[@]}"
  ((repo_active + requested_count <= hard_limit)) \
    || operational_error "repository process ceiling $hard_limit would be exceeded ($repo_active active, $requested_count requested)"
  ((pool_active + requested_count <= manifest_limit)) \
    || operational_error "manifest process ceiling $manifest_limit would be exceeded ($pool_active active, $requested_count requested)"
}

check_ownership_claims() {
  local claim_file claim_session claim_task selected_task selected_path claim_path
  [[ -d "$claims_dir" ]] || return 0
  shopt -s nullglob
  for claim_file in "$claims_dir"/*.json; do
    [[ -f "$claim_file" && ! -L "$claim_file" ]] \
      || operational_error "invalid ownership claim entry: $claim_file"
    jq -e '
      type == "object" and .schema_version == 1 and
      (.session | type == "string") and (.task | type == "string") and
      (.run_token | type == "string" and test("^[a-f0-9]{32}$")) and
      (.owns | type == "array" and all(.[]; type == "string"))
    ' "$claim_file" >/dev/null 2>&1 \
      || operational_error "malformed ownership claim: $claim_file"
    claim_session="$(jq -r '.session' "$claim_file")"
    claim_task="$(jq -r '.task' "$claim_file")"
    tmux_has_session "$claim_session" \
      || operational_error "stale ownership claim from task $claim_task; run stop with its manifest"

    for selected_task in "${selected_tasks[@]}"; do
      [[ "${task_modes[$selected_task]}" == "owned-write" ]] || continue
      while IFS= read -r selected_path; do
        while IFS= read -r claim_path; do
          paths_overlap "$selected_path" "$claim_path" \
            && operational_error "ownership collision: $selected_task:$selected_path overlaps $claim_task:$claim_path"
        done < <(jq -r '.owns[]' "$claim_file")
      done < <(jq -r '.[]' <<<"${task_owns[$selected_task]}")
    done
  done
  shopt -u nullglob
}

if [[ "$command_name" == "status" ]]; then
  if [[ -d "$repo_state" ]]; then
    require_command flock
    [[ -f "$lock_file" && ! -L "$lock_file" ]] \
      || operational_error "invalid repository state lock"
    exec 8<"$lock_file"
    flock -s 8
  fi
  printf 'TASK\tSTATE\tSESSION\tMODEL\tREASONING\tMODE\tRUN_DIR\n'
  status_code=0
  for task_id in "${selected_tasks[@]}"; do
    current_file="$(current_file_for "$task_id")"
    if [[ ! -e "$current_file" ]]; then
      printf '%s\tnot-started\t-\t%s\t%s\t%s\t-\n' \
        "$task_id" "${task_models[$task_id]}" "${task_reasoning[$task_id]}" "${task_modes[$task_id]}"
      continue
    fi
    if ! validate_current_file "$current_file" "$task_id"; then
      printf '%s\tinvalid-state\t-\t%s\t%s\t%s\t-\n' \
        "$task_id" "${task_models[$task_id]}" "${task_reasoning[$task_id]}" "${task_modes[$task_id]}"
      status_code=3
      continue
    fi
    state="$(effective_state "$current_file")"
    session="$(read_current_field "$current_file" '.session')"
    run_dir="$(read_current_field "$current_file" '.run_dir')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$task_id" "$state" "$session" "${task_models[$task_id]}" \
      "${task_reasoning[$task_id]}" "${task_modes[$task_id]}" "$run_dir"
    [[ "$state" != stale && "$state" != invalid-state ]] \
      || status_code=3
  done
  exit "$status_code"
fi

if [[ "$command_name" == "logs" || "$command_name" == "final" ]]; then
  task_id="${selected_tasks[0]}"
  current_file="$(current_file_for "$task_id")"
  if [[ "$command_name" == "final" ]]; then
    require_command flock
    [[ -f "$lock_file" && ! -L "$lock_file" ]] \
      || operational_error "invalid repository state lock"
    exec 8<"$lock_file"
    flock -s 8
  fi
  validate_current_file "$current_file" "$task_id" \
    || operational_error "no valid run state for task $task_id"
  if [[ "$command_name" == "logs" ]]; then
    artifact_file="$(read_current_field "$current_file" '.log_file')"
  else
    artifact_file="$(read_current_field "$current_file" '.final_file')"
  fi
  is_within "$(realpath -m -- "$artifact_file")" "$pool_state" \
    || operational_error "artifact path escaped pool state"
  [[ -f "$artifact_file" && ! -L "$artifact_file" ]] \
    || operational_error "$command_name output is not available for task $task_id"
  sed -n '1,$p' -- "$artifact_file"
  exit 0
fi

if [[ "$command_name" == "stop" ]]; then
  require_command flock
  require_command date
  if [[ ! -d "$repo_state" ]]; then
    for task_id in "${selected_tasks[@]}"; do
      printf 'not-started\t%s\n' "$task_id"
    done
    exit 0
  fi
  if ((dry_run == 1)); then
    for task_id in "${selected_tasks[@]}"; do
      current_file="$(current_file_for "$task_id")"
      if [[ ! -e "$current_file" ]]; then
        printf 'not-started\t%s\n' "$task_id"
      elif validate_current_file "$current_file" "$task_id"; then
        printf 'would-stop\t%s\t%s\n' "$task_id" "$(read_current_field "$current_file" '.session')"
      else
        operational_error "invalid state for task $task_id"
      fi
    done
    exit 0
  fi

  exec 9>"$lock_file"
  flock -x 9
  for task_id in "${selected_tasks[@]}"; do
    current_file="$(current_file_for "$task_id")"
    if [[ ! -e "$current_file" ]]; then
      printf 'not-started\t%s\n' "$task_id"
      continue
    fi
    validate_current_file "$current_file" "$task_id" \
      || operational_error "invalid state for task $task_id"
    session="$(read_current_field "$current_file" '.session')"
    run_token="$(read_current_field "$current_file" '.run_token')"
    if tmux_has_session "$session"; then
      tmux kill-session -t "=$session" >/dev/null
    fi

    current_state="$(read_current_field "$current_file" '.state')"
    case "$current_state" in
      starting | running)
        temporary="${current_file}.tmp.$$"
        jq --arg state stopped --arg at "$(timestamp)" --argjson code 143 \
          '.state = $state | .finished_at = $at | .exit_code = $code' \
          "$current_file" >"$temporary"
        atomic_replace "$temporary" "$current_file"
        ;;
    esac
    claim_file="$(read_current_field "$current_file" '.claim_file')"
    if [[ -n "$claim_file" && -f "$claim_file" && ! -L "$claim_file" ]] \
      && is_within "$(realpath -m -- "$claim_file")" "$claims_dir" \
      && [[ "$(jq -r '.run_token // empty' "$claim_file" 2>/dev/null)" == "$run_token" ]]; then
      rm -f -- "$claim_file"
    fi
    printf 'stopped\t%s\t%s\n' "$task_id" "$session"
  done
  exit 0
fi

[[ "$command_name" == "start" ]] || usage
require_command flock
require_command date
require_command od
require_command tr
require_command cp
if ((dry_run == 0)); then
  require_command codex
fi

if ((dry_run == 1)); then
  check_selected_states
  check_process_limits
  check_ownership_claims
  for task_id in "${selected_tasks[@]}"; do
    dry_hash="$(hash_text "$repo_root|$manifest_file|$pool_name|$task_id|dry-run" 14)"
    session="${session_prefix}${pool_name:0:14}-${task_id:0:14}-$dry_hash"
    sandbox="${task_sandboxes[$task_id]}"
    printf 'would-start\t%s\tsession=%s\tmodel=%s\treasoning=%s\tmode=%s\tsandbox=%s\tprompt=%s\towns=%s\n' \
      "$task_id" "$session" "${task_models[$task_id]}" "${task_reasoning[$task_id]}" \
      "${task_modes[$task_id]}" "$sandbox" "${task_prompts[$task_id]#"$repo_root"/}" \
      "${task_owns[$task_id]}"
  done
  exit 0
fi

mkdir -p -m 700 -- "$canonical_lock_root"
[[ -d "$canonical_lock_root" && ! -L "$canonical_lock_root" ]] \
  || operational_error "invalid canonical process lock directory"
exec 7>"$canonical_process_lock"
flock -x 7

mkdir -p -m 700 -- "$pool_state/tasks" "$claims_dir"
exec 9>"$lock_file"
flock -x 9
check_selected_states
check_process_limits
check_ownership_claims

declare -a prepared_currents=()
declare -a prepared_claims=()
declare -a prepared_sessions=()
declare -a launched_sessions=()

for task_id in "${selected_tasks[@]}"; do
  random_token="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  [[ ${#random_token} -eq 32 ]] || operational_error "could not generate a run token"
  run_hash="$(hash_text "$repo_root|$manifest_file|$pool_name|$task_id|$random_token" 14)"
  run_id="$(date -u +'%Y%m%dT%H%M%SZ')-$run_hash"
  session="${session_prefix}${pool_name:0:14}-${task_id:0:14}-$run_hash"
  tmux_has_session "$session" && operational_error "generated tmux session already exists: $session"

  task_state="$pool_state/tasks/$task_id"
  run_dir="$task_state/runs/$run_id"
  current_file="$task_state/current.json"
  log_file="$run_dir/run.log"
  final_file="$run_dir/final.txt"
  manifest_snapshot="$run_dir/manifest.json"
  prompt_snapshot="$run_dir/prompt.md"
  claim_file=""
  if [[ "${task_modes[$task_id]}" == "owned-write" ]]; then
    claim_hash="$(hash_text "$repo_root|$manifest_file|$task_id|$random_token|${task_owns[$task_id]}" 32)"
    claim_file="$claims_dir/$claim_hash.json"
  fi
  mkdir -p -m 700 -- "$run_dir"
  snapshot_file "$manifest_file" "$manifest_snapshot" \
    || operational_error "could not snapshot manifest for task $task_id"
  snapshot_file "${task_prompts[$task_id]}" "$prompt_snapshot" \
    || operational_error "could not snapshot prompt for task $task_id"
  manifest_sha256="$(hash_file "$manifest_snapshot")" \
    || operational_error "could not hash manifest snapshot for task $task_id"
  prompt_sha256="$(hash_file "$prompt_snapshot")" \
    || operational_error "could not hash prompt snapshot for task $task_id"

  temporary="${current_file}.tmp.$$"
  jq -n \
    --arg repo_root "$repo_root" \
    --arg manifest "$manifest_file" \
    --arg pool "$pool_name" \
    --arg task "$task_id" \
    --arg model "${task_models[$task_id]}" \
    --arg reasoning "${task_reasoning[$task_id]}" \
    --arg mode "${task_modes[$task_id]}" \
    --arg sandbox "${task_sandboxes[$task_id]}" \
    --arg prompt_file "${task_prompts[$task_id]}" \
    --arg manifest_snapshot "$manifest_snapshot" \
    --arg manifest_sha256 "$manifest_sha256" \
    --arg prompt_snapshot "$prompt_snapshot" \
    --arg prompt_sha256 "$prompt_sha256" \
    --arg run_id "$run_id" \
    --arg run_token "$random_token" \
    --arg session "$session" \
    --arg created_at "$(timestamp)" \
    --arg run_dir "$run_dir" \
    --arg log_file "$log_file" \
    --arg final_file "$final_file" \
    --arg claim_file "$claim_file" \
    --arg lock_file "$lock_file" \
    --argjson owns "${task_owns[$task_id]}" \
    '{
      schema_version: 1,
      repo_root: $repo_root,
      manifest: $manifest,
      pool: $pool,
      task: $task,
      model: $model,
      reasoning: $reasoning,
      mode: $mode,
      sandbox: $sandbox,
      owns: $owns,
      prompt_file: $prompt_file,
      manifest_snapshot: $manifest_snapshot,
      manifest_sha256: $manifest_sha256,
      prompt_snapshot: $prompt_snapshot,
      prompt_sha256: $prompt_sha256,
      run_id: $run_id,
      run_token: $run_token,
      session: $session,
      state: "starting",
      created_at: $created_at,
      started_at: null,
      finished_at: null,
      exit_code: null,
      run_dir: $run_dir,
      log_file: $log_file,
      final_file: $final_file,
      claim_file: $claim_file,
      lock_file: $lock_file
    }' >"$temporary"
  atomic_replace "$temporary" "$current_file"

  if [[ -n "$claim_file" ]]; then
    claim_temporary="${claim_file}.tmp.$$"
    jq -n \
      --arg repo_root "$repo_root" \
      --arg manifest "$manifest_file" \
      --arg pool "$pool_name" \
      --arg task "$task_id" \
      --arg run_token "$random_token" \
      --arg session "$session" \
      --arg created_at "$(timestamp)" \
      --argjson owns "${task_owns[$task_id]}" \
      '{
        schema_version: 1,
        repo_root: $repo_root,
        manifest: $manifest,
        pool: $pool,
        task: $task,
        run_token: $run_token,
        session: $session,
        created_at: $created_at,
        owns: $owns
      }' >"$claim_temporary"
    atomic_replace "$claim_temporary" "$claim_file"
  fi

  prepared_currents+=("$current_file")
  prepared_claims+=("$claim_file")
  prepared_sessions+=("$session")
done

launch_failed=0
for index in "${!selected_tasks[@]}"; do
  task_id="${selected_tasks[$index]}"
  current_file="${prepared_currents[$index]}"
  session="${prepared_sessions[$index]}"
  runner_command="exec $(shell_quote "$script_path") __run $(shell_quote "$current_file")"
  if tmux new-session -d -s "$session" -c "$repo_root" "$runner_command"; then
    launched_sessions+=("$session")
  else
    printf 'codex-pool: failed to launch task %s\n' "$task_id" >&2
    launch_failed=1
    break
  fi
done

if ((launch_failed == 1)); then
  for session in "${launched_sessions[@]}"; do
    tmux_has_session "$session" && tmux kill-session -t "=$session" >/dev/null || true
  done
  for index in "${!prepared_currents[@]}"; do
    current_file="${prepared_currents[$index]}"
    run_token="$(read_current_field "$current_file" '.run_token')"
    temporary="${current_file}.tmp.$$"
    jq --arg state launch-failed --arg at "$(timestamp)" --argjson code 125 \
      '.state = $state | .finished_at = $at | .exit_code = $code' \
      "$current_file" >"$temporary"
    atomic_replace "$temporary" "$current_file"
    claim_file="${prepared_claims[$index]}"
    if [[ -n "$claim_file" && -f "$claim_file" && ! -L "$claim_file" ]] \
      && [[ "$(jq -r '.run_token // empty' "$claim_file" 2>/dev/null)" == "$run_token" ]]; then
      rm -f -- "$claim_file"
    fi
  done
  exit 1
fi

for index in "${!selected_tasks[@]}"; do
  task_id="${selected_tasks[$index]}"
  current_file="${prepared_currents[$index]}"
  printf 'started\t%s\t%s\t%s\n' \
    "$task_id" "${prepared_sessions[$index]}" "$(read_current_field "$current_file" '.run_dir')"
done
