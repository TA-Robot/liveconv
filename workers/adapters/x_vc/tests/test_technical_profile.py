from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from workers.adapters.x_vc import backend
from workers.adapters.x_vc.worker import CAPACITY_FRAMES

ROOT = Path(__file__).resolve().parents[4]
MATERIAL_PATH = ROOT / "workers/adapters/x_vc/technical-profile.json"
PACK_PATH = ROOT / "workers/packs/x-vc.json"
SMOKE_REPORT_PATH = ROOT / "artifacts/x-vc/evidence/worker-supervisor-smoke-v2.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _configuration_from_material(value: dict[str, Any]) -> backend.XvcConfiguration:
    return backend.XvcConfiguration(
        source_root=Path("source-root"),
        source_revision=value["source_revision"],
        config_path=Path("config.yaml"),
        config_sha256=value["config_sha256"],
        checkpoint_path=Path("checkpoint.pt"),
        checkpoint_sha256=value["checkpoint_sha256"],
        glm_root=Path("glm-root"),
        glm_config_sha256=value["glm_config_sha256"],
        glm_preprocessor_sha256=value["glm_preprocessor_sha256"],
        glm_model_sha256=value["glm_model_sha256"],
        eres_root=Path("eres-root"),
        eres_config_sha256=value["eres_config_sha256"],
        eres_model_sha256=value["eres_model_sha256"],
        target_reference_path=Path("target.wav"),
        target_reference_sha256=value["target_reference_sha256"],
        target_authorization_path=Path("target-authorization.json"),
        target_authorization_sha256=value["target_authorization_sha256"],
        adapter_source_sha256=value["adapter_source_sha256"],
        runtime_lock_path=Path("requirements-runtime.lock"),
        runtime_lock_sha256=value["runtime_lock_sha256"],
        worker_wheel_path=Path("worker.whl"),
        worker_wheel_sha256=value["worker_wheel_sha256"],
        interpreter_path=Path("python"),
        interpreter_sha256=value["interpreter_sha256"],
        python_implementation=value["python_implementation"],
        python_version=value["python_version"],
        worker_package_version=value["worker_package_version"],
        device=value["device"],
    )


def test_technical_profile_recomputes_the_current_backend_identity() -> None:
    material = _load_json(MATERIAL_PATH)
    profile = material["profile"]
    runtime = material["runtime"]
    configuration = runtime["configuration"]
    smoke = material["evidence"]["worker_supervisor_smoke"]

    assert profile["implementation_revision"] == (
        f"{backend.IMPLEMENTATION_REVISION}+sha256:{backend.sha256_adapter_source()}"
    )
    assert configuration["adapter_revision"] == backend.IMPLEMENTATION_REVISION
    assert configuration["adapter_source_sha256"] == backend.sha256_adapter_source()
    assert configuration["checkpoint_sha256"] == backend.CHECKPOINT_SHA256
    assert configuration["config_sha256"] == backend.CONFIG_SHA256
    assert configuration["glm_config_sha256"] == backend.GLM_CONFIG_SHA256
    assert configuration["glm_preprocessor_sha256"] == backend.GLM_PREPROCESSOR_SHA256
    assert configuration["glm_model_sha256"] == backend.GLM_MODEL_SHA256
    assert configuration["eres_config_sha256"] == backend.ERES_CONFIG_SHA256
    assert configuration["eres_model_sha256"] == backend.ERES_MODEL_SHA256
    assert configuration["source_revision"] == backend.SOURCE_REVISION
    assert configuration["input_sample_rate"] == backend.INPUT_SAMPLE_RATE
    assert profile["minimum_context_ms"] == backend.WINDOW_MS
    assert configuration["window_ms"] == backend.WINDOW_MS
    assert configuration["current_ms"] == backend.CURRENT_MS
    assert configuration["future_ms"] == backend.FUTURE_MS
    assert configuration["smooth_ms"] == backend.SMOOTH_MS
    assert configuration["latent_hop_length"] == backend.LATENT_HOP_LENGTH
    assert (
        configuration["source_preprocessing_revision"]
        == backend.SOURCE_PREPROCESSING_REVISION
    )
    assert (
        configuration["output_resampler_revision"] == backend.OUTPUT_RESAMPLER_REVISION
    )

    derived = _configuration_from_material(configuration)
    assert derived.configuration_hash == smoke["configuration_hash"]
    assert derived.implementation_revision == profile["implementation_revision"]

    binding_digests = {
        item["env_var"]: item["sha256"] for item in runtime["artifact_bindings"]
    }
    assert binding_digests == {
        "LIVECONV_XVC_CONFIG_PATH": configuration["config_sha256"],
        "LIVECONV_XVC_CHECKPOINT_PATH": configuration["checkpoint_sha256"],
        "LIVECONV_XVC_GLM_CONFIG_PATH": configuration["glm_config_sha256"],
        "LIVECONV_XVC_GLM_PREPROCESSOR_PATH": configuration["glm_preprocessor_sha256"],
        "LIVECONV_XVC_GLM_MODEL_PATH": configuration["glm_model_sha256"],
        "LIVECONV_XVC_ERES_CONFIG_PATH": configuration["eres_config_sha256"],
        "LIVECONV_XVC_ERES_MODEL_PATH": configuration["eres_model_sha256"],
        "LIVECONV_XVC_TARGET_REFERENCE_PATH": configuration["target_reference_sha256"],
        "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH": configuration[
            "target_authorization_sha256"
        ],
        "LIVECONV_XVC_RUNTIME_LOCK_PATH": configuration["runtime_lock_sha256"],
        "LIVECONV_XVC_WORKER_WHEEL_PATH": configuration["worker_wheel_sha256"],
        "LIVECONV_XVC_INTERPRETER_PATH": configuration["interpreter_sha256"],
    }


def test_retained_smoke_evidence_and_pack_are_bound_to_the_profile() -> None:
    material = _load_json(MATERIAL_PATH)
    smoke = material["evidence"]["worker_supervisor_smoke"]
    report = _load_json(SMOKE_REPORT_PATH)
    pack = _load_json(PACK_PATH)
    configuration = material["runtime"]["configuration"]

    assert hashlib.sha256(SMOKE_REPORT_PATH.read_bytes()).hexdigest() == smoke[
        "sha256"
    ].removeprefix("sha256:")
    assert report["schema_version"] == smoke["schema_version"]
    assert report["status"] == smoke["status"]
    assert report["quality_status"] == smoke["quality_status"]
    assert report["identity"] == {
        "adapter_source_sha256": configuration["adapter_source_sha256"],
        "configuration_hash": smoke["configuration_hash"],
        "implementation_revision": material["profile"]["implementation_revision"],
        "interpreter_sha256": configuration["interpreter_sha256"],
        "runtime_lock_sha256": configuration["runtime_lock_sha256"],
        "target_authorization_sha256": configuration["target_authorization_sha256"],
        "weight_revision": material["profile"]["weight_revision"],
        "worker_wheel_sha256": configuration["worker_wheel_sha256"],
    }
    assert pack["status"] == "research"
    assert pack["ready_for_runtime"] is False
    assert pack["promotion_evidence"] == {
        "status": "technical_validation",
        "evidence_sha256": smoke["sha256"],
    }
    assert material["profile"]["promotion"] == {
        "status": "technical_validation",
        "pack_id": "x-vc",
        "pack_sha256": "sha256:" + hashlib.sha256(PACK_PATH.read_bytes()).hexdigest(),
        "evidence_sha256": smoke["sha256"],
        "endpoint_sha256": "sha256:" + configuration["interpreter_sha256"],
    }
    assert material["profile"]["quality_status"] == "fail-nonselectable"
    assert material["profile"]["selectable_default"] is False


def test_shared_synthetic_source_and_target_match_manifest_and_evidence() -> None:
    material = _load_json(MATERIAL_PATH)
    fixtures = material["evidence"]["synthetic_fixtures"]
    manifest_path = ROOT / fixtures["manifest_relative_path"]
    manifest = _load_json(manifest_path)
    source = fixtures["source"]
    target = fixtures["target"]
    source_entry = next(
        item for item in manifest["source"] if item["path"] == "source/LV001-JA-001.wav"
    )
    target_entry = manifest["target_reference"]

    for fixture, entry in ((source, source_entry), (target, target_entry)):
        path = ROOT / fixture["relative_path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["sha256"]
        assert entry["sha256"] == fixture["sha256"]

    report = _load_json(SMOKE_REPORT_PATH)
    assert report["source_fixture_sha256"] == source["sha256"]
    assert report["authorization"]["target_reference_sha256"] == target["sha256"]


def test_profile_material_has_only_relative_artifact_references() -> None:
    material = _load_json(MATERIAL_PATH)
    encoded = MATERIAL_PATH.read_text(encoding="utf-8")
    runtime = material["runtime"]

    assert "/workspace/" not in encoded
    assert "/authorized/" not in encoded
    assert runtime["worker_module"] == "workers.adapters.x_vc.worker"
    assert runtime["launch"] == {
        "interpreter_env_var": "LIVECONV_XVC_INTERPRETER_PATH",
        "arguments": ["-I", "-B", "-m", "workers.adapters.x_vc.worker"],
        "cwd": "/tmp",
        "delivery_mode": "live_frame_echo",
        "queue_capacity_frames": 25,
        "queue_budget_ms": 500,
        "startup_timeout_ms": 300000,
        "cancel_timeout_ms": 2000,
        "close_grace_ms": 5000,
        "terminate_grace_ms": 1000,
    }
    assert runtime["launch"]["queue_capacity_frames"] == CAPACITY_FRAMES
    assert runtime["launch"]["queue_budget_ms"] == CAPACITY_FRAMES * backend.FRAME_MS
    assert all(
        binding["env_var"].endswith("_PATH") for binding in runtime["artifact_bindings"]
    )
