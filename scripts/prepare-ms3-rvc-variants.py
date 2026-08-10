#!/usr/bin/env python3
"""Prepare an exact private MS-3 draft for the official Amitaro RVC voices."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-rvc-amitaro-intake.json"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"
ZERO_SHA256 = "sha256:" + "0" * 64


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_prepare_rvc_validator", VALIDATOR_PATH
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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be non-empty text")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bound_file(root: Path, relative: Path, expected_sha256: str) -> Path:
    root = root.resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    if (
        root not in candidate.parents
        or candidate.is_symlink()
        or not candidate.is_file()
    ):
        raise ValueError(f"candidate material is unsafe: {relative}")
    actual = _sha256_file(candidate)
    if actual != expected_sha256:
        raise ValueError(f"candidate material digest differs: {relative}")
    return candidate


def rvc_variant_environment_names(profile_id: str) -> dict[str, str]:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_RVC_VARIANT_{suffix}"
    return {
        "checkpoint_path": f"{prefix}_CHECKPOINT_PATH",
        "checkpoint_sha256": f"{prefix}_CHECKPOINT_SHA256",
        "index_path": f"{prefix}_INDEX_PATH",
        "index_sha256": f"{prefix}_INDEX_SHA256",
    }


def _base_rvc_profile(base_registry: object) -> dict[str, Any]:
    registry = _object(base_registry, "base registry")
    profiles = _array(registry.get("profiles"), "base registry profiles")
    matches = [
        profile
        for profile in profiles
        if profile.get("profile_id") == "vc.rvc.synthetic-ja.v1"
    ]
    if registry.get("schema_version") != 1 or len(matches) != 1:
        raise ValueError("base registry must contain the retained RVC profile")
    profile = matches[0]
    promotion = _object(profile.get("promotion"), "base RVC promotion")
    runtime = _object(profile.get("runtime"), "base RVC runtime")
    configuration = _object(runtime.get("configuration"), "base RVC configuration")
    if (
        promotion.get("pack_id") != "rvc-v2"
        or runtime.get("adapter") != "worker"
        or configuration.get("worker_module") != "workers.adapters.rvc_v2.worker"
    ):
        raise ValueError("base RVC profile has an incompatible adapter identity")
    return profile


def prepare_documents(
    base_registry: object,
    intake: object,
    candidate_root: Path,
    *,
    reviewed_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    reviewed_text = (
        reviewed_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    intake_document = _object(intake, "intake")
    if intake_document.get("schema_version") != 1:
        raise ValueError("unsupported intake schema")
    provider_id = _text(intake_document.get("provider_id"), "provider_id")
    provider_name = _text(intake_document.get("provider_name"), "provider_name")
    source_page_url = _text(intake_document.get("source_page_url"), "source_page_url")
    terms_url = _text(intake_document.get("terms_url"), "terms_url")
    required_attribution = _text(
        intake_document.get("required_attribution"), "required_attribution"
    )
    candidates = _array(intake_document.get("variants"), "intake variants")
    if not 1 <= len(candidates) <= 12:
        raise ValueError("intake must contain between one and twelve variants")
    base_profile = _base_rvc_profile(base_registry)
    candidate_root = candidate_root.resolve(strict=True)

    profiles: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    environment: dict[str, str] = {}
    for display_order, candidate in enumerate(candidates, start=1):
        variant_id = _text(candidate.get("variant_id"), "variant_id")
        profile_id = _text(candidate.get("profile_id"), f"{variant_id} profile_id")
        style_id = _text(candidate.get("style_id"), f"{variant_id} style_id")
        expected = {
            key: _text(candidate.get(key), f"{variant_id} {key}")
            for key in (
                "archive_sha256",
                "checkpoint_sha256",
                "index_sha256",
                "readme_sha256",
            )
        }
        archive = _bound_file(
            candidate_root,
            Path("downloads") / _text(candidate.get("archive_name"), "archive_name"),
            expected["archive_sha256"],
        )
        checkpoint = _bound_file(
            candidate_root,
            Path("extracted")
            / style_id
            / _text(candidate.get("checkpoint_name"), "checkpoint_name"),
            expected["checkpoint_sha256"],
        )
        index = _bound_file(
            candidate_root,
            Path("extracted")
            / style_id
            / _text(candidate.get("index_name"), "index_name"),
            expected["index_sha256"],
        )
        readme = _bound_file(
            candidate_root,
            Path("extracted")
            / style_id
            / _text(candidate.get("readme_name"), "readme_name"),
            expected["readme_sha256"],
        )

        profile = copy.deepcopy(base_profile)
        profile["profile_id"] = profile_id
        profile["weight_revision"] = f"sha256:{expected['checkpoint_sha256']}"
        profile["license_record"] = (
            f"{provider_name} official RVC V1.0; personal evaluation; "
            f"attribution required; bundled terms sha256:{expected['readme_sha256']}"
        )
        runtime = _object(profile.get("runtime"), f"{variant_id} runtime")
        configuration = _object(
            runtime.get("configuration"), f"{variant_id} configuration"
        )
        artifacts = _object(configuration.get("artifacts"), f"{variant_id} artifacts")
        artifacts["checkpoint_sha256"] = expected["checkpoint_sha256"]
        artifacts["index_sha256"] = expected["index_sha256"]
        profiles.append(profile)

        material_manifest = {
            "variant_id": variant_id,
            "provider_id": provider_id,
            "source_page_url": source_page_url,
            "terms_url": terms_url,
            "download_url": _text(candidate.get("download_url"), "download_url"),
            "archive_sha256": f"sha256:{expected['archive_sha256']}",
            "checkpoint_sha256": f"sha256:{expected['checkpoint_sha256']}",
            "index_sha256": f"sha256:{expected['index_sha256']}",
            "readme_sha256": f"sha256:{expected['readme_sha256']}",
            "required_attribution": required_attribution,
        }
        source_manifest_sha256 = VALIDATOR.canonical_hash(material_manifest)
        lineage_manifest_sha256 = VALIDATOR.canonical_hash(
            {
                "source_manifest_sha256": source_manifest_sha256,
                "profile_id": profile_id,
                "profile_hash": VALIDATOR.profile_hash(profile),
                "configuration_hash": VALIDATOR.configuration_hash(profile),
                "implementation_revision": profile["implementation_revision"],
            }
        )
        material_manifest["source_manifest_sha256"] = source_manifest_sha256
        material_manifest["lineage_manifest_sha256"] = lineage_manifest_sha256
        manifests.append(material_manifest)

        record = {
            "record_sha256": ZERO_SHA256,
            "variant_id": variant_id,
            "family_id": "rvc-v2",
            "profile_id": profile_id,
            "status": "approved",
            "scope": "personal-evaluation",
            "authorization_owner": "personal-operator",
            "retention_policy": "delete-on-expiry-or-revocation",
            "deletion_path": str(checkpoint.parent),
            "source_material_sha256": f"sha256:{expected['checkpoint_sha256']}",
            "source_manifest_sha256": source_manifest_sha256,
            "terms_sha256": f"sha256:{expected['readme_sha256']}",
            "lineage_manifest_sha256": lineage_manifest_sha256,
            "reviewed_at": reviewed_text,
            "expires_at": None,
            "attribution_state": "satisfied",
            "notice_state": "not-required-for-personal-evaluation",
        }
        record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
        records.append(record)
        promotion = _object(profile.get("promotion"), f"{variant_id} promotion")
        variants.append(
            {
                "variant_id": variant_id,
                "family_id": "rvc-v2",
                "display_order": display_order,
                "display_name": _text(
                    candidate.get("display_name"), f"{variant_id} display_name"
                ),
                "target_presentation": _text(
                    candidate.get("target_presentation"),
                    f"{variant_id} target_presentation",
                ),
                "lane": "voice-conversion",
                "invocation_mode": "live",
                "profile_id": profile_id,
                "profile_hash": ZERO_SHA256,
                "configuration_hash": ZERO_SHA256,
                "pack_id": "rvc-v2",
                "promotion_evidence_sha256": promotion["evidence_sha256"],
                "authorization_record_sha256": record["record_sha256"],
                "variant_manifest_sha256": ZERO_SHA256,
            }
        )

        names = rvc_variant_environment_names(profile_id)
        environment.update(
            {
                names["checkpoint_path"]: str(checkpoint),
                names["checkpoint_sha256"]: expected["checkpoint_sha256"],
                names["index_path"]: str(index),
                names["index_sha256"]: expected["index_sha256"],
            }
        )
        del archive, readme

    if len({profile["profile_id"] for profile in profiles}) != len(profiles):
        raise ValueError("prepared profile IDs must be unique")
    authorization_registry = {
        "schema_version": 1,
        "registry_revision": ZERO_SHA256,
        "records": records,
    }
    authorization_registry["registry_revision"] = (
        VALIDATOR.authorization_registry_revision(authorization_registry)
    )
    bundle_id = "ms3-amitaro-rvc-first-wave-v1"
    draft = {
        "schema_version": 1,
        "bundle_id": bundle_id,
        "created_at": reviewed_text,
        "bundle_revision": ZERO_SHA256,
        "protocol_version": 1,
        "gateway_profile_registry": {"schema_version": 1, "profiles": profiles},
        "authorization_registry_revision": authorization_registry["registry_revision"],
        "authorization_records": copy.deepcopy(records),
        "public_manifest": {
            "schema_version": 1,
            "bundle_id": bundle_id,
            "bundle_revision": ZERO_SHA256,
            "protocol_version": 1,
            "transport_scope": "loopback-ssh",
            "max_sessions": 1,
            "variants": variants,
        },
        "consumer_contract": {
            "public_manifest_path": "/v1/deployment-manifest",
            "public_manifest_authentication": "bearer",
            "authorization_registry_source": "operator-controlled-private-file",
            "canonicalization": (
                "json-utf8-ascii-sort-keys-compact-excluding-bundle-revision"
            ),
            "gateway_activation": "validate-before-atomic-swap",
            "whole_bundle_mismatch": "reject-load-native-only",
            "variant_mismatch": "disable-variant",
            "terminal_must_match": True,
            "extension_must_match": True,
        },
    }
    material_document = {
        "schema_version": 1,
        "provider_id": provider_id,
        "required_attribution": required_attribution,
        "manifests": manifests,
    }
    return draft, authorization_registry, material_document, environment


def _write_json(path: Path, value: object, mode: int) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(mode)


def write_preparation(
    destination: Path,
    draft: dict[str, Any],
    authorization_registry: dict[str, Any],
    material_document: dict[str, Any],
    environment: dict[str, str],
) -> None:
    destination = destination.resolve()
    if destination == REPOSITORY_ROOT or REPOSITORY_ROOT in destination.parents:
        raise ValueError("private preparation output must be outside the repository")
    if destination.exists():
        raise FileExistsError(f"preparation destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    staging.mkdir(mode=0o700)
    try:
        _write_json(staging / "draft.json", draft, 0o600)
        _write_json(
            staging / "authorization-registry.json", authorization_registry, 0o600
        )
        _write_json(staging / "material-manifests.json", material_document, 0o600)
        lines = [
            f"export {name}={shlex.quote(value)}"
            for name, value in sorted(environment.items())
        ]
        (staging / "identity.env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (staging / "identity.env").chmod(0o600)
        os.replace(staging, destination)
    except BaseException:
        for child in staging.iterdir() if staging.exists() else ():
            child.unlink()
        if staging.exists():
            staging.rmdir()
        raise


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-registry", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        base_registry = json.loads(arguments.base_registry.read_text(encoding="utf-8"))
        intake = json.loads(arguments.intake.read_text(encoding="utf-8"))
        prepared = prepare_documents(
            base_registry,
            intake,
            arguments.candidate_root,
            reviewed_at=datetime.now(UTC),
        )
        write_preparation(arguments.output, *prepared)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 RVC preparation failed: {exc}", file=sys.stderr)
        return 2
    print(f"prepared {len(prepared[0]['public_manifest']['variants'])} RVC variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
