#!/usr/bin/env python3
"""Extend a prepared MS-3 bundle with exact Amitaro OpenVoice variants."""

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
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-openvoice-amitaro-intake.json"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate-deployment-bundle.py"
MS2_BUILDER_PATH = REPOSITORY_ROOT / "scripts" / "build-ms2-profile-registry.py"
LAUNCHER_PATH = REPOSITORY_ROOT / "scripts" / "run-ms3-gateway.py"
ZERO_SHA256 = "sha256:" + "0" * 64
BASE_PROFILE_ID = "vc.openvoice-v2.synthetic-ja.v1"
APPROVED_TARGETS = {
    "vc.openvoice-v2.amitaro-runrun.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.3,
    ),
    "vc.openvoice-v2.amitaro-runrun-tau015.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.15,
    ),
    "vc.openvoice-v2.amitaro-runrun-tau060.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.6,
    ),
    "vc.openvoice-v2.amitaro-yofukashi.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.3,
    ),
    "vc.openvoice-v2.amitaro-yofukashi-tau015.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.15,
    ),
    "vc.openvoice-v2.amitaro-yofukashi-tau060.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.6,
    ),
}


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_prepare_openvoice_validator", VALIDATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("deployment validator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"support module could not be loaded: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MS2_BUILDER = _load_module("liveconv_prepare_openvoice_ms2_builder", MS2_BUILDER_PATH)
LAUNCHER = _load_module("liveconv_prepare_openvoice_launcher", LAUNCHER_PATH)


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


def target_environment_names(profile_id: str) -> tuple[str, str]:
    if profile_id not in APPROVED_TARGETS:
        raise ValueError(f"{profile_id}: OpenVoice profile ID is not approved")
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_OPENVOICE_V2_VARIANT_{suffix}"
    return (
        f"{prefix}_TARGET_REFERENCE_PATH",
        f"{prefix}_TARGET_REFERENCE_SHA256",
    )


def _expanded_candidates(intake_document: dict[str, Any]) -> list[dict[str, Any]]:
    voices = _array(intake_document.get("variants"), "intake variants")
    raw_presets = intake_document.get("parameter_presets")
    presets = (
        _array(raw_presets, "parameter presets")
        if raw_presets is not None
        else [
            {
                "preset_id": "tau030",
                "preserve_base_identity": True,
                "display_suffix": "tau 0.30",
                "tau": 0.3,
            }
        ]
    )
    if not voices or not presets or len(voices) * len(presets) > 8:
        raise ValueError(
            "OpenVoice intake must expand to between one and eight variants"
        )
    expanded: list[dict[str, Any]] = []
    for voice in voices:
        base_variant_id = _text(voice.get("variant_id"), "variant_id")
        base_profile_id = _text(voice.get("profile_id"), "profile_id")
        base_display_name = _text(voice.get("display_name"), "display_name")
        if not base_profile_id.endswith(".v1"):
            raise ValueError(f"{base_profile_id}: base profile must end in .v1")
        for preset in presets:
            preset_id = _text(preset.get("preset_id"), "preset_id")
            display_suffix = _text(preset.get("display_suffix"), "display_suffix")
            tau = preset.get("tau")
            if type(tau) not in {int, float} or not 0.0 <= tau <= 1.0:
                raise ValueError(f"{preset_id}: tau must be a number from 0 to 1")
            candidate = copy.deepcopy(voice)
            if preset.get("preserve_base_identity") is True:
                candidate["variant_id"] = base_variant_id
                candidate["profile_id"] = base_profile_id
            else:
                candidate["variant_id"] = f"{base_variant_id}-{preset_id}"
                candidate["profile_id"] = (
                    f"{base_profile_id.removesuffix('.v1')}-{preset_id}.v1"
                )
            candidate["display_name"] = f"{base_display_name} ・ {display_suffix}"
            candidate["tau"] = float(tau)
            expanded.append(candidate)
    return expanded


def _base_openvoice_profile(base_registry: object) -> dict[str, Any]:
    registry = _object(base_registry, "base registry")
    profiles = _array(registry.get("profiles"), "base registry profiles")
    matches = [
        profile for profile in profiles if profile.get("profile_id") == BASE_PROFILE_ID
    ]
    if registry.get("schema_version") != 1 or len(matches) != 1:
        raise ValueError("base registry must contain the retained OpenVoice profile")
    profile = matches[0]
    runtime = _object(profile.get("runtime"), "base OpenVoice runtime")
    promotion = _object(profile.get("promotion"), "base OpenVoice promotion")
    if (
        runtime.get("adapter") != "worker"
        or runtime.get("worker_module") != "workers.adapters.openvoice_v2"
        or promotion.get("pack_id") != "openvoice-v2"
    ):
        raise ValueError("base OpenVoice profile has an incompatible identity")
    return profile


def base_registry_from_identity(identity_path: Path) -> dict[str, Any]:
    values, _removed = LAUNCHER.read_identity_environment(identity_path)
    runtime_prefix = values.get("LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX")
    if not runtime_prefix:
        raise ValueError("OpenVoice identity is missing its runtime prefix")
    endpoint = Path(runtime_prefix) / "bin" / "python"
    material = MS2_BUILDER._load_object(
        REPOSITORY_ROOT
        / "workers"
        / "adapters"
        / "openvoice_v2"
        / "canonical-profile.json"
    )
    profile = MS2_BUILDER._openvoice_profile(
        material,
        endpoint=MS2_BUILDER._endpoint(endpoint, model_id="openvoice-v2"),
        repository_root=REPOSITORY_ROOT,
    )
    return {"schema_version": 1, "profiles": [profile]}


def _configuration_hash(configuration: dict[str, Any]) -> str:
    encoded = json.dumps(
        configuration,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _weight_revision(configuration: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in (
        "source_tree_sha256",
        "config_sha256",
        "checkpoint_sha256",
        "target_reference_sha256",
    ):
        digest.update(bytes.fromhex(_text(configuration.get(key), key)))
    return f"sha256:{digest.hexdigest()}"


def extend_documents(
    base_registry: object,
    prepared_draft: object,
    authorization_registry: object,
    intake: object,
    reference_root: Path,
    *,
    reviewed_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
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
    candidates = _expanded_candidates(intake_document)
    base_profile = _base_openvoice_profile(base_registry)
    reference_root = reference_root.resolve(strict=True)
    profile_registry = _object(
        draft.get("gateway_profile_registry"), "draft profile registry"
    )
    profiles = _array(profile_registry.get("profiles"), "draft profiles")
    public_manifest = _object(draft.get("public_manifest"), "public manifest")
    variants = _array(public_manifest.get("variants"), "public variants")
    records = _array(registry.get("records"), "authorization records")
    existing_profiles = {profile.get("profile_id") for profile in profiles}
    existing_variants = {variant.get("variant_id") for variant in variants}
    manifests: list[dict[str, Any]] = []
    environment: dict[str, str] = {}
    display_order = max(
        (int(variant.get("display_order", 0)) for variant in variants),
        default=0,
    )

    for candidate in candidates:
        variant_id = _text(candidate.get("variant_id"), "variant_id")
        profile_id = _text(candidate.get("profile_id"), f"{variant_id} profile_id")
        if variant_id in existing_variants or profile_id in existing_profiles:
            raise ValueError(f"duplicate prepared identity: {variant_id}")
        expected = APPROVED_TARGETS.get(profile_id)
        if isinstance(expected, str):
            expected = (expected, 0.3)
        if (
            expected is None
            or (candidate.get("reference_sha256"), candidate.get("tau")) != expected
        ):
            raise ValueError(f"{profile_id}: reference is not statically approved")
        style_id = _text(candidate.get("style_id"), f"{variant_id} style_id")
        archive_sha256 = _text(candidate.get("archive_sha256"), "archive_sha256")
        reference_sha256 = _text(candidate.get("reference_sha256"), "reference_sha256")
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
        configuration["tau"] = candidate["tau"]
        profile["weight_revision"] = _weight_revision(configuration)
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
            "readme_sha256": f"sha256:{readme_sha256}",
            "required_attribution": _text(
                intake_document.get("required_attribution"), "required_attribution"
            ),
            "tau": candidate["tau"],
        }
        source_manifest_sha256 = VALIDATOR.canonical_hash(material_manifest)
        lineage_manifest_sha256 = VALIDATOR.canonical_hash(
            {
                "source_manifest_sha256": source_manifest_sha256,
                "profile_id": profile_id,
                "profile_hash": VALIDATOR.profile_hash(profile),
                "configuration_hash": _configuration_hash(configuration),
                "implementation_revision": profile["implementation_revision"],
            }
        )
        material_manifest["source_manifest_sha256"] = source_manifest_sha256
        material_manifest["lineage_manifest_sha256"] = lineage_manifest_sha256
        manifests.append(material_manifest)
        record = {
            "record_sha256": ZERO_SHA256,
            "variant_id": variant_id,
            "family_id": "openvoice-v2",
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
                "family_id": "openvoice-v2",
                "display_order": display_order,
                "display_name": _text(candidate.get("display_name"), "display_name"),
                "target_presentation": _text(
                    candidate.get("target_presentation"), "target_presentation"
                ),
                "lane": "voice-conversion",
                "invocation_mode": "buffered_end",
                "profile_id": profile_id,
                "profile_hash": ZERO_SHA256,
                "configuration_hash": ZERO_SHA256,
                "pack_id": "openvoice-v2",
                "promotion_evidence_sha256": promotion["evidence_sha256"],
                "authorization_record_sha256": record["record_sha256"],
                "variant_manifest_sha256": ZERO_SHA256,
            }
        )
        existing_variants.add(variant_id)
        path_name, digest_name = target_environment_names(profile_id)
        environment[path_name] = str(reference)
        environment[digest_name] = reference_sha256
        del archive, readme

    registry["registry_revision"] = ZERO_SHA256
    registry["registry_revision"] = VALIDATOR.authorization_registry_revision(registry)
    draft["authorization_registry_revision"] = registry["registry_revision"]
    draft["authorization_records"] = copy.deepcopy(records)
    bundle_id = "ms3-amitaro-rvc-openvoice-first-wave-v1"
    draft["bundle_id"] = bundle_id
    draft["bundle_revision"] = ZERO_SHA256
    public_manifest["bundle_id"] = bundle_id
    public_manifest["bundle_revision"] = ZERO_SHA256
    material_document = {
        "schema_version": 1,
        "provider_id": "amitaro",
        "manifests": manifests,
    }
    return draft, registry, material_document, environment


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-registry", type=Path)
    source.add_argument("--openvoice-identity-env", type=Path)
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
            else base_registry_from_identity(arguments.openvoice_identity_env)
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
            reviewed_at=datetime.now(UTC),
        )
        write_preparation(arguments.output, *prepared)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"MS-3 OpenVoice preparation failed: {exc}", file=sys.stderr)
        return 2
    print(f"prepared {len(prepared[0]['public_manifest']['variants'])} total variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
