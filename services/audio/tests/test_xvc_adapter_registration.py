from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from liveconv_audio.model_adapters import x_vc
from liveconv_audio.profiles import ModelProfile


def _canonical_configuration() -> dict[str, object]:
    return deepcopy(x_vc._CANONICAL_CONFIGURATION)


def _profile(endpoint: Path) -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "profile_id": "vc.x-vc.synthetic-ja.v1",
            "kind": "voice_conversion",
            "readiness": "ready",
            "adapter_api_version": 1,
            "implementation_revision": (
                "x-vc-streaming-adapter-v1+sha256:"
                "d0737a67a05ca39616b312443b83610e891f79207066e8e5da6ee9ea2b304959"
            ),
            "weight_revision": (
                "sha256:"
                "1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687"
            ),
            "streaming": True,
            "cancellation": "immediate",
            "input_sample_rates": [48_000],
            "output_sample_rates": [48_000],
            "frame_ms": 20,
            "minimum_context_ms": 2_400,
            "voice_requirement": "pretrained_voice",
            "warmup_policy": "eager",
            "resource_class": "gpu",
            "license_record": "technical-validation-only",
            "timeouts": {"first_output_ms": 60_000, "stall_ms": 60_000},
            "runtime": {
                "adapter": "worker",
                "configuration": _canonical_configuration(),
                "worker_module": "workers.adapters.x_vc.worker",
                "worker_endpoint": str(endpoint),
                "max_vram_mb": 24_576,
            },
        }
    )


def _install_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    source_root = tmp_path / "source"
    glm_root = tmp_path / "glm"
    eres_root = tmp_path / "eres"
    source_root.mkdir()
    glm_root.mkdir()
    eres_root.mkdir()
    for root, relative_path in x_vc._DERIVED_ARTIFACT_PATHS.values():
        target_root = glm_root if root == "LIVECONV_XVC_GLM_ROOT" else eres_root
        (target_root / relative_path).write_bytes(b"synthetic test artifact")

    endpoint = tmp_path / "python"
    endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    endpoint.chmod(0o700)
    paths = {
        "LIVECONV_XVC_SOURCE_ROOT": source_root,
        "LIVECONV_XVC_CONFIG_PATH": tmp_path / "config.yaml",
        "LIVECONV_XVC_CHECKPOINT_PATH": tmp_path / "checkpoint.pt",
        "LIVECONV_XVC_GLM_ROOT": glm_root,
        "LIVECONV_XVC_ERES_ROOT": eres_root,
        "LIVECONV_XVC_TARGET_REFERENCE_PATH": tmp_path / "target.wav",
        "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH": tmp_path / "authorization.json",
        "LIVECONV_XVC_RUNTIME_LOCK_PATH": tmp_path / "runtime.lock",
        "LIVECONV_XVC_WORKER_WHEEL_PATH": tmp_path / "worker.whl",
        "LIVECONV_XVC_INTERPRETER_PATH": endpoint,
    }
    for name, path in paths.items():
        if path not in {source_root, glm_root, eres_root, endpoint}:
            path.write_bytes(b"synthetic test artifact")
        monkeypatch.setenv(name, str(path))
    for name, value in x_vc._ENVIRONMENT_BINDINGS.items():
        monkeypatch.setenv(name, value)
    return endpoint


def test_xvc_registration_uses_only_the_retained_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    endpoint = _install_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("PYTHONPATH", "/unreviewed/pythonpath")
    monkeypatch.setenv("PYTHONHOME", "/unreviewed/pythonhome")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("LIVECONV_ENABLE_TEST_BACKEND", "1")
    profile = _profile(endpoint)

    x_vc.validate_configuration(profile)
    worker_profile = x_vc.build_worker_profile(profile, "pipeline-1", 2_000)

    assert profile.configuration_hash == (
        "sha256:a0419cee1204d0a67f6e4a2c51f94da1363da386739d2308461bf43fdf6fe25b"
    )
    assert x_vc.delivery_mode(profile) == "live_frame_echo"
    assert x_vc.queue_capacity_frames(profile, 2_000) == 25
    assert worker_profile.command == (
        str(endpoint),
        "-I",
        "-B",
        "-m",
        "workers.adapters.x_vc.worker",
    )
    assert worker_profile.cwd == Path("/tmp")
    assert worker_profile.input_capacity_frames == 25
    assert worker_profile.queue_budget_ms == 500
    assert worker_profile.startup_timeout_ms == 300_000
    assert worker_profile.cancel_timeout_ms == 2_000
    assert worker_profile.close_grace_ms == 5_000
    assert worker_profile.terminate_grace_ms == 1_000
    assert set(worker_profile.environment) == {
        "PATH",
        *x_vc._REQUIRED_ENVIRONMENT,
        *x_vc._DERIVED_ARTIFACT_PATHS,
        *x_vc._FIXED_ENVIRONMENT,
    }
    assert {"PYTHONPATH", "PYTHONHOME", "LIVECONV_ENABLE_TEST_BACKEND"}.isdisjoint(
        worker_profile.environment
    )
    assert {
        name: worker_profile.environment[name] for name in x_vc._FIXED_ENVIRONMENT
    } == x_vc._FIXED_ENVIRONMENT
    assert [
        (artifact.env_var, artifact.sha256) for artifact in worker_profile.artifacts
    ] == [
        (env_var, x_vc._CANONICAL_CONFIGURATION[digest_key])
        for env_var, digest_key in x_vc._ARTIFACT_BINDINGS
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("worker_module", "workers.adapters.unreviewed.worker", "not approved"),
        ("interpreter_sha256", "0" * 64, "configuration differs"),
        ("ema_load", 0, "configuration differs"),
        ("cancellation", "cooperative", "immediate cancellation"),
        ("first_output_ms", 1_000, "timeouts do not match"),
    ),
)
def test_xvc_registration_rejects_identity_and_launch_drift(
    field: str,
    value: object,
    message: str,
    tmp_path: Path,
) -> None:
    endpoint = tmp_path / "python"
    endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    endpoint.chmod(0o700)
    profile = _profile(endpoint)
    if field == "worker_module":
        profile.runtime.worker_module = str(value)
    elif field == "cancellation":
        profile.cancellation = str(value)
    elif field == "first_output_ms":
        profile.timeouts.first_output_ms = int(value)
    else:
        profile.runtime.configuration[field] = value

    with pytest.raises(ValueError, match=message):
        x_vc.validate_configuration(profile)


def test_xvc_registration_rejects_interpreter_binding_injection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    endpoint = _install_environment(monkeypatch, tmp_path)
    unexpected_endpoint = tmp_path / "unexpected-python"
    unexpected_endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    unexpected_endpoint.chmod(0o700)
    monkeypatch.setenv("LIVECONV_XVC_INTERPRETER_PATH", str(unexpected_endpoint))

    with pytest.raises(ValueError, match="worker endpoint does not match interpreter"):
        x_vc.build_worker_profile(_profile(endpoint), "pipeline-1", 500)
