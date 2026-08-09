from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from liveconv_audio.profiles import ProfileRegistry

PROFILE_ID = "vc.rvc.synthetic-ja.v1"


@dataclass(frozen=True, slots=True)
class RetainedProfileFixture:
    path: Path
    profile_hash: str
    configuration_hash: str


def _rvc_configuration() -> dict[str, object]:
    return {
        "worker_module": "workers.adapters.rvc_v2.worker",
        "adapter_revision": "test-rvc-worker",
        "source_revision": "a" * 40,
        "artifacts": {
            "checkpoint_sha256": "b" * 64,
            "index_sha256": None,
            "hubert_config_sha256": "c" * 64,
            "hubert_preprocessor_sha256": "d" * 64,
            "hubert_weights_sha256": "e" * 64,
            "rmvpe_sha256": "f" * 64,
            "worker_wheel_sha256": "1" * 64,
            "worker_wheel_record_sha256": "2" * 64,
            "worker_module_sha256": "3" * 64,
            "backend_module_sha256": "4" * 64,
            "network_isolation_module_sha256": "5" * 64,
            "requirements_lock_sha256": "6" * 64,
        },
        "settings": {
            "speaker_id": 0,
            "pitch_shift": 0,
            "f0_method": "rmvpe",
            "index_rate": 0.0,
            "rms_mix_rate": 1.0,
            "sample_rate": 48_000,
            "block_ms": 500,
            "crossfade_ms": 50,
            "context_ms": 500,
            "frame_ms": 20,
            "inference_batch_frames": 25,
            "queue_capacity_frames": 25,
            "resident_capacity_frames": 50,
            "formant_shift": 0.0,
            "threshold_dbfs": -60.0,
        },
    }


def write_retained_rvc_profile(
    path: Path,
    *,
    first_output_ms: int = 120_000,
    extra_profile: bool = False,
) -> RetainedProfileFixture:
    worker_endpoint = path.parent / "rvc-worker"
    worker_endpoint.write_text("#!/bin/sh\nexit 0\n")
    worker_endpoint.chmod(0o700)
    pack = files("workers").joinpath("packs/rvc-v2.json").read_bytes()
    profile = {
        "profile_id": PROFILE_ID,
        "kind": "voice_conversion",
        "readiness": "ready",
        "adapter_api_version": 1,
        "implementation_revision": "test-rvc-worker+rvc." + "a" * 40,
        "weight_revision": "sha256:" + "b" * 64,
        "streaming": True,
        "cancellation": "cooperative",
        "input_sample_rates": [48_000],
        "output_sample_rates": [48_000],
        "frame_ms": 20,
        "minimum_context_ms": 500,
        "voice_requirement": "pretrained_voice",
        "warmup_policy": "lazy",
        "resource_class": "gpu",
        "license_record": "test-only technical profile",
        "promotion": {
            "status": "technical_validation",
            "pack_id": "rvc-v2",
            "pack_sha256": f"sha256:{hashlib.sha256(pack).hexdigest()}",
            "evidence_sha256": (
                "sha256:48aeffc090c1255f2d06194164e0ef730493606a1e0edae1a1c7b707548465e6"
            ),
            "endpoint_sha256": (
                f"sha256:{hashlib.sha256(worker_endpoint.read_bytes()).hexdigest()}"
            ),
        },
        "timeouts": {"first_output_ms": first_output_ms, "stall_ms": 5_000},
        "runtime": {
            "adapter": "worker",
            "configuration": _rvc_configuration(),
            "worker_endpoint": str(worker_endpoint),
            "max_vram_mb": 2_048,
        },
    }
    profiles = [profile]
    if extra_profile:
        profiles.append({**profile, "profile_id": "vc.rvc.second-ja.v1"})
    path.write_text(json.dumps({"schema_version": 1, "profiles": profiles}))
    selected = ProfileRegistry.load(path, allow_technical_profiles=True).get_selectable(
        PROFILE_ID
    )
    assert selected is not None
    return RetainedProfileFixture(
        path=path,
        profile_hash=selected.profile_hash,
        configuration_hash=selected.configuration_hash,
    )
