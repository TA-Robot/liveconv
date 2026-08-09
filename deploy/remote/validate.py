#!/usr/bin/env python3
"""Deterministic static checks for the remote deployment boundary."""

from __future__ import annotations

import argparse
import json
import math
import re
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the static remote deployment and an optional env file"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="validate concrete deployment values before running Compose",
    )
    return parser.parse_args(argv)


def _parse_env_file(path: Path, failures: list[str]) -> dict[str, str]:
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise OSError
        resolved = path.resolve(strict=True)
        if resolved == ROOT or ROOT in resolved.parents:
            require(
                False, "deployment env file must be outside the repository", failures
            )
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        require(False, "deployment env file must be an absolute regular file", failures)
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line != raw_line.strip():
            require(
                False,
                f"env file line {line_number} has surrounding whitespace",
                failures,
            )
            continue
        line = raw_line
        if line.startswith("export ") or "=" not in line:
            require(
                False, f"env file line {line_number} has unsupported syntax", failures
            )
            continue
        raw_name, value = line.split("=", maxsplit=1)
        name = raw_name.strip()
        value = value.strip()
        if (
            raw_name != name
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name)
            or name in values
        ):
            require(False, f"env file line {line_number} has an invalid key", failures)
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if "${" in value or "\n" in value or "\r" in value:
            require(False, f"env file value for {name} is not literal", failures)
            continue
        values[name] = value
    return values


def _mode_allows(path: Path, *, read: bool, execute: bool) -> bool:
    metadata = path.stat()
    if metadata.st_uid == 10001:
        shift = 6
    elif metadata.st_gid == 10001:
        shift = 3
    else:
        shift = 0
    permissions = (stat.S_IMODE(metadata.st_mode) >> shift) & 0b111
    return (not read or permissions & 0b100 != 0) and (
        not execute or permissions & 0b001 != 0
    )


def _external_path(
    raw_path: str,
    *,
    name: str,
    kind: str,
    failures: list[str],
) -> Path | None:
    candidate = Path(raw_path)
    if not candidate.is_absolute() or candidate.is_symlink():
        require(False, f"{name} must be an absolute non-symlink path", failures)
        return None
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        require(False, f"{name} does not exist", failures)
        return None
    if resolved == ROOT or ROOT in resolved.parents:
        require(False, f"{name} must be outside the repository", failures)
    if kind == "file":
        require(resolved.is_file(), f"{name} must be a regular file", failures)
    else:
        require(resolved.is_dir(), f"{name} must be a directory", failures)
    return resolved


def _validate_environment(path: Path, failures: list[str]) -> None:
    values = _parse_env_file(path, failures)
    required = (
        "LIVECONV_PUBLIC_HOST",
        "LIVECONV_ACME_EMAIL",
        "LIVECONV_API_TOKEN_FILE",
        "LIVECONV_MODEL_ARTIFACT_DIR",
        "LIVECONV_ALLOWED_ORIGINS",
    )
    for name in required:
        require(bool(values.get(name)), f"env file must set {name}", failures)
    if any(not values.get(name) for name in required):
        return

    hostname = values["LIVECONV_PUBLIC_HOST"]
    hostname_pattern = (
        r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
        r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
    )
    require(
        re.fullmatch(hostname_pattern, hostname) is not None,
        "LIVECONV_PUBLIC_HOST must be one lowercase DNS hostname",
        failures,
    )
    require(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,63}", values["LIVECONV_ACME_EMAIL"])
        is not None,
        "LIVECONV_ACME_EMAIL must be an email address",
        failures,
    )
    origins = [value.strip() for value in values["LIVECONV_ALLOWED_ORIGINS"].split(",")]
    require(
        bool(origins)
        and len(origins) == len(set(origins))
        and all(
            re.fullmatch(r"chrome-extension://[a-p]{32}", origin) is not None
            for origin in origins
        ),
        "LIVECONV_ALLOWED_ORIGINS must contain unique exact Extension origins",
        failures,
    )

    token_path = _external_path(
        values["LIVECONV_API_TOKEN_FILE"],
        name="LIVECONV_API_TOKEN_FILE",
        kind="file",
        failures=failures,
    )
    if token_path is not None and token_path.is_file():
        require(
            _mode_allows(token_path, read=True, execute=False),
            "API token file must be readable by numeric UID/GID 10001",
            failures,
        )
        try:
            token = token_path.read_bytes().rstrip(b"\n").decode("ascii")
            acceptable = (
                len(token.encode("ascii")) >= 32
                and len(set(token)) >= 16
                and all(0x21 <= ord(character) <= 0x7E for character in token)
            )
        except (OSError, UnicodeError):
            acceptable = False
        require(acceptable, "API token content does not meet Gateway policy", failures)

    artifact_root = _external_path(
        values["LIVECONV_MODEL_ARTIFACT_DIR"],
        name="LIVECONV_MODEL_ARTIFACT_DIR",
        kind="directory",
        failures=failures,
    )
    if artifact_root is not None and artifact_root.is_dir():
        require(
            _mode_allows(artifact_root, read=True, execute=True),
            "model artifact directory must be readable/searchable by UID/GID 10001",
            failures,
        )

    profile_value = values.get("LIVECONV_PROFILE_CONFIG_FILE", "")
    if profile_value:
        profile_path = _external_path(
            profile_value,
            name="LIVECONV_PROFILE_CONFIG_FILE",
            kind="file",
            failures=failures,
        )
        if profile_path is not None and profile_path.is_file():
            require(
                _mode_allows(profile_path, read=True, execute=False),
                "profile registry must be readable by UID/GID 10001",
                failures,
            )
            _validate_profile_registry(profile_path, failures)

    require(
        values.get("LIVECONV_ALLOW_TECHNICAL_PROFILES", "0") == "0",
        "remote deployment must not enable technical model profiles",
        failures,
    )

    _validate_numeric_settings(values, failures)


def _validate_numeric_settings(values: dict[str, str], failures: list[str]) -> None:
    numeric_settings = {
        "LIVECONV_TICKET_TTL_SECONDS": (False, 0),
        "LIVECONV_ATTACH_TIMEOUT_SECONDS": (False, 0),
        "LIVECONV_INGRESS_BUDGET_MS": (True, 20),
        "LIVECONV_MAX_SESSIONS": (True, 1),
        "LIVECONV_MAX_PENDING_ATTACHMENTS": (True, 1),
        "LIVECONV_SESSION_LIFETIME_SECONDS": (False, 0),
        "LIVECONV_REQUEST_CACHE_MAX": (True, 1),
        "LIVECONV_SEND_TIMEOUT_SECONDS": (False, 0),
        "LIVECONV_BIND_PORT": (True, 1),
    }
    for name, (integer, minimum) in numeric_settings.items():
        raw_value = values.get(name)
        if raw_value is None or raw_value == "":
            continue
        try:
            value = int(raw_value) if integer else float(raw_value)
            valid = math.isfinite(value) and value >= minimum
            if minimum == 0:
                valid = valid and value > 0
            if name == "LIVECONV_BIND_PORT":
                valid = valid and value <= 65_535
        except (OverflowError, ValueError):
            valid = False
        require(valid, f"{name} is outside the Gateway-supported range", failures)


def _validate_profile_registry(path: Path, failures: list[str]) -> None:
    try:
        import jsonschema

        schema = json.loads(
            (ROOT / "schemas/model-profile-registry.schema.json").read_text(
                encoding="utf-8"
            )
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(document)
    except (OSError, UnicodeError, json.JSONDecodeError):
        require(False, "profile registry is not valid JSON", failures)
        return
    except ImportError:
        require(
            False, "profile validation requires the locked jsonschema tool", failures
        )
        return
    except jsonschema.ValidationError:
        require(False, "profile registry does not match its schema", failures)
        return

    profiles = document["profiles"]
    profile_ids = [profile["profile_id"] for profile in profiles]
    require(
        len(profile_ids) == len(set(profile_ids)),
        "profile registry contains a duplicate profile_id",
        failures,
    )
    private_key = re.compile(
        r"(^|_)(api_?key|credential|directory|dir|endpoint|file|password|path|"
        r"private_?key|secret|socket|token|url)($|_)",
        re.IGNORECASE,
    )

    def configuration_is_public(value: object) -> bool:
        if isinstance(value, dict):
            return all(
                not private_key.search(str(key)) and configuration_is_public(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return all(configuration_is_public(child) for child in value)
        return True

    selectable = 0
    for profile in profiles:
        runtime = profile["runtime"]
        adapter = runtime["adapter"]
        configuration = runtime["configuration"]
        require(
            configuration_is_public(configuration),
            f"{profile['profile_id']} contains private runtime configuration keys",
            failures,
        )
        if adapter == "passthrough":
            require(
                not configuration,
                f"{profile['profile_id']} passthrough configuration must be empty",
                failures,
            )
        elif adapter == "gain":
            gain = configuration.get("gain") if set(configuration) == {"gain"} else None
            require(
                isinstance(gain, (int, float))
                and not isinstance(gain, bool)
                and math.isfinite(gain)
                and 0 <= gain <= 1,
                f"{profile['profile_id']} gain configuration is invalid",
                failures,
            )
        if profile["readiness"] == "ready" and adapter in {"passthrough", "gain"}:
            selectable += 1
    require(
        selectable > 0,
        "profile registry has no Gateway-selectable ready profile",
        failures,
    )


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    failures: list[str] = []
    dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8")
    compose = (HERE / "compose.yaml").read_text(encoding="utf-8")
    override = (HERE / "compose.profile-registry.yaml").read_text(encoding="utf-8")
    caddyfile = (HERE / "Caddyfile").read_text(encoding="utf-8")
    env_example = (HERE / ".env.example").read_text(encoding="utf-8")
    dockerignore = (HERE / "Dockerfile.dockerignore").read_text(encoding="utf-8")
    check_tools = (HERE / "check-tools.sh").read_text(encoding="utf-8")

    from_lines = re.findall(r"(?m)^FROM\s+(\S+)", dockerfile)
    require(
        len(from_lines) == 3, "Dockerfile must have exactly three FROM images", failures
    )
    for image in from_lines:
        require(
            re.fullmatch(r"[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}", image) is not None,
            f"base image is not tag-and-digest pinned: {image}",
            failures,
        )

    required_dockerfile_fragments = (
        "uv sync",
        "--frozen",
        "--no-dev",
        "--no-editable",
        "--package liveconv-audio",
        "default-model-profiles.json",
        "packages/speaker/pyproject.toml",
        "workers/model-pack.schema.json",
        "workers/packs/*.json",
        "workers/adapters/beatrice_2/*.py",
        "workers/adapters/openvoice_v2/*.py",
        "workers/adapters/rvc_v2/*.py",
        "workers/adapters/rvc_v2/tools/__init__.py",
        "workers/adapters/x_vc/*.py",
        "USER 10001:10001",
        "HEALTHCHECK",
        'ENTRYPOINT ["/opt/liveconv/bin/entrypoint.sh"]',
    )
    for fragment in required_dockerfile_fragments:
        require(fragment in dockerfile, f"Dockerfile is missing {fragment!r}", failures)

    required_environment = (
        "LIVECONV_PUBLIC_HOST",
        "LIVECONV_ACME_EMAIL",
        "LIVECONV_API_TOKEN_FILE",
        "LIVECONV_MODEL_ARTIFACT_DIR",
        "LIVECONV_ALLOWED_ORIGINS",
    )
    for name in required_environment:
        require(
            re.search(rf"\$\{{{name}:\?[^}}]+\}}", compose) is not None,
            f"compose must fail closed when {name} is absent",
            failures,
        )
        require(
            re.search(rf"(?m)^{name}=\s*$", env_example) is not None,
            f".env.example must leave {name} empty",
            failures,
        )

    caddy_images = re.findall(r"(?m)^\s+image:\s+(caddy:\S+)$", compose)
    require(len(caddy_images) == 1, "compose must define one Caddy image", failures)
    if caddy_images:
        require(
            re.fullmatch(r"caddy:[^@\s]+@sha256:[0-9a-f]{64}", caddy_images[0])
            is not None,
            "Caddy image must be tag-and-digest pinned",
            failures,
        )

    gateway_block = compose.split("\n  caddy:", maxsplit=1)[0]
    caddy_block = compose.split("\n  caddy:", maxsplit=1)[1].split(
        "\nnetworks:", maxsplit=1
    )[0]
    require(
        "ports:" not in gateway_block, "Gateway must not publish host ports", failures
    )
    for fragment in (
        "read_only: true",
        'user: "10001:10001"',
        "no-new-privileges:true",
        "cap_drop:",
        "pids_limit:",
        "mem_limit:",
        "cpus:",
        "target: /opt/liveconv/artifacts",
        "read_only: true",
        "- backend",
    ):
        require(
            fragment in gateway_block,
            f"Gateway compose block is missing {fragment!r}",
            failures,
        )

    require("internal: true" in compose, "backend network must be internal", failures)
    require(
        "target: liveconv_api_token" in compose,
        "token must use a Compose secret",
        failures,
    )
    require(
        "LIVECONV_API_TOKEN:" not in compose,
        "token value must not be Compose metadata",
        failures,
    )
    require(
        "/health/ready" in dockerfile,
        "Gateway healthcheck must exercise readiness",
        failures,
    )
    require(
        "/health/live" in compose,
        "Caddy healthcheck must exercise proxied liveness",
        failures,
    )
    for fragment in (
        "read_only: true",
        'user: "65534:65534"',
        "no-new-privileges:true",
        "cap_drop:",
        "pids_limit:",
        "mem_limit:",
        "cpus:",
        "source: caddy_data",
        "source: caddy_config",
        "- edge",
        "- backend",
    ):
        require(
            fragment in caddy_block,
            f"Caddy compose block is missing {fragment!r}",
            failures,
        )
    require(
        "--insecure" not in caddy_block,
        "Caddy healthcheck must validate the public certificate",
        failures,
    )

    for fragment in (
        "admin off",
        "{$LIVECONV_PUBLIC_HOST}",
        "reverse_proxy gateway:8765",
        "request_body",
        "max_size 16KB",
        "health_uri /health/live",
        'Cache-Control "no-store"',
        "Strict-Transport-Security",
    ):
        require(fragment in caddyfile, f"Caddyfile is missing {fragment!r}", failures)
    require(
        "\n\tlog" not in caddyfile, "Caddy access logging must stay disabled", failures
    )

    require(
        "target: /etc/liveconv/model-profiles.json" in override
        and "read_only: true" in override,
        "external profile registry override must be read-only",
        failures,
    )

    packaged_profiles = (
        ROOT / "services/audio/liveconv_audio/default-model-profiles.json"
    )
    require(
        packaged_profiles.is_file(),
        "packaged default profile registry is missing",
        failures,
    )
    if packaged_profiles.is_file():
        document = json.loads(packaged_profiles.read_text(encoding="utf-8"))
        profiles = document.get("profiles", [])
        require(
            document.get("schema_version") == 1,
            "default registry schema must be v1",
            failures,
        )
        require(bool(profiles), "default registry must contain profiles", failures)
        require(
            all(
                profile.get("readiness") == "ready"
                and profile.get("runtime", {}).get("adapter") in {"passthrough", "gain"}
                for profile in profiles
            ),
            "packaged defaults must contain only ready builtin adapters",
            failures,
        )

    forbidden_names = {"key", ".env"}
    committed_names = {path.name for path in HERE.iterdir()}
    require(
        not forbidden_names.intersection(committed_names),
        "deployment directory contains a credential-bearing filename",
        failures,
    )

    for forbidden_pattern in (
        "**/.env",
        "**/*key*",
        "**/*secret*",
        "**/*token*",
        "**/.venv/",
        "**/__pycache__/",
        "**/*.bin",
    ):
        require(
            forbidden_pattern in dockerignore,
            f"Docker build context deny rule is missing {forbidden_pattern!r}",
            failures,
        )
    for broad_reinclude in (
        "!packages/protocol/**",
        "!services/audio/**",
        "!workers/**",
    ):
        require(
            broad_reinclude not in dockerignore,
            f"Docker build context contains broad re-include {broad_reinclude!r}",
            failures,
        )

    required_context_includes = (
        "!packages/speaker/pyproject.toml",
        "!workers/README.md",
        "!workers/model-pack.schema.json",
        "!workers/packs/*.py",
        "!workers/packs/*.json",
        "!workers/adapters/__init__.py",
        "!workers/adapters/beatrice_2/*.py",
        "!workers/adapters/openvoice_v2/*.py",
        "!workers/adapters/rvc_v2/*.py",
        "!workers/adapters/rvc_v2/tools/__init__.py",
        "!workers/adapters/x_vc/*.py",
    )
    for include in required_context_includes:
        require(
            include in dockerignore,
            f"Docker build context allowlist is missing {include!r}",
            failures,
        )

    context_validator = HERE / "validate-build-context.py"
    require(
        context_validator.is_file(),
        "clean Docker build-context validator is missing",
        failures,
    )
    require(
        'python3 "$HERE/validate-build-context.py"' in check_tools,
        "official remote tool check must run the clean build-context validator",
        failures,
    )

    if arguments.env_file is not None:
        _validate_environment(arguments.env_file, failures)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    suffix = " and environment" if arguments.env_file is not None else ""
    print(f"remote deployment static{suffix} validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
