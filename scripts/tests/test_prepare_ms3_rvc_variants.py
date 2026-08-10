from __future__ import annotations

import hashlib
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "prepare-ms3-rvc-variants.py"
BUILDER_SCRIPT = Path(__file__).parents[1] / "build-ms3-deployment-bundle.py"


def _load(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = _load(SCRIPT, "prepare_ms3_rvc_variants")
BUILDER = _load(BUILDER_SCRIPT, "build_ms3_bundle_for_rvc_test")
REVIEWED_AT = datetime(2026, 8, 10, 12, tzinfo=UTC)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _base_registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "profiles": [
            {
                "profile_id": "vc.rvc.synthetic-ja.v1",
                "kind": "voice_conversion",
                "readiness": "ready",
                "adapter_api_version": 1,
                "implementation_revision": "rvc-adapter-v1+rvc.source",
                "weight_revision": f"sha256:{'1' * 64}",
                "streaming": True,
                "cancellation": "cooperative",
                "input_sample_rates": [48000],
                "output_sample_rates": [48000],
                "frame_ms": 20,
                "minimum_context_ms": 500,
                "voice_requirement": "pretrained_voice",
                "warmup_policy": "lazy",
                "resource_class": "gpu",
                "license_record": "base technical profile",
                "promotion": {
                    "status": "technical_validation",
                    "pack_id": "rvc-v2",
                    "pack_sha256": f"sha256:{'2' * 64}",
                    "evidence_sha256": f"sha256:{'3' * 64}",
                    "endpoint_sha256": f"sha256:{'4' * 64}",
                },
                "timeouts": {"first_output_ms": 120000, "stall_ms": 15000},
                "runtime": {
                    "adapter": "worker",
                    "configuration": {
                        "worker_module": "workers.adapters.rvc_v2.worker",
                        "artifacts": {
                            "checkpoint_sha256": "1" * 64,
                            "index_sha256": "5" * 64,
                        },
                    },
                    "worker_endpoint": "/private/runtime/bin/python",
                    "max_vram_mb": 2048,
                },
            }
        ],
    }


def _candidate_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    contents = {
        "archive": b"archive",
        "checkpoint": b"checkpoint",
        "index": b"index",
        "readme": b"terms",
    }
    root = tmp_path / "candidate"
    (root / "downloads").mkdir(parents=True)
    (root / "extracted" / "bright").mkdir(parents=True)
    (root / "downloads" / "voice.zip").write_bytes(contents["archive"])
    (root / "extracted" / "bright" / "voice.pth").write_bytes(contents["checkpoint"])
    (root / "extracted" / "bright" / "voice.index").write_bytes(contents["index"])
    (root / "extracted" / "bright" / "Readme.txt").write_bytes(contents["readme"])
    intake = {
        "schema_version": 1,
        "provider_id": "provider",
        "provider_name": "Voice Provider",
        "source_page_url": "https://example.test/voices",
        "terms_url": "https://example.test/terms",
        "required_attribution": "Voice Provider",
        "scope": "personal-evaluation",
        "variants": [
            {
                "variant_id": "rvc-provider-bright",
                "profile_id": "vc.rvc-v2.provider-bright.v1",
                "style_id": "bright",
                "display_name": "RVC Bright",
                "target_presentation": "bright-youthful-feminine",
                "download_url": "https://example.test/voice.zip",
                "archive_name": "voice.zip",
                "archive_sha256": _sha256(contents["archive"]),
                "checkpoint_name": "voice.pth",
                "checkpoint_sha256": _sha256(contents["checkpoint"]),
                "index_name": "voice.index",
                "index_sha256": _sha256(contents["index"]),
                "readme_name": "Readme.txt",
                "readme_sha256": _sha256(contents["readme"]),
            }
        ],
    }
    return root, intake


def test_preparation_binds_profile_authorization_and_private_environment(
    tmp_path: Path,
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)

    draft, registry, materials, environment = PREPARE.prepare_documents(
        _base_registry(),
        intake,
        candidate_root,
        reviewed_at=REVIEWED_AT,
    )
    sealed = BUILDER.seal_bundle(
        draft,
        registry,
        validation_time=REVIEWED_AT,
    )

    profile = sealed["gateway_profile_registry"]["profiles"][0]
    variant = sealed["public_manifest"]["variants"][0]
    assert profile["profile_id"] == "vc.rvc-v2.provider-bright.v1"
    assert (
        profile["weight_revision"].removeprefix("sha256:")
        == intake["variants"][0]["checkpoint_sha256"]
    )
    assert variant["profile_hash"] == PREPARE.VALIDATOR.profile_hash(profile)
    assert (
        variant["authorization_record_sha256"]
        == registry["records"][0]["record_sha256"]
    )
    assert materials["manifests"][0]["source_manifest_sha256"].startswith("sha256:")
    names = PREPARE.rvc_variant_environment_names(profile["profile_id"])
    assert environment[names["checkpoint_path"]].endswith("voice.pth")
    assert environment[names["index_path"]].endswith("voice.index")


def test_preparation_rejects_candidate_digest_drift(tmp_path: Path) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["variants"][0]["checkpoint_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="candidate material digest differs"):
        PREPARE.prepare_documents(
            _base_registry(),
            intake,
            candidate_root,
            reviewed_at=REVIEWED_AT,
        )


def test_private_preparation_is_atomic_and_outside_repository(tmp_path: Path) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    prepared = PREPARE.prepare_documents(
        _base_registry(),
        intake,
        candidate_root,
        reviewed_at=REVIEWED_AT,
    )
    destination = tmp_path / "prepared"

    PREPARE.write_preparation(destination, *prepared)

    assert {path.name for path in destination.iterdir()} == {
        "draft.json",
        "authorization-registry.json",
        "material-manifests.json",
        "identity.env",
    }
    assert oct((destination / "identity.env").stat().st_mode & 0o777) == "0o600"
    with pytest.raises(FileExistsError):
        PREPARE.write_preparation(destination, *prepared)
