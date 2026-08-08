#!/usr/bin/env bash
set -euo pipefail

if (($# != 1)); then
  printf 'usage: %s /path/to/private-key\n' "$0" >&2
  exit 2
fi

source_key="$1"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_key="$HOME/.ssh/liveconv_github"
known_hosts="$HOME/.ssh/known_hosts"
github_ed25519='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'

if [[ ! -f "$source_key" ]]; then
  printf 'private key not found: %s\n' "$source_key" >&2
  exit 1
fi

if [[ "$(readlink -f "$source_key")" == "$(readlink -m "$target_key")" ]]; then
  printf 'source key must differ from installed target: %s\n' "$target_key" >&2
  exit 2
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
umask 077

# Uploaded workspace files can lose mode bits and the final newline. Re-encode
# only the line endings while copying into a filesystem OpenSSH accepts.
sed -e 's/\r$//' -e '$a\' "$source_key" > "$target_key"
chmod 600 "$target_key"

# GitHub publishes this host key and fingerprint in its SSH documentation.
touch "$known_hosts"
chmod 600 "$known_hosts"
if ! grep -qxF "$github_ed25519" "$known_hosts"; then
  printf '%s\n' "$github_ed25519" >> "$known_hosts"
fi

if ! ssh-keygen -y -f "$target_key" >/dev/null; then
  printf 'the supplied file is not a usable OpenSSH private key\n' >&2
  exit 1
fi

cd "$root"
git config core.sshCommand "ssh -i $target_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts"

if git ls-remote origin >/dev/null; then
  printf 'GitHub SSH authentication is ready for %s\n' "$(git remote get-url origin)"
else
  printf 'key installed, but the configured origin is not accessible\n' >&2
  exit 1
fi
