#!/usr/bin/env python3
"""Validate one sealed MS-3 bundle and launch the matching Gateway."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_PREFLIGHT_PROGRAM = """
import hashlib
import json
from pathlib import Path

from liveconv_audio import Settings
from liveconv_audio._adapter_registry import worker_profile_for
from liveconv_audio.app import Gateway
from liveconv_audio.profiles import ProfileRegistry

settings = Settings.from_env()
errors = settings.configuration_errors
assert not errors, "; ".join(errors)
Gateway(settings)
registry = ProfileRegistry.load(
    settings.profile_config,
    allow_technical_profiles=settings.allow_technical_profiles,
)
profile_ids = [
    item["profile_id"]
    for item in json.loads(
        settings.profile_config.read_text(encoding="utf-8")
    )["profiles"]
]
verified = {}
for index, profile_id in enumerate(profile_ids, start=1):
    profile = registry.get_selectable(profile_id)
    assert profile is not None, f"{profile_id}: profile is not selectable"
    worker = worker_profile_for(
        profile,
        f"ms3-preflight-{index}",
        settings.ingress_budget_ms,
    )
    for artifact in worker.artifacts:
        raw_path = worker.environment.get(artifact.env_var)
        assert raw_path, f"{profile_id}: {artifact.env_var} is missing"
        path = Path(raw_path)
        assert path.is_absolute() and path.is_file(), (
            f"{profile_id}: {artifact.env_var} is unavailable"
        )
        resolved = path.resolve(strict=True)
        digest = verified.get(resolved)
        if digest is None:
            value = hashlib.sha256()
            with resolved.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    value.update(chunk)
            digest = value.hexdigest()
            verified[resolved] = digest
        assert digest == artifact.sha256, (
            f"{profile_id}: {artifact.env_var} digest differs"
        )
"""


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_run_deployment_validator", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("deployment validator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _json_file(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"deployment input must be a regular file: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_deployment(directory: Path, *, validation_time: datetime) -> dict[str, object]:
    directory = directory.resolve()
    bundle = _json_file(directory / "bundle.json")
    profiles = _json_file(directory / "profiles.json")
    manifest = _json_file(directory / "manifest.json")
    authorization_registry = _json_file(directory / "authorization-registry.json")
    if not isinstance(bundle, dict) or not isinstance(authorization_registry, dict):
        raise ValueError("deployment bundle and authorization registry must be objects")
    if profiles != bundle.get("gateway_profile_registry"):
        raise ValueError("profiles.json does not match the sealed bundle")
    if manifest != bundle.get("public_manifest"):
        raise ValueError("manifest.json does not match the sealed bundle")
    errors = VALIDATOR.validate_bundle(
        bundle,
        authorization_registry,
        validation_time=validation_time,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return bundle


def read_identity_environment(path: Path) -> tuple[dict[str, str], set[str]]:
    path = path.resolve(strict=True)
    if path.is_symlink() or not path.is_file():
        raise ValueError("identity environment must be a regular file")
    values: dict[str, str] = {}
    removed: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("unset "):
            names = line.removeprefix("unset ").split()
            if not names or any(
                name not in {"PYTHONPATH", "PYTHONHOME"} for name in names
            ):
                raise ValueError(f"{path.name}:{line_number}: invalid unset directive")
            removed.update(names)
            continue
        assignment = line.removeprefix("export ")
        name, separator, encoded_value = assignment.partition("=")
        if (
            not separator
            or not ENVIRONMENT_NAME.fullmatch(name)
            or not name.startswith("LIVECONV_")
            or any(marker in encoded_value for marker in ("$", "`", "\n", "\r"))
        ):
            raise ValueError(f"{path.name}:{line_number}: invalid assignment")
        decoded = shlex.split(encoded_value, posix=True)
        if len(decoded) != 1:
            raise ValueError(f"{path.name}:{line_number}: value must be one literal")
        values[name] = decoded[0]
    return values, removed


def activation_environment(
    directory: Path,
    identity_files: list[Path],
    *,
    base_environment: dict[str, str],
    validation_time: datetime,
) -> tuple[dict[str, str], dict[str, object]]:
    directory = directory.resolve()
    bundle = load_deployment(directory, validation_time=validation_time)
    environment = dict(base_environment)
    effective_identity_files = list(identity_files)
    embedded_identity = directory / "identity.env"
    if not effective_identity_files and embedded_identity.is_file():
        effective_identity_files.append(embedded_identity)
    for identity_file in effective_identity_files:
        values, removed = read_identity_environment(identity_file)
        environment.update(values)
        for name in removed:
            environment.pop(name, None)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "LIVECONV_DEPLOYMENT_BUNDLE": str(directory / "bundle.json"),
            "LIVECONV_PROFILE_CONFIG": str(directory / "profiles.json"),
            "LIVECONV_ALLOW_TECHNICAL_PROFILES": "1",
            "LIVECONV_MAX_SESSIONS": "1",
        }
    )
    return environment, bundle


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--gateway-env", type=Path)
    parser.add_argument("--bind-host")
    parser.add_argument("--bind-port", type=int)
    parser.add_argument(
        "--identity-env", type=Path, action="append", default=[], metavar="PATH"
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        base_environment = dict(os.environ)
        if arguments.gateway_env is not None:
            gateway_values, gateway_removed = read_identity_environment(
                arguments.gateway_env
            )
            base_environment.update(gateway_values)
            for name in gateway_removed:
                base_environment.pop(name, None)
        if arguments.bind_host is not None:
            base_environment["LIVECONV_BIND_HOST"] = arguments.bind_host
        if arguments.bind_port is not None:
            if not 1 <= arguments.bind_port <= 65_535:
                raise ValueError("bind port must be between 1 and 65535")
            base_environment["LIVECONV_BIND_PORT"] = str(arguments.bind_port)
        environment, bundle = activation_environment(
            arguments.deployment,
            arguments.identity_env,
            base_environment=base_environment,
            validation_time=datetime.now(UTC),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 Gateway activation failed: {exc}", file=sys.stderr)
        return 2
    command = [
        "uv",
        "run",
        "--frozen",
        "--all-packages",
        "python",
        "-m",
        "liveconv_audio",
    ]
    if arguments.check:
        preflight = subprocess.run(
            [
                "uv",
                "run",
                "--frozen",
                "--all-packages",
                "python",
                "-c",
                _PREFLIGHT_PROGRAM,
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=False,
        )
        if preflight.returncode != 0:
            return preflight.returncode
        print(f"ok   {bundle['bundle_revision']}")
        return 0
    os.chdir(REPOSITORY_ROOT)
    os.execvpe(command[0], command, environment)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
