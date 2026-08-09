# External Codex pool

Status: Development tool

`scripts/codex-pool.sh` runs independent, non-interactive Codex tasks in detached
tmux sessions. A JSON manifest fixes each task's model, reasoning level, access
mode, prompt file, and exclusive write ownership before any process starts.

The pool is intended for trusted repository work on one host. It coordinates
writers and keeps observable run state; it is not a security boundary for hostile
prompts or unrelated local processes.

## Prerequisites

Install `codex`, `tmux`, `jq`, `flock`, `realpath`, `sha256sum`, and standard
core utilities including `cp`. Authenticate the Codex CLI through its normal
login flow before starting the pool. The pool does not accept token fields,
hardcode tokens, inspect authentication files, or print credential environment
variables.

State defaults to `${TMPDIR:-/tmp}/liveconv-codex-pool`. Override it with
`--state-dir DIR` or `CODEX_POOL_STATE_DIR`. The resolved state directory must be
outside the repository and must not contain the repository.

## Manifest version 1

The manifest must be a regular, non-symlink JSON file outside a sensitive path;
the launcher rejects a sensitive manifest path before parsing it. Unknown keys are
rejected, which also prevents adding ad hoc commands, token fields, or implicit
defaults. Prompt paths and ownership paths are repository-relative.

```json
{
  "schema_version": 1,
  "pool": "audio-checkpoint",
  "max_processes": 2,
  "tasks": [
    {
      "id": "review-protocol",
      "model": "gpt-5.6-sol",
      "reasoning": "max",
      "mode": "read-only",
      "prompt": "prompts/pool/review-protocol.md",
      "owns": []
    },
    {
      "id": "implement-adapter",
      "model": "gpt-5.6-terra",
      "reasoning": "xhigh",
      "mode": "owned-write",
      "prompt": "prompts/pool/implement-adapter.md",
      "owns": [
        "workers/adapters/example.py",
        "workers/tests/test_example.py"
      ]
    }
  ]
}
```

Fields have these constraints:

- `pool` and task `id` use lowercase letters, digits, and hyphens; they begin
  with a letter and are at most 48 characters.
- `model` is exactly `gpt-5.6-sol` or `gpt-5.6-terra`.
- `reasoning` is `low`, `medium`, `high`, `xhigh`, `max`, or `ultra`.
- `mode` is `read-only` or `owned-write`.
- A read-only task has an empty `owns` array and uses the Codex `read-only`
  sandbox.
- An owned-write task has at least one ownership path and uses the Codex
  `workspace-write` sandbox.
- Prompt files must already exist. Prompt and ownership paths named `key`,
  `.env`, `credentials`, `secrets`, common SSH private-key names, or private-key
  file extensions are rejected. Prompt and ownership validation also reject a
  symlink whose canonical target has a sensitive path component; this includes an
  intermediate prompt-directory symlink and a dangling ownership symlink. Paths
  may not escape the repository, and a task may not own the repository root or
  `.git`.

The manifest is invalid if two owned-write tasks declare equal, ancestor, or
descendant paths. Use disjoint leaf paths when possible; declaring a directory
claims everything below it.

## Commands

Validate structure and paths first:

```bash
scripts/codex-pool.sh validate /path/to/tasks.json
```

Preview the selection without creating state, claims, logs, or tmux sessions:

```bash
scripts/codex-pool.sh --dry-run start /path/to/tasks.json
scripts/codex-pool.sh --dry-run start /path/to/tasks.json review-protocol
```

Start all tasks or an explicit subset:

```bash
scripts/codex-pool.sh start /path/to/tasks.json
scripts/codex-pool.sh start /path/to/tasks.json implement-adapter
```

Inspect state and outputs:

```bash
scripts/codex-pool.sh status /path/to/tasks.json
scripts/codex-pool.sh status /path/to/tasks.json implement-adapter
scripts/codex-pool.sh logs /path/to/tasks.json implement-adapter
scripts/codex-pool.sh final /path/to/tasks.json implement-adapter
```

`status` prints tab-separated task, effective state, tmux session, model,
reasoning, mode, and run directory. `logs` prints the combined Codex JSONL and
error stream. `final` prints the last assistant message captured with
`--output-last-message`.

Stop all tasks or an explicit subset:

```bash
scripts/codex-pool.sh --dry-run stop /path/to/tasks.json
scripts/codex-pool.sh stop /path/to/tasks.json implement-adapter
scripts/codex-pool.sh stop /path/to/tasks.json
```

`stop` kills only the exact recorded tmux session, marks a nonterminal run
stopped, and removes only the ownership claim whose random run token still
matches. It is also the explicit recovery operation for stale state.

Treat the manifest and referenced prompt files as immutable while any task is
active. Stop the affected tasks before moving, deleting, or renaming a manifest,
prompt, or task ID; lifecycle commands use that declaration to locate exact run
state.

Manifest errors exit with status 2. Operational conflicts exit with status 1.
`status` exits with status 3 if it reports invalid or stale state; otherwise it
exits with status 0. A terminal state remains terminal while its tmux process is
finishing, so normal completion does not transiently report an orphaned session.

## Process and ownership guards

`max_processes` limits active sessions for that manifest. A second,
repository-wide ceiling comes from `CODEX_POOL_MAX_PROCESSES`, defaults to 4,
and cannot exceed 32. A start is rejected before launch if either ceiling would
be exceeded. Select task IDs explicitly when a manifest contains more tasks than
its process limit. Before scanning and launching, every non-dry-run start takes
one canonical per-repository process lock at
`/tmp/liveconv-codex-pool-locks-$UID/SHA256(REPOSITORY_PATH).processes.lock`.
That lock is independent of `--state-dir` and `CODEX_POOL_STATE_DIR`, so alternate
state roots cannot race past the repository ceiling.

Every session name includes a repository-path hash, bounded pool and task labels,
and a hash derived from a fresh 128-bit run token. Re-running a task therefore
uses a different tmux name. Tokens are exactly 32 lowercase hexadecimal
characters. The full token is stored only in mode-0600 state and claim files; it
is neither printed nor included in the tmux pane command.

Owned-write claims are repository-wide across all pool manifests that use the
same state root. Starts take an exclusive `flock`, scan every active claim, and
reject equal, ancestor, or descendant overlaps before atomically publishing new
claims. The lock covers claim creation and tmux launch, so concurrent launchers
cannot both acquire a path.

Claims coordinate cooperating `codex-pool.sh` processes. They do not lock the
filesystem against a user, an unrelated tool, or a pool configured with a
different state root. The canonical process ceiling still applies across those
roots. The `owns` list is also injected into the task's safety prompt, but Codex
`workspace-write` applies to the workspace as a whole rather than only those
leaf paths. Review the diff after every writer run.

### Trusted-host read-only fallback

Some isolated Linux hosts disable the user namespaces required by Codex's
`read-only` sandbox and fail every command with a `bwrap` namespace error. Do not
silently treat that as a review pass. On a trusted disposable development host
only, an operator may explicitly run read-only tasks with:

```bash
CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY=1 \
CODEX_POOL_MAX_PROCESSES=16 \
scripts/codex-pool.sh start /path/to/tasks.json
```

The run state records `sandbox: danger-full-access`, while `mode` remains
`read-only`. The launcher still injects the no-edit, no-subagent, no-credential,
and no-Git-mutation contract. This is behavioral enforcement rather than an OS
security boundary, so never use it for untrusted prompts, repositories, or
machines. It is not available to `owned-write` tasks: writers continue to use
the `workspace-write` sandbox even when this switch is present. It is not the
default.

## State and stale sessions

State is private to the invoking user (`umask 077`) and has this shape:

```text
STATE_ROOT/
  repos/REPOSITORY_HASH/
    claims.lock
    claims/CLAIM_HASH.json
    pools/POOL_HASH/tasks/TASK/
      current.json
      runs/RUN_ID/
        manifest.json
        prompt.md
        run.log
        final.txt
```

The latest `current.json` records the random token, exact session, timestamps,
exit code, task settings, artifact paths, and SHA-256 hashes for the captured
manifest and prompt. The runner verifies both hashes and reads the mode-0600
`prompt.md` file in its private run directory; it also verifies that the snapshot
task settings match the state it is about to execute. Changing the source prompt
after `start` does not change that run's input. Codex runs use `--ephemeral`, so
the pool does not intentionally persist a resumable Codex transcript. Logs and
final messages can still contain task output and should be treated as private.

A task is `stale` when its recorded state is `starting` or `running` but its
exact tmux session no longer exists. `status` reads current state under a shared
lock, and `final` holds that lock from generation validation through output, so a
concurrent restart cannot mix generations. Inspect stale state, then use `stop`
with the same manifest to terminate any exact recorded session and release that
task's token-matched claim. Claims are never silently stolen or reclaimed by a
new start.

## Safety contract

Each run pins the selected model, effort, sandbox, working directory, and
non-interactive approval policy. Multi-agent tools are disabled. Model-generated
shells inherit only Codex's core environment, with default exclusions for names
containing `KEY`, `SECRET`, or `TOKEN`. `/tmp` and `$TMPDIR` are excluded from
model-generated workspace-write roots so pool state is not a writable task path.

Before the prompt file, the launcher adds mandatory instructions to:

- avoid subagents and model switching;
- never read credential, environment, ignored `key`, or private-key files;
- never inspect authentication stores or print credential-like variables;
- never commit, push, reset, clean, stash, or rewrite history;
- preserve unrelated working-tree changes; and
- remain read-only or edit only the declared ownership paths.

The launcher itself never runs `git commit` or `git push`. It also never scans
prompt contents for secrets, because doing so would require reading possibly
sensitive input. Operators must use reviewed, non-secret prompt files.

The credential-file prohibition is enforced by path validation and agent
instructions, not by an operating-system read-denial layer. The Codex CLI still
uses its normal authenticated client configuration. For untrusted prompts or a
checkout containing readable credentials, use a clean isolated worktree or
container with those files absent, or an administrator-enforced filesystem
`deny_read` policy, before starting the pool.
