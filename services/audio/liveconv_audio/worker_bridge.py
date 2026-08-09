from __future__ import annotations

import asyncio
import contextlib
import math
import os
import sys
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from liveconv_protocol import (
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)

from workers.runtime import ArtifactSpec, AudioFrame, WorkerProfile, WorkerSupervisor
from workers.runtime.errors import WorkerRuntimeError

from .profiles import ModelProfile

WorkerSupervisorFactory = Callable[
    [ModelProfile, str, int],
    WorkerSupervisor,
]


def builtin_supervisor_factory(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerSupervisor:
    adapter = profile.runtime.adapter
    if adapter == "worker":
        return _external_supervisor(profile, pipeline_id, queue_budget_ms)
    if adapter not in {"passthrough", "gain"}:
        raise ValueError(f"{profile.profile_id}: no builtin worker is available")

    # The public ingress budget can hold a longer burst, but every worker keeps
    # the private protocol's 500 ms cap.
    bounded_queue_ms = max(
        profile.frame_ms,
        min(500, (queue_budget_ms // profile.frame_ms) * profile.frame_ms),
    )
    worker_entrypoint = Path(__file__).with_name("builtin_worker.py")
    command = [
        sys.executable,
        str(worker_entrypoint),
        "--mode",
        adapter,
        "--implementation-revision",
        profile.implementation_revision,
        "--capacity-frames",
        str(bounded_queue_ms // profile.frame_ms),
    ]
    if profile.weight_revision is not None:
        command.extend(("--weight-revision", profile.weight_revision))
    if adapter == "gain":
        command.extend(("--gain", str(profile.runtime.configuration["gain"])))

    cancel_timeout_ms = max(
        50,
        min(profile.timeouts.first_output_ms, profile.timeouts.stall_ms),
    )
    close_grace_ms = max(50, min(250, profile.timeouts.stall_ms))
    worker_profile = WorkerProfile(
        profile_id=profile.profile_id,
        pipeline_id=pipeline_id,
        configuration_hash=profile.configuration_hash,
        command=tuple(command),
        cwd=Path(__file__).resolve().parent,
        environment={},
        implementation_revision=profile.implementation_revision,
        weight_revision=profile.weight_revision,
        frame_ms=profile.frame_ms,
        queue_budget_ms=bounded_queue_ms,
        startup_timeout_ms=max(1_000, profile.timeouts.first_output_ms),
        first_output_timeout_ms=profile.timeouts.first_output_ms,
        stall_timeout_ms=profile.timeouts.stall_ms,
        cancel_timeout_ms=cancel_timeout_ms,
        close_grace_ms=close_grace_ms,
        terminate_grace_ms=100,
        restart_limit=0,
        restart_window_ms=60_000,
    )
    return WorkerSupervisor(worker_profile)


def _external_supervisor(
    profile: ModelProfile,
    pipeline_id: str,
    queue_budget_ms: int,
) -> WorkerSupervisor:
    endpoint_value = profile.runtime.worker_endpoint
    if endpoint_value is None:
        raise ValueError(f"{profile.profile_id}: worker endpoint is missing")
    endpoint = Path(endpoint_value)
    if not endpoint.is_absolute() or not endpoint.is_file():
        raise ValueError(f"{profile.profile_id}: worker endpoint is unavailable")
    if not os.access(endpoint, os.X_OK):
        raise ValueError(f"{profile.profile_id}: worker endpoint is not executable")
    configuration = profile.runtime.configuration
    module = configuration["worker_module"]
    settings = configuration["settings"]
    if not isinstance(module, str) or not isinstance(settings, dict):
        raise ValueError(f"{profile.profile_id}: worker configuration is invalid")

    if module == "workers.adapters.rvc_v2.worker":
        environment, artifacts = _rvc_environment(profile, configuration)
    else:
        raise ValueError(f"{profile.profile_id}: worker module is not integrated")

    del queue_budget_ms
    bounded_queue_ms = int(settings["queue_capacity_frames"]) * profile.frame_ms
    return WorkerSupervisor(
        WorkerProfile(
            profile_id=profile.profile_id,
            pipeline_id=pipeline_id,
            configuration_hash=profile.configuration_hash,
            command=(str(endpoint), "-m", module),
            cwd=Path("/"),
            environment=environment,
            implementation_revision=profile.implementation_revision,
            weight_revision=profile.weight_revision,
            frame_ms=profile.frame_ms,
            queue_budget_ms=bounded_queue_ms,
            # First launch may populate deterministic compiler caches for the
            # pinned model runtime; keep it bounded but distinct from audio SLA.
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
    )


def _required_environment(names: tuple[str, ...]) -> dict[str, str]:
    environment: dict[str, str] = {}
    for name in names:
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"required worker environment is missing: {name}")
        environment[name] = value
    return environment


def _rvc_environment(
    profile: ModelProfile,
    configuration: dict[str, object],
) -> tuple[dict[str, str], tuple[ArtifactSpec, ...]]:
    artifacts_value = configuration.get("artifacts")
    settings_value = configuration.get("settings")
    source_revision = configuration.get("source_revision")
    adapter_revision = configuration.get("adapter_revision")
    if (
        not isinstance(artifacts_value, dict)
        or not isinstance(settings_value, dict)
        or not isinstance(source_revision, str)
        or not isinstance(adapter_revision, str)
    ):
        raise ValueError(f"{profile.profile_id}: RVC configuration is invalid")
    artifacts_config = artifacts_value
    settings = settings_value
    required_settings = {
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
    if set(settings) != required_settings:
        raise ValueError(f"{profile.profile_id}: RVC settings are incomplete")
    environment = _required_environment(
        (
            "LIVECONV_RVC_SOURCE_ROOT",
            "LIVECONV_RVC_SOURCE_REVISION",
            "LIVECONV_RVC_V2_CHECKPOINT_PATH",
            "LIVECONV_RVC_V2_CHECKPOINT_SHA256",
            "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
            "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256",
        )
    )
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
    }
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
    index_path = os.environ.get("LIVECONV_RVC_V2_INDEX_PATH")
    index_sha = os.environ.get("LIVECONV_RVC_V2_INDEX_SHA256")
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
    auxiliary = {
        "hubert_config_sha256": source_root / "assets/hubert_base/config.json",
        "hubert_preprocessor_sha256": (
            source_root / "assets/hubert_base/preprocessor_config.json"
        ),
        "hubert_weights_sha256": (source_root / "assets/hubert_base/pytorch_model.bin"),
        "rmvpe_sha256": source_root / "assets/rmvpe/rmvpe.pt",
    }
    for index, (key, path) in enumerate(auxiliary.items(), start=1):
        digest = artifacts_config.get(key)
        if not isinstance(digest, str):
            raise ValueError(f"{profile.profile_id}: RVC {key} is invalid")
        env_var = f"LIVECONV_RVC_VERIFIED_ARTIFACT_{index}"
        environment[env_var] = str(path)
        artifacts.append(ArtifactSpec(env_var=env_var, sha256=digest))
    return environment, tuple(artifacts)


@dataclass(frozen=True)
class _WorkerSlotReservation:
    epoch: int
    token: int


class WorkerBridge:
    """Translate public PCM frames to one session-owned worker supervisor."""

    def __init__(
        self,
        factory: WorkerSupervisorFactory,
        *,
        queue_budget_ms: int,
    ) -> None:
        self._factory = factory
        self._queue_budget_ms = queue_budget_ms
        self._supervisor: WorkerSupervisor | None = None
        self._identity: tuple[str, str, str] | None = None
        self._active_generation_id: int | None = None
        self._generation_ended = False
        self._slot_condition = asyncio.Condition()
        self._slot_epoch = 0
        self._slot_generation_id: int | None = None
        self._slot_supervisor: WorkerSupervisor | None = None
        self._slot_capacity = 0
        self._reserved_slots = 0
        self._pushed_sequences: deque[tuple[int, int]] = deque()
        self._next_slot_token = 0

    @property
    def supervisor(self) -> WorkerSupervisor | None:
        return self._supervisor

    async def start_generation(
        self,
        profile: ModelProfile,
        pipeline_id: str,
        generation_id: int,
    ) -> None:
        identity = (profile.profile_id, profile.configuration_hash, pipeline_id)
        if self._supervisor is not None and self._identity != identity:
            await self.close()

        if self._supervisor is None:
            try:
                self._supervisor = self._factory(
                    profile,
                    pipeline_id,
                    self._queue_budget_ms,
                )
            except (OSError, ValueError) as error:
                raise ProtocolValidationError(
                    ErrorCode.MODEL_UNAVAILABLE,
                    "profile worker could not be configured",
                ) from error
            self._identity = identity

        supervisor = self._supervisor
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
        except WorkerRuntimeError as error:
            await self._discard_supervisor(supervisor)
            raise _public_worker_error(error) from error
        self._active_generation_id = generation_id
        self._generation_ended = False
        await self._configure_worker_slots(
            generation_id,
            supervisor,
            supervisor.input_capacity_frames,
        )

    async def process_frame(self, frame: PcmFrame) -> PcmFrame:
        await self.push_frame(frame)
        return await self.next_frame(frame.header.generation_id)

    async def push_frame(self, frame: PcmFrame) -> None:
        supervisor = self._require_active(frame.header.generation_id)
        worker_frame = _worker_frame(frame)
        reservation = await self._reserve_worker_slot(
            frame.header.generation_id,
            supervisor,
            frame.header.sequence,
        )
        try:
            await supervisor.push_audio(worker_frame)
        except asyncio.CancelledError:
            await self._rollback_reserved_slot(
                frame.header.generation_id,
                supervisor,
                reservation,
            )
            raise
        except WorkerRuntimeError as error:
            await self._rollback_reserved_slot(
                frame.header.generation_id,
                supervisor,
                reservation,
            )
            raise _public_worker_error(error) from error
        except Exception:
            await self._rollback_reserved_slot(
                frame.header.generation_id,
                supervisor,
                reservation,
            )
            raise

    async def next_frame(self, generation_id: int) -> PcmFrame:
        supervisor = self._require_active(generation_id)
        try:
            output = await supervisor.next_output()
        except WorkerRuntimeError as error:
            await self._reset_worker_slots()
            raise _public_worker_error(error) from error
        await self._consume_worker_slot(
            generation_id,
            supervisor,
            output.sequence,
        )
        return _public_frame(output)

    async def end_generation(self, generation_id: int) -> None:
        supervisor = self._require_active(generation_id)
        try:
            await supervisor.end_generation(generation_id)
        except WorkerRuntimeError as error:
            await self._reset_worker_slots()
            raise _public_worker_error(error) from error
        self._generation_ended = True

    async def finish_generation(self, generation_id: int) -> None:
        self._require_active(generation_id)
        if not self._generation_ended:
            raise ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "profile worker has not completed the generation",
            )
        self._active_generation_id = None
        self._generation_ended = False
        await self._reset_worker_slots()

    async def cancel_generation(self, generation_id: int) -> None:
        supervisor = self._supervisor
        if supervisor is None or self._active_generation_id != generation_id:
            return
        self._active_generation_id = None
        generation_ended = self._generation_ended
        self._generation_ended = False
        await self._reset_worker_slots()
        if generation_ended:
            await self._discard_supervisor(supervisor)
            return
        try:
            await supervisor.cancel_generation(generation_id)
        except WorkerRuntimeError as error:
            await self._discard_supervisor(supervisor)
            raise _public_worker_error(error) from error

    async def close(self) -> None:
        supervisor = self._supervisor
        self._supervisor = None
        self._identity = None
        self._active_generation_id = None
        self._generation_ended = False
        await self._reset_worker_slots()
        if supervisor is not None:
            await supervisor.close()

    async def _discard_supervisor(self, supervisor: WorkerSupervisor) -> None:
        if self._supervisor is supervisor:
            self._supervisor = None
            self._identity = None
            self._active_generation_id = None
            self._generation_ended = False
        await self._reset_worker_slots()
        with contextlib.suppress(WorkerRuntimeError):
            await supervisor.close()

    def _require_active(self, generation_id: int) -> WorkerSupervisor:
        if self._supervisor is None or self._active_generation_id != generation_id:
            raise self._inactive_generation_error()
        return self._supervisor

    @staticmethod
    def _inactive_generation_error() -> ProtocolValidationError:
        return ProtocolValidationError(
            ErrorCode.WORKER_CRASH,
            "profile worker has no matching active generation",
        )

    async def _configure_worker_slots(
        self,
        generation_id: int,
        supervisor: WorkerSupervisor,
        capacity: int,
    ) -> None:
        if capacity < 1:
            raise ProtocolValidationError(
                ErrorCode.WORKER_CRASH,
                "profile worker has no input capacity",
            )
        async with self._slot_condition:
            self._slot_epoch += 1
            self._slot_generation_id = generation_id
            self._slot_supervisor = supervisor
            self._slot_capacity = capacity
            self._reserved_slots = 0
            self._pushed_sequences.clear()
            self._slot_condition.notify_all()

    async def _reset_worker_slots(self) -> None:
        async with self._slot_condition:
            self._slot_epoch += 1
            self._slot_generation_id = None
            self._slot_supervisor = None
            self._slot_capacity = 0
            self._reserved_slots = 0
            self._pushed_sequences.clear()
            self._slot_condition.notify_all()

    async def _reserve_worker_slot(
        self,
        generation_id: int,
        supervisor: WorkerSupervisor,
        sequence: int,
    ) -> _WorkerSlotReservation:
        async with self._slot_condition:
            while True:
                if (
                    self._active_generation_id != generation_id
                    or self._supervisor is not supervisor
                    or self._slot_generation_id != generation_id
                    or self._slot_supervisor is not supervisor
                ):
                    raise self._inactive_generation_error()
                if self._reserved_slots < self._slot_capacity:
                    reservation = _WorkerSlotReservation(
                        epoch=self._slot_epoch,
                        token=self._next_slot_token,
                    )
                    self._next_slot_token += 1
                    self._reserved_slots += 1
                    # The worker can publish an output before push_audio returns.
                    # Register its sequence with the reserved credit first.
                    self._pushed_sequences.append((reservation.token, sequence))
                    return reservation
                await self._slot_condition.wait()

    async def _rollback_reserved_slot(
        self,
        generation_id: int,
        supervisor: WorkerSupervisor,
        reservation: _WorkerSlotReservation,
    ) -> None:
        async with self._slot_condition:
            if not self._slot_matches(generation_id, supervisor, reservation):
                return
            for index, (token, _sequence) in enumerate(self._pushed_sequences):
                if token == reservation.token:
                    del self._pushed_sequences[index]
                    self._reserved_slots -= 1
                    self._slot_condition.notify_all()
                    return

    async def _consume_worker_slot(
        self,
        generation_id: int,
        supervisor: WorkerSupervisor,
        sequence: int,
    ) -> None:
        async with self._slot_condition:
            if (
                self._active_generation_id != generation_id
                or self._supervisor is not supervisor
                or self._slot_generation_id != generation_id
                or self._slot_supervisor is not supervisor
            ):
                raise self._inactive_generation_error()
            if not self._pushed_sequences or self._pushed_sequences[0][1] != sequence:
                raise ProtocolValidationError(
                    ErrorCode.WORKER_CRASH,
                    "profile worker output does not match accepted input",
                )
            self._pushed_sequences.popleft()
            self._reserved_slots -= 1
            self._slot_condition.notify_all()

    def _slot_matches(
        self,
        generation_id: int,
        supervisor: WorkerSupervisor,
        reservation: _WorkerSlotReservation,
    ) -> bool:
        return (
            self._slot_epoch == reservation.epoch
            and self._slot_generation_id == generation_id
            and self._slot_supervisor is supervisor
        )


def _worker_frame(frame: PcmFrame) -> AudioFrame:
    samples = frame.unpack_samples()
    if any(
        not math.isfinite(sample) or not -1.0 <= sample <= 1.0 for sample in samples
    ):
        raise ProtocolValidationError(
            ErrorCode.UNSUPPORTED_AUDIO,
            "PCM samples must be finite and normalized",
            field="payload",
        )
    header = frame.header
    try:
        return AudioFrame(
            generation_id=header.generation_id,
            sequence=header.sequence,
            sample_rate=header.sample_rate,
            channels=header.channels,
            samples_per_channel=header.samples_per_channel,
            source_monotonic_ns=header.source_monotonic_ns,
            pcm_f32le=frame.payload,
        )
    except ValueError as error:
        raise ProtocolValidationError(
            ErrorCode.UNSUPPORTED_AUDIO,
            "PCM frame is not valid worker input",
            field="payload",
        ) from error


def _public_frame(frame: AudioFrame) -> PcmFrame:
    if any(
        not math.isfinite(sample) or not -1.0 <= sample <= 1.0
        for sample in frame.unpack_samples()
    ):
        raise ProtocolValidationError(
            ErrorCode.WORKER_CRASH,
            "profile worker returned non-normalized PCM",
        )
    return PcmFrame(
        header=FrameHeader(
            kind=FrameKind.OUTPUT,
            generation_id=frame.generation_id,
            sequence=frame.sequence,
            sample_rate=frame.sample_rate,
            channels=frame.channels,
            samples_per_channel=frame.samples_per_channel,
            source_monotonic_ns=frame.source_monotonic_ns,
        ),
        payload=frame.pcm_f32le,
    )


def _public_worker_error(error: WorkerRuntimeError) -> ProtocolValidationError:
    try:
        code = ErrorCode(error.code)
    except ValueError:
        code = ErrorCode.WORKER_CRASH
    if code in {
        ErrorCode.AUTH_FAILED,
        ErrorCode.INVALID_STATE,
        ErrorCode.SEQUENCE_GAP,
        ErrorCode.STALE_GENERATION,
        ErrorCode.UNSUPPORTED_PROTOCOL,
    }:
        code = ErrorCode.WORKER_CRASH
    messages = {
        ErrorCode.MODEL_TIMEOUT: "profile worker deadline expired",
        ErrorCode.MODEL_UNAVAILABLE: "profile worker is unavailable",
        ErrorCode.QUEUE_OVERFLOW: "profile worker queue is full",
        ErrorCode.UNSUPPORTED_AUDIO: "profile worker rejected the audio format",
        ErrorCode.WORKER_CRASH: "profile worker failed",
    }
    return ProtocolValidationError(code, messages.get(code, "profile worker failed"))
