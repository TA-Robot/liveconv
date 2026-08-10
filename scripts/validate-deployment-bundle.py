#!/usr/bin/env python3
"""Validate an MS-3 deployment bundle and its cross-document identities."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_SCHEMA = REPOSITORY_ROOT / "schemas" / "deployment-bundle.schema.json"
PROFILE_SCHEMA = REPOSITORY_ROOT / "schemas" / "model-profile-registry.schema.json"
AUTHORIZATION_SCHEMA = (
    REPOSITORY_ROOT / "schemas" / "voice-authorization-registry.schema.json"
)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def profile_hash(profile: Mapping[str, Any]) -> str:
    material = copy.deepcopy(dict(profile))
    runtime = material.get("runtime")
    if isinstance(runtime, dict):
        runtime.pop("worker_endpoint", None)
        if runtime.get("worker_module") is None:
            runtime.pop("worker_module", None)
    if material.get("promotion") is None:
        material.pop("promotion", None)
    return canonical_hash(material)


def configuration_hash(profile: Mapping[str, Any]) -> str:
    runtime = profile.get("runtime")
    if not isinstance(runtime, dict):
        return canonical_hash(None)
    return canonical_hash(runtime.get("configuration"))


def variant_manifest_hash(variant: Mapping[str, Any]) -> str:
    material = dict(variant)
    material.pop("variant_manifest_sha256", None)
    return canonical_hash(material)


def authorization_record_hash(record: Mapping[str, Any]) -> str:
    material = dict(record)
    material.pop("record_sha256", None)
    return canonical_hash(material)


def authorization_registry_revision(registry: Mapping[str, Any]) -> str:
    material = copy.deepcopy(dict(registry))
    material.pop("registry_revision", None)
    return canonical_hash(material)


def bundle_revision(bundle: Mapping[str, Any]) -> str:
    material = copy.deepcopy(dict(bundle))
    material.pop("bundle_revision", None)
    public_manifest = material.get("public_manifest")
    if isinstance(public_manifest, dict):
        public_manifest.pop("bundle_revision", None)
    return canonical_hash(material)


def _schema_errors(schema_path: Path, value: object, label: str) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{label}: {error.json_path}: {error.message}"
        for error in sorted(
            validator.iter_errors(value), key=lambda item: item.json_path
        )
    ]


def validate_bundle(
    bundle: object,
    authorization_registry: object | None,
    *,
    validation_time: datetime | None,
) -> list[str]:
    if validation_time is None:
        return ["trusted validation_time is required"]
    if validation_time.tzinfo is None or validation_time.utcoffset() is None:
        return ["trusted validation_time must be timezone-aware"]
    validation_time = validation_time.astimezone(UTC)

    errors = _schema_errors(BUNDLE_SCHEMA, bundle, "bundle")
    if errors or not isinstance(bundle, dict):
        return errors

    if authorization_registry is None:
        return ["trusted authorization registry is required"]
    errors.extend(
        _schema_errors(
            AUTHORIZATION_SCHEMA,
            authorization_registry,
            "authorization_registry",
        )
    )
    if errors or not isinstance(authorization_registry, dict):
        return errors
    expected_registry_revision = authorization_registry_revision(authorization_registry)
    if authorization_registry["registry_revision"] != expected_registry_revision:
        errors.append("authorization registry revision mismatch")
    if bundle["authorization_registry_revision"] != expected_registry_revision:
        errors.append("bundle authorization registry revision mismatch")

    registry = bundle["gateway_profile_registry"]
    errors.extend(_schema_errors(PROFILE_SCHEMA, registry, "gateway_profile_registry"))
    if errors or not isinstance(registry, dict):
        return errors

    manifest = bundle["public_manifest"]
    authorization_records = bundle["authorization_records"]
    assert isinstance(manifest, dict)
    assert isinstance(authorization_records, list)
    variants = manifest["variants"]
    profiles = registry["profiles"]
    assert isinstance(variants, list)
    assert isinstance(profiles, list)

    for field in ("bundle_id", "protocol_version"):
        if bundle[field] != manifest[field]:
            errors.append(f"public_manifest.{field} does not match bundle.{field}")
    if bundle["bundle_revision"] != manifest["bundle_revision"]:
        errors.append("public_manifest.bundle_revision does not match bundle")
    expected_revision = bundle_revision(bundle)
    if bundle["bundle_revision"] != expected_revision:
        errors.append("bundle_revision does not match canonical bundle material")

    variant_ids = [variant["variant_id"] for variant in variants]
    profile_ids = [variant["profile_id"] for variant in variants]
    display_orders = [variant["display_order"] for variant in variants]
    if len(variant_ids) != len(set(variant_ids)):
        errors.append("public_manifest contains duplicate variant_id values")
    if len(profile_ids) != len(set(profile_ids)):
        errors.append("public_manifest contains duplicate profile_id values")
    if sorted(display_orders) != list(range(1, len(variants) + 1)):
        errors.append("public_manifest display_order values must be contiguous from 1")
    if display_orders != sorted(display_orders):
        errors.append("public_manifest variants must be ordered by display_order")
    registry_profile_ids = [profile["profile_id"] for profile in profiles]
    if len(registry_profile_ids) != len(set(registry_profile_ids)):
        errors.append("gateway_profile_registry contains duplicate profile_id values")
    if set(registry_profile_ids) != set(profile_ids):
        errors.append("public variants and gateway profiles do not have the same IDs")

    record_variant_ids = [record["variant_id"] for record in authorization_records]
    record_hashes = [record["record_sha256"] for record in authorization_records]
    if len(record_variant_ids) != len(set(record_variant_ids)):
        errors.append("authorization_records contains duplicate variant_id values")
    if len(record_hashes) != len(set(record_hashes)):
        errors.append("authorization_records contains duplicate record hashes")
    if set(record_variant_ids) != set(variant_ids):
        errors.append(
            "public variants and authorization records do not have the same IDs"
        )

    trusted_records = authorization_registry["records"]
    assert isinstance(trusted_records, list)
    trusted_by_hash = {record["record_sha256"]: record for record in trusted_records}
    if len(trusted_by_hash) != len(trusted_records):
        errors.append("trusted authorization registry contains duplicate record hashes")
    if set(record_hashes) != set(trusted_by_hash):
        errors.append("bundle authorization records do not match the trusted registry")
    else:
        for record in authorization_records:
            if trusted_by_hash[record["record_sha256"]] != record:
                errors.append(
                    f"{record['variant_id']}: authorization record differs "
                    "from trusted registry"
                )

    created_at = datetime.fromisoformat(bundle["created_at"].replace("Z", "+00:00"))
    if created_at > validation_time:
        errors.append("bundle created_at is after the trusted validation time")
    records_by_variant_id = {
        record["variant_id"]: record for record in authorization_records
    }
    for record in authorization_records:
        if authorization_record_hash(record) != record["record_sha256"]:
            errors.append(f"{record['variant_id']}: authorization record hash mismatch")
        reviewed_at = datetime.fromisoformat(
            record["reviewed_at"].replace("Z", "+00:00")
        )
        if reviewed_at > created_at:
            errors.append(
                f"{record['variant_id']}: authorization review postdates "
                "bundle creation"
            )
        if reviewed_at > validation_time:
            errors.append(
                f"{record['variant_id']}: authorization review is after "
                "the trusted validation time"
            )
        expires_at = record["expires_at"]
        if expires_at is not None:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry <= validation_time:
                errors.append(f"{record['variant_id']}: authorization is expired")

    profiles_by_id = {profile["profile_id"]: profile for profile in profiles}
    for variant in variants:
        if variant_manifest_hash(variant) != variant["variant_manifest_sha256"]:
            errors.append(f"{variant['variant_id']}: variant manifest hash mismatch")
        if variant["family_id"] != variant["pack_id"]:
            errors.append(f"{variant['variant_id']}: family_id and pack_id differ")

        authorization = records_by_variant_id.get(variant["variant_id"])
        if authorization is not None:
            if authorization["record_sha256"] != variant["authorization_record_sha256"]:
                errors.append(f"{variant['variant_id']}: authorization digest mismatch")
            if authorization["family_id"] != variant["family_id"]:
                errors.append(f"{variant['variant_id']}: authorization family mismatch")
            if authorization["profile_id"] != variant["profile_id"]:
                errors.append(
                    f"{variant['variant_id']}: authorization profile mismatch"
                )

        profile = profiles_by_id.get(variant["profile_id"])
        if profile is None:
            continue
        if profile["kind"] != "voice_conversion":
            errors.append(f"{variant['variant_id']}: profile is not voice conversion")
        if profile["readiness"] != "ready":
            errors.append(f"{variant['variant_id']}: profile is not ready")
        if profile_hash(profile) != variant["profile_hash"]:
            errors.append(f"{variant['variant_id']}: profile hash mismatch")
        if configuration_hash(profile) != variant["configuration_hash"]:
            errors.append(f"{variant['variant_id']}: configuration hash mismatch")

        promotion = profile.get("promotion")
        if not isinstance(promotion, dict):
            errors.append(f"{variant['variant_id']}: promotion is missing")
            continue
        if promotion["pack_id"] != variant["pack_id"]:
            errors.append(f"{variant['variant_id']}: promotion pack mismatch")
        if promotion["evidence_sha256"] != variant["promotion_evidence_sha256"]:
            errors.append(f"{variant['variant_id']}: promotion evidence mismatch")

    return errors


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: validate-deployment-bundle.py bundle.json "
            "authorization-registry.json",
            file=sys.stderr,
        )
        return 2
    try:
        bundle = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        authorization_registry = json.loads(
            Path(sys.argv[2]).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid deployment bundle: {exc}", file=sys.stderr)
        return 2

    errors = validate_bundle(
        bundle,
        authorization_registry,
        validation_time=datetime.now(UTC),
    )
    if errors:
        for error in errors:
            print(f"fail deployment bundle: {error}", file=sys.stderr)
        return 1
    print("ok   deployment bundle identities and public projection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
