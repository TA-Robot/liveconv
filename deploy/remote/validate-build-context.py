#!/usr/bin/env python3
"""Prove the allowlisted Docker source layout can install the Gateway."""

from __future__ import annotations

import fnmatch
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOCKERFILE = HERE / "Dockerfile"
DOCKERIGNORE = HERE / "Dockerfile.dockerignore"

FORBIDDEN_SUFFIXES = {
    ".bin",
    ".ckpt",
    ".index",
    ".npy",
    ".npz",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
    ".wav",
}
FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "checkpoints",
    "models",
    "weights",
}


class ContextValidationError(RuntimeError):
    """Raised when the Docker source layout is unsafe or incomplete."""


def _matches_docker_rule(relative: str, pattern: str) -> bool:
    normalized = pattern.removeprefix("/").rstrip("/")
    if normalized == "**":
        return True
    candidates = [normalized]
    if normalized.startswith("**/"):
        candidates.append(normalized[3:])
    path = PurePosixPath(relative)
    return any(
        path.match(candidate) or fnmatch.fnmatchcase(relative, candidate)
        for candidate in candidates
    )


def _dockerignore_rules() -> list[tuple[bool, str]]:
    rules: list[tuple[bool, str]] = []
    for raw_line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        included = line.startswith("!")
        rules.append((included, line[1:] if included else line))
    if not rules or rules[0] != (False, "**"):
        raise ContextValidationError("Docker ignore policy must begin by excluding **")
    return rules


def _is_included(relative: str, rules: list[tuple[bool, str]]) -> bool:
    included = True
    for rule_includes, pattern in rules:
        if _matches_docker_rule(relative, pattern):
            included = rule_includes
    return included


def _assert_safe_source(path: Path, relative: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ContextValidationError(
            f"context source is not a regular file: {relative}"
        )
    parts = set(PurePosixPath(relative).parts)
    lowered_name = path.name.lower()
    if (
        parts.intersection(FORBIDDEN_PARTS)
        or path.suffix.lower() in FORBIDDEN_SUFFIXES
        or "secret" in lowered_name
        or "token" in lowered_name
        or "key" in lowered_name
    ):
        raise ContextValidationError(f"sensitive source entered context: {relative}")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
        cwd=ROOT,
        check=False,
    )
    if ignored.returncode == 0:
        raise ContextValidationError(f"Git-ignored source entered context: {relative}")
    if ignored.returncode not in {0, 1}:
        raise ContextValidationError(f"could not check Git ignore status: {relative}")


def _allowlisted_files() -> dict[str, Path]:
    rules = _dockerignore_rules()
    include_patterns = [
        pattern for included, pattern in rules if included and not pattern.endswith("/")
    ]
    files: dict[str, Path] = {}
    for pattern in include_patterns:
        matches = sorted(ROOT.glob(pattern))
        if not matches:
            raise ContextValidationError(
                f"Docker context include matches no source: {pattern}"
            )
        for path in matches:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if not _is_included(relative, rules):
                continue
            _assert_safe_source(path, relative)
            files[relative] = path
    if not files:
        raise ContextValidationError("Docker context allowlist contains no files")
    return files


def _context_copy_lines(*, before_sync_only: bool) -> list[list[str]]:
    copies: list[list[str]] = []
    for raw_line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if before_sync_only and stripped.startswith("RUN uv sync"):
            break
        if not stripped.startswith("COPY "):
            continue
        tokens = shlex.split(stripped)
        options = [token for token in tokens[1:] if token.startswith("--")]
        if any(option.startswith("--from=") for option in options):
            continue
        arguments = [token for token in tokens[1:] if not token.startswith("--")]
        if len(arguments) < 2:
            raise ContextValidationError(f"unsupported Docker COPY: {stripped}")
        copies.append(arguments)
    return copies


def _expand_copy_sources(
    context_root: Path, arguments: list[str]
) -> tuple[list[Path], str]:
    destination = arguments[-1]
    sources: list[Path] = []
    for pattern in arguments[:-1]:
        if pattern.startswith("/") or ".." in PurePosixPath(pattern).parts:
            raise ContextValidationError(f"unsafe Docker COPY source: {pattern}")
        matches = sorted(context_root.glob(pattern))
        if not matches:
            raise ContextValidationError(f"Docker COPY source is absent: {pattern}")
        if any(not match.is_file() or match.is_symlink() for match in matches):
            raise ContextValidationError(
                f"Docker COPY must use allowlisted regular files only: {pattern}"
            )
        sources.extend(matches)
    return sources, destination


def _apply_builder_copies(context_root: Path, build_root: Path) -> set[str]:
    consumed: set[str] = set()
    for arguments in _context_copy_lines(before_sync_only=True):
        sources, destination = _expand_copy_sources(context_root, arguments)
        if destination.startswith("/") or ".." in PurePosixPath(destination).parts:
            raise ContextValidationError(
                f"pre-sync Docker COPY destination escapes /build: {destination}"
            )
        destination_is_directory = destination.endswith("/") or len(sources) > 1
        for source in sources:
            target = build_root / destination
            if destination_is_directory:
                target /= source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            consumed.add(source.relative_to(context_root).as_posix())
    return consumed


def _all_consumed_context_files(context_root: Path) -> set[str]:
    consumed: set[str] = set()
    for arguments in _context_copy_lines(before_sync_only=False):
        sources, _ = _expand_copy_sources(context_root, arguments)
        consumed.update(
            source.relative_to(context_root).as_posix() for source in sources
        )
    return consumed


def _run_frozen_install(build_root: Path, environment_root: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise ContextValidationError("uv is required for clean-context validation")
    environment = os.environ.copy()
    for name in (
        "PIP_EXTRA_INDEX_URL",
        "PIP_INDEX_URL",
        "UV_DEFAULT_INDEX",
        "UV_EXTRA_INDEX_URL",
        "UV_INDEX",
        "UV_INDEX_URL",
        "UV_PROJECT",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "UV_COMPILE_BYTECODE": "1",
            "UV_LINK_MODE": "copy",
            "UV_PROJECT_ENVIRONMENT": str(environment_root),
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    command = [
        uv,
        "sync",
        "--frozen",
        "--no-dev",
        "--no-editable",
        "--package",
        "liveconv-audio",
    ]
    completed = subprocess.run(
        command,
        cwd=build_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ContextValidationError(f"clean-context uv sync failed:\n{detail}")

    probe = """
from importlib import import_module
from importlib.metadata import files
from importlib.resources import files as resource_files

required_worker_files = {
    "workers/model-pack.schema.json",
    "workers/packs/__init__.py",
    "workers/packs/rvc-v2.json",
    "workers/adapters/__init__.py",
    "workers/adapters/beatrice_2/__init__.py",
    "workers/adapters/openvoice_v2/__init__.py",
    "workers/adapters/rvc_v2/__init__.py",
    "workers/adapters/rvc_v2/tools/__init__.py",
    "workers/adapters/x_vc/__init__.py",
    "workers/conformance/fake_worker.py",
    "workers/runtime/supervisor.py",
}
installed_worker_files = {
    str(path) for path in (files("liveconv-worker-runtime") or ())
}
missing = required_worker_files - installed_worker_files
assert not missing, f"worker install is incomplete: {sorted(missing)}"
for module in (
    "workers.adapters.beatrice_2",
    "workers.adapters.openvoice_v2",
    "workers.adapters.rvc_v2",
    "workers.adapters.x_vc",
):
    import_module(module)
assert resource_files("liveconv_audio").joinpath(
    "default-model-profiles.json"
).is_file()
"""
    completed = subprocess.run(
        [str(environment_root / "bin" / "python"), "-c", probe],
        cwd=build_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ContextValidationError(f"installed Gateway probe failed:\n{detail}")


def main() -> int:
    try:
        allowlisted = _allowlisted_files()
        with tempfile.TemporaryDirectory(prefix="liveconv-remote-context-") as raw:
            temporary_root = Path(raw)
            context_root = temporary_root / "context"
            build_root = temporary_root / "build"
            environment_root = temporary_root / "venv"
            for relative, source in allowlisted.items():
                target = context_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            consumed_before_sync = _apply_builder_copies(context_root, build_root)
            consumed_all = _all_consumed_context_files(context_root)
            unused = set(allowlisted) - consumed_all
            if unused:
                raise ContextValidationError(
                    f"Docker context includes unused files: {sorted(unused)}"
                )
            if not consumed_before_sync:
                raise ContextValidationError("Docker builder has no pre-sync sources")
            _run_frozen_install(build_root, environment_root)
    except (ContextValidationError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("remote Docker clean-context install validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
