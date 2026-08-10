from __future__ import annotations

import json
from pathlib import Path

from workers.adapters.beatrice_2 import backend
from workers.adapters.beatrice_2.worker import _CAPACITY_FRAMES

ADAPTER_ROOT = Path(__file__).resolve().parents[1]
WORKERS_ROOT = ADAPTER_ROOT.parents[1]


def _material() -> dict[str, object]:
    return json.loads(
        (ADAPTER_ROOT / "profile-material.json").read_text(encoding="utf-8")
    )


def _configuration(material: dict[str, object]) -> backend.BeatriceConfiguration:
    worker = material["worker"]
    assert isinstance(worker, dict)
    payload = worker["configuration_payload"]
    assert isinstance(payload, dict)
    artifacts = material["artifact_digests"]
    assert isinstance(artifacts, dict)
    return backend.BeatriceConfiguration(
        source_root=Path("private-source-root"),
        source_revision=str(payload["source_revision"]),
        source_sha256=str(payload["source_sha256"]),
        source_tree_sha256=str(payload["source_tree_sha256"]),
        phone_checkpoint=Path("private-phone-checkpoint"),
        phone_sha256=str(payload["phone_sha256"]),
        pitch_checkpoint=Path("private-pitch-checkpoint"),
        pitch_sha256=str(payload["pitch_sha256"]),
        converter_checkpoint=Path("private-converter-checkpoint"),
        converter_sha256=str(payload["converter_sha256"]),
        runtime_lock_sha256=str(payload["runtime_lock_sha256"]),
        worker_runtime=backend.WorkerRuntimeBinding(
            worker_wheel_path=Path("private-worker-wheel"),
            worker_wheel_sha256=str(payload["worker_wheel_sha256"]),
            wheel_record_sha256=str(payload["wheel_record_sha256"]),
            installed_record_sha256=str(payload["installed_record_sha256"]),
            distribution_manifest_sha256=str(payload["distribution_manifest_sha256"]),
            executed_project_modules_sha256=str(
                payload["executed_project_modules_sha256"]
            ),
            runtime_codec_sha256=str(payload["runtime_codec_sha256"]),
            requirements_lock_sha256=str(payload["runtime_lock_sha256"]),
            installed_distribution_inventory_sha256=str(
                payload["installed_distribution_inventory_sha256"]
            ),
            distribution_version="0.1.0",
        ),
        target_speaker_id=int(payload["target_speaker_id"]),
        sample_rate=int(payload["sample_rate"]),
        batch_ms=int(payload["batch_ms"]),
        device=str(payload["device"]),
    )


def test_profile_material_matches_backend_identity_construction() -> None:
    material = _material()
    worker = material["worker"]
    assert isinstance(worker, dict)
    payload = worker["configuration_payload"]
    assert isinstance(payload, dict)
    configuration = _configuration(material)

    assert material["schema"] == "liveconv-beatrice-2-profile-material-v1"
    assert material["technical_status"] == "technical_nonselectable"
    assert material["ready_for_runtime"] is False
    assert material["selectable"] is False
    assert worker["module"] == "workers.adapters.beatrice_2.worker"
    assert worker["implementation_revision"] == configuration.source_revision
    assert worker["weight_revision"] == f"sha256:{configuration.converter_sha256}"
    assert payload == configuration.canonical_payload
    assert worker["configuration_hash"] == configuration.configuration_hash
    assert worker["configuration_hash"] == (
        "sha256:f22e4937c3c7c217788c352ef1b729c28af8f227db45f3b18f7044c569fde40c"
    )


def test_profile_material_carries_worker_contract_and_private_name_map() -> None:
    material = _material()
    worker = material["worker"]
    streaming = material["streaming"]
    artifacts = material["artifact_digests"]
    environment = material["private_environment_name_map"]
    assert isinstance(worker, dict)
    assert isinstance(streaming, dict)
    assert isinstance(artifacts, dict)
    assert isinstance(environment, dict)

    assert streaming == {
        "context_mode": "frame_streaming",
        "gateway_delivery_mode": "live_frame_echo",
        "input_sample_rate_hz": 48_000,
        "output_sample_rate_hz": 48_000,
        "frame_ms": backend.FRAME_MS,
        "batch_ms": 500,
        "minimum_inference_ms": backend.MINIMUM_INFERENCE_MS,
        "capacity_frames": _CAPACITY_FRAMES,
        "queue_budget_ms": _CAPACITY_FRAMES * backend.FRAME_MS,
        "pcm_encoding": "pcm_f32le_base64",
    }
    assert set(environment) == {
        "source_root",
        "source_revision",
        "source_module",
        "source_sha256",
        "source_tree_sha256",
        "phone_checkpoint",
        "phone_sha256",
        "pitch_checkpoint",
        "pitch_sha256",
        "converter_checkpoint",
        "converter_sha256",
        "runtime_lock_sha256",
        "worker_wheel",
        "worker_wheel_sha256",
        "target_speaker_id",
        "sample_rate",
        "batch_ms",
        "device",
    }
    assert all(
        isinstance(name, str) and name.startswith("LIVECONV_BEATRICE_")
        for name in environment.values()
    )
    assert all(not str(value).startswith("/") for value in environment.values())
    payload = worker["configuration_payload"]
    assert isinstance(payload, dict)
    assert artifacts == {
        "source_module_sha256": payload["source_sha256"],
        "source_tree_sha256": payload["source_tree_sha256"],
        "phone_checkpoint_sha256": payload["phone_sha256"],
        "pitch_checkpoint_sha256": payload["pitch_sha256"],
        "converter_checkpoint_sha256": payload["converter_sha256"],
        "runtime_lock_sha256": payload["runtime_lock_sha256"],
        "worker_wheel_sha256": payload["worker_wheel_sha256"],
        "worker_wheel_record_sha256": payload["wheel_record_sha256"],
        "installed_record_sha256": payload["installed_record_sha256"],
        "distribution_manifest_sha256": payload["distribution_manifest_sha256"],
        "executed_project_modules_sha256": payload["executed_project_modules_sha256"],
        "installed_distribution_inventory_sha256": payload[
            "installed_distribution_inventory_sha256"
        ],
        "runtime_codec_sha256": payload["runtime_codec_sha256"],
    }
    assert material["pre_spawn_artifact_keys"] == [
        "source_module",
        "phone_checkpoint",
        "pitch_checkpoint",
        "converter_checkpoint",
        "worker_wheel",
    ]
    assert set(material["pre_spawn_artifact_keys"]) <= set(environment)
    assert artifacts["converter_checkpoint_sha256"] == worker[
        "weight_revision"
    ].removeprefix("sha256:")


def test_profile_material_binds_blocked_pack_to_retained_identity_evidence() -> None:
    material = _material()
    pack = json.loads(
        (WORKERS_ROOT / "packs" / "beatrice-2.json").read_text(encoding="utf-8")
    )
    evidence = material["promotion_evidence"]
    constraints = material["nonselection_constraints"]
    assert isinstance(evidence, dict)
    assert isinstance(constraints, dict)

    assert pack["status"] == constraints["pack_status"] == "blocked"
    assert pack["ready_for_runtime"] is False
    assert pack["promotion_evidence"] == {
        "status": evidence["status"],
        "evidence_sha256": evidence["retained_identity_evidence_sha256"],
    }
    assert pack["license_gate"]["overall_status"] == constraints["license_gate_status"]
    assert [item["id"] for item in pack["blockers"]] == constraints["blocker_ids"]
