from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from workers.adapters.rvc_v2 import backend
from workers.adapters.rvc_v2.backend import AdapterRuntimeBinding, RvcConfiguration

ADAPTER_ROOT = Path(__file__).resolve().parents[1]
MATERIAL_PATH = ADAPTER_ROOT / "ms2-profile-material.json"


def load_material() -> dict[str, object]:
    value = json.loads(MATERIAL_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def configuration_from_material(
    material: dict[str, object], tmp_path: Path
) -> RvcConfiguration:
    canonical = material["canonical_configuration"]
    assert isinstance(canonical, dict)
    artifacts = canonical["artifacts"]
    settings = canonical["settings"]
    assert isinstance(artifacts, dict)
    assert isinstance(settings, dict)
    return RvcConfiguration(
        source_root=tmp_path / "source",
        checkpoint_path=tmp_path / "checkpoint.pth",
        source_revision=str(canonical["source_revision"]),
        checkpoint_sha256=str(artifacts["checkpoint_sha256"]),
        adapter_runtime=AdapterRuntimeBinding(
            worker_wheel_path=tmp_path / "worker.whl",
            worker_wheel_sha256=str(artifacts["worker_wheel_sha256"]),
            worker_wheel_record_sha256=str(artifacts["worker_wheel_record_sha256"]),
            worker_module_sha256=str(artifacts["worker_module_sha256"]),
            backend_module_sha256=str(artifacts["backend_module_sha256"]),
            network_isolation_module_sha256=str(
                artifacts["network_isolation_module_sha256"]
            ),
            requirements_lock_sha256=str(artifacts["requirements_lock_sha256"]),
        ),
        index_path=tmp_path / "index.bin",
        index_sha256=str(artifacts["index_sha256"]),
        speaker_id=int(settings["speaker_id"]),
        pitch_shift=int(settings["pitch_shift"]),
        f0_method=str(settings["f0_method"]),
        index_rate=float(settings["index_rate"]),
        rms_mix_rate=float(settings["rms_mix_rate"]),
        sample_rate=int(settings["sample_rate"]),
        block_ms=int(settings["block_ms"]),
        crossfade_ms=int(settings["crossfade_ms"]),
        context_ms=int(settings["context_ms"]),
    )


def test_material_has_retained_rvc_v14_identity_and_deployment_handoff() -> None:
    material = load_material()
    profile = material["deployment_profile"]
    canonical = material["canonical_configuration"]
    launch = material["trusted_launch"]
    capacity = material["capacity"]
    assert isinstance(profile, dict)
    assert isinstance(canonical, dict)
    assert isinstance(launch, dict)
    assert isinstance(capacity, dict)

    assert canonical_hash(canonical) == material["configuration_hash"]
    assert profile["implementation_revision"] == (
        "liveconv-rvc-v2-worker-v1.4+rvc.81eed5e8f68b6bed1789f682fe78cdd324495afc"
    )
    assert profile["weight_revision"] == (
        "sha256:46b60b686a9f540aabc3788ac405dbdfb66e370c56751e592b496f8e6967789c"
    )
    assert launch == {
        "command": {
            "executable_from_profile_field": "runtime.worker_endpoint",
            "arguments": ["-m", "workers.adapters.rvc_v2.worker"],
        },
        "cwd": "/tmp",
        "pythonpath": "unset",
    }
    assert material["delivery_mode"] == "live_frame_echo"
    assert capacity == {
        "supervisor_queue_capacity_frames": 25,
        "inference_batch_frames": 25,
        "resident_capacity_frames": 50,
    }


def test_current_backend_reproduces_material_identity_without_gpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    material = load_material()
    canonical = material["canonical_configuration"]
    assert isinstance(canonical, dict)
    artifacts = canonical["artifacts"]
    assert isinstance(artifacts, dict)
    configuration = configuration_from_material(material, tmp_path)

    expected_by_name = {
        "config.json": artifacts["hubert_config_sha256"],
        "preprocessor_config.json": artifacts["hubert_preprocessor_sha256"],
        "pytorch_model.bin": artifacts["hubert_weights_sha256"],
        "rmvpe.pt": artifacts["rmvpe_sha256"],
    }

    def retained_digest(path: Path) -> str:
        return str(expected_by_name[path.name])

    monkeypatch.setattr(backend, "sha256_file", retained_digest)
    assert configuration.identity_material() == canonical
    assert configuration.configuration_hash == material["configuration_hash"]

    changed = json.loads(json.dumps(canonical))
    assert isinstance(changed, dict)
    changed_settings = changed["settings"]
    assert isinstance(changed_settings, dict)
    changed_settings["queue_capacity_frames"] = 24
    assert canonical_hash(changed) != material["configuration_hash"]


def test_material_keeps_the_nonselectable_failed_quality_record() -> None:
    material = load_material()
    status = material["source_status"]
    assert isinstance(status, dict)
    assert status["promotion_status"] == "technical_validation"
    assert status["selection_status"] == "technical-validation-only-not-selectable"
    quality_lanes = status["quality_lanes"]
    assert isinstance(quality_lanes, dict)
    assert quality_lanes["content_preservation"] == "failed"
    assert quality_lanes["speaker_change"] == "unassessed"
