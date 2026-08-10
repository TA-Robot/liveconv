from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "validate-deployment-bundle.py"
BUILDER_SCRIPT = Path(__file__).parents[1] / "build-ms3-deployment-bundle.py"
LAUNCHER_SCRIPT = Path(__file__).parents[1] / "run-ms3-gateway.py"


def load_validator() -> object:
    spec = importlib.util.spec_from_file_location("validate_deployment_bundle", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator()


def load_builder() -> object:
    spec = importlib.util.spec_from_file_location(
        "build_ms3_deployment_bundle", BUILDER_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def load_launcher() -> object:
    spec = importlib.util.spec_from_file_location("run_ms3_gateway", LAUNCHER_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAUNCHER = load_launcher()
VALIDATION_TIME = datetime.fromisoformat("2026-08-10T12:00:00+00:00")


def validate_bundle(
    bundle: object,
    authorization_registry: object | None,
    *,
    validation_time: datetime = VALIDATION_TIME,
) -> list[str]:
    return VALIDATOR.validate_bundle(
        bundle,
        authorization_registry,
        validation_time=validation_time,
    )


def digest(number: int) -> str:
    return f"sha256:{number:064x}"


def profile(profile_id: str, pack_id: str, number: int) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "kind": "voice_conversion",
        "readiness": "ready",
        "adapter_api_version": 1,
        "implementation_revision": f"implementation-{number}",
        "weight_revision": digest(100 + number),
        "streaming": True,
        "cancellation": "generation_only",
        "input_sample_rates": [48000],
        "output_sample_rates": [48000],
        "frame_ms": 20,
        "minimum_context_ms": 500,
        "voice_requirement": "pretrained_voice",
        "warmup_policy": "lazy",
        "resource_class": "gpu",
        "license_record": f"reviewed-license-{number}",
        "promotion": {
            "status": "technical_validation",
            "pack_id": pack_id,
            "pack_sha256": digest(200 + number),
            "evidence_sha256": digest(300 + number),
            "endpoint_sha256": digest(400 + number),
        },
        "timeouts": {"first_output_ms": 120000, "stall_ms": 10000},
        "runtime": {
            "adapter": "worker",
            "worker_module": "workers.adapters.rvc_v2.worker",
            "configuration": {"variant_revision": number},
            "worker_endpoint": f"/private/runtime-{number}/bin/python",
            "max_vram_mb": 12000,
        },
    }


def deployment_bundle() -> dict[str, object]:
    families = ("rvc-v2", "meanvc2", "x-vc", "openvoice-v2")
    profiles = []
    variants = []
    authorization_records = []
    for index in range(1, 10):
        family = families[(index - 1) % len(families)]
        profile_id = f"vc.{family}.voice-{index}.v1"
        bound_profile = profile(profile_id, family, index)
        profiles.append(bound_profile)
        authorization_record = {
            "record_sha256": digest(0),
            "variant_id": f"{family}-voice-{index}",
            "family_id": family,
            "profile_id": profile_id,
            "status": "approved",
            "scope": "personal-evaluation",
            "authorization_owner": "personal-operator",
            "retention_policy": "delete-on-expiry-or-revocation",
            "deletion_path": f"/private/voice-material/{family}-voice-{index}",
            "source_material_sha256": digest(500 + index),
            "source_manifest_sha256": digest(600 + index),
            "terms_sha256": digest(700 + index),
            "lineage_manifest_sha256": digest(800 + index),
            "reviewed_at": "2026-08-09T00:00:00Z",
            "expires_at": None,
            "attribution_state": "satisfied",
            "notice_state": "not-required-for-personal-evaluation",
        }
        authorization_record["record_sha256"] = VALIDATOR.authorization_record_hash(
            authorization_record
        )
        authorization_records.append(authorization_record)
        variant = {
            "variant_id": f"{family}-voice-{index}",
            "family_id": family,
            "display_order": index,
            "display_name": f"Voice {index}",
            "target_presentation": "youthful-feminine",
            "lane": "voice-conversion",
            "invocation_mode": "live",
            "profile_id": profile_id,
            "profile_hash": VALIDATOR.profile_hash(bound_profile),
            "configuration_hash": VALIDATOR.configuration_hash(bound_profile),
            "pack_id": family,
            "promotion_evidence_sha256": bound_profile["promotion"]["evidence_sha256"],
            "authorization_record_sha256": authorization_record["record_sha256"],
            "variant_manifest_sha256": digest(0),
        }
        variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)
        variants.append(variant)

    authorization_registry = {
        "schema_version": 1,
        "registry_revision": digest(0),
        "records": deepcopy(authorization_records),
    }
    authorization_registry["registry_revision"] = (
        VALIDATOR.authorization_registry_revision(authorization_registry)
    )
    bundle = {
        "schema_version": 1,
        "bundle_id": "ms3-test-bundle-v1",
        "created_at": "2026-08-10T00:00:00Z",
        "bundle_revision": digest(0),
        "protocol_version": 1,
        "gateway_profile_registry": {"schema_version": 1, "profiles": profiles},
        "authorization_registry_revision": authorization_registry["registry_revision"],
        "authorization_records": authorization_records,
        "public_manifest": {
            "schema_version": 1,
            "bundle_id": "ms3-test-bundle-v1",
            "bundle_revision": digest(0),
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
    revision = VALIDATOR.bundle_revision(bundle)
    bundle["bundle_revision"] = revision
    bundle["public_manifest"]["bundle_revision"] = revision
    return bundle


def authorization_registry_for(bundle: dict[str, object]) -> dict[str, object]:
    registry = {
        "schema_version": 1,
        "registry_revision": digest(0),
        "records": deepcopy(bundle["authorization_records"]),
    }
    registry["registry_revision"] = VALIDATOR.authorization_registry_revision(registry)
    return registry


def rebind_bundle(bundle: dict[str, object]) -> None:
    revision = VALIDATOR.bundle_revision(bundle)
    bundle["bundle_revision"] = revision
    bundle["public_manifest"]["bundle_revision"] = revision


def test_valid_bundle_has_private_registry_and_public_safe_projection() -> None:
    bundle = deployment_bundle()

    assert validate_bundle(bundle, authorization_registry_for(bundle)) == []
    public_json = json.dumps(bundle["public_manifest"], sort_keys=True)
    assert "/private/" not in public_json
    assert "worker_endpoint" not in public_json
    assert "token" not in public_json


def test_builder_seals_all_derived_identities_and_writes_one_private_directory(
    tmp_path: Path,
) -> None:
    draft = deployment_bundle()
    registry = authorization_registry_for(draft)
    draft["gateway_profile_registry"]["profiles"][0]["runtime"]["configuration"][
        "variant_revision"
    ] = 99
    draft["authorization_records"] = []
    for variant in draft["public_manifest"]["variants"]:
        variant["profile_hash"] = digest(0)
        variant["configuration_hash"] = digest(0)
        variant["authorization_record_sha256"] = digest(0)
        variant["variant_manifest_sha256"] = digest(0)

    sealed = BUILDER.seal_bundle(
        draft,
        registry,
        validation_time=VALIDATION_TIME,
    )
    destination = tmp_path / "deployment-v1"
    BUILDER.write_bundle_directory(destination, sealed, registry)

    assert validate_bundle(sealed, registry) == []
    assert json.loads((destination / "bundle.json").read_text()) == sealed
    assert (
        json.loads((destination / "profiles.json").read_text())
        == sealed["gateway_profile_registry"]
    )
    assert (
        json.loads((destination / "manifest.json").read_text())
        == sealed["public_manifest"]
    )
    assert (destination / "bundle.json").stat().st_mode & 0o777 == 0o600
    assert (destination / "manifest.json").stat().st_mode & 0o777 == 0o644


def test_builder_refuses_private_output_inside_the_repository() -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        BUILDER.write_bundle_directory(
            Path(__file__).parents[2] / "private-deployment",
            deployment_bundle(),
            authorization_registry_for(deployment_bundle()),
        )


def test_terminal_activation_uses_only_the_sealed_bundle_and_literal_identity_env(
    tmp_path: Path,
) -> None:
    draft = deployment_bundle()
    registry = authorization_registry_for(draft)
    sealed = BUILDER.seal_bundle(
        draft,
        registry,
        validation_time=VALIDATION_TIME,
    )
    destination = tmp_path / "deployment-v1"
    BUILDER.write_bundle_directory(destination, sealed, registry)
    identity = tmp_path / "identity.env"
    identity.write_text(
        "# local runtime identity\n"
        "unset PYTHONPATH PYTHONHOME\n"
        "export LIVECONV_RVC_SOURCE_ROOT='/private/runtime path'\n",
        encoding="utf-8",
    )

    environment, activated = LAUNCHER.activation_environment(
        destination,
        [identity],
        base_environment={"PYTHONPATH": "unsafe", "UNCHANGED": "yes"},
        validation_time=VALIDATION_TIME,
    )

    assert activated["bundle_revision"] == sealed["bundle_revision"]
    assert environment["LIVECONV_DEPLOYMENT_BUNDLE"] == str(destination / "bundle.json")
    assert environment["LIVECONV_PROFILE_CONFIG"] == str(destination / "profiles.json")
    assert environment["LIVECONV_RVC_SOURCE_ROOT"] == "/private/runtime path"
    assert environment["LIVECONV_MAX_SESSIONS"] == "1"
    assert environment["UNCHANGED"] == "yes"
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment


def test_terminal_activation_rejects_a_manifest_from_another_bundle(
    tmp_path: Path,
) -> None:
    draft = deployment_bundle()
    registry = authorization_registry_for(draft)
    sealed = BUILDER.seal_bundle(
        draft,
        registry,
        validation_time=VALIDATION_TIME,
    )
    destination = tmp_path / "deployment-v1"
    BUILDER.write_bundle_directory(destination, sealed, registry)
    manifest = json.loads((destination / "manifest.json").read_text())
    manifest["bundle_id"] = "another-bundle"
    (destination / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="manifest.json does not match"):
        LAUNCHER.activation_environment(
            destination,
            [],
            base_environment={},
            validation_time=VALIDATION_TIME,
        )


def test_conflicting_duplicate_variant_id_is_rejected() -> None:
    bundle = deployment_bundle()
    authorization_registry = authorization_registry_for(bundle)
    variants = bundle["public_manifest"]["variants"]
    variants[1]["variant_id"] = variants[0]["variant_id"]
    variants[1]["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(
        variants[1]
    )
    rebind_bundle(bundle)

    assert "public_manifest contains duplicate variant_id values" in (
        validate_bundle(bundle, authorization_registry)
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("profile_hash", "profile hash mismatch"),
        ("configuration_hash", "configuration hash mismatch"),
        ("promotion_evidence_sha256", "promotion evidence mismatch"),
    ],
)
def test_public_variant_identity_must_match_private_profile(
    field: str, expected: str
) -> None:
    bundle = deployment_bundle()
    authorization_registry = authorization_registry_for(bundle)
    variant = bundle["public_manifest"]["variants"][0]
    variant[field] = digest(999)
    variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)
    rebind_bundle(bundle)

    assert any(
        expected in error for error in validate_bundle(bundle, authorization_registry)
    )


def test_public_manifest_rejects_secret_or_private_locator_fields() -> None:
    for forbidden in ("token", "bearer", "worker_endpoint", "runtime_path"):
        bundle = deployment_bundle()
        authorization_registry = authorization_registry_for(bundle)
        bundle["public_manifest"][forbidden] = "private-value"
        rebind_bundle(bundle)

        assert any(
            "Additional properties are not allowed" in error
            for error in validate_bundle(bundle, authorization_registry)
        )


def test_bundle_revision_and_atomic_failure_contract_are_enforced() -> None:
    stale = deployment_bundle()
    stale_authorization_registry = authorization_registry_for(stale)
    stale["gateway_profile_registry"]["profiles"][0]["runtime"]["configuration"][
        "variant_revision"
    ] = 999
    assert "bundle_revision does not match canonical bundle material" in (
        validate_bundle(stale, stale_authorization_registry)
    )

    unsafe = deployment_bundle()
    unsafe_authorization_registry = authorization_registry_for(unsafe)
    unsafe["consumer_contract"]["whole_bundle_mismatch"] = "partial-load"
    rebind_bundle(unsafe)
    assert any(
        "'reject-load-native-only' was expected" in error
        for error in validate_bundle(unsafe, unsafe_authorization_registry)
    )


def test_profile_and_variant_sets_must_match_exactly() -> None:
    bundle = deployment_bundle()
    authorization_registry = authorization_registry_for(bundle)
    bundle["gateway_profile_registry"]["profiles"][0]["profile_id"] = (
        "vc.rvc-v2.hidden.v1"
    )
    rebind_bundle(bundle)

    assert "public variants and gateway profiles do not have the same IDs" in (
        validate_bundle(bundle, authorization_registry)
    )


def test_trusted_authorization_registry_is_required() -> None:
    assert validate_bundle(deployment_bundle(), None) == [
        "trusted authorization registry is required"
    ]


@pytest.mark.parametrize(
    "field",
    ["authorization_owner", "retention_policy", "deletion_path"],
)
def test_authorization_record_requires_governance_fields(field: str) -> None:
    bundle = deployment_bundle()
    del bundle["authorization_records"][0][field]
    authorization_registry = authorization_registry_for(bundle)
    bundle["authorization_registry_revision"] = authorization_registry[
        "registry_revision"
    ]
    rebind_bundle(bundle)

    assert any(
        f"'{field}' is a required property" in error
        for error in validate_bundle(bundle, authorization_registry)
    )


def test_trusted_validation_time_is_required_and_timezone_aware() -> None:
    bundle = deployment_bundle()
    registry = authorization_registry_for(bundle)

    assert VALIDATOR.validate_bundle(
        bundle,
        registry,
        validation_time=None,
    ) == ["trusted validation_time is required"]
    assert VALIDATOR.validate_bundle(
        bundle,
        registry,
        validation_time=datetime.fromisoformat("2026-08-10T12:00:00"),
    ) == ["trusted validation_time must be timezone-aware"]


def test_forged_lineage_record_cannot_replace_the_trusted_record() -> None:
    bundle = deployment_bundle()
    authorization_registry = authorization_registry_for(bundle)
    record = bundle["authorization_records"][0]
    record["lineage_manifest_sha256"] = digest(999)
    record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
    variant = bundle["public_manifest"]["variants"][0]
    variant["authorization_record_sha256"] = record["record_sha256"]
    variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)
    rebind_bundle(bundle)

    assert "bundle authorization records do not match the trusted registry" in (
        validate_bundle(bundle, authorization_registry)
    )


def test_expired_authorization_is_rejected_even_when_registry_matches() -> None:
    bundle = deployment_bundle()
    record = bundle["authorization_records"][0]
    record["expires_at"] = "2026-08-09T12:00:00Z"
    record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
    variant = bundle["public_manifest"]["variants"][0]
    variant["authorization_record_sha256"] = record["record_sha256"]
    variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)
    authorization_registry = authorization_registry_for(bundle)
    bundle["authorization_registry_revision"] = authorization_registry[
        "registry_revision"
    ]
    rebind_bundle(bundle)

    assert any(
        "authorization is expired" in error
        for error in validate_bundle(bundle, authorization_registry)
    )


def test_authorization_expiry_is_checked_at_activation_time() -> None:
    bundle = deployment_bundle()
    record = bundle["authorization_records"][0]
    record["expires_at"] = "2026-08-11T00:00:00Z"
    record["record_sha256"] = VALIDATOR.authorization_record_hash(record)
    variant = bundle["public_manifest"]["variants"][0]
    variant["authorization_record_sha256"] = record["record_sha256"]
    variant["variant_manifest_sha256"] = VALIDATOR.variant_manifest_hash(variant)
    authorization_registry = authorization_registry_for(bundle)
    bundle["authorization_registry_revision"] = authorization_registry[
        "registry_revision"
    ]
    rebind_bundle(bundle)

    errors = validate_bundle(
        bundle,
        authorization_registry,
        validation_time=datetime.fromisoformat("2026-08-12T00:00:00+00:00"),
    )

    assert any("authorization is expired" in error for error in errors)


def test_bundle_creation_and_review_cannot_be_after_validation_time() -> None:
    bundle = deployment_bundle()
    registry = authorization_registry_for(bundle)

    errors = validate_bundle(
        bundle,
        registry,
        validation_time=datetime.fromisoformat("2026-08-08T00:00:00+00:00"),
    )

    assert "bundle created_at is after the trusted validation time" in errors
    assert any(
        "authorization review is after the trusted validation time" in error
        for error in errors
    )
