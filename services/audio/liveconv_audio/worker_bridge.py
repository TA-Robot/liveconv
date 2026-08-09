from __future__ import annotations

import asyncio
import contextlib
import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from liveconv_protocol import (
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)

from workers.runtime import AudioFrame, WorkerSupervisor
from workers.runtime.errors import WorkerRuntimeError

from ._adapter_registry import _rvc_environment, worker_profile_for  # noqa: F401
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
    return WorkerSupervisor(worker_profile_for(profile, pipeline_id, queue_budget_ms))


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
