#!/usr/bin/env python3
"""Extend a prepared MS-3 bundle with exact Amitaro X-VC variants."""

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
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-xvc-amitaro-intake.json"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"
MS2_BUILDER_PATH = REPOSITORY_ROOT / "scripts" / "build-ms2-profile-registry.py"
LAUNCHER_PATH = REPOSITORY_ROOT / "scripts" / "run-ms3-gateway.py"
ZERO_SHA256 = "sha256:" + "0" * 64
BASE_PROFILE_ID = "vc.x-vc.synthetic-ja.v1"
APPROVED_TARGETS = {
    "vc.x-vc.amitaro-runrun.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        "7a878609fb31fb2852ccb885405c97aad27bf1016ee7d3f4e1e3b0e751d02199",
    ),
    "vc.x-vc.amitaro-yofukashi.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        "313edea2bc054aa885e58919d560c2708487c3be6f7692a06aab5a907c8d619c",
    ),
}


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"support module could not be loaded: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_module("liveconv_prepare_xvc_validator", VALIDATOR_PATH)
MS2_BUILDER = _load_module("liveconv_prepare_xvc_ms2_builder", MS2_BUILDER_PATH)
LAUNCHER = _load_module("liveconv_prepare_xvc_launcher", LAUNCHER_PATH)


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
        raise ValueError(f"reference material is unsafe: {relative}")
    if _sha256_file(candidate) != expected_sha256:
        raise ValueError(f"reference material digest differs: {relative}")
    return candidate


def target_environment_names(profile_id: str) -> tuple[str, str, str, str]:
    if profile_id not in APPROVED_TARGETS:
        raise ValueError(f"{profile_id}: X-VC profile ID is not approved")
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_XVC_VARIANT_{suffix}"
    return (
        f"{prefix}_TARGET_REFERENCE_PATH",
        f"{prefix}_TARGET_REFERENCE_SHA256",
        f"{prefix}_TARGET_AUTHORIZATION_PATH",
        f"{prefix}_TARGET_AUTHORIZATION_SHA256",
    )


def _base_xvc_profile(base_registry: object) -> dict[str, Any]:
    registry = _object(base_registry, "base registry")
    profiles = _array(registry.get("profiles"), "base registry profiles")
    matches = [
        profile for profile in profiles if profile.get("profile_id") == BASE_PROFILE_ID
    ]
    if registry.get("schema_version") != 1 or len(matches) != 1:
        raise ValueError("base registry must contain the retained X-VC profile")
    profile = matches[0]
    runtime = _object(profile.get("runtime"), "base X-VC runtime")
    promotion = _object(profile.get("promotion"), "base X-VC promotion")
    if (
        runtime.get("adapter") != "worker"
        or runtime.get("worker_module") != "workers.adapters.x_vc.worker"
        or promotion.get("pack_id") != "x-vc"
    ):
        raise ValueError("base X-VC profile has an incompatible identity")
    return profile


def base_registry_from_identity(identity_path: Path) -> dict[str, Any]:
    values, _removed = LAUNCHER.read_identity_environment(identity_path)
    endpoint_value = values.get("LIVECONV_XVC_INTERPRETER_PATH")
    if not endpoint_value:
        raise ValueError("X-VC identity is missing its interpreter path")
    material = MS2_BUILDER._load_object(
        REPOSITORY_ROOT / "workers" / "adapters" / "x_vc" / "technical-profile.json"
    )
    endpoint = MS2_BUILDER._endpoint(Path(endpoint_value), model_id="x-vc")
    profile = MS2_BUILDER._xvc_profile(
        material,
        endpoint=endpoint,
        repository_root=REPOSITORY_ROOT,
    )
    return {"schema_version": 1, "profiles": [profile]}


def _authorization_document(candidate: dict[str, Any]) -> dict[str, object]:
    style_id = _text(candidate.get("style_id"), "style_id")
    archive_sha256 = _text(candidate.get("archive_sha256"), "archive_sha256")
    reference_sha256 = _text(candidate.get("reference_sha256"), "reference_sha256")
    return {
        "authorization_id": f"liveconv-ms3-amitaro-{style_id}-v1",
        "authorization_record": (
            f"amitaro-mana-corpus-{style_id}@sha256:{archive_sha256}"
        ),
        "classification": (
            "licensed human voice; attribution required; no impersonation"
        ),
        "deletion_path": (
            f"operator-private:amitaro-reference/{style_id}/QUESTION_007.wav"
        ),
        "owner": "personal operator",
        "permitted_purpose": "personal Japanese voice-conversion evaluation",
        "retention_policy": "delete on authorization revocation or MS-3 completion",
        "schema_version": 1,
        "target_reference_sha256": reference_sha256,
    }


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def extend_documents(
    base_registry: object,
    prepared_draft: object,
    authorization_registry: object,
    intake: object,
    reference_root: Path,
    authorization_directory: Path,
    *,
    reviewed_at: datetime,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, str],
    dict[str, dict[str, object]],
]:
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    reviewed_text = (
        reviewed_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    draft = copy.deepcopy(_object(prepared_draft, "prepared draft"))
    registry = copy.deepcopy(_object(authorization_registry, "authorization registry"))
    intake_document = _object(intake, "intake")
    if intake_document.get("schema_version") != 1:
        raise ValueError("unsupported intake schema")
    candidates = _array(intake_document.get("variants"), "intake variants")
    if not 1 <= len(candidates) <= 4:
        raise ValueError("intake must contain between one and four variants")
    base_profile = _base_xvc_profile(base_registry)
    reference_root = reference_root.resolve(strict=True)
    authorization_directory = authorization_directory.resolve()
    profile_registry = _object(
        draft.get("gateway_profile_registry"), "draft profile registry"
    )
    profiles = _array(profile_registry.get("profiles"), "draft profiles")
    public_manifest = _object(draft.get("public_manifest"), "public manifest")
    variants = _array(public_manifest.get("variants"), "public variants")
    records = _array(registry.get("records"), "authorization records")
    existing_profiles = {profile.get("profile_id") for profile in profiles}
    existing_variants = {variant.get("variant_id") for variant in variants}
    display_order = max(
        (int(item.get("display_order", 0)) for item in variants), default=0
    )
    manifests: list[dict[str, Any]] = []
    environment: dict[str, str] = {}
    authorization_documents: dict[str, dict[str, object]] = {}

    for candidate in candidates:
        variant_id = _text(candidate.get("variant_id"), "variant_id")
        profile_id = _text(candidate.get("profile_id"), f"{variant_id} profile_id")
        if variant_id in existing_variants or profile_id in existing_profiles:
            raise ValueError(f"duplicate prepared identity: {variant_id}")
        expected = APPROVED_TARGETS.get(profile_id)
        if (
            expected is None
            or (
                candidate.get("reference_sha256"),
                candidate.get("target_authorization_sha256"),
            )
            != expected
        ):
            raise ValueError(
                f"{profile_id}: target identity is not statically approved"
            )
        style_id = _text(candidate.get("style_id"), f"{variant_id} style_id")
        archive_sha256 = _text(candidate.get("archive_sha256"), "archive_sha256")
        reference_sha256, authorization_sha256 = expected
        readme_sha256 = _text(candidate.get("readme_sha256"), "readme_sha256")
        archive = _bound_file(
            reference_root,
            Path("downloads") / _text(candidate.get("archive_name"), "archive_name"),
            archive_sha256,
        )
        reference = _bound_file(
            reference_root,
            Path("extracted")
            / style_id
            / _text(candidate.get("reference_name"), "reference_name"),
            reference_sha256,
        )
        readme = _bound_file(
            reference_root,
            Path("extracted")
            / style_id
            / _text(candidate.get("readme_name"), "readme_name"),
            readme_sha256,
        )
        authorization = _authorization_document(candidate)
        if (
            hashlib.sha256(_json_bytes(authorization)).hexdigest()
            != authorization_sha256
        ):
            raise ValueError(f"{profile_id}: generated authorization digest differs")
        authorization_name = f"{style_id}.json"
        authorization_documents[authorization_name] = authorization

        profile = copy.deepcopy(base_profile)
        profile["profile_id"] = profile_id
        profile["license_record"] = (
            "Amitaro MANA corpus personal evaluation; attribution required; "
            f"bundled terms sha256:{readme_sha256}"
        )
        runtime = _object(profile.get("runtime"), f"{variant_id} runtime")
        configuration = _object(
            runtime.get("configuration"), f"{variant_id} configuration"
        )
        configuration["target_reference_sha256"] = reference_sha256
        configuration["target_authorization_sha256"] = authorization_sha256
        profiles.append(profile)
        existing_profiles.add(profile_id)

        material_manifest = {
            "variant_id": variant_id,
            "provider_id": "amitaro",
            "source_page_url": _text(
                intake_document.get("source_page_url"), "source_page_url"
            ),
            "download_page_url": _text(
                intake_document.get("download_page_url"), "download_page_url"
            ),
            "terms_url": _text(intake_document.get("terms_url"), "terms_url"),
            "download_url": _text(candidate.get("download_url"), "download_url"),
            "archive_sha256": f"sha256:{archive_sha256}",
            "reference_sha256": f"sha256:{reference_sha256}",
            "authorization_sha256": f"sha256:{authorization_sha256}",
            "readme_sha256": f"sha256:{readme_sha256}",
            "required_attribution": _text(
                intake_document.get("required_attribution"), "required_attribution"
            ),
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
            "family_id": "x-vc",
            "profile_id": profile_id,
            "status": "approved",
            "scope": "personal-evaluation",
            "authorization_owner": "personal-operator",
            "retention_policy": "delete-on-expiry-or-revocation",
            "deletion_path": str(reference.parent),
            "source_material_sha256": f"sha256:{reference_sha256}",
            "source_manifest_sha256": source_manifest_sha256,
            "terms_sha256": f"sha256:{readme_sha256}",
            "lineage_manifest_sha256": lineage_manifest_sha256,
            "reviewed_at": reviewed_text,
            "expires_at": None,
            "attribution_state": "satisfied",
            "notice_state": "not-required-for-personal-evaluation",
        }
        record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
        records.append(record)
        promotion = _object(profile.get("promotion"), f"{variant_id} promotion")
        display_order += 1
        variants.append(
            {
                "variant_id": variant_id,
                "family_id": "x-vc",
                "display_order": display_order,
                "display_name": _text(candidate.get("display_name"), "display_name"),
                "target_presentation": _text(
                    candidate.get("target_presentation"), "target_presentation"
                ),
                "lane": "voice-conversion",
                "invocation_mode": "live",
                "profile_id": profile_id,
                "profile_hash": ZERO_SHA256,
                "configuration_hash": ZERO_SHA256,
                "pack_id": "x-vc",
                "promotion_evidence_sha256": promotion["evidence_sha256"],
                "authorization_record_sha256": record["record_sha256"],
                "variant_manifest_sha256": ZERO_SHA256,
            }
        )
        existing_variants.add(variant_id)
        names = target_environment_names(profile_id)
        environment.update(
            {
                names[0]: str(reference),
                names[1]: reference_sha256,
                names[2]: str(authorization_directory / authorization_name),
                names[3]: authorization_sha256,
            }
        )
        del archive, readme

    registry["registry_revision"] = ZERO_SHA256
    registry["registry_revision"] = VALIDATOR.authorization_registry_revision(registry)
    draft["authorization_registry_revision"] = registry["registry_revision"]
    draft["authorization_records"] = copy.deepcopy(records)
    bundle_id = "ms3-amitaro-rvc-openvoice-xvc-first-wave-v1"
    draft["bundle_id"] = bundle_id
    draft["bundle_revision"] = ZERO_SHA256
    public_manifest["bundle_id"] = bundle_id
    public_manifest["bundle_revision"] = ZERO_SHA256
    materials = {"schema_version": 1, "provider_id": "amitaro", "manifests": manifests}
    return draft, registry, materials, environment, authorization_documents


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_json_bytes(value))
    path.chmod(0o600)


def write_preparation(
    destination: Path,
    draft: dict[str, Any],
    registry: dict[str, Any],
    materials: dict[str, Any],
    environment: dict[str, str],
    authorization_documents: dict[str, dict[str, object]],
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
        _write_json(staging / "draft.json", draft)
        _write_json(staging / "authorization-registry.json", registry)
        _write_json(staging / "material-manifests.json", materials)
        authorization_root = staging / "target-authorizations"
        authorization_root.mkdir(mode=0o700)
        for name, document in authorization_documents.items():
            _write_json(authorization_root / name, document)
        lines = [
            f"export {name}={shlex.quote(value)}"
            for name, value in sorted(environment.items())
        ]
        (staging / "identity.env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (staging / "identity.env").chmod(0o600)
        os.replace(staging, destination)
    except BaseException:
        if staging.exists():
            for child in sorted(staging.rglob("*"), reverse=True):
                child.rmdir() if child.is_dir() else child.unlink()
            staging.rmdir()
        raise


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-registry", type=Path)
    source.add_argument("--xvc-identity-env", type=Path)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        base_registry = (
            json.loads(arguments.base_registry.read_text(encoding="utf-8"))
            if arguments.base_registry is not None
            else base_registry_from_identity(arguments.xvc_identity_env)
        )
        draft = json.loads(
            (arguments.prepared / "draft.json").read_text(encoding="utf-8")
        )
        registry = json.loads(
            (arguments.prepared / "authorization-registry.json").read_text(
                encoding="utf-8"
            )
        )
        intake = json.loads(arguments.intake.read_text(encoding="utf-8"))
        prepared = extend_documents(
            base_registry,
            draft,
            registry,
            intake,
            arguments.reference_root,
            arguments.output / "target-authorizations",
            reviewed_at=datetime.now(UTC),
        )
        write_preparation(arguments.output, *prepared)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 X-VC preparation failed: {exc}", file=sys.stderr)
        return 2
    print(f"prepared {len(prepared[0]['public_manifest']['variants'])} total variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
