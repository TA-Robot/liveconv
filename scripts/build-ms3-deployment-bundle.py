#!/usr/bin/env python3
"""Seal one private MS-3 draft into an immutable deployment directory."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_validate_deployment_bundle", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("deployment validator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def seal_bundle(
    draft: object,
    authorization_registry: object,
    *,
    validation_time: datetime,
) -> dict[str, Any]:
    """Derive every public identity from private profiles and trusted records."""
    if validation_time.tzinfo is None or validation_time.utcoffset() is None:
        raise ValueError("validation_time must be timezone-aware")
    bundle = copy.deepcopy(_object(draft, "draft bundle"))
    trusted_registry = copy.deepcopy(
        _object(authorization_registry, "authorization registry")
    )
    manifest = _object(bundle.get("public_manifest"), "public manifest")
    profile_registry = _object(
        bundle.get("gateway_profile_registry"), "gateway profile registry"
    )
    profiles = _array(profile_registry.get("profiles"), "gateway profiles")
    variants = _array(manifest.get("variants"), "public variants")
    trusted_records = _array(trusted_registry.get("records"), "authorization records")

    profile_by_id = {profile.get("profile_id"): profile for profile in profiles}
    record_by_variant = {record.get("variant_id"): record for record in trusted_records}
    variant_ids = {variant.get("variant_id") for variant in variants}
    if len(profile_by_id) != len(profiles) or len(record_by_variant) != len(
        trusted_records
    ):
        raise ValueError(
            "profiles and authorization records must have unique identities"
        )
    if set(record_by_variant) != variant_ids:
        raise ValueError("trusted authorization records must exactly match variants")

    expected_registry_revision = VALIDATOR.authorization_registry_revision(
        trusted_registry
    )
    if trusted_registry.get("registry_revision") != expected_registry_revision:
        raise ValueError("trusted authorization registry revision mismatch")
    bundle["authorization_registry_revision"] = expected_registry_revision
    bundle["authorization_records"] = copy.deepcopy(trusted_records)
    bundle["created_at"] = _utc_text(validation_time)

    for variant in variants:
        variant_id = variant.get("variant_id")
        profile = profile_by_id.get(variant.get("profile_id"))
        record = record_by_variant.get(variant_id)
        if profile is None or record is None:
            raise ValueError(
                f"{variant_id}: profile or authorization record is missing"
            )
        promotion = _object(profile.get("promotion"), f"{variant_id} promotion")
        variant["profile_hash"] = VALIDATOR.profile_hash(profile)
        variant["configuration_hash"] = VALIDATOR.configuration_hash(profile)
        variant["pack_id"] = promotion.get("pack_id")
        variant["promotion_evidence_sha256"] = promotion.get("evidence_sha256")
        variant["authorization_record_sha256"] = record.get("record_sha256")
        variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)

    bundle["bundle_revision"] = "sha256:" + "0" * 64
    manifest["bundle_revision"] = bundle["bundle_revision"]
    revision = VALIDATOR.bundle_revision(bundle)
    bundle["bundle_revision"] = revision
    manifest["bundle_revision"] = revision
    errors = VALIDATOR.validate_bundle(
        bundle,
        trusted_registry,
        validation_time=validation_time,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return bundle


def _write_json(path: Path, value: object, mode: int) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(mode)


def write_bundle_directory(
    destination: Path,
    bundle: dict[str, Any],
    authorization_registry: dict[str, Any],
) -> None:
    destination = destination.resolve()
    if destination == REPOSITORY_ROOT or REPOSITORY_ROOT in destination.parents:
        raise ValueError("private deployment output must be outside the repository")
    if destination.exists():
        raise FileExistsError(f"deployment destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    staging.mkdir(mode=0o700)
    try:
        _write_json(staging / "bundle.json", bundle, 0o600)
        _write_json(
            staging / "profiles.json", bundle["gateway_profile_registry"], 0o600
        )
        _write_json(staging / "manifest.json", bundle["public_manifest"], 0o644)
        _write_json(
            staging / "authorization-registry.json", authorization_registry, 0o600
        )
        os.replace(staging, destination)
    except BaseException:
        for child in staging.iterdir() if staging.exists() else ():
            child.unlink()
        if staging.exists():
            staging.rmdir()
        raise


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: build-ms3-deployment-bundle.py "
            "draft.json authorization-registry.json output-directory",
            file=sys.stderr,
        )
        return 2
    try:
        draft = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        authorization_registry = json.loads(
            Path(sys.argv[2]).read_text(encoding="utf-8")
        )
        now = datetime.now(UTC)
        bundle = seal_bundle(draft, authorization_registry, validation_time=now)
        write_bundle_directory(
            Path(sys.argv[3]), bundle, _object(authorization_registry, "registry")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"deployment bundle build failed: {exc}", file=sys.stderr)
        return 2
    print(f"ok   {bundle['bundle_revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
