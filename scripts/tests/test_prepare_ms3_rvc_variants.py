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
                        "settings": {
                            "block_ms": 500,
                            "context_ms": 2500,
                            "crossfade_ms": 50,
                            "f0_method": "rmvpe",
                            "formant_shift": 0.0,
                            "frame_ms": 20,
                            "index_rate": 0.75,
                            "inference_batch_frames": 25,
                            "pitch_shift": 0,
                            "queue_capacity_frames": 25,
                            "resident_capacity_frames": 50,
                            "rms_mix_rate": 1.0,
                            "sample_rate": 48000,
                            "speaker_id": 0,
                            "threshold_dbfs": -60.0,
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
    settings = profile["runtime"]["configuration"]["settings"]
    assert {key: settings[key] for key in PREPARE.RVC_PARAMETER_KEYS} == {
        "context_ms": 2500,
        "crossfade_ms": 50,
        "index_rate": 0.75,
        "pitch_shift": 0,
        "rms_mix_rate": 1.0,
    }
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


def test_preparation_expands_each_voice_into_distinct_parameter_profiles(
    tmp_path: Path,
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["parameter_presets"] = [
        {
            "preset_id": "standard",
            "preserve_base_identity": True,
            "display_suffix": "standard",
            "settings": {
                "pitch_shift": 0,
                "index_rate": 0.75,
                "rms_mix_rate": 1.0,
                "context_ms": 2500,
                "crossfade_ms": 50,
            },
        },
        {
            "preset_id": "girl-bright",
            "display_suffix": "girl bright",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.6,
                "rms_mix_rate": 0.65,
                "context_ms": 3000,
                "crossfade_ms": 80,
            },
        },
    ]

    draft, *_ = PREPARE.prepare_documents(
        _base_registry(), intake, candidate_root, reviewed_at=REVIEWED_AT
    )

    profiles = draft["gateway_profile_registry"]["profiles"]
    assert [profile["profile_id"] for profile in profiles] == [
        "vc.rvc-v2.provider-bright.v1",
        "vc.rvc-v2.provider-bright-girl-bright.v1",
    ]
    assert profiles[1]["runtime"]["configuration"]["settings"]["pitch_shift"] == 4


def test_quality_preparation_binds_gain_and_gate_as_new_profile_identity(
    tmp_path: Path,
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["parameter_presets"] = [
        {
            "preset_id": "quality-low-index",
            "display_suffix": "quality low index",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.2,
                "rms_mix_rate": 0.25,
                "context_ms": 3500,
                "crossfade_ms": 40,
                "input_gain_db": 9.0,
                "threshold_dbfs": -50.0,
            },
        }
    ]

    draft, *_ = PREPARE.prepare_documents(
        _base_registry(), intake, candidate_root, reviewed_at=REVIEWED_AT
    )

    profile = draft["gateway_profile_registry"]["profiles"][0]
    settings = profile["runtime"]["configuration"]["settings"]
    assert profile["profile_id"] == "vc.rvc-v2.provider-bright-quality-low-index.v1"
    assert settings["input_gain_db"] == 9.0
    assert settings["threshold_dbfs"] == -50.0
    assert settings["crossfade_ms"] == 40


def test_quality_preparation_rejects_candidates_that_only_differ_by_sola_crossfade(
    tmp_path: Path,
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["parameter_presets"] = [
        {
            "preset_id": "quality-crossfade-40",
            "display_suffix": "quality crossfade 40",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.2,
                "rms_mix_rate": 0.25,
                "context_ms": 3500,
                "crossfade_ms": 40,
                "input_gain_db": 9.0,
                "threshold_dbfs": -50.0,
            },
        },
        {
            "preset_id": "quality-crossfade-90",
            "display_suffix": "quality crossfade 90",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.2,
                "rms_mix_rate": 0.25,
                "context_ms": 3500,
                "crossfade_ms": 90,
                "input_gain_db": 9.0,
                "threshold_dbfs": -50.0,
            },
        },
    ]

    with pytest.raises(
        ValueError, match="cannot differ only by effective SOLA crossfade"
    ):
        PREPARE.prepare_documents(
            _base_registry(), intake, candidate_root, reviewed_at=REVIEWED_AT
        )


def test_seeded_preparation_binds_generation_seed_without_quality_gain(
    tmp_path: Path,
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["parameter_presets"] = [
        {
            "preset_id": "clean-bright-seed0",
            "display_suffix": "clean bright seed 0",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.3,
                "rms_mix_rate": 0.5,
                "context_ms": 3500,
                "crossfade_ms": 90,
                "inference_seed": 0,
            },
        }
    ]

    draft, *_ = PREPARE.prepare_documents(
        _base_registry(), intake, candidate_root, reviewed_at=REVIEWED_AT
    )

    profile = draft["gateway_profile_registry"]["profiles"][0]
    settings = profile["runtime"]["configuration"]["settings"]
    assert profile["profile_id"] == (
        "vc.rvc-v2.provider-bright-clean-bright-seed0.v1"
    )
    assert settings["inference_seed"] == 0
    assert "input_gain_db" not in settings


@pytest.mark.parametrize("seed", [-1, 2**63, 1.5, True])
def test_seeded_preparation_rejects_invalid_generation_seed(
    tmp_path: Path, seed: object
) -> None:
    candidate_root, intake = _candidate_fixture(tmp_path)
    intake["parameter_presets"] = [
        {
            "preset_id": "seeded",
            "display_suffix": "seeded",
            "settings": {
                "pitch_shift": 4,
                "index_rate": 0.3,
                "rms_mix_rate": 0.5,
                "context_ms": 3500,
                "crossfade_ms": 90,
                "inference_seed": seed,
            },
        }
    ]

    with pytest.raises(ValueError, match="inference_seed"):
        PREPARE.prepare_documents(
            _base_registry(), intake, candidate_root, reviewed_at=REVIEWED_AT
        )
