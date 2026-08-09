from __future__ import annotations

import contextlib
import math
import sys
from collections.abc import Callable
from pathlib import Path

from liveconv_protocol import (
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)

from workers.runtime import AudioFrame, WorkerProfile, WorkerSupervisor
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
    if adapter not in {"passthrough", "gain"}:
        raise ValueError(f"{profile.profile_id}: no builtin worker is available")

    worker_entrypoint = Path(__file__).with_name("builtin_worker.py")
    command = [
        sys.executable,
        str(worker_entrypoint),
        "--mode",
        adapter,
        "--implementation-revision",
        profile.implementation_revision,
        "--capacity-frames",
        str(max(1, queue_budget_ms // profile.frame_ms)),
    ]
    if profile.weight_revision is not None:
        command.extend(("--weight-revision", profile.weight_revision))
    if adapter == "gain":
        command.extend(("--gain", str(profile.runtime.configuration["gain"])))

    bounded_queue_ms = max(
        profile.frame_ms,
        (queue_budget_ms // profile.frame_ms) * profile.frame_ms,
    )
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

    async def process_frame(self, frame: PcmFrame) -> PcmFrame:
        supervisor = self._require_active(frame.header.generation_id)
        worker_frame = _worker_frame(frame)
        try:
            await supervisor.push_audio(worker_frame)
            output = await supervisor.next_output()
        except WorkerRuntimeError as error:
            raise _public_worker_error(error) from error
        return _public_frame(output)

    async def end_generation(self, generation_id: int) -> None:
        supervisor = self._require_active(generation_id)
        try:
            await supervisor.end_generation(generation_id)
        except WorkerRuntimeError as error:
            raise _public_worker_error(error) from error
        self._active_generation_id = None

    async def cancel_generation(self, generation_id: int) -> None:
        supervisor = self._supervisor
        if supervisor is None or self._active_generation_id != generation_id:
            return
        self._active_generation_id = None
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
        if supervisor is not None:
            await supervisor.close()

    async def _discard_supervisor(self, supervisor: WorkerSupervisor) -> None:
        if self._supervisor is supervisor:
            self._supervisor = None
            self._identity = None
            self._active_generation_id = None
        with contextlib.suppress(WorkerRuntimeError):
            await supervisor.close()

    def _require_active(self, generation_id: int) -> WorkerSupervisor:
        if self._supervisor is None or self._active_generation_id != generation_id:
            raise ProtocolValidationError(
                ErrorCode.WORKER_CRASH,
                "profile worker has no matching active generation",
            )
        return self._supervisor


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
