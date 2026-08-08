#!/usr/bin/env bash
set -euo pipefail

if (($# != 3)); then
  printf 'usage: %s EXP-NNN short-slug "Experiment title"\n' "$0" >&2
  exit 2
fi

experiment_id="$1"
slug="$2"
title="$3"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
registry="$root/experiments/registry.json"

[[ "$experiment_id" =~ ^EXP-[0-9]{3}$ ]] || {
  printf 'invalid experiment ID: %s\n' "$experiment_id" >&2
  exit 2
}

[[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
  printf 'invalid slug: %s\n' "$slug" >&2
  exit 2
}

if ((${#title} < 3)); then
  printf 'experiment title must contain at least 3 characters\n' >&2
  exit 2
fi

if jq -e --arg id "$experiment_id" '.experiments[] | select(.id == $id)' "$registry" >/dev/null; then
  printf 'experiment already registered: %s\n' "$experiment_id" >&2
  exit 1
fi

directory="$root/experiments/$experiment_id-$slug"
path="experiments/$experiment_id-$slug/experiment.json"
[[ ! -e "$directory" ]] || {
  printf 'experiment directory already exists: %s\n' "$directory" >&2
  exit 1
}

timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
staging_directory="$(mktemp -d "$root/experiments/.new-$experiment_id.XXXXXX")"
temporary_registry="$(mktemp "$root/experiments/.registry.XXXXXX")"
directory_installed=0

cleanup() {
  rm -rf "$staging_directory"
  rm -f "$temporary_registry"
  if ((directory_installed == 1)); then
    rm -rf "$directory"
  fi
}
trap cleanup EXIT INT TERM

jq -n \
  --arg id "$experiment_id" \
  --arg title "$title" \
  --arg timestamp "$timestamp" \
  '{
    schema_version: 1,
    id: $id,
    title: $title,
    status: "draft",
    phase: 0,
    owner: null,
    created_at: $timestamp,
    updated_at: $timestamp,
    question: "TBD: state one primary question.",
    hypothesis: "TBD: state one falsifiable hypothesis.",
    links: [],
    control: {id: "control", description: "TBD control", configuration: {}},
    variants: [{id: "variant_a", description: "TBD variant", configuration: {}}],
    fixtures: {manifest: "TBD", version: "draft-0", classification: "synthetic", frozen: false},
    environment: {git_commit: "TBD", runtime: "TBD", hardware: "TBD", model_revisions: {}},
    procedure: {
      summary: "TBD: define the controlled procedure.",
      warmup: "TBD",
      sample_count: null,
      commands: [],
      invalidation_conditions: ["The frozen protocol changes after approval."]
    },
    metrics: [{name: "TBD", kind: "quality", unit: "TBD", primary: true}],
    decision_rule: "TBD: define a falsifiable decision rule before approval.",
    artifact_policy: {
      raw_location: "TBD: authorized artifact store",
      git_contents: "Aggregate metrics and decision only.",
      retention: "TBD",
      authorization: "TBD"
    },
    result: null,
    decision: null
  }' > "$staging_directory/experiment.json"

printf '# %s working notes\n\nResolve all material TBD fields before approval.\n' "$experiment_id" > "$staging_directory/notes.md"

jq \
  --arg id "$experiment_id" \
  --arg slug "$slug" \
  --arg title "$title" \
  --arg path "$path" \
  '.experiments += [{id: $id, slug: $slug, title: $title, status: "draft", phase: 0, path: $path, owner: null}] | .experiments |= sort_by(.id)' \
  "$registry" > "$temporary_registry"

python3 "$root/scripts/validate-json.py" \
  "$root/schemas/experiment.schema.json" \
  "$staging_directory/experiment.json"
python3 "$root/scripts/validate-json.py" \
  "$root/schemas/experiment-registry.schema.json" \
  "$temporary_registry"

mv "$staging_directory" "$directory"
directory_installed=1
mv "$temporary_registry" "$registry"
directory_installed=0
trap - EXIT INT TERM

printf 'created %s\n' "$path"
printf 'next: resolve TBD fields, review the plan, then set status to approved in both files\n'
