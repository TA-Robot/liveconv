from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from liveconv_audio.model_adapters import openvoice_v2
from liveconv_audio.profiles import ModelProfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MATERIAL_PATH = (
    REPOSITORY_ROOT / "workers" / "adapters" / "openvoice_v2" / "canonical-profile.json"
)


def _canonical_configuration() -> dict[str, float | int | str]:
    return deepcopy(openvoice_v2._CANONICAL_CONFIGURATION)


def _profile(endpoint: Path) -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": "vc.openvoice-v2.synthetic-ja.v1",
            "kind": "voice_conversion",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": openvoice_v2._IMPLEMENTATION_REVISION,
            "weight_revision": openvoice_v2._WEIGHT_REVISION,
            "streaming": False,
            "cancellation": "cooperative",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 60,
            "voice_requirement": "pretrained_voice",
            "warmup_policy": "lazy",
            "resource_class": "gpu",
            "license_record": "technical-validation-only",
            "timeouts": {"first_output_ms": 60_000, "stall_ms": 60_000},
            "runtime": {
                "adapter": "worker",
                "configuration": _canonical_configuration(),
                "worker_module": "workers.adapters.openvoice_v2",
                "worker_endpoint": str(endpoint),
                "max_vram_mb": 8_192,
            },
        }
    )


def _install_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    runtime_prefix = tmp_path / "runtime"
    runtime_prefix.mkdir()
    artifact_paths = {
        "LIVECONV_OPENVOICE_V2_SOURCE_ROOT": source_root,
        "LIVECONV_OPENVOICE_V2_CONFIG_PATH": tmp_path / "config.json",
        "LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH": tmp_path / "checkpoint.pth",
        "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH": tmp_path / "target.wav",
        "LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX": runtime_prefix,
        "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH": tmp_path / "worker.whl",
    }
    for name, path in artifact_paths.items():
        if path not in {source_root, runtime_prefix}:
            path.write_bytes(b"synthetic test artifact")
        monkeypatch.setenv(name, str(path))

    for name, value in openvoice_v2._ENVIRONMENT_BINDINGS.items():
        monkeypatch.setenv(name, value)


def test_openvoice_registration_binds_only_canonical_profile_material() -> None:
    material = json.loads(MATERIAL_PATH.read_text(encoding="utf-8"))

    assert openvoice_v2.WORKER_MODULE == material["trusted_worker"]["entrypoint_module"]
    assert material["trusted_worker"]["entrypoint_args"] == [
        "-I",
        "-m",
        openvoice_v2.WORKER_MODULE,
    ]
    assert (
        openvoice_v2._CANONICAL_CONFIGURATION
        == material["canonical_engine_configuration"]
    )
    assert openvoice_v2._CONFIGURATION_HASH == material["configuration_hash"]
    assert openvoice_v2._WEIGHT_REVISION == material["revisions"]["weight_revision"]
    assert (
        openvoice_v2._IMPLEMENTATION_REVISION
        == material["retained_repaired_worker"]["implementation_revision"]
    )
    assert openvoice_v2._REQUIRED_ENVIRONMENT == tuple(
        material["private_environment"]["required_names"]
    )
    assert set(openvoice_v2._OPTIONAL_ENVIRONMENT_BINDINGS) == set(
        material["private_environment"]["optional_names"]
    )
    assert material["pack"] == {
        "pack_id": "openvoice-v2",
        "status": "research",
        "ready_for_runtime": False,
        "promotion_status": "technical_validation",
        "promotion_evidence_sha256": openvoice_v2._PROMOTION_EVIDENCE_SHA256,
    }
    assert material["delivery"] == {
        "mode": "end_buffered",
        "streaming": False,
        "frame_ms": 20,
        "minimum_input_frames": 3,
        "maximum_input_frames": 25,
        "minimum_context_ms": 60,
        "maximum_context_ms": 500,
        "cancellation": "cooperative",
    }


@pytest.fixture
def endpoint(tmp_path: Path) -> Path:
    path = tmp_path / "runtime-endpoint"
    path.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    path.chmod(0o700)
    return path


def test_openvoice_registration_uses_only_the_retained_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_UNREVIEWED_WORKER_ENVIRONMENT", "ignored")
    profile = _profile(endpoint)

    openvoice_v2.validate_configuration(profile)
    worker_profile = openvoice_v2.build_worker_profile(
        profile, "pipeline-1", queue_budget_ms=2_000
    )

    assert profile.configuration_hash == openvoice_v2._CONFIGURATION_HASH
    assert openvoice_v2.delivery_mode(profile) == "end_buffered"
    assert openvoice_v2.queue_capacity_frames(profile, 2_000) == 25
    assert worker_profile.command == (
        str(endpoint),
        "-I",
        "-m",
        "workers.adapters.openvoice_v2",
    )
    assert worker_profile.cwd == Path("/tmp")
    assert worker_profile.input_capacity_frames == 25
    assert worker_profile.queue_budget_ms == 500
    assert worker_profile.implementation_revision == profile.implementation_revision
    assert set(worker_profile.environment) == {
        *openvoice_v2._REQUIRED_ENVIRONMENT,
        *openvoice_v2._OPTIONAL_ENVIRONMENT_BINDINGS,
    }
    assert "PYTHONPATH" not in worker_profile.environment
    assert "PYTHONHOME" not in worker_profile.environment
    assert "LIVECONV_UNREVIEWED_WORKER_ENVIRONMENT" not in worker_profile.environment
    assert [
        (artifact.env_var, artifact.sha256) for artifact in worker_profile.artifacts
    ] == [
        (
            "LIVECONV_OPENVOICE_V2_CONFIG_PATH",
            openvoice_v2._CANONICAL_CONFIGURATION["config_sha256"],
        ),
        (
            "LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH",
            openvoice_v2._CANONICAL_CONFIGURATION["checkpoint_sha256"],
        ),
        (
            "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH",
            openvoice_v2._CANONICAL_CONFIGURATION["target_reference_sha256"],
        ),
        (
            "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH",
            openvoice_v2._CANONICAL_CONFIGURATION["worker_wheel_sha256"],
        ),
    ]


def test_openvoice_registration_rejects_missing_private_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    monkeypatch.delenv("LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH")

    with pytest.raises(
        ValueError,
        match=(
            "required worker environment is missing: "
            "LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH"
        ),
    ):
        openvoice_v2.build_worker_profile(_profile(endpoint), "pipeline-1", 500)


def test_openvoice_registration_rejects_environment_digest_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256", "0" * 64)

    with pytest.raises(
        ValueError,
        match="IMPLEMENTATION_SHA256 does not match retained identity",
    ):
        openvoice_v2.build_worker_profile(_profile(endpoint), "pipeline-1", 500)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("checkpoint_sha256", "0" * 64, "configuration differs"),
        (
            "implementation_revision",
            "openvoice-v2-offline-adapter-v4+sha256:" + "0" * 64,
            "implementation revision",
        ),
        ("weight_revision", "sha256:" + "0" * 64, "weight revision"),
        ("streaming", True, "must remain non-live"),
        ("minimum_context_ms", 80, "exactly 60 ms"),
    ),
)
def test_openvoice_registration_rejects_identity_and_delivery_drift(
    field: str,
    value: object,
    message: str,
    endpoint: Path,
) -> None:
    profile = _profile(endpoint)
    if field == "checkpoint_sha256":
        profile.runtime.configuration[field] = value
    else:
        setattr(profile, field, value)

    with pytest.raises(ValueError, match=message):
        openvoice_v2.validate_configuration(profile)


def test_openvoice_registration_exposes_the_canonical_rebind_state() -> None:
    material = json.loads(MATERIAL_PATH.read_text(encoding="utf-8"))
    trusted_worker = material["trusted_worker"]

    assert (
        openvoice_v2.CURRENT_SOURCE_IMPLEMENTATION_SHA256
        == trusted_worker["current_source_implementation_sha256"]
    )
    assert (
        openvoice_v2.CURRENT_SOURCE_RUNTIME_REBUILD_REQUIRED
        is trusted_worker["current_source_runtime_rebuild_required"]
    )
