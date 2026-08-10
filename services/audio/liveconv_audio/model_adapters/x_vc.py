"""Trusted Gateway binding for the retained X-VC worker identity."""

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


WORKER_MODULE = "workers.adapters.x_vc.worker"
_PROFILE_ID = "vc.x-vc.synthetic-ja.v1"
_IMPLEMENTATION_REVISION = (
    "x-vc-streaming-adapter-v1+sha256:"
    "d0737a67a05ca39616b312443b83610e891f79207066e8e5da6ee9ea2b304959"
)
_WEIGHT_REVISION = (
    "sha256:1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687"
)
_CONFIGURATION_HASH = (
    "sha256:a0419cee1204d0a67f6e4a2c51f94da1363da386739d2308461bf43fdf6fe25b"
)
_FRAME_MS = 20
_QUEUE_CAPACITY_FRAMES = 25
_QUEUE_BUDGET_MS = _FRAME_MS * _QUEUE_CAPACITY_FRAMES
_STARTUP_TIMEOUT_MS = 300_000
_FIRST_OUTPUT_TIMEOUT_MS = 60_000
_STALL_TIMEOUT_MS = 60_000
_CANCEL_TIMEOUT_MS = 2_000
_CLOSE_GRACE_MS = 5_000
_TERMINATE_GRACE_MS = 1_000

# This is the reviewed configuration payload, not a runtime material file. Paths
# are intentionally absent: private artifacts are supplied only through the
# allowlisted child environment below.
_CANONICAL_CONFIGURATION: dict[str, object] = {
    "adapter_revision": "x-vc-streaming-adapter-v1",
    "adapter_source_sha256": (
        "d0737a67a05ca39616b312443b83610e891f79207066e8e5da6ee9ea2b304959"
    ),
    "checkpoint_sha256": (
        "1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687"
    ),
    "config_sha256": "5f9aae0487ffcf1b69f5833317d068bfe62c6de1a12b0921abebe742b39c3be7",
    "current_ms": 120,
    "device": "cuda:0",
    "ema_load": False,
    "eres_config_sha256": (
        "bbd0c639f5c73325ad9f080d9f8866b613f739546216dc090eabe65ed0bbdd18"
    ),
    "eres_model_sha256": (
        "d8941f5952e31820173c8854562cb6d7897aaa58cd65c18f30d5a2e52d30847d"
    ),
    "future_ms": 100,
    "glm_config_sha256": (
        "5a5181fcc293ced0a1e7455f6e3503ce4e8be9229922ea34aeb785f62720c0aa"
    ),
    "glm_model_sha256": (
        "2800bd503f52b51e45f0c53cfd5c31dcfe8ef7f13d22b396aa3d53e0280dd1e4"
    ),
    "glm_preprocessor_sha256": (
        "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"
    ),
    "input_sample_rate": 48_000,
    "interpreter_sha256": (
        "1d3cf64f97cadc79fdc6fe2496a21b7b456cb94211978cfef5a65f616af74fd5"
    ),
    "latent_hop_length": 1_280,
    "mask_target_condition": False,
    "output_resampler_revision": "torchaudio-sinc-hann-overlap-v1",
    "python_implementation": "CPython",
    "python_version": "3.12.3",
    "runtime_lock_sha256": (
        "e5e5ccbb88ad3c49eac8d6ed0cd1f17120cbbbdea9183905be2fc120fbd66f14"
    ),
    "smooth_ms": 20,
    "source_preprocessing_revision": "xvc-bounded-official-functions-v1",
    "source_revision": "49df8c591eafc48b096e466d96f9839f9c0dd739",
    "target_authorization_sha256": (
        "ac61316ef93d6591ef0e02945f1eb6bb6c8ea74b682a40d8269cc9be91e8c2f2"
    ),
    "target_reference_sha256": (
        "a92aaa78a600be0afa2425e55a8adb57dc0630789ce9a50284bf467345631ff7"
    ),
    "window_ms": 2_400,
    "worker_package_version": "0.1.0",
    "worker_wheel_sha256": (
        "2dba703e830b0db405e0f74ae881fcdb9894ab2f9b4d5224884089fdff373b22"
    ),
}

_APPROVED_TARGETS = {
    _PROFILE_ID: (
        _CANONICAL_CONFIGURATION["target_reference_sha256"],
        _CANONICAL_CONFIGURATION["target_authorization_sha256"],
    ),
    "vc.x-vc.amitaro-runrun.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        "7a878609fb31fb2852ccb885405c97aad27bf1016ee7d3f4e1e3b0e751d02199",
    ),
    "vc.x-vc.amitaro-yofukashi.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        "313edea2bc054aa885e58919d560c2708487c3be6f7692a06aab5a907c8d619c",
    ),
}

_REQUIRED_ENVIRONMENT = (
    "LIVECONV_XVC_SOURCE_ROOT",
    "LIVECONV_XVC_SOURCE_REVISION",
    "LIVECONV_XVC_CONFIG_PATH",
    "LIVECONV_XVC_CONFIG_SHA256",
    "LIVECONV_XVC_CHECKPOINT_PATH",
    "LIVECONV_XVC_CHECKPOINT_SHA256",
    "LIVECONV_XVC_GLM_ROOT",
    "LIVECONV_XVC_GLM_CONFIG_SHA256",
    "LIVECONV_XVC_GLM_PREPROCESSOR_SHA256",
    "LIVECONV_XVC_GLM_MODEL_SHA256",
    "LIVECONV_XVC_ERES_ROOT",
    "LIVECONV_XVC_ERES_CONFIG_SHA256",
    "LIVECONV_XVC_ERES_MODEL_SHA256",
    "LIVECONV_XVC_TARGET_REFERENCE_PATH",
    "LIVECONV_XVC_TARGET_REFERENCE_SHA256",
    "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH",
    "LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256",
    "LIVECONV_XVC_ADAPTER_SOURCE_SHA256",
    "LIVECONV_XVC_RUNTIME_LOCK_PATH",
    "LIVECONV_XVC_RUNTIME_LOCK_SHA256",
    "LIVECONV_XVC_WORKER_WHEEL_PATH",
    "LIVECONV_XVC_WORKER_WHEEL_SHA256",
    "LIVECONV_XVC_INTERPRETER_PATH",
    "LIVECONV_XVC_INTERPRETER_SHA256",
    "LIVECONV_XVC_PYTHON_IMPLEMENTATION",
    "LIVECONV_XVC_PYTHON_VERSION",
    "LIVECONV_XVC_WORKER_PACKAGE_VERSION",
    "LIVECONV_XVC_DEVICE",
)

_ENVIRONMENT_BINDINGS = {
    "LIVECONV_XVC_SOURCE_REVISION": _CANONICAL_CONFIGURATION["source_revision"],
    "LIVECONV_XVC_CONFIG_SHA256": _CANONICAL_CONFIGURATION["config_sha256"],
    "LIVECONV_XVC_CHECKPOINT_SHA256": _CANONICAL_CONFIGURATION["checkpoint_sha256"],
    "LIVECONV_XVC_GLM_CONFIG_SHA256": _CANONICAL_CONFIGURATION["glm_config_sha256"],
    "LIVECONV_XVC_GLM_PREPROCESSOR_SHA256": _CANONICAL_CONFIGURATION[
        "glm_preprocessor_sha256"
    ],
    "LIVECONV_XVC_GLM_MODEL_SHA256": _CANONICAL_CONFIGURATION["glm_model_sha256"],
    "LIVECONV_XVC_ERES_CONFIG_SHA256": _CANONICAL_CONFIGURATION["eres_config_sha256"],
    "LIVECONV_XVC_ERES_MODEL_SHA256": _CANONICAL_CONFIGURATION["eres_model_sha256"],
    "LIVECONV_XVC_ADAPTER_SOURCE_SHA256": _CANONICAL_CONFIGURATION[
        "adapter_source_sha256"
    ],
    "LIVECONV_XVC_RUNTIME_LOCK_SHA256": _CANONICAL_CONFIGURATION["runtime_lock_sha256"],
    "LIVECONV_XVC_WORKER_WHEEL_SHA256": _CANONICAL_CONFIGURATION["worker_wheel_sha256"],
    "LIVECONV_XVC_INTERPRETER_SHA256": _CANONICAL_CONFIGURATION["interpreter_sha256"],
    "LIVECONV_XVC_PYTHON_IMPLEMENTATION": _CANONICAL_CONFIGURATION[
        "python_implementation"
    ],
    "LIVECONV_XVC_PYTHON_VERSION": _CANONICAL_CONFIGURATION["python_version"],
    "LIVECONV_XVC_WORKER_PACKAGE_VERSION": _CANONICAL_CONFIGURATION[
        "worker_package_version"
    ],
    "LIVECONV_XVC_DEVICE": _CANONICAL_CONFIGURATION["device"],
}

_DERIVED_ARTIFACT_PATHS = {
    "LIVECONV_XVC_GLM_CONFIG_PATH": ("LIVECONV_XVC_GLM_ROOT", "config.json"),
    "LIVECONV_XVC_GLM_PREPROCESSOR_PATH": (
        "LIVECONV_XVC_GLM_ROOT",
        "preprocessor_config.json",
    ),
    "LIVECONV_XVC_GLM_MODEL_PATH": (
        "LIVECONV_XVC_GLM_ROOT",
        "model.safetensors",
    ),
    "LIVECONV_XVC_ERES_CONFIG_PATH": (
        "LIVECONV_XVC_ERES_ROOT",
        "configuration.json",
    ),
    "LIVECONV_XVC_ERES_MODEL_PATH": (
        "LIVECONV_XVC_ERES_ROOT",
        "pretrained_eres2net.ckpt",
    ),
}

_FIXED_ENVIRONMENT = {
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_OFFLINE": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}

_ARTIFACT_BINDINGS = (
    ("LIVECONV_XVC_CONFIG_PATH", "config_sha256"),
    ("LIVECONV_XVC_CHECKPOINT_PATH", "checkpoint_sha256"),
    ("LIVECONV_XVC_GLM_CONFIG_PATH", "glm_config_sha256"),
    ("LIVECONV_XVC_GLM_PREPROCESSOR_PATH", "glm_preprocessor_sha256"),
    ("LIVECONV_XVC_GLM_MODEL_PATH", "glm_model_sha256"),
    ("LIVECONV_XVC_ERES_CONFIG_PATH", "eres_config_sha256"),
    ("LIVECONV_XVC_ERES_MODEL_PATH", "eres_model_sha256"),
    ("LIVECONV_XVC_TARGET_REFERENCE_PATH", "target_reference_sha256"),
    ("LIVECONV_XVC_TARGET_AUTHORIZATION_PATH", "target_authorization_sha256"),
    ("LIVECONV_XVC_RUNTIME_LOCK_PATH", "runtime_lock_sha256"),
    ("LIVECONV_XVC_WORKER_WHEEL_PATH", "worker_wheel_sha256"),
    ("LIVECONV_XVC_INTERPRETER_PATH", "interpreter_sha256"),
)


def validate_configuration(profile: ModelProfile) -> None:
    """Reject every route that is not the retained X-VC worker identity."""

    if profile.profile_id not in _APPROVED_TARGETS:
        raise ValueError(f"{profile.profile_id}: X-VC profile ID is not approved")
    if profile.runtime.adapter != "worker":
        raise ValueError(f"{profile.profile_id}: X-VC requires the worker adapter")
    if profile.runtime.worker_module != WORKER_MODULE:
        raise ValueError(f"{profile.profile_id}: X-VC worker module is not approved")
    configuration = _configuration(profile.profile_id)
    if not _is_canonical_configuration(profile.runtime.configuration, configuration):
        raise ValueError(
            f"{profile.profile_id}: X-VC configuration differs from retained identity"
        )
    if profile.configuration_hash != _configuration_hash(configuration):
        raise ValueError(
            f"{profile.profile_id}: X-VC configuration hash does not match"
        )
    if profile.implementation_revision != _IMPLEMENTATION_REVISION:
        raise ValueError(
            f"{profile.profile_id}: X-VC implementation revision does not match"
        )
    if profile.weight_revision != _WEIGHT_REVISION:
        raise ValueError(f"{profile.profile_id}: X-VC weight revision does not match")
    if profile.kind != "voice_conversion":
        raise ValueError(f"{profile.profile_id}: X-VC must be voice conversion")
    if profile.cancellation != "immediate":
        raise ValueError(f"{profile.profile_id}: X-VC requires immediate cancellation")
    if not profile.streaming or profile.frame_ms != _FRAME_MS:
        raise ValueError(f"{profile.profile_id}: X-VC requires 20 ms streaming")
    if profile.minimum_context_ms != 2_400:
        raise ValueError(f"{profile.profile_id}: X-VC requires 2400 ms context")
    if profile.input_sample_rates != [48_000] or profile.output_sample_rates != [
        48_000
    ]:
        raise ValueError(f"{profile.profile_id}: X-VC requires 48 kHz PCM")
    if profile.warmup_policy != "eager":
        raise ValueError(f"{profile.profile_id}: X-VC requires eager warmup")
    if profile.resource_class != "gpu" or profile.runtime.max_vram_mb != 24_576:
        raise ValueError(f"{profile.profile_id}: X-VC resource binding does not match")
    if (
        profile.timeouts.first_output_ms != _FIRST_OUTPUT_TIMEOUT_MS
        or profile.timeouts.stall_ms != _STALL_TIMEOUT_MS
    ):
        raise ValueError(f"{profile.profile_id}: X-VC timeouts do not match")
    _worker_endpoint(profile)


def build_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    """Build the static command and private child environment for X-VC."""

    del queue_budget_ms
    validate_configuration(profile)
    configuration = _configuration(profile.profile_id)
    environment = _environment(profile, configuration)
    endpoint = _bound_worker_endpoint(profile, environment)
    artifacts = tuple(
        ArtifactSpec(
            env_var=env_var,
            sha256=_digest(configuration, digest_key),
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
        implementation_revision=_IMPLEMENTATION_REVISION,
        weight_revision=_WEIGHT_REVISION,
        frame_ms=_FRAME_MS,
        queue_budget_ms=_QUEUE_BUDGET_MS,
        startup_timeout_ms=_STARTUP_TIMEOUT_MS,
        first_output_timeout_ms=_FIRST_OUTPUT_TIMEOUT_MS,
        stall_timeout_ms=_STALL_TIMEOUT_MS,
        cancel_timeout_ms=_CANCEL_TIMEOUT_MS,
        close_grace_ms=_CLOSE_GRACE_MS,
        terminate_grace_ms=_TERMINATE_GRACE_MS,
        restart_limit=0,
        restart_window_ms=60_000,
        artifacts=artifacts,
    )


def delivery_mode(_profile: ModelProfile) -> Literal["live_frame_echo"]:
    return "live_frame_echo"


def queue_capacity_frames(_profile: ModelProfile, _queue_budget_ms: int) -> int:
    return _QUEUE_CAPACITY_FRAMES


def _configuration(profile_id: str) -> dict[str, object]:
    try:
        target_reference_sha256, target_authorization_sha256 = _APPROVED_TARGETS[
            profile_id
        ]
    except KeyError as exc:
        raise ValueError(f"{profile_id}: X-VC profile ID is not approved") from exc
    return {
        **_CANONICAL_CONFIGURATION,
        "target_reference_sha256": target_reference_sha256,
        "target_authorization_sha256": target_authorization_sha256,
    }


def _configuration_hash(configuration: dict[str, object]) -> str:
    encoded = json.dumps(
        configuration,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def target_environment_names(profile_id: str) -> tuple[str, str, str, str]:
    if profile_id == _PROFILE_ID:
        return (
            "LIVECONV_XVC_TARGET_REFERENCE_PATH",
            "LIVECONV_XVC_TARGET_REFERENCE_SHA256",
            "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH",
            "LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256",
        )
    if profile_id not in _APPROVED_TARGETS:
        raise ValueError(f"{profile_id}: X-VC profile ID is not approved")
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_XVC_VARIANT_{suffix}"
    return (
        f"{prefix}_TARGET_REFERENCE_PATH",
        f"{prefix}_TARGET_REFERENCE_SHA256",
        f"{prefix}_TARGET_AUTHORIZATION_PATH",
        f"{prefix}_TARGET_AUTHORIZATION_SHA256",
    )


def _is_canonical_configuration(
    configuration: object,
    expected_configuration: dict[str, object],
) -> bool:
    if not isinstance(configuration, dict) or set(configuration) != set(
        expected_configuration
    ):
        return False
    return all(
        type(configuration[key]) is type(expected) and configuration[key] == expected
        for key, expected in expected_configuration.items()
    )


def _worker_endpoint(profile: ModelProfile) -> Path:
    endpoint_value = profile.runtime.worker_endpoint
    if endpoint_value is None or not Path(endpoint_value).is_absolute():
        raise ValueError(
            f"{profile.profile_id}: worker_endpoint must be an absolute path"
        )
    endpoint = Path(endpoint_value)
    if not endpoint.is_file() or not (endpoint.stat().st_mode & 0o111):
        raise ValueError(
            f"{profile.profile_id}: worker_endpoint must be an executable file"
        )
    return endpoint


def _bound_worker_endpoint(profile: ModelProfile, environment: dict[str, str]) -> Path:
    endpoint = _worker_endpoint(profile)
    if str(endpoint) != environment["LIVECONV_XVC_INTERPRETER_PATH"]:
        raise ValueError(
            f"{profile.profile_id}: worker endpoint does not match interpreter"
        )
    return endpoint


def _environment(
    profile: ModelProfile,
    configuration: dict[str, object],
) -> dict[str, str]:
    environment: dict[str, str] = {}
    variant_names = target_environment_names(profile.profile_id)
    variant_sources = {
        "LIVECONV_XVC_TARGET_REFERENCE_PATH": variant_names[0],
        "LIVECONV_XVC_TARGET_REFERENCE_SHA256": variant_names[1],
        "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH": variant_names[2],
        "LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256": variant_names[3],
    }
    for name in _REQUIRED_ENVIRONMENT:
        source_name = variant_sources.get(name, name)
        value = os.environ.get(source_name)
        if not value:
            raise ValueError(f"required worker environment is missing: {source_name}")
        environment[name] = value
    for name, expected in _ENVIRONMENT_BINDINGS.items():
        if environment[name] != expected:
            raise ValueError(
                f"{profile.profile_id}: {name} does not match retained identity"
            )
    for name, key in (
        ("LIVECONV_XVC_TARGET_REFERENCE_SHA256", "target_reference_sha256"),
        ("LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256", "target_authorization_sha256"),
    ):
        if environment[name] != configuration[key]:
            raise ValueError(
                f"{profile.profile_id}: {name} does not match approved identity"
            )
    for name, (root_name, relative_path) in _DERIVED_ARTIFACT_PATHS.items():
        environment[name] = str(Path(environment[root_name]) / relative_path)
    path = os.environ.get("PATH")
    if not path:
        raise ValueError("required worker environment is missing: PATH")
    # Constructing this allowlist is what prevents host Python settings and
    # offline-mode overrides from reaching the isolated interpreter.
    return {
        "PATH": path,
        **_FIXED_ENVIRONMENT,
        **environment,
    }


def _digest(configuration: dict[str, object], key: str) -> str:
    value = configuration[key]
    assert isinstance(value, str)
    return value
