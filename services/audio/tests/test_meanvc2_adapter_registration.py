from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from liveconv_audio.model_adapters import meanvc2
from liveconv_audio.profiles import ModelProfile


def profile(endpoint: Path, profile_id: str = meanvc2.PROFILE_ID) -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": profile_id,
            "kind": "voice_conversion",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": meanvc2.IMPLEMENTATION_REVISION,
            "weight_revision": meanvc2.WEIGHT_REVISION,
            "streaming": True,
            "cancellation": "immediate",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 160,
            "voice_requirement": "pretrained_voice",
            "warmup_policy": "eager",
            "resource_class": "gpu",
            "license_record": "technical-validation-only",
            "timeouts": {"first_output_ms": 120_000, "stall_ms": 30_000},
            "runtime": {
                "adapter": "worker",
                "configuration": deepcopy(meanvc2._configuration(profile_id)),
                "worker_module": meanvc2.WORKER_MODULE,
                "worker_endpoint": str(endpoint),
                "max_vram_mb": 16_384,
            },
        }
    )


def install_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    endpoint = tmp_path / "python"
    endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    endpoint.chmod(0o700)
    path_names = [
        name for name in meanvc2._REQUIRED_ENVIRONMENT if name.endswith("_PATH")
    ]
    for name in path_names:
        path = (
            endpoint if name == "LIVECONV_MEANVC2_INTERPRETER_PATH" else tmp_path / name
        )
        if path != endpoint:
            path.write_bytes(b"test artifact")
        monkeypatch.setenv(name, str(path))
    source_root = tmp_path / "source"
    source_root.mkdir()
    monkeypatch.setenv("LIVECONV_MEANVC2_SOURCE_ROOT", str(source_root))
    for name, value in meanvc2._ENVIRONMENT_BINDINGS.items():
        monkeypatch.setenv(name, str(value))
    return endpoint


def test_meanvc2_registration_builds_only_the_static_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    endpoint = install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("PYTHONPATH", "/unreviewed")
    candidate = profile(endpoint)

    worker = meanvc2.build_worker_profile(candidate, "pipeline-meanvc2", 2_000)

    assert candidate.configuration_hash == meanvc2.CONFIGURATION_HASH
    assert worker.command == (
        str(endpoint),
        "-I",
        "-B",
        "-m",
        "workers.adapters.meanvc2",
    )
    assert worker.cwd == Path("/tmp")
    assert worker.input_capacity_frames == 25
    assert worker.environment["HF_HUB_OFFLINE"] == "1"
    assert "PYTHONPATH" not in worker.environment
    assert len(worker.artifacts) == len(meanvc2._ARTIFACT_BINDINGS)
    assert meanvc2.delivery_mode(candidate) == "live_frame_echo"


def test_meanvc2_registration_binds_the_long_reference_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    endpoint = install_environment(monkeypatch, tmp_path)
    profile_id = "vc.meanvc2.amitaro-runrun-q34.v1"
    reference_digest, authorization_digest = meanvc2._APPROVED_TARGETS[profile_id]
    reference_path = tmp_path / "runrun-q34.wav"
    authorization_path = tmp_path / "runrun-q34.json"
    reference_path.write_bytes(b"long reference")
    authorization_path.write_text("{}\n", encoding="utf-8")
    (
        reference_path_name,
        reference_sha_name,
        authorization_path_name,
        authorization_sha_name,
    ) = meanvc2.target_environment_names(profile_id)
    monkeypatch.setenv(reference_path_name, str(reference_path))
    monkeypatch.setenv(reference_sha_name, reference_digest)
    monkeypatch.setenv(authorization_path_name, str(authorization_path))
    monkeypatch.setenv(authorization_sha_name, authorization_digest)

    worker = meanvc2.build_worker_profile(
        profile(endpoint, profile_id), "pipeline-q34", 500
    )
    artifact_digests = {
        artifact.env_var: artifact.sha256 for artifact in worker.artifacts
    }

    assert worker.environment["LIVECONV_MEANVC2_TARGET_REFERENCE_PATH"] == str(
        reference_path
    )
    assert (
        artifact_digests["LIVECONV_MEANVC2_TARGET_REFERENCE_PATH"] == reference_digest
    )
    assert (
        artifact_digests["LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH"]
        == authorization_digest
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("profile", "profile ID"),
        ("module", "worker is not approved"),
        ("configuration", "configuration differs"),
        ("weight", "weights differ"),
        ("streaming", "streaming VC"),
    ],
)
def test_meanvc2_registration_rejects_identity_drift(
    mutation: str, message: str, tmp_path: Path
) -> None:
    endpoint = tmp_path / "python"
    endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    endpoint.chmod(0o700)
    candidate = profile(endpoint)
    if mutation == "profile":
        candidate.profile_id = "vc.meanvc2.operator.v1"
    elif mutation == "module":
        candidate.runtime.worker_module = "workers.adapters.operator"
    elif mutation == "configuration":
        candidate.runtime.configuration["inference_frames"] = 4
    elif mutation == "weight":
        candidate.weight_revision = "sha256:" + "0" * 64
    else:
        candidate.streaming = False
    with pytest.raises(ValueError, match=message):
        meanvc2.validate_configuration(candidate)


def test_meanvc2_registration_rejects_environment_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    endpoint = install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_MEANVC2_ASR_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="ASR_SHA256 differs"):
        meanvc2.build_worker_profile(profile(endpoint), "pipeline-meanvc2", 500)
