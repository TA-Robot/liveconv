from __future__ import annotations

import math
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from workers.runtime import ArtifactSpec, WorkerProfile

from .model_adapters import beatrice_2, meanvc2, openvoice_v2, x_vc

if TYPE_CHECKING:
    from .profiles import ModelProfile


DeliveryMode = Literal["live_frame_echo", "end_buffered"]
_RVC_WORKER_MODULE = "workers.adapters.rvc_v2.worker"

_RVC_CONFIGURATION_KEYS = {
    "worker_module",
    "adapter_revision",
    "source_revision",
    "artifacts",
    "settings",
}

_RVC_ARTIFACT_KEYS = {
    "checkpoint_sha256",
    "index_sha256",
    "hubert_config_sha256",
    "hubert_preprocessor_sha256",
    "hubert_weights_sha256",
    "rmvpe_sha256",
    "worker_wheel_sha256",
    "worker_wheel_record_sha256",
    "worker_module_sha256",
    "backend_module_sha256",
    "network_isolation_module_sha256",
    "requirements_lock_sha256",
}

_RVC_RETAINED_SETTING_KEYS = frozenset(
    {
        "speaker_id",
        "pitch_shift",
        "f0_method",
        "index_rate",
        "rms_mix_rate",
        "sample_rate",
        "block_ms",
        "crossfade_ms",
        "context_ms",
        "frame_ms",
        "inference_batch_frames",
        "queue_capacity_frames",
        "resident_capacity_frames",
        "formant_shift",
        "threshold_dbfs",
    }
)
_RVC_QUALITY_SETTING_KEYS = _RVC_RETAINED_SETTING_KEYS | {"input_gain_db"}
_RVC_SEEDED_SETTING_KEYS = _RVC_RETAINED_SETTING_KEYS | {"inference_seed"}
_RVC_SEEDED_QUALITY_SETTING_KEYS = _RVC_QUALITY_SETTING_KEYS | {
    "inference_seed"
}

_RVC_REQUIRED_ENVIRONMENT = (
    "LIVECONV_RVC_SOURCE_ROOT",
    "LIVECONV_RVC_SOURCE_REVISION",
    "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
    "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256",
)

_RVC_RETAINED_PROFILE_ID = "vc.rvc.synthetic-ja.v1"

_RVC_AUXILIARY_ARTIFACTS = (
    ("hubert_config_sha256", "assets/hubert_base/config.json"),
    (
        "hubert_preprocessor_sha256",
        "assets/hubert_base/preprocessor_config.json",
    ),
    ("hubert_weights_sha256", "assets/hubert_base/pytorch_model.bin"),
    ("rmvpe_sha256", "assets/rmvpe/rmvpe.pt"),
)


@dataclass(frozen=True)
class _AdapterRegistration:
    """Static, reviewed adapter behavior for one runtime route.

    A model leaf may add one value to the static tables below. It must provide
    validation, a trusted worker profile builder, a delivery mode, and a bounded
    queue capacity; profile configuration never supplies executable behavior.
    """

    runtime_adapter: str
    worker_module: str | None
    expected_pack_id: str | None
    validate_configuration: Callable[[ModelProfile], None]
    build_worker_profile: Callable[[ModelProfile, str, int], WorkerProfile]
    delivery_mode: Callable[[ModelProfile], DeliveryMode]
    queue_capacity_frames: Callable[[ModelProfile, int], int]


def validate_profile_adapter(profile: ModelProfile) -> None:
    """Validate only the reviewed runtime route selected by this profile."""

    _registration_for_profile(profile).validate_configuration(profile)


def delivery_mode_for_profile(profile: ModelProfile) -> DeliveryMode:
    return _registration_for_profile(profile).delivery_mode(profile)


def buffered_input_capacity_frames(profile: ModelProfile, queue_budget_ms: int) -> int:
    """Return the registration-owned cap used before buffered output begins."""

    capacity = _registration_for_profile(profile).queue_capacity_frames(
        profile, queue_budget_ms
    )
    if not 1 <= capacity <= 25:
        raise ValueError(f"{profile.profile_id}: adapter queue capacity is invalid")
    return capacity


def worker_profile_for(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    """Construct a worker profile from reviewed registration code only."""

    registration = _registration_for_profile(profile)
    capacity = registration.queue_capacity_frames(profile, queue_budget_ms)
    worker_profile = registration.build_worker_profile(
        profile,
        pipeline_id,
        queue_budget_ms,
    )
    if (
        worker_profile.profile_id != profile.profile_id
        or worker_profile.pipeline_id != pipeline_id
        or worker_profile.configuration_hash != profile.configuration_hash
        or worker_profile.implementation_revision != profile.implementation_revision
        or worker_profile.weight_revision != profile.weight_revision
        or worker_profile.frame_ms != profile.frame_ms
        or worker_profile.input_capacity_frames != capacity
    ):
        raise ValueError(
            f"{profile.profile_id}: worker profile differs from adapter registration"
        )
    return worker_profile


def _registration_for_profile(profile: ModelProfile) -> _AdapterRegistration:
    runtime = profile.runtime
    if runtime.adapter == "worker":
        module = _worker_module_for_profile(profile)
        if not isinstance(module, str):
            raise ValueError(f"{profile.profile_id}: worker module is not approved")
        registration = _WORKER_REGISTRATIONS.get(module)
        if registration is None:
            raise ValueError(f"{profile.profile_id}: worker module is not approved")
        _validate_registration_promotion(profile, registration)
        return registration
    registration = _BUILTIN_REGISTRATIONS.get(runtime.adapter)
    if registration is None:
        raise ValueError(f"{profile.profile_id}: no builtin worker is available")
    return registration


def _validate_registration_promotion(
    profile: ModelProfile,
    registration: _AdapterRegistration,
) -> None:
    promotion = profile.promotion
    if (
        registration.expected_pack_id is None
        or promotion is None
        or promotion.pack_id != registration.expected_pack_id
    ):
        expected = registration.expected_pack_id or "no model pack"
        raise ValueError(
            f"{profile.profile_id}: worker registration requires pack {expected}"
        )


def _worker_module_for_profile(profile: ModelProfile) -> object:
    """Use the trusted runtime field, with an RVC-compatible legacy fallback."""

    configured_module = profile.runtime.worker_module
    legacy_module = profile.runtime.configuration.get("worker_module")
    if configured_module is not None:
        if legacy_module is not None and legacy_module != configured_module:
            raise ValueError(f"{profile.profile_id}: worker module binding conflicts")
        return configured_module
    return legacy_module


def _live_or_buffered(profile: ModelProfile) -> DeliveryMode:
    return "live_frame_echo" if profile.streaming else "end_buffered"


def _live_frame_echo(_profile: ModelProfile) -> DeliveryMode:
    return "live_frame_echo"


def _validate_passthrough(profile: ModelProfile) -> None:
    _validate_builtin_runtime(profile)
    if profile.runtime.configuration:
        raise ValueError(
            f"{profile.profile_id}: passthrough configuration must be empty"
        )


def _validate_gain(profile: ModelProfile) -> None:
    _validate_builtin_runtime(profile)
    configuration = profile.runtime.configuration
    if set(configuration) != {"gain"}:
        raise ValueError(f"{profile.profile_id}: gain requires only configuration.gain")
    gain = configuration["gain"]
    if isinstance(gain, bool) or not isinstance(gain, (int, float)):
        raise ValueError(f"{profile.profile_id}: gain must be numeric")
    if not math.isfinite(gain) or not 0 <= gain <= 1:
        raise ValueError(
            f"{profile.profile_id}: gain must be finite and between 0 and 1"
        )


def _validate_builtin_runtime(profile: ModelProfile) -> None:
    if profile.runtime.worker_module is not None:
        raise ValueError(
            f"{profile.profile_id}: worker_module is only valid for worker adapters"
        )


def _builtin_queue_capacity(profile: ModelProfile, queue_budget_ms: int) -> int:
    return max(1, min(25, queue_budget_ms // profile.frame_ms))


def _builtin_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
    *,
    mode: Literal["passthrough", "gain"],
) -> WorkerProfile:
    capacity_frames = _builtin_queue_capacity(profile, queue_budget_ms)
    command = [
        sys.executable,
        str(Path(__file__).with_name("builtin_worker.py")),
        "--mode",
        mode,
        "--implementation-revision",
        profile.implementation_revision,
        "--capacity-frames",
        str(capacity_frames),
    ]
    if profile.weight_revision is not None:
        command.extend(("--weight-revision", profile.weight_revision))
    if mode == "gain":
        command.extend(("--gain", str(profile.runtime.configuration["gain"])))

    cancel_timeout_ms = max(
        50,
        min(profile.timeouts.first_output_ms, profile.timeouts.stall_ms),
    )
    close_grace_ms = max(50, min(250, profile.timeouts.stall_ms))
    return WorkerProfile(
        profile_id=profile.profile_id,
        pipeline_id=pipeline_id,
        configuration_hash=profile.configuration_hash,
        command=tuple(command),
        cwd=Path(__file__).resolve().parent,
        environment={},
        implementation_revision=profile.implementation_revision,
        weight_revision=profile.weight_revision,
        frame_ms=profile.frame_ms,
        queue_budget_ms=capacity_frames * profile.frame_ms,
        startup_timeout_ms=max(1_000, profile.timeouts.first_output_ms),
        first_output_timeout_ms=profile.timeouts.first_output_ms,
        stall_timeout_ms=profile.timeouts.stall_ms,
        cancel_timeout_ms=cancel_timeout_ms,
        close_grace_ms=close_grace_ms,
        terminate_grace_ms=100,
        restart_limit=0,
        restart_window_ms=60_000,
    )


def _passthrough_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    return _builtin_worker_profile(
        profile, pipeline_id, queue_budget_ms, mode="passthrough"
    )


def _gain_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    return _builtin_worker_profile(profile, pipeline_id, queue_budget_ms, mode="gain")


def _validate_rvc(profile: ModelProfile) -> None:
    endpoint_value = profile.runtime.worker_endpoint
    if endpoint_value is None or not Path(endpoint_value).is_absolute():
        raise ValueError(
            f"{profile.profile_id}: worker_endpoint must be an absolute path"
        )
    endpoint = Path(endpoint_value)
    if not endpoint.is_file() or not endpoint.stat().st_mode & 0o111:
        raise ValueError(
            f"{profile.profile_id}: worker_endpoint must be an executable file"
        )

    configuration = profile.runtime.configuration
    if set(configuration) != _rvc_configuration_keys(profile):
        raise ValueError(f"{profile.profile_id}: worker configuration shape is invalid")
    if _worker_module_for_profile(profile) != _RVC_WORKER_MODULE:
        raise ValueError(f"{profile.profile_id}: worker module is not approved")
    adapter_revision = configuration["adapter_revision"]
    source_revision = configuration["source_revision"]
    if not isinstance(adapter_revision, str) or not isinstance(source_revision, str):
        raise ValueError(f"{profile.profile_id}: worker revisions must be strings")
    artifacts = configuration["artifacts"]
    settings = configuration["settings"]
    if not isinstance(artifacts, dict) or set(artifacts) != _RVC_ARTIFACT_KEYS:
        raise ValueError(f"{profile.profile_id}: RVC artifacts are incomplete")
    if not _has_approved_rvc_settings(settings):
        raise ValueError(f"{profile.profile_id}: RVC settings are incomplete")
    if settings["frame_ms"] != profile.frame_ms:
        raise ValueError(f"{profile.profile_id}: RVC frame duration differs")
    if settings["inference_batch_frames"] != 25:
        raise ValueError(f"{profile.profile_id}: RVC inference batch must be 25 frames")
    if settings["queue_capacity_frames"] != 25:
        raise ValueError(
            f"{profile.profile_id}: RVC worker queue capacity must be 25 frames"
        )
    if settings["resident_capacity_frames"] != 50:
        raise ValueError(
            f"{profile.profile_id}: RVC resident capacity must be 50 frames"
        )


def _rvc_queue_capacity(profile: ModelProfile, _queue_budget_ms: int) -> int:
    settings = profile.runtime.configuration["settings"]
    if not isinstance(settings, dict):
        raise ValueError(f"{profile.profile_id}: RVC settings are incomplete")
    capacity = settings["queue_capacity_frames"]
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise ValueError(f"{profile.profile_id}: RVC worker queue capacity is invalid")
    return capacity


def _rvc_worker_profile(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerProfile:
    del queue_budget_ms
    _validate_rvc(profile)
    endpoint_value = profile.runtime.worker_endpoint
    assert endpoint_value is not None
    environment, artifacts = _rvc_environment(profile, profile.runtime.configuration)
    capacity_frames = _rvc_queue_capacity(profile, 0)
    return WorkerProfile(
        profile_id=profile.profile_id,
        pipeline_id=pipeline_id,
        configuration_hash=profile.configuration_hash,
        command=(str(Path(endpoint_value)), "-m", _RVC_WORKER_MODULE),
        cwd=Path("/tmp"),
        environment=environment,
        implementation_revision=profile.implementation_revision,
        weight_revision=profile.weight_revision,
        frame_ms=profile.frame_ms,
        queue_budget_ms=capacity_frames * profile.frame_ms,
        # First launch may populate deterministic compiler caches for the pinned
        # model runtime; keep it bounded but distinct from the audio SLA.
        startup_timeout_ms=max(180_000, profile.timeouts.first_output_ms),
        first_output_timeout_ms=profile.timeouts.first_output_ms,
        stall_timeout_ms=profile.timeouts.stall_ms,
        cancel_timeout_ms=max(
            100,
            min(profile.timeouts.first_output_ms, profile.timeouts.stall_ms),
        ),
        close_grace_ms=250,
        terminate_grace_ms=250,
        restart_limit=0,
        restart_window_ms=60_000,
        artifacts=artifacts,
    )


def _required_environment(names: tuple[str, ...]) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in names:
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"required worker environment is missing: {name}")
        environment[name] = value
    return environment


def _rvc_model_environment_names(profile_id: str) -> dict[str, str]:
    if profile_id == _RVC_RETAINED_PROFILE_ID:
        prefix = "LIVECONV_RVC_V2"
    else:
        suffix = re.sub(r"[^A-Za-z0-9]+", "_", profile_id).strip("_").upper()
        prefix = f"LIVECONV_RVC_VARIANT_{suffix}"
    return {
        "checkpoint_path": f"{prefix}_CHECKPOINT_PATH",
        "checkpoint_sha256": f"{prefix}_CHECKPOINT_SHA256",
        "index_path": f"{prefix}_INDEX_PATH",
        "index_sha256": f"{prefix}_INDEX_SHA256",
    }


def _rvc_environment(
    profile: ModelProfile,
    configuration: dict[str, object],
) -> tuple[dict[str, str], tuple[ArtifactSpec, ...]]:
    """Build RVC's private process environment from fixed registration bindings."""

    _validate_rvc_configuration(profile, configuration)
    artifacts_value = configuration["artifacts"]
    settings_value = configuration["settings"]
    source_revision = configuration["source_revision"]
    adapter_revision = configuration["adapter_revision"]
    assert isinstance(artifacts_value, dict)
    assert isinstance(settings_value, dict)
    assert isinstance(source_revision, str)
    assert isinstance(adapter_revision, str)
    artifacts_config = artifacts_value
    settings = settings_value
    environment = _required_environment(_RVC_REQUIRED_ENVIRONMENT)
    model_names = _rvc_model_environment_names(profile.profile_id)
    model_environment = _required_environment(
        (model_names["checkpoint_path"], model_names["checkpoint_sha256"])
    )
    environment["LIVECONV_RVC_V2_CHECKPOINT_PATH"] = model_environment[
        model_names["checkpoint_path"]
    ]
    environment["LIVECONV_RVC_V2_CHECKPOINT_SHA256"] = model_environment[
        model_names["checkpoint_sha256"]
    ]
    if environment["LIVECONV_RVC_SOURCE_REVISION"] != source_revision:
        raise ValueError(f"{profile.profile_id}: RVC source revision does not match")
    expected_implementation = f"{adapter_revision}+rvc.{source_revision}"
    if profile.implementation_revision != expected_implementation:
        raise ValueError(
            f"{profile.profile_id}: RVC implementation revision does not match"
        )
    mapping = {
        "speaker_id": "LIVECONV_RVC_V2_SPEAKER_ID",
        "pitch_shift": "LIVECONV_RVC_V2_PITCH_SHIFT",
        "f0_method": "LIVECONV_RVC_V2_F0_METHOD",
        "index_rate": "LIVECONV_RVC_V2_INDEX_RATE",
        "rms_mix_rate": "LIVECONV_RVC_V2_RMS_MIX_RATE",
        "sample_rate": "LIVECONV_RVC_V2_SAMPLE_RATE",
        "block_ms": "LIVECONV_RVC_V2_BLOCK_MS",
        "crossfade_ms": "LIVECONV_RVC_V2_CROSSFADE_MS",
        "context_ms": "LIVECONV_RVC_V2_CONTEXT_MS",
        "threshold_dbfs": "LIVECONV_RVC_V2_THRESHOLD_DBFS",
    }
    if "input_gain_db" in settings:
        mapping["input_gain_db"] = "LIVECONV_RVC_V2_INPUT_GAIN_DB"
    if "inference_seed" in settings:
        mapping["inference_seed"] = "LIVECONV_RVC_V2_INFERENCE_SEED"
    for key, name in mapping.items():
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{profile.profile_id}: RVC setting {key} is invalid")
        environment[name] = str(value)

    checkpoint_sha = environment["LIVECONV_RVC_V2_CHECKPOINT_SHA256"].lower()
    if checkpoint_sha != artifacts_config.get("checkpoint_sha256"):
        raise ValueError(f"{profile.profile_id}: RVC checkpoint digest does not match")
    if profile.weight_revision != f"sha256:{checkpoint_sha}":
        raise ValueError(f"{profile.profile_id}: RVC weight revision does not match")
    artifacts = [
        ArtifactSpec(
            env_var="LIVECONV_RVC_V2_CHECKPOINT_PATH",
            sha256=checkpoint_sha,
        ),
        ArtifactSpec(
            env_var="LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
            sha256=environment["LIVECONV_RVC_V2_WORKER_WHEEL_SHA256"].lower(),
        ),
    ]
    if environment[
        "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256"
    ].lower() != artifacts_config.get("worker_wheel_sha256"):
        raise ValueError(
            f"{profile.profile_id}: RVC worker wheel digest does not match"
        )
    index_path = os.environ.get(model_names["index_path"])
    index_sha = os.environ.get(model_names["index_sha256"])
    if index_path or index_sha:
        if not index_path or not index_sha:
            raise ValueError(f"{profile.profile_id}: RVC index binding is incomplete")
        environment["LIVECONV_RVC_V2_INDEX_PATH"] = index_path
        environment["LIVECONV_RVC_V2_INDEX_SHA256"] = index_sha.lower()
        if index_sha.lower() != artifacts_config.get("index_sha256"):
            raise ValueError(f"{profile.profile_id}: RVC index digest does not match")
        artifacts.append(
            ArtifactSpec(
                env_var="LIVECONV_RVC_V2_INDEX_PATH",
                sha256=index_sha.lower(),
            )
        )
    elif float(settings["index_rate"]) != 0 or artifacts_config.get("index_sha256"):
        raise ValueError(f"{profile.profile_id}: RVC index is required")

    source_root = Path(environment["LIVECONV_RVC_SOURCE_ROOT"])
    for index, (key, relative_path) in enumerate(_RVC_AUXILIARY_ARTIFACTS, start=1):
        digest = artifacts_config.get(key)
        if not isinstance(digest, str):
            raise ValueError(f"{profile.profile_id}: RVC {key} is invalid")
        env_var = f"LIVECONV_RVC_VERIFIED_ARTIFACT_{index}"
        environment[env_var] = str(source_root / relative_path)
        artifacts.append(ArtifactSpec(env_var=env_var, sha256=digest))
    return environment, tuple(artifacts)


def _validate_rvc_configuration(
    profile: ModelProfile,
    configuration: dict[str, object],
) -> None:
    if set(configuration) != _rvc_configuration_keys(profile):
        raise ValueError(f"{profile.profile_id}: worker configuration shape is invalid")
    if _worker_module_for_profile(profile) != _RVC_WORKER_MODULE:
        raise ValueError(f"{profile.profile_id}: worker module is not approved")
    if not isinstance(configuration.get("adapter_revision"), str) or not isinstance(
        configuration.get("source_revision"), str
    ):
        raise ValueError(f"{profile.profile_id}: worker revisions must be strings")
    artifacts = configuration.get("artifacts")
    settings = configuration.get("settings")
    if not isinstance(artifacts, dict) or set(artifacts) != _RVC_ARTIFACT_KEYS:
        raise ValueError(f"{profile.profile_id}: RVC artifacts are incomplete")
    if not _has_approved_rvc_settings(settings):
        raise ValueError(f"{profile.profile_id}: RVC settings are incomplete")


def _has_approved_rvc_settings(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return frozenset(value) in {
        _RVC_RETAINED_SETTING_KEYS,
        _RVC_QUALITY_SETTING_KEYS,
        _RVC_SEEDED_SETTING_KEYS,
        _RVC_SEEDED_QUALITY_SETTING_KEYS,
    }


def _rvc_configuration_keys(profile: ModelProfile) -> set[str]:
    if profile.runtime.worker_module is None:
        return _RVC_CONFIGURATION_KEYS
    return _RVC_CONFIGURATION_KEYS - {"worker_module"}


_BUILTIN_REGISTRATIONS = {
    "passthrough": _AdapterRegistration(
        runtime_adapter="passthrough",
        worker_module=None,
        expected_pack_id=None,
        validate_configuration=_validate_passthrough,
        build_worker_profile=_passthrough_worker_profile,
        delivery_mode=_live_or_buffered,
        queue_capacity_frames=_builtin_queue_capacity,
    ),
    "gain": _AdapterRegistration(
        runtime_adapter="gain",
        worker_module=None,
        expected_pack_id=None,
        validate_configuration=_validate_gain,
        build_worker_profile=_gain_worker_profile,
        delivery_mode=_live_or_buffered,
        queue_capacity_frames=_builtin_queue_capacity,
    ),
}

_WORKER_REGISTRATIONS = {
    meanvc2.WORKER_MODULE: _AdapterRegistration(
        runtime_adapter="worker",
        worker_module=meanvc2.WORKER_MODULE,
        expected_pack_id="meanvc2",
        validate_configuration=meanvc2.validate_configuration,
        build_worker_profile=meanvc2.build_worker_profile,
        delivery_mode=meanvc2.delivery_mode,
        queue_capacity_frames=meanvc2.queue_capacity_frames,
    ),
    openvoice_v2.WORKER_MODULE: _AdapterRegistration(
        runtime_adapter="worker",
        worker_module=openvoice_v2.WORKER_MODULE,
        expected_pack_id="openvoice-v2",
        validate_configuration=openvoice_v2.validate_configuration,
        build_worker_profile=openvoice_v2.build_worker_profile,
        delivery_mode=openvoice_v2.delivery_mode,
        queue_capacity_frames=openvoice_v2.queue_capacity_frames,
    ),
    beatrice_2.WORKER_MODULE: _AdapterRegistration(
        runtime_adapter="worker",
        worker_module=beatrice_2.WORKER_MODULE,
        expected_pack_id="beatrice-2",
        validate_configuration=beatrice_2.validate_configuration,
        build_worker_profile=beatrice_2.build_worker_profile,
        delivery_mode=beatrice_2.delivery_mode,
        queue_capacity_frames=beatrice_2.queue_capacity_frames,
    ),
    x_vc.WORKER_MODULE: _AdapterRegistration(
        runtime_adapter="worker",
        worker_module=x_vc.WORKER_MODULE,
        expected_pack_id="x-vc",
        validate_configuration=x_vc.validate_configuration,
        build_worker_profile=x_vc.build_worker_profile,
        delivery_mode=x_vc.delivery_mode,
        queue_capacity_frames=x_vc.queue_capacity_frames,
    ),
    _RVC_WORKER_MODULE: _AdapterRegistration(
        runtime_adapter="worker",
        worker_module=_RVC_WORKER_MODULE,
        expected_pack_id="rvc-v2",
        validate_configuration=_validate_rvc,
        build_worker_profile=_rvc_worker_profile,
        delivery_mode=_live_frame_echo,
        queue_capacity_frames=_rvc_queue_capacity,
    ),
}
