"""Static Gateway binding for the retained MeanVC2 Runrun route."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from workers.runtime import ArtifactSpec, WorkerProfile

if TYPE_CHECKING:
    from ..profiles import ModelProfile


WORKER_MODULE = "workers.adapters.meanvc2"
PROFILE_ID = "vc.meanvc2.amitaro-runrun.v1"
IMPLEMENTATION_REVISION = (
    "meanvc2-streaming-adapter-v1+sha256:"
    "db3b6db5e9f6b30fcb2ac5e4f430dfdd551913a39c8def0081fe7de4ca6b2f4b"
)
WEIGHT_REVISION = (
    "sha256:1dd8dc5fcb0b0d5c17c9c380887accc61f935d061b7b5f909b4e5b945e1b1196"
)
CONFIGURATION_HASH = (
    "sha256:da9835df812bc15cf1d7920592b2878108caa70ebe4d27b3f211a9bacb725c19"
)
FRAME_MS = 20
QUEUE_CAPACITY_FRAMES = 25

CANONICAL_CONFIGURATION: dict[str, object] = {
    "adapter_source_sha256": (
        "db3b6db5e9f6b30fcb2ac5e4f430dfdd551913a39c8def0081fe7de4ca6b2f4b"
    ),
    "asr_sha256": "4338739bd13e0f7718276373e9547ce1f9aa02ec0867452860df9e837f90e4d2",
    "checkpoint_sha256": (
        "01caafec9a3991a5514df9412952d24ae3370406358a01e20e03df41f2f5d515"
    ),
    "config_sha256": "1207e631961b8b0a983f248b77dee0d9b8441c521c8955ffbec89d251064ba43",
    "device": "cuda:0",
    "inference_frames": 8,
    "native_sample_rate": 16_000,
    "output_sample_rate": 48_000,
    "queue_capacity_frames": QUEUE_CAPACITY_FRAMES,
    "runtime_lock_sha256": (
        "79fe29dd21e7c51e7a3e686b2f50650218262aa09c572aeccdb008f48dfab04d"
    ),
    "source_revision": "0d39c8ae416a37edb9884db67334e4b9d0c3e308",
    "source_sha256": "6b2359bfcc02f7188ba6996da52525c2653b9eae0e6dd9f4e13a36125183baee",
    "speaker_checkpoint_sha256": (
        "51f07e3b94d9e0262a6a675ef5a087be3dd09e8c62e9d886827f44f82fe7f94b"
    ),
    "speaker_config_sha256": (
        "43d2656272cacdba3b6cd303c6e9604188325e91640a44911ada69df16285bbf"
    ),
    "target_authorization_sha256": (
        "b5e7994c1cabaef4ac24a63a607e9d4e4a040c7f7db8e38fe6ac07def6e541ec"
    ),
    "target_reference_sha256": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126"
    ),
    "vocoder_sha256": (
        "df1f2ba9f7ac35c96832579421ee1ed913a68c3a1d2f8a6536739f902f194a93"
    ),
    "worker_wheel_sha256": (
        "e4971f2dbf9dd5181002e7a192e13f09dd75c7b3397c9efdb4a8fc9e2105cd9f"
    ),
}

_APPROVED_TARGETS = {
    PROFILE_ID: (
        CANONICAL_CONFIGURATION["target_reference_sha256"],
        CANONICAL_CONFIGURATION["target_authorization_sha256"],
    ),
    "vc.meanvc2.amitaro-runrun-q34.v1": (
        "0cd4bd58aabbf438ab11b304a9f01d9d0fdf5c49e73e1a3edbc22bae1273f3bd",
        "76392ed4fe498dbefe3f1adc6381534c048f571d6163e21cbd2f30191097361f",
    ),
}

_REQUIRED_ENVIRONMENT = (
    "LIVECONV_MEANVC2_SOURCE_ROOT",
    "LIVECONV_MEANVC2_SOURCE_REVISION",
    "LIVECONV_MEANVC2_SOURCE_SHA256",
    "LIVECONV_MEANVC2_CONFIG_PATH",
    "LIVECONV_MEANVC2_CONFIG_SHA256",
    "LIVECONV_MEANVC2_ASR_PATH",
    "LIVECONV_MEANVC2_ASR_SHA256",
    "LIVECONV_MEANVC2_CHECKPOINT_PATH",
    "LIVECONV_MEANVC2_CHECKPOINT_SHA256",
    "LIVECONV_MEANVC2_VOCODER_PATH",
    "LIVECONV_MEANVC2_VOCODER_SHA256",
    "LIVECONV_MEANVC2_SPEAKER_CONFIG_PATH",
    "LIVECONV_MEANVC2_SPEAKER_CONFIG_SHA256",
    "LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_PATH",
    "LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_SHA256",
    "LIVECONV_MEANVC2_TARGET_REFERENCE_PATH",
    "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256",
    "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH",
    "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256",
    "LIVECONV_MEANVC2_ADAPTER_SOURCE_SHA256",
    "LIVECONV_MEANVC2_RUNTIME_LOCK_PATH",
    "LIVECONV_MEANVC2_RUNTIME_LOCK_SHA256",
    "LIVECONV_MEANVC2_WORKER_WHEEL_PATH",
    "LIVECONV_MEANVC2_WORKER_WHEEL_SHA256",
    "LIVECONV_MEANVC2_INTERPRETER_PATH",
    "LIVECONV_MEANVC2_INTERPRETER_SHA256",
    "LIVECONV_MEANVC2_DEVICE",
)

_ENVIRONMENT_BINDINGS = {
    "LIVECONV_MEANVC2_SOURCE_REVISION": CANONICAL_CONFIGURATION["source_revision"],
    "LIVECONV_MEANVC2_SOURCE_SHA256": CANONICAL_CONFIGURATION["source_sha256"],
    "LIVECONV_MEANVC2_CONFIG_SHA256": CANONICAL_CONFIGURATION["config_sha256"],
    "LIVECONV_MEANVC2_ASR_SHA256": CANONICAL_CONFIGURATION["asr_sha256"],
    "LIVECONV_MEANVC2_CHECKPOINT_SHA256": CANONICAL_CONFIGURATION["checkpoint_sha256"],
    "LIVECONV_MEANVC2_VOCODER_SHA256": CANONICAL_CONFIGURATION["vocoder_sha256"],
    "LIVECONV_MEANVC2_SPEAKER_CONFIG_SHA256": CANONICAL_CONFIGURATION[
        "speaker_config_sha256"
    ],
    "LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_SHA256": CANONICAL_CONFIGURATION[
        "speaker_checkpoint_sha256"
    ],
    "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256": CANONICAL_CONFIGURATION[
        "target_reference_sha256"
    ],
    "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256": CANONICAL_CONFIGURATION[
        "target_authorization_sha256"
    ],
    "LIVECONV_MEANVC2_ADAPTER_SOURCE_SHA256": CANONICAL_CONFIGURATION[
        "adapter_source_sha256"
    ],
    "LIVECONV_MEANVC2_RUNTIME_LOCK_SHA256": CANONICAL_CONFIGURATION[
        "runtime_lock_sha256"
    ],
    "LIVECONV_MEANVC2_WORKER_WHEEL_SHA256": CANONICAL_CONFIGURATION[
        "worker_wheel_sha256"
    ],
    "LIVECONV_MEANVC2_INTERPRETER_SHA256": (
        "1d3cf64f97cadc79fdc6fe2496a21b7b456cb94211978cfef5a65f616af74fd5"
    ),
    "LIVECONV_MEANVC2_DEVICE": CANONICAL_CONFIGURATION["device"],
}

_ARTIFACT_BINDINGS = (
    ("LIVECONV_MEANVC2_CONFIG_PATH", "config_sha256"),
    ("LIVECONV_MEANVC2_ASR_PATH", "asr_sha256"),
    ("LIVECONV_MEANVC2_CHECKPOINT_PATH", "checkpoint_sha256"),
    ("LIVECONV_MEANVC2_VOCODER_PATH", "vocoder_sha256"),
    ("LIVECONV_MEANVC2_SPEAKER_CONFIG_PATH", "speaker_config_sha256"),
    ("LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_PATH", "speaker_checkpoint_sha256"),
    ("LIVECONV_MEANVC2_TARGET_REFERENCE_PATH", "target_reference_sha256"),
    ("LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH", "target_authorization_sha256"),
    ("LIVECONV_MEANVC2_RUNTIME_LOCK_PATH", "runtime_lock_sha256"),
    ("LIVECONV_MEANVC2_WORKER_WHEEL_PATH", "worker_wheel_sha256"),
    ("LIVECONV_MEANVC2_INTERPRETER_PATH", "interpreter_sha256"),
)


def _configuration_hash(configuration: object) -> str:
    encoded = json.dumps(
        configuration, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _configuration(profile_id: str) -> dict[str, object]:
    try:
        target_reference_sha256, target_authorization_sha256 = _APPROVED_TARGETS[
            profile_id
        ]
    except KeyError as exc:
        raise ValueError(f"{profile_id}: MeanVC2 profile ID is not approved") from exc
    return {
        **CANONICAL_CONFIGURATION,
        "target_reference_sha256": target_reference_sha256,
        "target_authorization_sha256": target_authorization_sha256,
    }


def validate_configuration(profile: ModelProfile) -> None:
    if profile.profile_id not in _APPROVED_TARGETS:
        raise ValueError(f"{profile.profile_id}: MeanVC2 profile ID is not approved")
    if (
        profile.runtime.adapter != "worker"
        or profile.runtime.worker_module != WORKER_MODULE
    ):
        raise ValueError(f"{profile.profile_id}: MeanVC2 worker is not approved")
    configuration = _configuration(profile.profile_id)
    if profile.runtime.configuration != configuration:
        raise ValueError(f"{profile.profile_id}: MeanVC2 configuration differs")
    if profile.configuration_hash != _configuration_hash(
        configuration
    ) or _configuration_hash(profile.runtime.configuration) != _configuration_hash(
        configuration
    ):
        raise ValueError(f"{profile.profile_id}: MeanVC2 configuration hash differs")
    if profile.implementation_revision != IMPLEMENTATION_REVISION:
        raise ValueError(f"{profile.profile_id}: MeanVC2 implementation differs")
    if profile.weight_revision != WEIGHT_REVISION:
        raise ValueError(f"{profile.profile_id}: MeanVC2 weights differ")
    if profile.kind != "voice_conversion" or not profile.streaming:
        raise ValueError(f"{profile.profile_id}: MeanVC2 must be streaming VC")
    if profile.frame_ms != FRAME_MS or profile.minimum_context_ms != 160:
        raise ValueError(f"{profile.profile_id}: MeanVC2 frame contract differs")
    if profile.input_sample_rates != [48_000] or profile.output_sample_rates != [
        48_000
    ]:
        raise ValueError(f"{profile.profile_id}: MeanVC2 requires 48 kHz PCM")
    if profile.cancellation != "immediate" or profile.warmup_policy != "eager":
        raise ValueError(f"{profile.profile_id}: MeanVC2 lifecycle differs")
    if profile.resource_class != "gpu" or profile.runtime.max_vram_mb != 16_384:
        raise ValueError(f"{profile.profile_id}: MeanVC2 GPU budget differs")
    if (
        profile.timeouts.first_output_ms != 120_000
        or profile.timeouts.stall_ms != 30_000
    ):
        raise ValueError(f"{profile.profile_id}: MeanVC2 timeouts differ")
    _worker_endpoint(profile)


def build_worker_profile(
    profile: ModelProfile, pipeline_id: str, queue_budget_ms: int
) -> WorkerProfile:
    del queue_budget_ms
    validate_configuration(profile)
    configuration = _configuration(profile.profile_id)
    environment = _environment(profile, configuration)
    endpoint = _worker_endpoint(profile)
    artifacts = tuple(
        ArtifactSpec(
            env_var=env_var,
            sha256=_artifact_digest(configuration, env_var, digest_key),
        )
        for env_var, digest_key in _ARTIFACT_BINDINGS
    )
    return WorkerProfile(
        profile_id=profile.profile_id,
        pipeline_id=pipeline_id,
        configuration_hash=_configuration_hash(configuration),
        command=(str(endpoint), "-I", "-B", "-m", WORKER_MODULE),
        cwd=Path("/tmp"),
        environment=environment,
        implementation_revision=IMPLEMENTATION_REVISION,
        weight_revision=WEIGHT_REVISION,
        frame_ms=FRAME_MS,
        queue_budget_ms=FRAME_MS * QUEUE_CAPACITY_FRAMES,
        startup_timeout_ms=120_000,
        first_output_timeout_ms=120_000,
        stall_timeout_ms=30_000,
        cancel_timeout_ms=2_000,
        close_grace_ms=2_000,
        terminate_grace_ms=1_000,
        restart_limit=0,
        restart_window_ms=60_000,
        artifacts=artifacts,
    )


def delivery_mode(_profile: ModelProfile) -> Literal["live_frame_echo"]:
    return "live_frame_echo"


def queue_capacity_frames(_profile: ModelProfile, _queue_budget_ms: int) -> int:
    return QUEUE_CAPACITY_FRAMES


def target_environment_names(profile_id: str) -> tuple[str, str, str, str]:
    if profile_id == PROFILE_ID:
        return (
            "LIVECONV_MEANVC2_TARGET_REFERENCE_PATH",
            "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256",
            "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH",
            "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256",
        )
    if profile_id not in _APPROVED_TARGETS:
        raise ValueError(f"{profile_id}: MeanVC2 profile ID is not approved")
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_MEANVC2_VARIANT_{suffix}"
    return (
        f"{prefix}_TARGET_REFERENCE_PATH",
        f"{prefix}_TARGET_REFERENCE_SHA256",
        f"{prefix}_TARGET_AUTHORIZATION_PATH",
        f"{prefix}_TARGET_AUTHORIZATION_SHA256",
    )


def _environment(
    profile: ModelProfile, configuration: dict[str, object]
) -> dict[str, str]:
    environment: dict[str, str] = {}
    variant_names = target_environment_names(profile.profile_id)
    variant_sources = {
        "LIVECONV_MEANVC2_TARGET_REFERENCE_PATH": variant_names[0],
        "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256": variant_names[1],
        "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH": variant_names[2],
        "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256": variant_names[3],
    }
    for name in _REQUIRED_ENVIRONMENT:
        value = os.environ.get(variant_sources.get(name, name))
        if not value:
            raise ValueError(f"{profile.profile_id}: {name} is required")
        environment[name] = value
    for name, expected in _ENVIRONMENT_BINDINGS.items():
        if name in {
            "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256",
            "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256",
        }:
            continue
        if environment[name] != expected:
            raise ValueError(f"{profile.profile_id}: {name} differs")
    for name, key in (
        ("LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256", "target_reference_sha256"),
        (
            "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256",
            "target_authorization_sha256",
        ),
    ):
        if environment[name] != configuration[key]:
            raise ValueError(f"{profile.profile_id}: {name} differs")
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    return environment


def _artifact_digest(
    configuration: dict[str, object], env_var: str, digest_key: str
) -> str:
    if digest_key in {"target_reference_sha256", "target_authorization_sha256"}:
        digest = configuration[digest_key]
    else:
        digest = _ENVIRONMENT_BINDINGS.get(env_var.replace("_PATH", "_SHA256"))
        if digest is None:
            digest = configuration[digest_key]
    if not isinstance(digest, str):
        raise ValueError(f"{env_var}: MeanVC2 artifact digest is invalid")
    return digest


def _worker_endpoint(profile: ModelProfile) -> Path:
    value = profile.runtime.worker_endpoint
    if value is None:
        raise ValueError(f"{profile.profile_id}: MeanVC2 endpoint is required")
    endpoint = Path(value)
    if (
        not endpoint.is_absolute()
        or not endpoint.is_file()
        or not os.access(endpoint, os.X_OK)
    ):
        raise ValueError(f"{profile.profile_id}: MeanVC2 endpoint is invalid")
    expected = os.environ.get("LIVECONV_MEANVC2_INTERPRETER_PATH")
    if expected is None or endpoint.resolve() != Path(expected).resolve():
        raise ValueError(f"{profile.profile_id}: MeanVC2 endpoint differs")
    return endpoint
