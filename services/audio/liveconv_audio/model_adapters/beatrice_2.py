"""Trusted Gateway binding for the retained Beatrice 2 worker identity."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from workers.runtime import ArtifactSpec, WorkerProfile

if TYPE_CHECKING:
    from ..profiles import ModelProfile


WORKER_MODULE = "workers.adapters.beatrice_2.worker"
_IMPLEMENTATION_REVISION = "f34836de014b86956096878aecb8d3b17feaaa0b"
_WEIGHT_REVISION = (
    "sha256:14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a"
)
_CONFIGURATION_HASH = (
    "sha256:93dd010b64771604ab5750b5a8e00ce0dfe21e38e5ad67c746c166f838ca1fd6"
)
_FRAME_MS = 20
_QUEUE_CAPACITY_FRAMES = 25
_QUEUE_BUDGET_MS = _FRAME_MS * _QUEUE_CAPACITY_FRAMES

# This is the reviewed configuration payload, not a runtime material file.  Paths
# are intentionally absent: private artifacts are supplied only through the
# allowlisted environment below.
_CANONICAL_CONFIGURATION: dict[str, int | str] = {
    "adapter_revision": "beatrice-2-worker-v3",
    "batch_ms": 500,
    "converter_sha256": (
        "14ecdb01e51cf22b80664973daa3dedeeb0bada48bbf5262e58950c818cdcb1a"
    ),
    "device": "cuda",
    "distribution_manifest_sha256": (
        "d0970328bece0f9f2bdf4b9743de934637e8672fd62b9a06900cf70572375fb0"
    ),
    "executed_project_modules_sha256": (
        "1b5ac83a7b646fc989ebca11e7d1900c43ed921798fc055bd49d472aba8f28c3"
    ),
    "frame_ms": 20,
    "installed_distribution_inventory_sha256": (
        "03f841b61a980329e14387c1c45973ee5012b1d3480b4769a70c7c088b5ca034"
    ),
    "installed_record_sha256": (
        "af36716c39491bb6d9fa89d648a5cb00a967f42a61ca7be670e0fcf174eb6af3"
    ),
    "minimum_inference_ms": 60,
    "phone_sha256": "46e2d609825ace2158c83672cfc9cc1dcb3c2b7c8d294ee911fcb6840a592bae",
    "pitch_sha256": "174e5411009e0e4f6ee8a8c97c4cd2f646791eae1b9aa2b425acb797e0353ef4",
    "runtime_codec_sha256": (
        "6b6862c1d19959aa4fdb20a72d94cd0746fb710d6d612409fa109e18d79ea783"
    ),
    "runtime_lock_sha256": (
        "30d8099043f8ee8a550376b1b3228c726b76048b6aedefb239b091cad421197a"
    ),
    "sample_rate": 48_000,
    "schema": "liveconv-beatrice-2-worker-configuration-v2",
    "source_revision": "f34836de014b86956096878aecb8d3b17feaaa0b",
    "source_sha256": "c191a4fabdb63730b749fc2fbbe27384223fc27862a06a0d9db713bdee688e83",
    "source_tree_sha256": (
        "e92451a602413e03aefc4135a4d5b288c0a178b1ff7547b2d5943cdd83b150b0"
    ),
    "target_speaker_id": 37,
    "wheel_record_sha256": (
        "7b67024d180a58b11570d7510deb5f0179f97cb23d3f50d87ab609f095888a9f"
    ),
    "worker_wheel_sha256": (
        "cf9592ee3461ed3601f84472a6219ee3dec017f25d4ed31a55e93d245fd0b7bc"
    ),
}

_REQUIRED_ENVIRONMENT = (
    "LIVECONV_BEATRICE_SOURCE_ROOT",
    "LIVECONV_BEATRICE_SOURCE_REVISION",
    "LIVECONV_BEATRICE_SOURCE_MODULE",
    "LIVECONV_BEATRICE_SOURCE_SHA256",
    "LIVECONV_BEATRICE_SOURCE_TREE_SHA256",
    "LIVECONV_BEATRICE_PHONE_CHECKPOINT",
    "LIVECONV_BEATRICE_PHONE_SHA256",
    "LIVECONV_BEATRICE_PITCH_CHECKPOINT",
    "LIVECONV_BEATRICE_PITCH_SHA256",
    "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT",
    "LIVECONV_BEATRICE_CONVERTER_SHA256",
    "LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256",
    "LIVECONV_BEATRICE_WORKER_WHEEL",
    "LIVECONV_BEATRICE_WORKER_WHEEL_SHA256",
    "LIVECONV_BEATRICE_TARGET_SPEAKER_ID",
    "LIVECONV_BEATRICE_SAMPLE_RATE",
    "LIVECONV_BEATRICE_BATCH_MS",
    "LIVECONV_BEATRICE_DEVICE",
)

_ENVIRONMENT_BINDINGS = {
    "LIVECONV_BEATRICE_SOURCE_REVISION": _CANONICAL_CONFIGURATION["source_revision"],
    "LIVECONV_BEATRICE_SOURCE_SHA256": _CANONICAL_CONFIGURATION["source_sha256"],
    "LIVECONV_BEATRICE_SOURCE_TREE_SHA256": _CANONICAL_CONFIGURATION[
        "source_tree_sha256"
    ],
    "LIVECONV_BEATRICE_PHONE_SHA256": _CANONICAL_CONFIGURATION["phone_sha256"],
    "LIVECONV_BEATRICE_PITCH_SHA256": _CANONICAL_CONFIGURATION["pitch_sha256"],
    "LIVECONV_BEATRICE_CONVERTER_SHA256": _CANONICAL_CONFIGURATION["converter_sha256"],
    "LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256": _CANONICAL_CONFIGURATION[
        "runtime_lock_sha256"
    ],
    "LIVECONV_BEATRICE_WORKER_WHEEL_SHA256": _CANONICAL_CONFIGURATION[
        "worker_wheel_sha256"
    ],
    "LIVECONV_BEATRICE_TARGET_SPEAKER_ID": str(
        _CANONICAL_CONFIGURATION["target_speaker_id"]
    ),
    "LIVECONV_BEATRICE_SAMPLE_RATE": str(_CANONICAL_CONFIGURATION["sample_rate"]),
    "LIVECONV_BEATRICE_BATCH_MS": str(_CANONICAL_CONFIGURATION["batch_ms"]),
    "LIVECONV_BEATRICE_DEVICE": _CANONICAL_CONFIGURATION["device"],
}

_ARTIFACT_BINDINGS = (
    ("LIVECONV_BEATRICE_SOURCE_MODULE", "source_sha256"),
    ("LIVECONV_BEATRICE_PHONE_CHECKPOINT", "phone_sha256"),
    ("LIVECONV_BEATRICE_PITCH_CHECKPOINT", "pitch_sha256"),
    ("LIVECONV_BEATRICE_CONVERTER_CHECKPOINT", "converter_sha256"),
    ("LIVECONV_BEATRICE_WORKER_WHEEL", "worker_wheel_sha256"),
)


def validate_configuration(profile: ModelProfile) -> None:
    """Reject every route that is not the retained Beatrice 2 identity."""

    if profile.runtime.adapter != "worker":
        raise ValueError(f"{profile.profile_id}: Beatrice requires the worker adapter")
    if profile.runtime.worker_module != WORKER_MODULE:
        raise ValueError(
            f"{profile.profile_id}: Beatrice worker module is not approved"
        )
    if not _is_canonical_configuration(profile.runtime.configuration):
        raise ValueError(
            f"{profile.profile_id}: Beatrice configuration differs from "
            "retained identity"
        )
    if profile.configuration_hash != _CONFIGURATION_HASH:
        raise ValueError(
            f"{profile.profile_id}: Beatrice configuration hash does not match"
        )
    if profile.implementation_revision != _IMPLEMENTATION_REVISION:
        raise ValueError(
            f"{profile.profile_id}: Beatrice implementation revision does not match"
        )
    if profile.weight_revision != _WEIGHT_REVISION:
        raise ValueError(
            f"{profile.profile_id}: Beatrice weight revision does not match"
        )
    if profile.kind != "voice_conversion":
        raise ValueError(f"{profile.profile_id}: Beatrice must be voice conversion")
    if not profile.streaming or profile.frame_ms != _FRAME_MS:
        raise ValueError(f"{profile.profile_id}: Beatrice requires 20 ms streaming")
    if profile.input_sample_rates != [48_000] or profile.output_sample_rates != [
        48_000
    ]:
        raise ValueError(f"{profile.profile_id}: Beatrice requires 48 kHz PCM")
    _worker_endpoint(profile)


def build_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    """Build the static command and private child environment for Beatrice."""

    del queue_budget_ms
    validate_configuration(profile)
    endpoint = _worker_endpoint(profile)
    environment = _environment(profile)
    artifacts = tuple(
        ArtifactSpec(env_var=env_var, sha256=_digest(digest_key))
        for env_var, digest_key in _ARTIFACT_BINDINGS
    )
    return WorkerProfile(
        profile_id=profile.profile_id,
        pipeline_id=pipeline_id,
        configuration_hash=_CONFIGURATION_HASH,
        command=(str(endpoint), "-I", "-B", "-m", WORKER_MODULE),
        cwd=Path("/tmp"),
        environment=environment,
        implementation_revision=_IMPLEMENTATION_REVISION,
        weight_revision=_WEIGHT_REVISION,
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


def delivery_mode(_profile: ModelProfile) -> Literal["live_frame_echo"]:
    return "live_frame_echo"


def queue_capacity_frames(_profile: ModelProfile, _queue_budget_ms: int) -> int:
    return _QUEUE_CAPACITY_FRAMES


def _is_canonical_configuration(configuration: object) -> bool:
    if not isinstance(configuration, dict) or set(configuration) != set(
        _CANONICAL_CONFIGURATION
    ):
        return False
    return all(
        type(configuration[key]) is type(expected) and configuration[key] == expected
        for key, expected in _CANONICAL_CONFIGURATION.items()
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


def _environment(profile: ModelProfile) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in _REQUIRED_ENVIRONMENT:
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"required worker environment is missing: {name}")
        environment[name] = value
    for name, expected in _ENVIRONMENT_BINDINGS.items():
        if environment[name] != expected:
            raise ValueError(
                f"{profile.profile_id}: {name} does not match retained identity"
            )
    return environment


def _digest(key: str) -> str:
    value = _CANONICAL_CONFIGURATION[key]
    assert isinstance(value, str)
    return value
