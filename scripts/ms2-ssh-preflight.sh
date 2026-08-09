#!/usr/bin/env bash
# Validate the non-secret MS-2 SSH and Gateway boundary before connecting.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ms2-ssh-preflight.sh --ssh-config PATH --host-alias NAME \
  --expected-identity-file PATH --expected-known-hosts PATH \
  --expected-extension-origin ORIGIN --server-evidence PATH \
  --gateway-evidence PATH [--ssh-bin PATH]

The evidence files must use the schemas documented in
docs/development/ms2-ssh-preflight.md. Successful output is JSON metadata only.
EOF
}

fail() {
  printf 'liveconv MS-2 SSH preflight: %s\n' "$*" >&2
  exit 1
}

ssh_bin="/usr/bin/ssh"
ssh_config=""
host_alias=""
expected_identity=""
expected_known_hosts=""
expected_extension_origin=""
server_evidence=""
gateway_evidence=""

while (($# > 0)); do
  case "$1" in
    --ssh-bin)
      (($# >= 2)) || fail "--ssh-bin needs a path"
      ssh_bin="$2"
      shift 2
      ;;
    --ssh-config)
      (($# >= 2)) || fail "--ssh-config needs a path"
      ssh_config="$2"
      shift 2
      ;;
    --host-alias)
      (($# >= 2)) || fail "--host-alias needs a name"
      host_alias="$2"
      shift 2
      ;;
    --expected-identity-file|--identity-file)
      (($# >= 2)) || fail "$1 needs a path"
      expected_identity="$2"
      shift 2
      ;;
    --expected-known-hosts|--known-hosts)
      (($# >= 2)) || fail "$1 needs a path"
      expected_known_hosts="$2"
      shift 2
      ;;
    --expected-extension-origin)
      (($# >= 2)) || fail "--expected-extension-origin needs an Origin"
      expected_extension_origin="$2"
      shift 2
      ;;
    --server-evidence)
      (($# >= 2)) || fail "--server-evidence needs a path"
      server_evidence="$2"
      shift 2
      ;;
    --gateway-evidence)
      (($# >= 2)) || fail "--gateway-evidence needs a path"
      gateway_evidence="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$ssh_config" ]] || fail "--ssh-config is required"
[[ -n "$host_alias" ]] || fail "--host-alias is required"
[[ -n "$expected_identity" ]] || fail "--expected-identity-file is required"
[[ -n "$expected_known_hosts" ]] || fail "--expected-known-hosts is required"
[[ -n "$expected_extension_origin" ]] \
  || fail "--expected-extension-origin is required"
[[ -n "$server_evidence" ]] || fail "--server-evidence is required"
[[ -n "$gateway_evidence" ]] || fail "--gateway-evidence is required"

command -v jq >/dev/null 2>&1 || fail "jq is required"
command -v ssh-keygen >/dev/null 2>&1 || fail "ssh-keygen is required"
command -v realpath >/dev/null 2>&1 || fail "realpath is required"
command -v stat >/dev/null 2>&1 || fail "stat is required"
command -v awk >/dev/null 2>&1 || fail "awk is required"

require_single_line() {
  local value="$1"
  local label="$2"

  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] \
    || fail "$label must not contain a line break"
}

canonical_regular_readable_file() {
  local candidate="$1"
  local label="$2"
  local canonical

  require_single_line "$candidate" "$label path"
  canonical="$(realpath -e -- "$candidate" 2>/dev/null)" \
    || fail "$label is unavailable"
  [[ -f "$canonical" ]] || fail "$label is not a regular file"
  [[ -r "$canonical" ]] || fail "$label is unreadable"
  REPLY="$canonical"
}

canonical_owned_regular_file() {
  local candidate="$1"
  local label="$2"
  local canonical
  local owner
  local mode
  local mode_number

  canonical_regular_readable_file "$candidate" "$label"
  canonical="$REPLY"
  owner="$(stat -c '%u' -- "$canonical" 2>/dev/null)" \
    || fail "$label metadata is unavailable"
  [[ "$owner" == "$(id -u)" ]] || fail "$label is not owned by the current user"
  mode="$(stat -c '%a' -- "$canonical" 2>/dev/null)" \
    || fail "$label metadata is unavailable"
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || fail "$label has an invalid mode"
  mode_number=$((8#$mode))
  (( (mode_number & 18) == 0 )) \
    || fail "$label is writable by group or others"

  REPLY="$canonical"
}

require_private_identity_metadata() {
  local identity="$1"
  local mode
  local mode_number

  mode="$(stat -c '%a' -- "$identity" 2>/dev/null)" \
    || fail "expected identity metadata is unavailable"
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || fail "expected identity has an invalid mode"
  mode_number=$((8#$mode))
  (( (mode_number & 63) == 0 )) \
    || fail "expected identity is accessible to group or others"
}

canonicalize_effective_path() {
  local value="$1"
  local label="$2"
  local expanded
  local canonical

  require_single_line "$value" "$label"
  [[ -n "$value" && "${value,,}" != "none" ]] \
    || fail "$label is disabled"
  [[ "$value" != *[[:space:]]* ]] \
    || fail "$label must contain exactly one path"
  case "$value" in
    '~') expanded="$HOME" ;;
    '~/'*) expanded="$HOME/${value#~/}" ;;
    '~'*) fail "$label uses an unsupported home expansion" ;;
    *) expanded="$value" ;;
  esac
  canonical="$(realpath -e -- "$expanded" 2>/dev/null)" \
    || fail "$label is unavailable"
  [[ -f "$canonical" ]] || fail "$label is not a regular file"
  REPLY="$canonical"
}

prescan_ssh_config() {
  local line
  local trimmed
  local keyword

  if ! LC_ALL=C awk '
    {
      line = $0
      gsub(/\t/, "", line)
      if (line ~ /[[:cntrl:]]/) {
        exit 1
      }
    }
  ' "$ssh_config"; then
    fail "isolated SSH config contains a disallowed control byte"
  fi

  while IFS= read -r line || [[ -n "$line" ]]; do
    trimmed="${line#"${line%%[!$' \t']*}"}"
    [[ -z "$trimmed" || "${trimmed:0:1}" == "#" ]] && continue
    if [[ "$trimmed" =~ ^([[:alpha:]][[:alnum:]-]*)[[:space:]=] ]]; then
      keyword="${BASH_REMATCH[1],,}"
    else
      continue
    fi
    case "$keyword" in
      include)
        fail "isolated SSH config must not use Include"
        ;;
      match)
        fail "isolated SSH config must not use Match"
        ;;
    esac
  done < "$ssh_config"
}

extension_origin_pattern='^chrome-extension://[a-p]{32}$'
require_single_line "$host_alias" "host alias"
require_single_line "$expected_extension_origin" "expected extension Origin"
[[ "$expected_extension_origin" =~ $extension_origin_pattern ]] \
  || fail "expected extension Origin is invalid"

canonical_owned_regular_file "$ssh_config" "isolated SSH config"
ssh_config="$REPLY"
canonical_owned_regular_file "$expected_identity" "expected identity"
expected_identity="$REPLY"
require_private_identity_metadata "$expected_identity"
canonical_owned_regular_file "$expected_known_hosts" "expected known-hosts file"
expected_known_hosts="$REPLY"
canonical_regular_readable_file "$server_evidence" "server evidence"
server_evidence="$REPLY"
canonical_regular_readable_file "$gateway_evidence" "Gateway evidence"
gateway_evidence="$REPLY"

if [[ "$ssh_bin" != */* ]]; then
  ssh_bin="$(command -v -- "$ssh_bin" 2>/dev/null)" \
    || fail "SSH executable is unavailable"
fi
require_single_line "$ssh_bin" "SSH executable path"
ssh_bin="$(realpath -e -- "$ssh_bin" 2>/dev/null)" \
  || fail "SSH executable is unavailable"
[[ -f "$ssh_bin" && -x "$ssh_bin" ]] || fail "SSH executable is unavailable"

# Do not permit config directives that can change what ssh -G reads or execute code.
prescan_ssh_config

jq empty "$server_evidence" >/dev/null 2>&1 \
  || fail "server evidence is not valid JSON"
jq empty "$gateway_evidence" >/dev/null 2>&1 \
  || fail "Gateway evidence is not valid JSON"

require_json() {
  local file="$1"
  local expression="$2"
  local label="$3"

  jq -e --arg expected_extension_origin "$expected_extension_origin" \
    "$expression" "$file" >/dev/null 2>&1 \
    || fail "$label does not meet the MS-2 contract"
}

require_json "$server_evidence" '
  type == "object"
  and keys == ["account", "authorized_key", "kind", "schema_version", "sshd"]
  and .schema_version == 1
  and .kind == "liveconv-ms2-ssh-server-evidence"
  and .account == "liveconv-tunnel"
  and (.authorized_key | type == "object"
       and keys == ["permitopen", "port_forwarding", "restrict"]
       and .restrict == true
       and .port_forwarding == true
       and (.permitopen | type == "string"
            and index("\n") == null
            and index("\r") == null
            and test("^127\\.0\\.0\\.1:[1-9][0-9]{0,4}$")))
  and (.sshd | type == "object"
       and keys == ["allowagentforwarding", "allowstreamlocalforwarding", "allowtcpforwarding", "authenticationmethods", "disableforwarding", "kbdinteractiveauthentication", "maxsessions", "passwordauthentication", "permitopen", "permittty", "permittunnel", "permituserrc", "pubkeyauthentication", "x11forwarding"]
       and .authenticationmethods == "publickey"
       and .pubkeyauthentication == "yes"
       and .passwordauthentication == "no"
       and .kbdinteractiveauthentication == "no"
       and .disableforwarding == "no"
       and .allowtcpforwarding == "local"
       and .allowstreamlocalforwarding == "no"
       and (.permitopen | type == "string"
            and index("\n") == null
            and index("\r") == null
            and test("^127\\.0\\.0\\.1:[1-9][0-9]{0,4}$"))
       and .permittty == "no"
       and .permittunnel == "no"
       and .maxsessions == "0"
       and .x11forwarding == "no"
       and .allowagentforwarding == "no"
       and .permituserrc == "no")
' "server evidence"

server_port="$(jq -r '.sshd.permitopen | split(":")[-1]' "$server_evidence")"
key_port="$(jq -r '.authorized_key.permitopen | split(":")[-1]' "$server_evidence")"
[[ "$server_port" =~ ^[1-9][0-9]{0,4}$ && "$server_port" -le 65535 ]] \
  || fail "server PermitOpen port is invalid"
[[ "$key_port" == "$server_port" ]] \
  || fail "authorized-key PermitOpen differs from sshd PermitOpen"

require_json "$gateway_evidence" '
  type == "object"
  and keys == ["allowed_origin", "bearer_auth_required", "bind_host", "bind_port", "kind", "max_sessions", "schema_version", "ticket"]
  and .schema_version == 1
  and .kind == "liveconv-ms2-gateway-evidence"
  and .bind_host == "127.0.0.1"
  and .bearer_auth_required == true
  and .max_sessions == 1
  and (.bind_port | type == "number" and floor == . and . >= 1 and . <= 65535)
  and (.allowed_origin | type == "string"
       and index("\n") == null
       and index("\r") == null
       and test("^chrome-extension://[a-p]{32}$")
       and . == $expected_extension_origin)
  and (.ticket | type == "object"
       and keys == ["one_use", "ttl_seconds"]
       and .one_use == true
       and (.ttl_seconds | type == "number" and . > 0 and . <= 30))
' "Gateway evidence"

gateway_port="$(jq -r '.bind_port' "$gateway_evidence")"
[[ "$server_port" == "$gateway_port" ]] \
  || fail "server PermitOpen and Gateway bind port differ"

# This exact argv preserves the isolated config and makes a host alias starting
# with a dash unambiguously positional.
effective="$("$ssh_bin" -F "$ssh_config" -G -- "$host_alias" 2>/dev/null)" \
  || fail "cannot read effective SSH config"

values=()
read_values() {
  local name="$1"
  local value

  values=()
  while IFS= read -r value || [[ -n "$value" ]]; do
    values+=("$value")
  done < <(awk -v name="$name" '
    tolower($1) == name {
      sub(/^[^[:space:]]+[[:space:]]*/, "", $0)
      print
    }
  ' <<<"$effective")
}

read_exactly_one_value() {
  local name="$1"

  read_values "$name"
  [[ ${#values[@]} -eq 1 ]] || fail "expected one effective $name value"
  EFFECTIVE_VALUE="${values[0]}"
}

read_exactly_one_value user
[[ "$EFFECTIVE_VALUE" == "liveconv-tunnel" ]] \
  || fail "effective SSH user is not the forwarding account"
read_exactly_one_value identitiesonly
[[ "${EFFECTIVE_VALUE,,}" == "yes" ]] \
  || fail "effective SSH config does not require its dedicated identity"

read_exactly_one_value identityfile
[[ "${EFFECTIVE_VALUE,,}" != "none" ]] \
  || fail "effective SSH identity is disabled"
canonicalize_effective_path "$EFFECTIVE_VALUE" "effective SSH identity"
[[ "$REPLY" == "$expected_identity" ]] \
  || fail "effective SSH identity differs from the expected identity"

read_exactly_one_value userknownhostsfile
[[ "${EFFECTIVE_VALUE,,}" != "none" ]] \
  || fail "dedicated host-pin file is disabled"
canonicalize_effective_path "$EFFECTIVE_VALUE" "effective host-pin file"
known_hosts="$REPLY"
[[ "$known_hosts" == "$expected_known_hosts" ]] \
  || fail "effective host-pin file differs from the expected known-hosts file"
[[ -r "$known_hosts" ]] || fail "dedicated host-pin file is unavailable"

read_exactly_one_value globalknownhostsfile
[[ "${EFFECTIVE_VALUE,,}" == "none" ]] \
  || fail "global known-hosts source is enabled"
read_values knownhostscommand
for value in "${values[@]}"; do
  [[ "${value,,}" == "none" ]] || fail "KnownHostsCommand is enabled"
done
read_exactly_one_value verifyhostkeydns
case "${EFFECTIVE_VALUE,,}" in
  no|false) ;;
  *) fail "VerifyHostKeyDNS is enabled" ;;
esac
read_exactly_one_value nohostauthenticationforlocalhost
case "${EFFECTIVE_VALUE,,}" in
  no|false) ;;
  *) fail "NoHostAuthenticationForLocalhost is enabled" ;;
esac
read_values hostkeyalias
[[ ${#values[@]} -eq 0 ]] || fail "HostKeyAlias is configured"

read_exactly_one_value controlmaster
case "${EFFECTIVE_VALUE,,}" in
  no|false) ;;
  *) fail "ControlMaster is enabled" ;;
esac
read_values controlpath
if [[ ${#values[@]} -eq 1 && "${values[0],,}" == "none" ]]; then
  :
elif [[ ${#values[@]} -ne 0 ]]; then
  fail "ControlPath is configured"
fi
read_exactly_one_value controlpersist
case "${EFFECTIVE_VALUE,,}" in
  no|false) ;;
  *) fail "ControlPersist is enabled" ;;
esac

read_exactly_one_value stricthostkeychecking
case "${EFFECTIVE_VALUE,,}" in
  yes|true) ;;
  *) fail "strict host-key checking is disabled" ;;
esac
read_exactly_one_value updatehostkeys
case "${EFFECTIVE_VALUE,,}" in
  no|false) ;;
  *) fail "UpdateHostKeys is enabled" ;;
esac
read_exactly_one_value batchmode
[[ "${EFFECTIVE_VALUE,,}" == "yes" ]] || fail "BatchMode is disabled"
read_exactly_one_value exitonforwardfailure
[[ "${EFFECTIVE_VALUE,,}" == "yes" ]] \
  || fail "ExitOnForwardFailure is disabled"

read_exactly_one_value hostname
remote_host="$EFFECTIVE_VALUE"
[[ -n "$remote_host" && "$remote_host" != *[[:space:]]* ]] \
  || fail "effective SSH host is invalid"
read_exactly_one_value port
remote_port="$EFFECTIVE_VALUE"
[[ "$remote_port" =~ ^[1-9][0-9]{0,4}$ && "$remote_port" -le 65535 ]] \
  || fail "effective SSH port is invalid"
if [[ "$remote_port" == "22" ]]; then
  known_host_lookup="$remote_host"
else
  known_host_lookup="[$remote_host]:$remote_port"
fi
known_host_matches="$(ssh-keygen -F "$known_host_lookup" -f "$known_hosts" 2>/dev/null)" \
  || fail "dedicated host-pin file has no entry for the effective SSH host"

validate_matching_host_pins() {
  local record
  local first
  local second
  local third
  local fourth
  local marker
  local key_type
  local key_blob
  local key_id
  local -A candidate_keys=()
  local -A revoked_keys=()

  while IFS= read -r record || [[ -n "$record" ]]; do
    [[ -z "$record" || "$record" =~ ^[[:space:]]*# ]] && continue
    first=""
    second=""
    third=""
    fourth=""
    marker=""
    key_type=""
    key_blob=""
    read -r first second third fourth _ <<<"$record"
    case "$first" in
      @revoked)
        marker="$first"
        key_type="$third"
        key_blob="$fourth"
        ;;
      @*)
        marker="$first"
        key_type="$third"
        key_blob="$fourth"
        ;;
      *)
        key_type="$second"
        key_blob="$third"
        ;;
    esac
    [[ -n "$key_type" && -n "$key_blob" ]] \
      || fail "dedicated host-pin file has an invalid matching key"
    if ! printf '%s %s\n' "$key_type" "$key_blob" \
      | ssh-keygen -lf - >/dev/null 2>&1; then
      fail "dedicated host-pin file has an invalid matching key"
    fi
    key_id="$key_type:$key_blob"
    if [[ "$marker" == "@revoked" ]]; then
      revoked_keys["$key_id"]=1
    else
      candidate_keys["$key_id"]=1
    fi
  done <<<"$known_host_matches"

  [[ ${#candidate_keys[@]} -gt 0 ]] \
    || fail "dedicated host-pin file has only revoked entries for the effective SSH host"
  for key_id in "${!candidate_keys[@]}"; do
    [[ -z "${revoked_keys[$key_id]+present}" ]] \
      || fail "dedicated host-pin file marks a candidate key as revoked"
  done
}

validate_matching_host_pins

read_values localforward
[[ ${#values[@]} -eq 1 ]] || fail "expected exactly one LocalForward"
local_forward="${values[0]}"
if [[ "$local_forward" =~ ^\[127\.0\.0\.1\]:([1-9][0-9]{0,4})\ \[127\.0\.0\.1\]:([1-9][0-9]{0,4})$ ]]; then
  listen_port="${BASH_REMATCH[1]}"
  target_port="${BASH_REMATCH[2]}"
else
  fail "LocalForward is not IPv4-loopback only"
fi
[[ "$listen_port" -le 65535 && "$target_port" -le 65535 ]] \
  || fail "LocalForward port is invalid"
[[ "$target_port" == "$gateway_port" ]] \
  || fail "LocalForward target does not match the remote Gateway port"

read_values dynamicforward
[[ ${#values[@]} -eq 0 ]] || fail "dynamic forwarding is configured"
read_values remoteforward
[[ ${#values[@]} -eq 0 ]] || fail "remote forwarding is configured"

jq -n \
  --argjson listen_port "$listen_port" \
  --argjson target_port "$target_port" \
  '{
    schema_version: 1,
    check: "liveconv-ms2-ssh-preflight",
    status: "pass",
    client: {
      host_key_pinned: true,
      strict_host_key_checking: true,
      local_forward: {
        listen_host: "127.0.0.1",
        listen_port: $listen_port,
        target_host: "127.0.0.1",
        target_port: $target_port
      }
    },
    server: { forwarding_only: true, permitopen_loopback: true },
    gateway: {
      loopback_bound: true,
      bearer_auth_required: true,
      exact_extension_origin: true,
      one_use_ticket: true,
      max_sessions: 1
    }
  }'
