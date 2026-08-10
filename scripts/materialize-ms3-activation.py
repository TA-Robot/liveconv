#!/usr/bin/env python3
"""Materialize one sealed MS-3 bundle and its model identities for one-command use."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = REPOSITORY_ROOT / "artifacts" / "ms3"
LAUNCHER_PATH = REPOSITORY_ROOT / "scripts" / "run-ms3-gateway.py"
ALLOWED_IDENTITY_NAME = re.compile(
    r"^LIVECONV_(?:RVC|OPENVOICE|XVC|MEANVC2)[A-Z0-9_]*$"
)
SENSITIVE_NAME = re.compile(r"(?:TOKEN|SECRET|PASSWORD|BEARER|PRIVATE_KEY)")


def _load_launcher() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_materialize_ms3_launcher", LAUNCHER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("MS-3 launcher could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAUNCHER = _load_launcher()


def _write_identity(path: Path, values: dict[str, str], removed: set[str]) -> None:
    lines = [
        f"export {name}={shlex.quote(value)}" for name, value in sorted(values.items())
    ]
    if removed:
        lines.append("unset " + " ".join(sorted(removed)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def materialize(
    deployment: Path,
    identity_files: list[Path],
    destination: Path,
    *,
    validation_time: datetime,
) -> dict[str, object]:
    if validation_time.tzinfo is None or validation_time.utcoffset() is None:
        raise ValueError("validation_time must be timezone-aware")
    deployment = deployment.resolve(strict=True)
    destination = destination.resolve()
    artifact_root = ARTIFACT_ROOT.resolve()
    if artifact_root not in destination.parents:
        raise ValueError("activation destination must be below artifacts/ms3")
    if destination.exists():
        raise FileExistsError(f"activation destination exists: {destination}")
    bundle = LAUNCHER.load_deployment(deployment, validation_time=validation_time)
    values: dict[str, str] = {}
    removed = {"PYTHONHOME", "PYTHONPATH"}
    for identity_file in identity_files:
        additions, identity_removed = LAUNCHER.read_identity_environment(identity_file)
        for name in additions:
            if (
                ALLOWED_IDENTITY_NAME.fullmatch(name) is None
                or SENSITIVE_NAME.search(name) is not None
            ):
                raise ValueError(f"model identity name is not allowed: {name}")
        values.update(additions)
        removed.update(identity_removed)
    if not values:
        raise ValueError("at least one model identity file is required")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    staging.mkdir(mode=0o700)
    try:
        for name, mode in (
            ("bundle.json", 0o600),
            ("profiles.json", 0o600),
            ("manifest.json", 0o644),
            ("authorization-registry.json", 0o600),
        ):
            shutil.copyfile(deployment / name, staging / name)
            (staging / name).chmod(mode)
        _write_identity(staging / "identity.env", values, removed)
        metadata = {
            "schema_version": 1,
            "bundle_id": bundle["bundle_id"],
            "bundle_revision": bundle["bundle_revision"],
            "identity_variable_count": len(values),
            "secrets_included": False,
        }
        (staging / "activation.json").write_text(
            json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "activation.json").chmod(0o644)
        os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()
        raise
    return bundle


def update_current_link(link: Path, destination: Path) -> None:
    link = link.absolute()
    artifact_root = ARTIFACT_ROOT.resolve()
    if artifact_root not in link.parent.resolve().parents and link.parent.resolve() != (
        artifact_root
    ):
        raise ValueError("current link must be below artifacts/ms3")
    temporary = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    relative_target = os.path.relpath(
        destination.resolve(), start=link.parent.resolve()
    )
    temporary.symlink_to(relative_target, target_is_directory=True)
    os.replace(temporary, link)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument(
        "--identity-env", type=Path, action="append", required=True, metavar="PATH"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--current-link", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        bundle = materialize(
            arguments.deployment,
            arguments.identity_env,
            arguments.output,
            validation_time=datetime.now(UTC),
        )
        if arguments.current_link is not None:
            update_current_link(arguments.current_link, arguments.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 activation materialization failed: {exc}", file=sys.stderr)
        return 2
    print(f"ok   {bundle['bundle_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
