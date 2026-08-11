"""Trusted Gateway binding for the retained OpenVoice V2 preview worker."""

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


WORKER_MODULE = "workers.adapters.openvoice_v2"
_PROFILE_ID = "vc.openvoice-v2.synthetic-ja.v1"
_IMPLEMENTATION_REVISION = (
    "openvoice-v2-offline-adapter-v4+sha256:"
    "f4391211dd981906d25a556a6c32c75efc46e0383138d8abedfae82a5cacb862"
)
_WEIGHT_REVISION = (
    "sha256:29e76b818c6677c3c79666b83a2e9d05799258d51e05edc2337a8940a0dc9e69"
)
_CONFIGURATION_HASH = (
    "sha256:cb28dfe641651e20b073f568c8eaf76d68caa4fbc8582c3ccee9406232be9170"
)
_PROMOTION_EVIDENCE_SHA256 = (
    "sha256:bff2066e3ef311dc123f1b8d85d5f98a14610a71cc6f4ecf71d34670fc85e057"
)
_FRAME_MS = 20
_MINIMUM_INPUT_FRAMES = 3
_QUEUE_CAPACITY_FRAMES = 25
_QUEUE_BUDGET_MS = _FRAME_MS * _QUEUE_CAPACITY_FRAMES

# These markers expose the material's rebind state without treating it as a
# Gateway approval or a latency result.
CURRENT_SOURCE_IMPLEMENTATION_SHA256 = (
    "f4391211dd981906d25a556a6c32c75efc46e0383138d8abedfae82a5cacb862"
)
CURRENT_SOURCE_RUNTIME_REBUILD_REQUIRED = False

# This is the retained engine identity from canonical-profile.json. Artifact
# paths remain private environment inputs and cannot be supplied in a profile.
_CANONICAL_CONFIGURATION: dict[str, float | int | str] = {
    "checkpoint_sha256": (
        "9652c27e92b6b2a91632590ac9962ef7ae2b712e5c5b7f4c34ec55ee2b37ab9e"
    ),
    "config_sha256": (
        "9dfff60350b8c63f2c664efd92a61b2516efb22671466960f0e5dfebd881fa47"
    ),
    "device": "cuda:0",
    "distribution_manifest_sha256": (
        "989e69c0bb2f06fd3d81de068c1be6509c93f876c23197c1b8bf462a087e574d"
    ),
    "implementation_sha256": (
        "f4391211dd981906d25a556a6c32c75efc46e0383138d8abedfae82a5cacb862"
    ),
    "installed_record_sha256": (
        "5420073f64e18818702d470b1b1a4be4685c342bcfec0fe1ade8aecf3f093127"
    ),
    "pyvenv_sha256": (
        "4fdb5d77a543f844b05c25637fa11d8c94ac824d04be9cf4db27b25cc635e0b6"
    ),
    "runtime_lock_sha256": (
        "3df9be85423bd8d3d8bf7406020baf90684ef0601e89dbb467166edbc67c5de1"
    ),
    "seed": 123,
    "source_tree_sha256": (
        "9b362e858a720107fcfcac6abfc47e12edd568beefd9de45a8b5dd70b9e0ad46"
    ),
    "target_reference_sha256": (
        "a92aaa78a600be0afa2425e55a8adb57dc0630789ce9a50284bf467345631ff7"
    ),
    "tau": 0.3,
    "wheel_record_sha256": (
        "0d0402b1c45db08bb010ed3bbabd798fe8c6c4805b06672e582341a01c33d232"
    ),
    "worker_wheel_sha256": (
        "7c8ebdbc0ec925d151c975223a5d22440e6c8ed357f3976ba211283f1e928ed6"
    ),
}

_APPROVED_VARIANTS = {
    _PROFILE_ID: (_CANONICAL_CONFIGURATION["target_reference_sha256"], 0.3),
    "vc.openvoice-v2.amitaro-runrun.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.3,
    ),
    "vc.openvoice-v2.amitaro-runrun-tau015.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.15,
    ),
    "vc.openvoice-v2.amitaro-runrun-tau060.v1": (
        "ea78016e6a15eb7236b3f25fca877a6d1117a8fa1c5efda6635d7d4516dd6126",
        0.6,
    ),
    "vc.openvoice-v2.amitaro-yofukashi.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.3,
    ),
    "vc.openvoice-v2.amitaro-yofukashi-tau015.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.15,
    ),
    "vc.openvoice-v2.amitaro-yofukashi-tau060.v1": (
        "a40396353b2543cc7923b673cdc42c25bb63f9204008e240b3659e55bd3c518f",
        0.6,
    ),
}

_REQUIRED_ENVIRONMENT = (
    "LIVECONV_OPENVOICE_V2_SOURCE_ROOT",
    "LIVECONV_OPENVOICE_V2_SOURCE_TREE_SHA256",
    "LIVECONV_OPENVOICE_V2_CONFIG_PATH",
    "LIVECONV_OPENVOICE_V2_CONFIG_SHA256",
    "LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH",
    "LIVECONV_OPENVOICE_V2_CHECKPOINT_SHA256",
    "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH",
    "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256",
    "LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX",
    "LIVECONV_OPENVOICE_V2_PYVENV_SHA256",
    "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH",
    "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256",
    "LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256",
    "LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256",
    "LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256",
    "LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256",
    "LIVECONV_OPENVOICE_V2_RUNTIME_LOCK_SHA256",
)

_OPTIONAL_ENVIRONMENT_BINDINGS = {
    "LIVECONV_OPENVOICE_V2_DEVICE": _CANONICAL_CONFIGURATION["device"],
    "LIVECONV_OPENVOICE_V2_TAU": str(_CANONICAL_CONFIGURATION["tau"]),
    "LIVECONV_OPENVOICE_V2_SEED": str(_CANONICAL_CONFIGURATION["seed"]),
}

_ENVIRONMENT_BINDINGS = {
    "LIVECONV_OPENVOICE_V2_SOURCE_TREE_SHA256": _CANONICAL_CONFIGURATION[
        "source_tree_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_CONFIG_SHA256": _CANONICAL_CONFIGURATION["config_sha256"],
    "LIVECONV_OPENVOICE_V2_CHECKPOINT_SHA256": _CANONICAL_CONFIGURATION[
        "checkpoint_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_PYVENV_SHA256": _CANONICAL_CONFIGURATION["pyvenv_sha256"],
    "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256": _CANONICAL_CONFIGURATION[
        "worker_wheel_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256": _CANONICAL_CONFIGURATION[
        "wheel_record_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256": _CANONICAL_CONFIGURATION[
        "installed_record_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256": _CANONICAL_CONFIGURATION[
        "distribution_manifest_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256": _CANONICAL_CONFIGURATION[
        "implementation_sha256"
    ],
    "LIVECONV_OPENVOICE_V2_RUNTIME_LOCK_SHA256": _CANONICAL_CONFIGURATION[
        "runtime_lock_sha256"
    ],
}

_ARTIFACT_BINDINGS = (
    ("LIVECONV_OPENVOICE_V2_CONFIG_PATH", "config_sha256"),
    ("LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH", "checkpoint_sha256"),
    ("LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH", "target_reference_sha256"),
    ("LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH", "worker_wheel_sha256"),
)


def validate_configuration(profile: ModelProfile) -> None:
    """Reject routes that differ from the retained offline preview identity."""

    if profile.profile_id not in _APPROVED_VARIANTS:
        raise ValueError(f"{profile.profile_id}: OpenVoice profile ID is not approved")
    if profile.runtime.adapter != "worker":
        raise ValueError(f"{profile.profile_id}: OpenVoice requires the worker adapter")
    if profile.runtime.worker_module != WORKER_MODULE:
        raise ValueError(
            f"{profile.profile_id}: OpenVoice worker module is not approved"
        )
    configuration = _configuration(profile.profile_id)
    if not _is_canonical_configuration(profile.runtime.configuration, configuration):
        raise ValueError(
            f"{profile.profile_id}: OpenVoice configuration differs from "
            "retained identity"
        )
    if profile.configuration_hash != _configuration_hash(configuration):
        raise ValueError(
            f"{profile.profile_id}: OpenVoice configuration hash does not match"
        )
    if profile.implementation_revision != _IMPLEMENTATION_REVISION:
        raise ValueError(
            f"{profile.profile_id}: OpenVoice implementation revision does not match"
        )
    if profile.weight_revision != _weight_revision(configuration):
        raise ValueError(
            f"{profile.profile_id}: OpenVoice weight revision does not match"
        )
    if profile.kind != "voice_conversion":
        raise ValueError(f"{profile.profile_id}: OpenVoice must be voice conversion")
    if profile.readiness != "ready":
        raise ValueError(
            f"{profile.profile_id}: OpenVoice technical preview must be ready"
        )
    if profile.streaming:
        raise ValueError(
            f"{profile.profile_id}: OpenVoice preview must remain non-live"
        )
    if profile.cancellation != "cooperative":
        raise ValueError(
            f"{profile.profile_id}: OpenVoice preview requires cooperative cancellation"
        )
    if profile.frame_ms != _FRAME_MS:
        raise ValueError(f"{profile.profile_id}: OpenVoice requires 20 ms frames")
    if profile.minimum_context_ms != _MINIMUM_INPUT_FRAMES * _FRAME_MS:
        raise ValueError(
            f"{profile.profile_id}: OpenVoice requires exactly 60 ms minimum context"
        )
    if profile.input_sample_rates != [48_000] or profile.output_sample_rates != [
        48_000
    ]:
        raise ValueError(f"{profile.profile_id}: OpenVoice requires 48 kHz PCM")
    if profile.voice_requirement != "pretrained_voice":
        raise ValueError(
            f"{profile.profile_id}: OpenVoice requires the fixed pretrained voice"
        )
    if profile.resource_class != "gpu":
        raise ValueError(f"{profile.profile_id}: OpenVoice requires the GPU class")
    promotion = profile.promotion
    if promotion is not None and (
        promotion.status != "technical_validation"
        or promotion.pack_id != "openvoice-v2"
        or promotion.evidence_sha256 != _PROMOTION_EVIDENCE_SHA256
    ):
        raise ValueError(
            f"{profile.profile_id}: OpenVoice remains technical-validation only"
        )
    _worker_endpoint(profile)


def build_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    """Build OpenVoice's fixed isolated command and allowlisted environment."""

    del queue_budget_ms
    validate_configuration(profile)
    endpoint = _worker_endpoint(profile)
    configuration = _configuration(profile.profile_id)
    environment = _environment(profile, configuration)
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
        command=(str(endpoint), "-I", "-m", WORKER_MODULE),
        cwd=Path("/tmp"),
        environment=environment,
        implementation_revision=_IMPLEMENTATION_REVISION,
        weight_revision=_weight_revision(configuration),
        frame_ms=_FRAME_MS,
        queue_budget_ms=_QUEUE_BUDGET_MS,
        startup_timeout_ms=max(60_000, profile.timeouts.first_output_ms),
        first_output_timeout_ms=profile.timeouts.first_output_ms,
        stall_timeout_ms=profile.timeouts.stall_ms,
        cancel_timeout_ms=max(
            2_000,
            min(profile.timeouts.first_output_ms, profile.timeouts.stall_ms),
        ),
        close_grace_ms=5_000,
        terminate_grace_ms=1_000,
        restart_limit=0,
        restart_window_ms=60_000,
        artifacts=artifacts,
    )


def delivery_mode(_profile: ModelProfile) -> Literal["end_buffered"]:
    return "end_buffered"


def queue_capacity_frames(_profile: ModelProfile, _queue_budget_ms: int) -> int:
    return _QUEUE_CAPACITY_FRAMES


def _configuration(profile_id: str) -> dict[str, float | int | str]:
    try:
        target_reference_sha256, tau = _APPROVED_VARIANTS[profile_id]
    except KeyError as exc:
        raise ValueError(f"{profile_id}: OpenVoice profile ID is not approved") from exc
    return {
        **_CANONICAL_CONFIGURATION,
        "target_reference_sha256": target_reference_sha256,
        "tau": tau,
    }


def _configuration_hash(configuration: dict[str, float | int | str]) -> str:
    encoded = json.dumps(
        configuration,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _weight_revision(configuration: dict[str, float | int | str]) -> str:
    identity = hashlib.sha256()
    for key in (
        "source_tree_sha256",
        "config_sha256",
        "checkpoint_sha256",
        "target_reference_sha256",
    ):
        value = configuration[key]
        assert isinstance(value, str)
        identity.update(bytes.fromhex(value))
    return f"sha256:{identity.hexdigest()}"


def target_environment_names(profile_id: str) -> tuple[str, str]:
    if profile_id == _PROFILE_ID:
        return (
            "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH",
            "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256",
        )
    if profile_id not in _APPROVED_VARIANTS:
        raise ValueError(f"{profile_id}: OpenVoice profile ID is not approved")
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
    prefix = f"LIVECONV_OPENVOICE_V2_VARIANT_{suffix}"
    return (
        f"{prefix}_TARGET_REFERENCE_PATH",
        f"{prefix}_TARGET_REFERENCE_SHA256",
    )


def _is_canonical_configuration(
    configuration: object,
    expected_configuration: dict[str, float | int | str],
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


def _environment(
    profile: ModelProfile,
    configuration: dict[str, float | int | str],
) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in _REQUIRED_ENVIRONMENT:
        source_name = name
        if name == "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH":
            source_name = target_environment_names(profile.profile_id)[0]
        elif name == "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256":
            source_name = target_environment_names(profile.profile_id)[1]
        value = os.environ.get(source_name)
        if not value:
            raise ValueError(f"required worker environment is missing: {source_name}")
        environment[name] = value
    for name, expected in _ENVIRONMENT_BINDINGS.items():
        if environment[name] != expected:
            raise ValueError(
                f"{profile.profile_id}: {name} does not match retained identity"
            )
    expected_target = configuration["target_reference_sha256"]
    if environment["LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256"] != expected_target:
        raise ValueError(
            f"{profile.profile_id}: target reference does not match approved identity"
        )
    environment.update(
        {
            **_OPTIONAL_ENVIRONMENT_BINDINGS,
            "LIVECONV_OPENVOICE_V2_TAU": str(configuration["tau"]),
        }
    )
    return environment


def _digest(configuration: dict[str, float | int | str], key: str) -> str:
    value = configuration[key]
    assert isinstance(value, str)
    return value
