from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

SOURCE_SCRIPT = Path(__file__).parents[1] / "codex-pool.sh"

FAKE_TMUX = r"""#!/usr/bin/env python3
import fcntl
import json
import os
import sys
import time
from pathlib import Path

state_path = Path(os.environ["FAKE_TMUX_STATE"])
lock_path = state_path.with_suffix(state_path.suffix + ".lock")


def load_state():
    if not state_path.exists():
        return {"commands": [], "sessions": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    temporary.replace(state_path)


args = sys.argv[1:]
if not args:
    raise SystemExit(2)

command = args[0]
lock_path.parent.mkdir(parents=True, exist_ok=True)
with lock_path.open("a+", encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    state = load_state()
    if command == "has-session":
        target = args[args.index("-t") + 1].removeprefix("=")
        exit_code = 0 if target in state["sessions"] else 1
    elif command == "list-sessions":
        sessions = list(state["sessions"])
        exit_code = 0
    elif command == "new-session":
        if os.environ.get("FAKE_TMUX_FAIL_NEW") == "1":
            exit_code = 1
        else:
            session = args[args.index("-s") + 1]
            if session in state["sessions"]:
                exit_code = 1
            else:
                state["sessions"].append(session)
                state["commands"].append({"command": args[-1], "session": session})
                save_state(state)
                exit_code = 0
    elif command == "kill-session":
        target = args[args.index("-t") + 1].removeprefix("=")
        state["sessions"] = [item for item in state["sessions"] if item != target]
        save_state(state)
        exit_code = 0
    else:
        exit_code = 2

if command == "list-sessions":
    # Return an atomic session snapshot after an optional test-only delay. This
    # makes competing launchers deterministically exercise the launcher lock.
    time.sleep(float(os.environ.get("FAKE_TMUX_LIST_DELAY_SECONDS", "0")))
    for session in sessions:
        print(session)
raise SystemExit(exit_code)
"""

FAKE_CODEX = r"""#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
time.sleep(float(os.environ.get("FAKE_CODEX_SLEEP_SECONDS", "0")))
capture_path = Path(os.environ["FAKE_CODEX_CAPTURE"])
capture_path.parent.mkdir(parents=True, exist_ok=True)
capture_path.write_text(
    json.dumps({"args": args, "prompt": prompt}, sort_keys=True),
    encoding="utf-8",
)
output_flag = args.index("--output-last-message")
final_path = Path(args[output_flag + 1])
final_path.write_text("fake final output\n", encoding="utf-8")
print(json.dumps({"type": "fake.completed"}, sort_keys=True))
raise SystemExit(int(os.environ.get("FAKE_CODEX_EXIT", "0")))
"""


def task(
    task_id: str,
    *,
    mode: str = "read-only",
    model: str = "gpt-5.6-terra",
    reasoning: str = "high",
    prompt: str = "prompts/task.md",
    owns: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "mode": mode,
        "model": model,
        "owns": owns or [],
        "prompt": prompt,
        "reasoning": reasoning,
    }


def manifest(
    *tasks: dict[str, Any], pool: str = "test-pool", max_processes: int = 4
) -> dict[str, Any]:
    return {
        "max_processes": max_processes,
        "pool": pool,
        "schema_version": 1,
        "tasks": list(tasks),
    }


def make_repo(tmp_path: Path, name: str = "repo") -> tuple[Path, dict[str, str]]:
    repo = tmp_path / name
    scripts = repo / "scripts"
    prompts = repo / "prompts"
    fake_bin = tmp_path / "fake-bin"
    scripts.mkdir(parents=True)
    prompts.mkdir()
    fake_bin.mkdir()

    script = scripts / "codex-pool.sh"
    shutil.copy2(SOURCE_SCRIPT, script)
    script.chmod(0o755)
    (prompts / "task.md").write_text("Inspect the requested scope.\n", encoding="utf-8")
    (prompts / "writer.md").write_text(
        "Implement only the owned file.\n", encoding="utf-8"
    )

    tmux = fake_bin / "tmux"
    codex = fake_bin / "codex"
    tmux.write_text(FAKE_TMUX, encoding="utf-8")
    codex.write_text(FAKE_CODEX, encoding="utf-8")
    tmux.chmod(0o755)
    codex.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CODEX_POOL_MAX_PROCESSES": "4",
            "CODEX_POOL_STATE_DIR": str(tmp_path / "pool-state"),
            "FAKE_CODEX_CAPTURE": str(tmp_path / "codex-capture.json"),
            "FAKE_TMUX_STATE": str(tmp_path / "tmux-state.json"),
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )
    return repo, environment


def write_manifest(repo: Path, data: dict[str, Any], name: str = "tasks.json") -> Path:
    path = repo / name
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def run_pool(
    repo: Path,
    environment: dict[str, str],
    *arguments: str | Path,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(repo / "scripts" / "codex-pool.sh"), *(str(arg) for arg in arguments)],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        pytest.fail(
            f"pool command failed ({result.returncode})\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def tmux_state(environment: dict[str, str]) -> dict[str, Any]:
    path = Path(environment["FAKE_TMUX_STATE"])
    if not path.exists():
        return {"commands": [], "sessions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def kill_fake_session(environment: dict[str, str], session: str) -> None:
    subprocess.run(
        ["tmux", "kill-session", "-t", f"={session}"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def current_states(environment: dict[str, str]) -> list[Path]:
    state_root = Path(environment["CODEX_POOL_STATE_DIR"])
    return sorted(state_root.glob("repos/*/pools/*/tasks/*/current.json"))


def current_state_for(
    environment: dict[str, str], task_id: str
) -> tuple[Path, dict[str, Any]]:
    for path in current_states(environment):
        state = json.loads(path.read_text(encoding="utf-8"))
        if state["task"] == task_id:
            return path, state
    pytest.fail(f"no current state for task {task_id}")


def wait_for_file(path: Path, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists(), f"timed out waiting for {path}"


def test_validate_and_dry_run_are_declarative_and_non_mutating(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    data = manifest(
        task("review", model="gpt-5.6-sol", reasoning="xhigh"),
        task(
            "writer",
            mode="owned-write",
            model="gpt-5.6-terra",
            reasoning="max",
            prompt="prompts/writer.md",
            owns=["src/owned.py"],
        ),
        max_processes=2,
    )
    manifest_path = write_manifest(repo, data)

    validated = run_pool(repo, environment, "validate", manifest_path, check=True)
    assert validated.stdout == "valid\tpool=test-pool\ttasks=2\tmax_processes=2\n"

    state_root = Path(environment["CODEX_POOL_STATE_DIR"])
    planned = run_pool(
        repo, environment, "--dry-run", "start", manifest_path, check=True
    )
    assert "would-start\treview\t" in planned.stdout
    assert "model=gpt-5.6-sol" in planned.stdout
    assert "mode=read-only\tsandbox=read-only" in planned.stdout
    assert "would-start\twriter\t" in planned.stdout
    assert "reasoning=max\tmode=owned-write\tsandbox=workspace-write" in planned.stdout
    assert 'owns=["src/owned.py"]' in planned.stdout
    assert not state_root.exists()
    assert not Path(environment["FAKE_TMUX_STATE"]).exists()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["tasks"][0].update({"model": "gpt-5.6-luna"}),
            "schema version 1",
        ),
        (
            lambda value: value["tasks"][0].update({"api_token": "not-a-token"}),
            "schema version 1",
        ),
        (
            lambda value: value["tasks"][0].update({"prompt": "key"}),
            "sensitive path",
        ),
    ],
)
def test_manifest_rejects_unsupported_or_sensitive_fields(
    tmp_path: Path, mutate: Any, message: str
) -> None:
    repo, environment = make_repo(tmp_path)
    data = manifest(task("review"))
    mutate(data)
    manifest_path = write_manifest(repo, data)

    result = run_pool(repo, environment, "validate", manifest_path)

    assert result.returncode == 2
    assert message in result.stderr


def test_sensitive_manifest_path_is_rejected_before_opening_it(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)

    result = run_pool(repo, environment, "validate", repo / "key")

    assert result.returncode == 2
    assert "manifest uses a sensitive path" in result.stderr
    assert "regular, non-symlink" not in result.stderr


def test_ownership_symlink_to_sensitive_target_is_rejected_without_target_content(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    (repo / "owned-link").symlink_to("key")
    manifest_path = write_manifest(
        repo,
        manifest(task("writer", mode="owned-write", owns=["owned-link"])),
    )

    result = run_pool(repo, environment, "validate", manifest_path)

    assert result.returncode == 2
    assert "ownership resolves to a sensitive path: owned-link" in result.stderr


def test_prompt_intermediate_symlink_to_sensitive_directory_is_rejected(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    sensitive_directory = repo / "secrets"
    sensitive_directory.mkdir()
    (sensitive_directory / "task.md").write_text(
        "This prompt must never be snapshotted or sent.\n", encoding="utf-8"
    )
    (repo / "prompts" / "prompt-alias").symlink_to(
        "../secrets", target_is_directory=True
    )
    manifest_path = write_manifest(
        repo,
        manifest(task("review", prompt="prompts/prompt-alias/task.md")),
    )

    result = run_pool(repo, environment, "validate", manifest_path)

    assert result.returncode == 2
    assert (
        "prompt resolves to a sensitive path: prompts/prompt-alias/task.md"
        in result.stderr
    )
    assert not Path(environment["CODEX_POOL_STATE_DIR"]).exists()


def test_manifest_rejects_overlapping_owned_paths(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    data = manifest(
        task("first", mode="owned-write", owns=["src"]),
        task("second", mode="owned-write", owns=["src/module.py"]),
    )
    manifest_path = write_manifest(repo, data)

    result = run_pool(repo, environment, "validate", manifest_path)

    assert result.returncode == 2
    assert "ownership collision in manifest" in result.stderr


def test_process_ceiling_blocks_a_second_session(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    data = manifest(task("first"), task("second"), max_processes=1)
    manifest_path = write_manifest(repo, data)

    first = run_pool(repo, environment, "start", manifest_path, "first", check=True)
    assert first.stdout.startswith("started\tfirst\tlcp-")

    blocked = run_pool(repo, environment, "start", manifest_path, "second")
    assert blocked.returncode == 1
    assert "manifest process ceiling 1 would be exceeded" in blocked.stderr

    run_pool(repo, environment, "stop", manifest_path, "first", check=True)
    second = run_pool(repo, environment, "start", manifest_path, "second", check=True)
    assert second.stdout.startswith("started\tsecond\tlcp-")
    run_pool(repo, environment, "stop", manifest_path, "second", check=True)


def test_repository_process_ceiling_uses_one_canonical_lock_across_state_roots(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    environment["CODEX_POOL_MAX_PROCESSES"] = "1"
    environment["FAKE_TMUX_LIST_DELAY_SECONDS"] = "0.3"
    manifest_path = write_manifest(
        repo,
        manifest(task("first"), task("second"), max_processes=1),
    )
    first_state_root = tmp_path / "state-a"
    second_state_root = tmp_path / "state-b"
    commands = [
        [
            str(repo / "scripts" / "codex-pool.sh"),
            "--state-dir",
            str(first_state_root),
            "start",
            str(manifest_path),
            "first",
        ],
        [
            str(repo / "scripts" / "codex-pool.sh"),
            "--state-dir",
            str(second_state_root),
            "start",
            str(manifest_path),
            "second",
        ],
    ]
    launchers = [
        subprocess.Popen(
            command,
            cwd=repo,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for command in commands
    ]
    results = [launcher.communicate(timeout=5) for launcher in launchers]

    return_codes = [launcher.returncode for launcher in launchers]
    assert sorted(return_codes) == [0, 1]
    failed_stderr = results[return_codes.index(1)][1]
    assert "repository process ceiling 1 would be exceeded" in failed_stderr
    assert len(tmux_state(environment)["sessions"]) == 1

    run_pool(
        repo,
        environment,
        "--state-dir",
        first_state_root,
        "stop",
        manifest_path,
        "first",
        check=True,
    )
    run_pool(
        repo,
        environment,
        "--state-dir",
        second_state_root,
        "stop",
        manifest_path,
        "second",
        check=True,
    )


def test_repository_wide_ownership_claims_block_overlaps(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    first_manifest = write_manifest(
        repo,
        manifest(task("writer-a", mode="owned-write", owns=["src"]), pool="pool-a"),
        "first.json",
    )
    second_manifest = write_manifest(
        repo,
        manifest(
            task("writer-b", mode="owned-write", owns=["src/module.py"]),
            pool="pool-b",
        ),
        "second.json",
    )

    run_pool(repo, environment, "start", first_manifest, check=True)
    collision = run_pool(repo, environment, "start", second_manifest)

    assert collision.returncode == 1
    assert (
        "ownership collision: writer-b:src/module.py overlaps writer-a:src"
        in collision.stderr
    )

    run_pool(repo, environment, "stop", first_manifest, check=True)
    run_pool(repo, environment, "start", second_manifest, check=True)
    run_pool(repo, environment, "stop", second_manifest, check=True)


def test_stale_session_fails_closed_until_explicit_stop(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    manifest_path = write_manifest(
        repo, manifest(task("writer", mode="owned-write", owns=["src/owned.py"]))
    )

    started = run_pool(repo, environment, "start", manifest_path, check=True)
    first_session = started.stdout.split("\t")[2]
    kill_fake_session(environment, first_session)

    status = run_pool(repo, environment, "status", manifest_path)
    assert status.returncode == 3
    assert "writer\tstale\t" in status.stdout
    restart = run_pool(repo, environment, "start", manifest_path)
    assert restart.returncode == 1
    assert "stale state; run stop before restarting" in restart.stderr

    run_pool(repo, environment, "stop", manifest_path, check=True)
    claims = Path(environment["CODEX_POOL_STATE_DIR"]).glob("repos/*/claims/*.json")
    assert not list(claims)

    restarted = run_pool(repo, environment, "start", manifest_path, check=True)
    second_session = restarted.stdout.split("\t")[2]
    assert second_session != first_session
    run_pool(repo, environment, "stop", manifest_path, check=True)


def test_state_and_claim_tokens_must_match_the_strict_generated_format(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    first_manifest = write_manifest(
        repo,
        manifest(task("writer", mode="owned-write", owns=["src/owned.py"])),
        "first.json",
    )
    second_manifest = write_manifest(
        repo,
        manifest(task("review"), pool="second-pool"),
        "second.json",
    )
    run_pool(repo, environment, "start", first_manifest, check=True)
    current_file, current = current_state_for(environment, "writer")
    current["run_token"] = "f" * 31
    current_file.write_text(json.dumps(current), encoding="utf-8")

    status = run_pool(repo, environment, "status", first_manifest)
    assert status.returncode == 3
    assert "writer\tinvalid-state\t" in status.stdout

    [claim_file] = Path(environment["CODEX_POOL_STATE_DIR"]).glob(
        "repos/*/claims/*.json"
    )
    claim = json.loads(claim_file.read_text(encoding="utf-8"))
    claim["run_token"] = ""
    claim_file.write_text(json.dumps(claim), encoding="utf-8")

    blocked = run_pool(repo, environment, "start", second_manifest)
    assert blocked.returncode == 1
    assert "malformed ownership claim" in blocked.stderr


def test_runner_pins_safety_options_and_records_outputs(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path, "repo with 'quote")
    environment["CODEX_POOL_STATE_DIR"] = str(tmp_path / "state with 'quote")
    manifest_path = write_manifest(
        repo,
        manifest(
            task(
                "writer",
                mode="owned-write",
                model="gpt-5.6-sol",
                reasoning="ultra",
                prompt="prompts/writer.md",
                owns=["src/owned.py"],
            ),
            max_processes=1,
        ),
    )

    started = run_pool(repo, environment, "start", manifest_path, check=True)
    session = started.stdout.split("\t")[2]
    command = tmux_state(environment)["commands"][0]["command"]
    current_file, current_before_run = current_state_for(environment, "writer")
    assert current_before_run["run_token"] not in command
    assert current_file.stat().st_mode & 0o777 == 0o600
    manifest_snapshot = Path(current_before_run["manifest_snapshot"])
    prompt_snapshot = Path(current_before_run["prompt_snapshot"])
    assert manifest_snapshot.read_bytes() == manifest_path.read_bytes()
    assert (
        prompt_snapshot.read_text(encoding="utf-8")
        == "Implement only the owned file.\n"
    )
    assert (
        current_before_run["manifest_sha256"]
        == hashlib.sha256(manifest_snapshot.read_bytes()).hexdigest()
    )
    assert (
        current_before_run["prompt_sha256"]
        == hashlib.sha256(prompt_snapshot.read_bytes()).hexdigest()
    )
    assert manifest_snapshot.stat().st_mode & 0o777 == 0o600
    assert prompt_snapshot.stat().st_mode & 0o777 == 0o600
    (repo / "prompts" / "writer.md").write_text(
        "Replacement prompt that must not reach the run.\n", encoding="utf-8"
    )

    runner = subprocess.run(
        ["bash", "-c", command],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert runner.returncode == 0, runner.stderr

    capture = json.loads(
        Path(environment["FAKE_CODEX_CAPTURE"]).read_text(encoding="utf-8")
    )
    arguments = capture["args"]
    assert arguments[arguments.index("--model") + 1] == "gpt-5.6-sol"
    assert arguments[arguments.index("--sandbox") + 1] == "workspace-write"
    assert "--strict-config" in arguments
    assert "--ephemeral" in arguments
    assert "--json" in arguments
    assert 'model_reasoning_effort="ultra"' in arguments
    assert 'approval_policy="never"' in arguments
    assert "agents.enabled=false" in arguments
    assert 'agents.default_subagent_model="gpt-5.6-sol"' in arguments
    assert 'shell_environment_policy.inherit="core"' in arguments
    assert "shell_environment_policy.ignore_default_excludes=false" in arguments
    assert arguments[arguments.index("--disable") + 1] == "multi_agent"
    assert "gpt-5.6-luna" not in " ".join(arguments)

    prompt = capture["prompt"]
    assert "Do not spawn, delegate to, or invoke subagents." in prompt
    assert "Never read a file or symlink named key" in prompt
    assert "Never commit, push, reset, clean, stash" in prompt
    assert "  - src/owned.py" in prompt
    assert "Implement only the owned file." in prompt
    assert "Replacement prompt" not in prompt

    current = json.loads(current_file.read_text(encoding="utf-8"))
    assert current["state"] == "completed"
    assert current["exit_code"] == 0
    claims = Path(environment["CODEX_POOL_STATE_DIR"]).glob("repos/*/claims/*.json")
    assert not list(claims)

    status = run_pool(repo, environment, "status", manifest_path, check=True)
    assert "writer\tcompleted\t" in status.stdout
    assert "orphaned-session" not in status.stdout
    final = run_pool(repo, environment, "final", manifest_path, "writer", check=True)
    assert final.stdout == "fake final output\n"
    logs = run_pool(repo, environment, "logs", manifest_path, "writer", check=True)
    assert json.loads(logs.stdout)["type"] == "fake.completed"
    kill_fake_session(environment, session)


def test_final_holds_a_generation_consistent_state_snapshot_during_restart(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    manifest_path = write_manifest(repo, manifest(task("review")))
    started = run_pool(repo, environment, "start", manifest_path, check=True)
    first_session = started.stdout.split("\t")[2]
    first_command = tmux_state(environment)["commands"][0]["command"]
    first_runner = subprocess.run(
        ["bash", "-c", first_command],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first_runner.returncode == 0, first_runner.stderr
    _, first_state = current_state_for(environment, "review")

    real_jq = shutil.which("jq")
    assert real_jq is not None
    marker = tmp_path / "final-field-read"
    release = tmp_path / "release-final-field-read"
    fake_jq = tmp_path / "fake-bin" / "jq"
    fake_jq.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *".final_file"* && -n "${FAKE_JQ_FINAL_READY:-}" ]]; then\n'
        '  : >"${FAKE_JQ_FINAL_READY}"\n'
        '  while [[ ! -e "${FAKE_JQ_FINAL_RELEASE}" ]]; do sleep 0.01; done\n'
        "fi\n"
        f'exec {shlex.quote(real_jq)} "$@"\n',
        encoding="utf-8",
    )
    fake_jq.chmod(0o755)
    environment["FAKE_JQ_FINAL_READY"] = str(marker)
    environment["FAKE_JQ_FINAL_RELEASE"] = str(release)

    final_process = subprocess.Popen(
        [
            str(repo / "scripts" / "codex-pool.sh"),
            "final",
            str(manifest_path),
            "review",
        ],
        cwd=repo,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for_file(marker)
    restart_process = subprocess.Popen(
        [
            str(repo / "scripts" / "codex-pool.sh"),
            "start",
            str(manifest_path),
            "review",
        ],
        cwd=repo,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.1)
    assert restart_process.poll() is None

    release.touch()
    final_stdout, final_stderr = final_process.communicate(timeout=5)
    restart_stdout, restart_stderr = restart_process.communicate(timeout=5)
    assert final_process.returncode == 0, final_stderr
    assert final_stdout == "fake final output\n"
    assert restart_process.returncode == 0, restart_stderr
    assert restart_stdout.startswith("started\treview\t")
    _, restarted_state = current_state_for(environment, "review")
    assert restarted_state["run_id"] != first_state["run_id"]

    kill_fake_session(environment, first_session)
    kill_fake_session(environment, restarted_state["session"])


def test_failed_codex_run_is_terminal_and_releases_ownership(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    environment["FAKE_CODEX_EXIT"] = "7"
    manifest_path = write_manifest(
        repo, manifest(task("writer", mode="owned-write", owns=["src/owned.py"]))
    )

    started = run_pool(repo, environment, "start", manifest_path, check=True)
    session = started.stdout.split("\t")[2]
    command = tmux_state(environment)["commands"][0]["command"]
    runner = subprocess.run(
        ["bash", "-c", command],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert runner.returncode == 7
    kill_fake_session(environment, session)

    [current_file] = current_states(environment)
    current = json.loads(current_file.read_text(encoding="utf-8"))
    assert current["state"] == "failed"
    assert current["exit_code"] == 7
    claims = Path(environment["CODEX_POOL_STATE_DIR"]).glob("repos/*/claims/*.json")
    assert not list(claims)


def test_tmux_launch_failure_rolls_back_claim(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    environment["FAKE_TMUX_FAIL_NEW"] = "1"
    manifest_path = write_manifest(
        repo, manifest(task("writer", mode="owned-write", owns=["src/owned.py"]))
    )

    result = run_pool(repo, environment, "start", manifest_path)

    assert result.returncode == 1
    assert "failed to launch task writer" in result.stderr
    [current_file] = current_states(environment)
    current = json.loads(current_file.read_text(encoding="utf-8"))
    assert current["state"] == "launch-failed"
    claims = Path(environment["CODEX_POOL_STATE_DIR"]).glob("repos/*/claims/*.json")
    assert not list(claims)
    assert tmux_state(environment)["sessions"] == []


def test_multiple_runners_hold_the_state_lock_only_during_updates(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    environment["FAKE_CODEX_SLEEP_SECONDS"] = "1"
    manifest_path = write_manifest(
        repo,
        manifest(task("first"), task("second"), max_processes=2),
    )

    run_pool(repo, environment, "start", manifest_path, check=True)
    commands = [entry["command"] for entry in tmux_state(environment)["commands"]]
    runners = [
        subprocess.Popen(
            ["bash", "-c", command],
            cwd=repo,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for command in commands
    ]
    try:
        deadline = time.monotonic() + 0.75
        states: list[str] = []
        while time.monotonic() < deadline:
            states = [
                json.loads(path.read_text(encoding="utf-8"))["state"]
                for path in current_states(environment)
            ]
            if states == ["running", "running"]:
                break
            time.sleep(0.01)
        assert states == ["running", "running"]
    finally:
        for runner in runners:
            runner.wait(timeout=3)

    assert [runner.returncode for runner in runners] == [0, 0]


def test_unsandboxed_read_only_fallback_is_explicit_recorded_and_pinned(
    tmp_path: Path,
) -> None:
    repo, environment = make_repo(tmp_path)
    environment["CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY"] = "1"
    manifest_path = write_manifest(
        repo,
        manifest(
            task("review"),
            task(
                "writer",
                mode="owned-write",
                prompt="prompts/writer.md",
                owns=["src/owned.py"],
            ),
        ),
    )

    run_pool(repo, environment, "start", manifest_path, check=True)
    _, review_state = current_state_for(environment, "review")
    _, writer_state = current_state_for(environment, "writer")
    assert review_state["mode"] == "read-only"
    assert review_state["sandbox"] == "danger-full-access"
    assert writer_state["mode"] == "owned-write"
    assert writer_state["sandbox"] == "workspace-write"

    review_command = next(
        item["command"]
        for item in tmux_state(environment)["commands"]
        if item["session"] == review_state["session"]
    )
    review_runner = subprocess.run(
        ["bash", "-c", review_command],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert review_runner.returncode == 0, review_runner.stderr
    review_capture = json.loads(
        Path(environment["FAKE_CODEX_CAPTURE"]).read_text(encoding="utf-8")
    )
    review_arguments = review_capture["args"]
    assert (
        review_arguments[review_arguments.index("--sandbox") + 1]
        == "danger-full-access"
    )
    assert "Full access is a transport fallback only" in review_capture["prompt"]

    writer_command = next(
        item["command"]
        for item in tmux_state(environment)["commands"]
        if item["session"] == writer_state["session"]
    )
    runner = subprocess.run(
        ["bash", "-c", writer_command],
        cwd=repo,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert runner.returncode == 0, runner.stderr
    capture = json.loads(
        Path(environment["FAKE_CODEX_CAPTURE"]).read_text(encoding="utf-8")
    )
    arguments = capture["args"]
    assert arguments[arguments.index("--sandbox") + 1] == "workspace-write"
    assert "Full access is a transport fallback only" not in capture["prompt"]


def test_unsandboxed_read_only_fallback_rejects_invalid_switch(tmp_path: Path) -> None:
    repo, environment = make_repo(tmp_path)
    environment["CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY"] = "yes"
    manifest_path = write_manifest(repo, manifest(task("review")))

    result = run_pool(repo, environment, "start", manifest_path)

    assert result.returncode == 2
    assert "CODEX_POOL_ALLOW_UNSANDBOXED_READ_ONLY must be 0 or 1" in result.stderr


def test_shell_source_has_valid_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SOURCE_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_fake_programs_are_valid_python() -> None:
    compile(textwrap.dedent(FAKE_TMUX), "<fake-tmux>", "exec")
    compile(textwrap.dedent(FAKE_CODEX), "<fake-codex>", "exec")
