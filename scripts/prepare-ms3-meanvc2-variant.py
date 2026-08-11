#!/usr/bin/env python3
"""Add the exact MeanVC2 Runrun technical route to an MS-3 deployment draft."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from liveconv_audio.model_adapters import meanvc2

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-meanvc2-amitaro-intake.json"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"
LAUNCHER_PATH = REPOSITORY_ROOT / "scripts" / "run-ms3-gateway.py"
ZERO_SHA256 = "sha256:" + "0" * 64
EXPECTED_EVIDENCE = (
    "sha256:b103f6382092606d4c8351963066dcaa3b23994773d07973a6cc37bd8a804e3b"
)
EXPECTED_ENDPOINT_SHA256 = (
    "sha256:1d3cf64f97cadc79fdc6fe2496a21b7b456cb94211978cfef5a65f616af74fd5"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"support module could not be loaded: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_module("liveconv_prepare_meanvc2_validator", VALIDATOR_PATH)
LAUNCHER = _load_module("liveconv_prepare_meanvc2_launcher", LAUNCHER_PATH)


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


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _bound_file(root: Path, relative: Path, expected_sha256: str) -> Path:
    root = root.resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    if (
        root not in candidate.parents
        or candidate.is_symlink()
        or not candidate.is_file()
    ):
        raise ValueError(f"MeanVC2 candidate material is unsafe: {relative}")
    if _sha256_file(candidate) != expected_sha256:
        raise ValueError(f"MeanVC2 candidate material digest differs: {relative}")
    return candidate


def _pack_identity() -> tuple[str, str]:
    path = REPOSITORY_ROOT / "workers" / "packs" / "meanvc2.json"
    pack = _object(json.loads(path.read_text(encoding="utf-8")), "MeanVC2 pack")
    evidence = _object(pack.get("promotion_evidence"), "promotion evidence")
    if (
        pack.get("pack_id") != "meanvc2"
        or evidence.get("status") != "technical_validation"
        or evidence.get("evidence_sha256") != EXPECTED_EVIDENCE
    ):
        raise ValueError("MeanVC2 pack is not bound to the retained technical smoke")
    return "sha256:" + _sha256_file(path), EXPECTED_EVIDENCE


def verify_identity_environment(values: dict[str, str]) -> None:
    expected = {
        "LIVECONV_MEANVC2_SOURCE_REVISION": meanvc2.CANONICAL_CONFIGURATION[
            "source_revision"
        ],
        "LIVECONV_MEANVC2_SOURCE_SHA256": meanvc2.CANONICAL_CONFIGURATION[
            "source_sha256"
        ],
        "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256": (
            meanvc2.CANONICAL_CONFIGURATION["target_reference_sha256"]
        ),
        "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256": (
            meanvc2.CANONICAL_CONFIGURATION["target_authorization_sha256"]
        ),
        "LIVECONV_MEANVC2_INTERPRETER_SHA256": EXPECTED_ENDPOINT_SHA256.removeprefix(
            "sha256:"
        ),
    }
    for name, expected_value in expected.items():
        if values.get(name) != expected_value:
            raise ValueError(f"MeanVC2 identity differs: {name}")
    source_root = Path(_text(values.get("LIVECONV_MEANVC2_SOURCE_ROOT"), "source root"))
    if not source_root.is_absolute() or not source_root.is_dir():
        raise ValueError("MeanVC2 source root is unavailable")
    for name, value in values.items():
        if not name.startswith("LIVECONV_MEANVC2_") or not name.endswith("_PATH"):
            continue
        path = Path(value)
        digest_name = name.removesuffix("_PATH") + "_SHA256"
        expected_digest = values.get(digest_name)
        resolved = path.resolve(strict=True) if path.is_absolute() else path
        if (
            not path.is_absolute()
            or not resolved.is_file()
            or (path.is_symlink() and name != "LIVECONV_MEANVC2_INTERPRETER_PATH")
            or expected_digest is None
            or _sha256_file(resolved) != expected_digest
        ):
            raise ValueError(f"MeanVC2 artifact differs: {name}")


def _profile(values: dict[str, str], profile_id: str) -> dict[str, Any]:
    pack_sha256, evidence_sha256 = _pack_identity()
    configuration = meanvc2._configuration(profile_id)
    return {
        "adapter_api_version": 1,
        "cancellation": "immediate",
        "frame_ms": meanvc2.FRAME_MS,
        "implementation_revision": meanvc2.IMPLEMENTATION_REVISION,
        "input_sample_rates": [48_000],
        "kind": "voice_conversion",
        "license_record": (
            "Personal technical evaluation only; official Hugging Face card and "
            "upstream README declare Apache-2.0, but the reviewed Git snapshot has "
            "no root LICENSE; Amitaro attribution required"
        ),
        "minimum_context_ms": 160,
        "output_sample_rates": [48_000],
        "profile_id": profile_id,
        "promotion": {
            "endpoint_sha256": EXPECTED_ENDPOINT_SHA256,
            "evidence_sha256": evidence_sha256,
            "pack_id": "meanvc2",
            "pack_sha256": pack_sha256,
            "status": "technical_validation",
        },
        "readiness": "ready",
        "resource_class": "gpu",
        "runtime": {
            "adapter": "worker",
            "configuration": copy.deepcopy(configuration),
            "max_vram_mb": 16_384,
            "worker_endpoint": _text(
                values.get("LIVECONV_MEANVC2_INTERPRETER_PATH"), "worker endpoint"
            ),
            "worker_module": meanvc2.WORKER_MODULE,
        },
        "streaming": True,
        "timeouts": {"first_output_ms": 120_000, "stall_ms": 30_000},
        "voice_requirement": "pretrained_voice",
        "warmup_policy": "eager",
        "weight_revision": meanvc2.WEIGHT_REVISION,
    }


def extend_documents(
    base_bundle: object,
    authorization_registry: object,
    intake: object,
    identity_values: dict[str, str],
    reference_root: Path,
    authorization_root: Path,
    *,
    reviewed_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    draft = copy.deepcopy(_object(base_bundle, "base bundle"))
    registry = copy.deepcopy(_object(authorization_registry, "authorization registry"))
    intake_document = _object(intake, "MeanVC2 intake")
    if intake_document.get("schema_version") != 1:
        raise ValueError("unsupported MeanVC2 intake schema")
    candidates = _array(intake_document.get("variants"), "MeanVC2 variants")
    if not 1 <= len(candidates) <= 4:
        raise ValueError("MeanVC2 intake must contain between one and four variants")
    reference_root = reference_root.resolve(strict=True)
    authorization_root = authorization_root.resolve(strict=True)

    profile_registry = _object(
        draft.get("gateway_profile_registry"), "profile registry"
    )
    profiles = _array(profile_registry.get("profiles"), "profiles")
    public_manifest = _object(draft.get("public_manifest"), "public manifest")
    variants = _array(public_manifest.get("variants"), "variants")
    records = _array(registry.get("records"), "authorization records")
    reviewed_text = (
        reviewed_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    manifests: list[dict[str, Any]] = []
    environment: dict[str, str] = {}
    existing_profiles = {item.get("profile_id") for item in profiles}
    existing_variants = {item.get("variant_id") for item in variants}
    display_order = max(
        (int(item.get("display_order", 0)) for item in variants), default=0
    )
    for candidate_item in candidates:
        candidate = {**intake_document, **candidate_item}
        variant_id = _text(candidate.get("variant_id"), "variant_id")
        profile_id = _text(candidate.get("profile_id"), "profile_id")
        if (
            candidate.get("family_id") != "meanvc2"
            or profile_id not in meanvc2._APPROVED_TARGETS
        ):
            raise ValueError("MeanVC2 intake identity is not approved")
        expected_reference, expected_authorization = meanvc2._APPROVED_TARGETS[
            profile_id
        ]
        if (
            candidate.get("reference_sha256"),
            candidate.get("target_authorization_sha256"),
        ) != (expected_reference, expected_authorization):
            raise ValueError("MeanVC2 target identity differs")
        if profile_id in existing_profiles or variant_id in existing_variants:
            raise ValueError("MeanVC2 variant already exists")

        if profile_id == meanvc2.PROFILE_ID:
            reference = Path(identity_values["LIVECONV_MEANVC2_TARGET_REFERENCE_PATH"])
            authorization = Path(
                identity_values["LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH"]
            )
        else:
            reference = _bound_file(
                reference_root,
                Path("extracted")
                / _text(candidate.get("style_id"), "style_id")
                / _text(candidate.get("reference_name"), "reference_name"),
                expected_reference,
            )
            authorization = _bound_file(
                authorization_root,
                Path(_text(candidate.get("authorization_name"), "authorization_name")),
                expected_authorization,
            )
            names = meanvc2.target_environment_names(profile_id)
            environment.update(
                {
                    names[0]: str(reference),
                    names[1]: expected_reference,
                    names[2]: str(authorization),
                    names[3]: expected_authorization,
                }
            )

        profile = _profile(identity_values, profile_id)
        profiles.append(profile)
        existing_profiles.add(profile_id)
        material_manifest = {
            "schema_version": 1,
            "variant_id": variant_id,
            "provider_id": candidate["provider_id"],
            "source_page_url": candidate["source_page_url"],
            "terms_url": candidate["terms_url"],
            "model_source_url": candidate["model_source_url"],
            "model_revision": candidate["model_revision"],
            "model_snapshot_url": candidate["model_snapshot_url"],
            "model_snapshot_revision": candidate["model_snapshot_revision"],
            "license_state": candidate["license_state"],
            "reference_sha256": "sha256:" + expected_reference,
            "target_authorization_sha256": "sha256:" + expected_authorization,
            "adapter_source_sha256": (
                "sha256:"
                + str(meanvc2.CANONICAL_CONFIGURATION["adapter_source_sha256"])
            ),
            "checkpoint_sha256": (
                "sha256:" + str(meanvc2.CANONICAL_CONFIGURATION["checkpoint_sha256"])
            ),
            "worker_smoke_evidence_sha256": EXPECTED_EVIDENCE,
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
        record = {
            "record_sha256": ZERO_SHA256,
            "variant_id": variant_id,
            "family_id": "meanvc2",
            "profile_id": profile_id,
            "status": "approved",
            "scope": "personal-evaluation",
            "authorization_owner": "personal-operator",
            "retention_policy": "delete-on-expiry-or-revocation",
            "deletion_path": str(reference.parent),
            "source_material_sha256": "sha256:" + expected_reference,
            "source_manifest_sha256": source_manifest_sha256,
            "terms_sha256": "sha256:" + candidate["reference_terms_sha256"],
            "lineage_manifest_sha256": lineage_manifest_sha256,
            "reviewed_at": reviewed_text,
            "expires_at": None,
            "attribution_state": "satisfied",
            "notice_state": "not-required-for-personal-evaluation",
        }
        record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
        records.append(record)
        display_order += 1
        variants.append(
            {
                "variant_id": variant_id,
                "family_id": "meanvc2",
                "display_order": display_order,
                "display_name": candidate["display_name"],
                "target_presentation": candidate["target_presentation"],
                "lane": "voice-conversion",
                "invocation_mode": "live",
                "profile_id": profile_id,
                "profile_hash": ZERO_SHA256,
                "configuration_hash": ZERO_SHA256,
                "pack_id": "meanvc2",
                "promotion_evidence_sha256": EXPECTED_EVIDENCE,
                "authorization_record_sha256": record["record_sha256"],
                "variant_manifest_sha256": ZERO_SHA256,
            }
        )
        existing_variants.add(variant_id)
        material_manifest["source_manifest_sha256"] = source_manifest_sha256
        material_manifest["lineage_manifest_sha256"] = lineage_manifest_sha256
        manifests.append(material_manifest)
    registry["registry_revision"] = ZERO_SHA256
    registry["registry_revision"] = VALIDATOR.authorization_registry_revision(registry)
    bundle_id = "ms3-amitaro-rvc-openvoice-xvc-meanvc2-first-wave-v1"
    draft["bundle_id"] = bundle_id
    draft["bundle_revision"] = ZERO_SHA256
    draft["authorization_registry_revision"] = registry["registry_revision"]
    draft["authorization_records"] = copy.deepcopy(records)
    public_manifest["bundle_id"] = bundle_id
    public_manifest["bundle_revision"] = ZERO_SHA256
    materials = {
        "schema_version": 1,
        "provider_id": "amitaro-meanvc2",
        "manifests": manifests,
    }
    return draft, registry, materials, environment


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_json_bytes(value))
    path.chmod(0o600)


def write_preparation(
    destination: Path,
    draft: dict[str, Any],
    registry: dict[str, Any],
    materials: dict[str, Any],
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
        _write_json(staging / "draft.json", draft)
        _write_json(staging / "authorization-registry.json", registry)
        _write_json(staging / "material-manifests.json", materials)
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
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--meanvc2-identity-env", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument(
        "--authorization-root",
        type=Path,
        default=REPOSITORY_ROOT / "artifacts" / "meanvc2" / "target-authorizations",
    )
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        values, _removed = LAUNCHER.read_identity_environment(
            arguments.meanvc2_identity_env
        )
        verify_identity_environment(values)
        base_bundle = json.loads(
            (arguments.deployment / "bundle.json").read_text(encoding="utf-8")
        )
        authorization_registry = json.loads(
            (arguments.deployment / "authorization-registry.json").read_text(
                encoding="utf-8"
            )
        )
        intake = json.loads(arguments.intake.read_text(encoding="utf-8"))
        prepared = extend_documents(
            base_bundle,
            authorization_registry,
            intake,
            values,
            arguments.reference_root,
            arguments.authorization_root,
            reviewed_at=datetime.now(UTC),
        )
        write_preparation(arguments.output, *prepared)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 MeanVC2 preparation failed: {exc}", file=sys.stderr)
        return 2
    print(f"prepared {len(prepared[0]['public_manifest']['variants'])} total variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
