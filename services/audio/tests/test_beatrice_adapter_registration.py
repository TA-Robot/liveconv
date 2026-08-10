from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from liveconv_audio.model_adapters import beatrice_2
from liveconv_audio.profiles import ModelProfile


def _canonical_configuration() -> dict[str, int | str]:
    return deepcopy(beatrice_2._CANONICAL_CONFIGURATION)


def _profile(endpoint: Path) -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": "vc.beatrice.synthetic-ja.v1",
            "kind": "voice_conversion",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": "f34836de014b86956096878aecb8d3b17feaaa0b",
            "weight_revision": (
                "sha256:14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a"
            ),
            "streaming": True,
            "cancellation": "cooperative",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 60,
            "voice_requirement": "pretrained_voice",
            "warmup_policy": "lazy",
            "resource_class": "gpu",
            "license_record": "technical-validation-only",
            "timeouts": {"first_output_ms": 30_000, "stall_ms": 5_000},
            "runtime": {
                "adapter": "worker",
                "configuration": _canonical_configuration(),
                "worker_module": "workers.adapters.beatrice_2.worker",
                "worker_endpoint": str(endpoint),
                "max_vram_mb": 2_048,
            },
        }
    )


def _install_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    artifact_paths = {
        "LIVECONV_BEATRICE_SOURCE_ROOT": source_root,
        "LIVECONV_BEATRICE_SOURCE_MODULE": tmp_path / "source-module.py",
        "LIVECONV_BEATRICE_PHONE_CHECKPOINT": tmp_path / "phone.pt",
        "LIVECONV_BEATRICE_PITCH_CHECKPOINT": tmp_path / "pitch.pt",
        "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT": tmp_path / "converter.pt",
        "LIVECONV_BEATRICE_WORKER_WHEEL": tmp_path / "worker.whl",
    }
    for name, path in artifact_paths.items():
        if path != source_root:
            path.write_bytes(b"synthetic test artifact")
        monkeypatch.setenv(name, str(path))

    for name, value in beatrice_2._ENVIRONMENT_BINDINGS.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def endpoint(tmp_path: Path) -> Path:
    path = tmp_path / "python"
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def test_beatrice_registration_uses_only_the_retained_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    profile = _profile(endpoint)

    beatrice_2.validate_configuration(profile)
    worker_profile = beatrice_2.build_worker_profile(
        profile, "pipeline-1", queue_budget_ms=2_000
    )

    assert profile.configuration_hash == (
        "sha256:f22e4937c3c7c217788c352ef1b729c28af8f227db45f3b18f7044c569fde40c"
    )
    assert beatrice_2.delivery_mode(profile) == "live_frame_echo"
    assert beatrice_2.queue_capacity_frames(profile, 2_000) == 25
    assert worker_profile.command == (
        str(endpoint),
        "-I",
        "-B",
        "-m",
        "workers.adapters.beatrice_2.worker",
    )
    assert worker_profile.cwd == Path("/tmp")
    assert worker_profile.input_capacity_frames == 25
    assert worker_profile.queue_budget_ms == 500
    assert set(worker_profile.environment) == set(beatrice_2._REQUIRED_ENVIRONMENT)
    assert "PYTHONPATH" not in worker_profile.environment
    assert "PYTHONHOME" not in worker_profile.environment
    actual_artifacts = [
        (artifact.env_var, artifact.sha256) for artifact in worker_profile.artifacts
    ]
    assert actual_artifacts == [
        (
            "LIVECONV_BEATRICE_SOURCE_MODULE",
            "c191a4fabdb63730b749fc2fbbe27384223fc27862a06a0d9db713bdee688e83",
        ),
        (
            "LIVECONV_BEATRICE_PHONE_CHECKPOINT",
            "46e2d609825ace2158c83672cfc9cc1dcb3c2b7c8d294ee911fcb6840a592bae",
        ),
        (
            "LIVECONV_BEATRICE_PITCH_CHECKPOINT",
            "174e5411009e0e4f6ee8a8c97c4cd2f646791eae1b9aa2b425acb797e0353ef4",
        ),
        (
            "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT",
            "14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a",
        ),
        (
            "LIVECONV_BEATRICE_WORKER_WHEEL",
            "cf9592ee3461ed3601f84472a6219ee3dec017f25d4ed31a55e93d245fd0b7bc",
        ),
    ]


def test_beatrice_registration_rejects_missing_private_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    monkeypatch.delenv("LIVECONV_BEATRICE_CONVERTER_CHECKPOINT")

    with pytest.raises(
        ValueError,
        match=(
            "required worker environment is missing: "
            "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT"
        ),
    ):
        beatrice_2.build_worker_profile(_profile(endpoint), "pipeline-1", 500)


def test_beatrice_registration_rejects_environment_digest_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: Path,
) -> None:
    _install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("LIVECONV_BEATRICE_PITCH_SHA256", "0" * 64)

    with pytest.raises(
        ValueError,
        match="PITCH_SHA256 does not match retained identity",
    ):
        beatrice_2.build_worker_profile(_profile(endpoint), "pipeline-1", 500)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("converter_sha256", "0" * 64, "configuration differs"),
        ("implementation_revision", "0" * 40, "implementation revision"),
        ("weight_revision", "sha256:" + "0" * 64, "weight revision"),
    ),
)
def test_beatrice_registration_rejects_identity_mismatch(
    field: str,
    value: str,
    message: str,
    endpoint: Path,
) -> None:
    profile = _profile(endpoint)
    if field == "converter_sha256":
        profile.runtime.configuration[field] = value
    else:
        setattr(profile, field, value)

    with pytest.raises(ValueError, match=message):
        beatrice_2.validate_configuration(profile)
