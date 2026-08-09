from __future__ import annotations

import asyncio
import contextlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from liveconv_protocol import (
    ErrorEvent,
    FallbackRequiredEvent,
    FrameHeader,
    FrameKind,
    GenerationCancel,
    GenerationCanceledEvent,
    GenerationCompletedEvent,
    GenerationEnd,
    GenerationReadyEvent,
    GenerationStart,
    ParsedServerEvent,
    PcmFrame,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_control_message,
    parse_server_event,
)

from .config import FULL_BATCH_FRAMES
from .errors import RouteValidationError, TransportError
from .trace import TraceRecorder
from .transport import (
    GatewayApi,
    ProfileIdentity,
    SessionDescriptor,
    WebSocketConnection,
)

_EventT = TypeVar("_EventT", bound=ParsedServerEvent)
_FRAME_NS = 20_000_000
_SYNTHETIC_EPOCH_NS = 1_000_000_000
_EXPECTED_INGRESS_BUDGET_MS = 1_000
_EXPECTED_INGRESS_FRAMES = 50


class Pacer(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class RealtimePacer:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class CreditWindow:
    """Track immutable v1 accepted-ingress credit while the reader drains output."""

    def __init__(self, maximum: int) -> None:
        if maximum <= 0:
            raise ValueError("credit maximum must be positive")
        self.maximum = maximum
        self.in_flight = 0
        self.high_water = 0
        self._failure: Exception | None = None
        self._condition = asyncio.Condition()

    async def reserve(self) -> None:
        async with self._condition:
            await self._condition.wait_for(
                lambda: self.in_flight < self.maximum or self._failure is not None
            )
            if self._failure is not None:
                raise self._failure
            self.in_flight += 1
            self.high_water = max(self.high_water, self.in_flight)

    async def release(self) -> None:
        async with self._condition:
            if self.in_flight <= 0:
                raise RouteValidationError(
                    "Gateway output exceeded accepted input credit"
                )
            self.in_flight -= 1
            self._condition.notify_all()

    async def abort(self, failure: Exception) -> None:
        async with self._condition:
            self._failure = failure
            self.in_flight = 0
            self._condition.notify_all()


@dataclass(slots=True)
class GenerationEvidence:
    generation_id: int
    identity: ProfileIdentity
    pipeline_id: str
    credit: CreditWindow
    inputs: dict[int, tuple[int, bytes]] = field(default_factory=dict)
    next_sequence: int = 0
    accepted_output_frames: int = 0
    changed_samples: int = 0
    finite_samples: int = 0
    absolute_peak: float = 0.0


def synthetic_frame(generation_id: int, sequence: int) -> PcmFrame:
    """Return deterministic, non-speech project-authored PCM without persistence."""

    offset = sequence * 960
    samples = (
        0.28 * math.sin(2 * math.pi * 233 * (offset + index) / 48_000)
        + 0.11 * math.sin(2 * math.pi * 487 * (offset + index) / 48_000)
        for index in range(960)
    )
    return PcmFrame.from_samples(
        FrameHeader(
            kind=FrameKind.INPUT,
            generation_id=generation_id,
            sequence=sequence,
            source_monotonic_ns=_SYNTHETIC_EPOCH_NS + sequence * _FRAME_NS,
        ),
        samples,
    )


class RvcGatewayRoute:
    """One-profile route gate built only from the frozen protocol-v1 abstractions."""

    def __init__(
        self,
        api: GatewayApi,
        trace: TraceRecorder,
        descriptor: SessionDescriptor,
        websocket: WebSocketConnection,
        *,
        timeout_seconds: float,
        generation_ready_timeout_seconds: float,
        pacer: Pacer | None = None,
    ) -> None:
        self.api = api
        self.trace = trace
        self.descriptor = descriptor
        self.websocket = websocket
        self.timeout_seconds = timeout_seconds
        self.generation_ready_timeout_seconds = generation_ready_timeout_seconds
        self.pacer = pacer or RealtimePacer()
        self.identity = descriptor.identity
        self.pipeline_id = descriptor.pipeline_id
        self.credit_frames = 0
        self._active: GenerationEvidence | None = None
        self._finished_generation = 0
        self._invalidated: set[int] = set()
        self._excluded_by_generation: dict[int, int] = defaultdict(int)
        self._events: asyncio.Queue[ParsedServerEvent | Exception] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._request_counter = 0

    @classmethod
    async def attach(
        cls,
        api: GatewayApi,
        trace: TraceRecorder,
        descriptor: SessionDescriptor,
        *,
        timeout_seconds: float,
        generation_ready_timeout_seconds: float,
        pacer: Pacer | None = None,
    ) -> RvcGatewayRoute:
        websocket = await api.connect(descriptor)
        route = cls(
            api,
            trace,
            descriptor,
            websocket,
            timeout_seconds=timeout_seconds,
            generation_ready_timeout_seconds=generation_ready_timeout_seconds,
            pacer=pacer,
        )
        try:
            await route._complete_attach()
        except Exception:
            await websocket.close()
            raise
        return route

    def _request_id(self, action: str) -> str:
        self._request_counter += 1
        return f"exp004.{action}.{self._request_counter}"

    async def _send(self, message: str | bytes) -> None:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self.websocket.send(message)
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket send timed out") from exc

    async def _receive(self, *, timeout_seconds: float | None = None) -> str | bytes:
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            async with asyncio.timeout(timeout):
                return await self.websocket.recv()
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket receive timed out") from exc

    async def _complete_attach(self) -> None:
        request_id = self._request_id("attach")
        await self._send(
            encode_control_message(
                SessionAttach(
                    protocol_version=1,
                    request_id=request_id,
                    session_id=self.descriptor.session_id,
                    ticket=self.descriptor.ticket,
                )
            )
        )
        message = await self._receive()
        if not isinstance(message, str):
            raise RouteValidationError("session attach returned binary data")
        event = parse_server_event(message)
        if not isinstance(event, SessionReadyEvent):
            raise RouteValidationError("session attach did not return session.ready")
        if (
            event.request_id != request_id
            or event.session_id != self.descriptor.session_id
            or event.profile_id != self.identity.profile_id
            or event.profile_hash != self.identity.profile_hash
            or event.configuration_hash != self.identity.configuration_hash
            or event.pipeline_id != self.pipeline_id
        ):
            raise RouteValidationError(
                "session.ready identity does not match catalog/session"
            )
        credit_from_budget = event.limits.ingress_budget_ms // 20
        if (
            event.limits.ingress_budget_ms != _EXPECTED_INGRESS_BUDGET_MS
            or event.limits.max_ingress_frames != _EXPECTED_INGRESS_FRAMES
            or credit_from_budget != _EXPECTED_INGRESS_FRAMES
        ):
            raise RouteValidationError(
                "Gateway did not advertise the exact 50-frame ingress credit"
            )
        self.credit_frames = _EXPECTED_INGRESS_FRAMES
        self.trace.set_profile_identity(
            profile_hash=self.identity.profile_hash,
            configuration_hash=self.identity.configuration_hash,
        )
        self.trace.add_result(
            "catalog_session_attach",
            passed=True,
            evidence={
                "catalog_session_ready_identity_matched": True,
                "authenticated_session_created": True,
                "exact_origin_attach_accepted": True,
                "one_use_attach_accepted": True,
                "effective_ingress_credit_frames": self.credit_frames,
                "required_gateway_credit_available": True,
            },
        )
        self._reader_task = asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        try:
            while True:
                message = await self._receive()
                if isinstance(message, bytes):
                    await self._handle_output(message)
                else:
                    await self._events.put(parse_server_event(message))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._active is not None:
                await self._active.credit.abort(exc)
            await self._events.put(exc)

    async def _stop_reader(self) -> None:
        task = self._reader_task
        self._reader_task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _handle_output(self, encoded: bytes) -> None:
        frame = PcmFrame.decode(encoded)
        header = frame.header
        if header.kind is not FrameKind.OUTPUT:
            raise RouteValidationError("Gateway returned non-output PCM")
        active = self._active
        if active is None or header.generation_id != active.generation_id:
            if header.generation_id in self._invalidated:
                self._excluded_by_generation[header.generation_id] += 1
                return
            raise RouteValidationError("Gateway output belongs to no active generation")
        if header.sequence != active.next_sequence:
            raise RouteValidationError("Gateway output sequence is not contiguous")
        expected = active.inputs.pop(header.sequence, None)
        if expected is None:
            raise RouteValidationError("Gateway output has no accepted input frame")
        expected_timestamp, input_payload = expected
        if header.source_monotonic_ns != expected_timestamp:
            raise RouteValidationError("Gateway output timestamp differs from input")
        output_samples = frame.unpack_samples()
        if any(not math.isfinite(value) for value in output_samples):
            raise RouteValidationError("Gateway output contains non-finite PCM")
        peak = max(abs(value) for value in output_samples)
        if peak > 1.0:
            raise RouteValidationError(
                "Gateway output PCM is outside normalized bounds"
            )
        input_samples = PcmFrame(
            FrameHeader(
                kind=FrameKind.INPUT,
                generation_id=header.generation_id,
                sequence=header.sequence,
                source_monotonic_ns=header.source_monotonic_ns,
            ),
            input_payload,
        ).unpack_samples()
        active.next_sequence += 1
        active.accepted_output_frames += 1
        active.changed_samples += sum(
            abs(output - source) > 1e-7
            for output, source in zip(output_samples, input_samples, strict=True)
        )
        active.finite_samples += len(output_samples)
        active.absolute_peak = max(active.absolute_peak, peak)
        await active.credit.release()

    async def _next_event(self) -> ParsedServerEvent:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                item = await self._events.get()
        except TimeoutError as exc:
            raise TransportError("Gateway server event timed out") from exc
        if isinstance(item, Exception):
            raise item
        return self._checked_event(item)

    @staticmethod
    def _checked_event(event: ParsedServerEvent) -> ParsedServerEvent:
        if isinstance(event, ErrorEvent):
            raise RouteValidationError(f"Gateway returned error code {event.code}")
        if isinstance(event, FallbackRequiredEvent):
            raise RouteValidationError("Gateway requested fallback")
        return event

    async def _expect(self, event_type: type[_EventT]) -> _EventT:
        event = await self._next_event()
        if not isinstance(event, event_type):
            raise RouteValidationError(
                f"expected {event_type.message_type}, got {event.message_type}"
            )
        return event

    async def _start(self, generation_id: int) -> GenerationEvidence:
        if self._active is not None or generation_id <= self._finished_generation:
            raise RouteValidationError("generation IDs must strictly increase")
        request_id = self._request_id("start")
        await self._stop_reader()
        await self._send(
            encode_control_message(
                GenerationStart(
                    protocol_version=1,
                    request_id=request_id,
                    session_id=self.descriptor.session_id,
                    generation_id=generation_id,
                )
            )
        )
        message = await self._receive(
            timeout_seconds=self.generation_ready_timeout_seconds
        )
        if not isinstance(message, str):
            raise RouteValidationError("generation start returned binary data")
        event = self._checked_event(parse_server_event(message))
        if not isinstance(event, GenerationReadyEvent):
            raise RouteValidationError(
                "expected "
                f"{GenerationReadyEvent.message_type}, got {event.message_type}"
            )
        if (
            event.request_id != request_id
            or event.generation_id != generation_id
            or event.profile_id != self.identity.profile_id
            or event.profile_hash != self.identity.profile_hash
            or event.configuration_hash != self.identity.configuration_hash
            or event.pipeline_id != self.pipeline_id
        ):
            raise RouteValidationError(
                "generation.ready identity does not match session"
            )
        active = GenerationEvidence(
            generation_id=generation_id,
            identity=self.identity,
            pipeline_id=self.pipeline_id,
            credit=CreditWindow(self.credit_frames),
        )
        self._active = active
        self._reader_task = asyncio.create_task(self._reader())
        return active

    async def _send_frames(
        self, evidence: GenerationEvidence, frame_count: int
    ) -> None:
        for sequence in range(frame_count):
            await evidence.credit.reserve()
            frame = synthetic_frame(evidence.generation_id, sequence)
            evidence.inputs[sequence] = (
                frame.header.source_monotonic_ns,
                frame.payload,
            )
            await self._send(frame.encode())
            if sequence + 1 < frame_count:
                await self.pacer.sleep(0.020)

    async def _end(self, evidence: GenerationEvidence) -> None:
        request_id = self._request_id("end")
        await self._send(
            encode_control_message(
                GenerationEnd(
                    protocol_version=1,
                    request_id=request_id,
                    session_id=self.descriptor.session_id,
                    generation_id=evidence.generation_id,
                )
            )
        )
        event = await self._expect(GenerationCompletedEvent)
        if (
            event.request_id != request_id
            or event.generation_id != evidence.generation_id
            or event.pipeline_id != evidence.pipeline_id
        ):
            raise RouteValidationError("generation.completed identity is invalid")
        if evidence.inputs or evidence.credit.in_flight:
            raise RouteValidationError(
                "generation completed before accepted audio drained"
            )
        if evidence.changed_samples <= 0:
            raise RouteValidationError(
                "RVC output did not change a synthetic PCM sample"
            )
        self._active = None
        self._finished_generation = evidence.generation_id

    async def run_full_batch_with_tail(self, tail_frames: int) -> None:
        evidence = await self._start(1)
        total_frames = FULL_BATCH_FRAMES + tail_frames
        await self._send_frames(evidence, total_frames)
        await self._end(evidence)
        self.trace.add_result(
            "generation_1_batch_tail_flush",
            passed=True,
            evidence={
                "generation_id": 1,
                "full_batch_frames": FULL_BATCH_FRAMES,
                "tail_frames": tail_frames,
                "input_frames": total_frames,
                "accepted_output_frames": evidence.accepted_output_frames,
                "paced_frame_interval_ms": 20,
                "sequence_contiguous": True,
                "timestamps_echoed": True,
                "all_output_finite": True,
                "all_output_normalized": True,
                "output_changed": True,
                "overflow_or_fallback_observed": False,
                "changed_value_count": evidence.changed_samples,
                "finite_value_count": evidence.finite_samples,
                "absolute_peak": evidence.absolute_peak,
                "credit_high_water": evidence.credit.high_water,
                "advertised_ingress_credit_frames": evidence.credit.maximum,
                "credit_bound_respected": (
                    evidence.credit.high_water <= evidence.credit.maximum
                ),
            },
        )

    async def run_cancel(
        self, cancel_frames: int, *, stale_grace_seconds: float
    ) -> None:
        evidence = await self._start(2)
        await self._send_frames(evidence, cancel_frames)
        self._active = None
        self._invalidated.add(evidence.generation_id)
        await evidence.credit.abort(RouteValidationError("local output gate closed"))
        request_id = self._request_id("cancel")
        await self._send(
            encode_control_message(
                GenerationCancel(
                    protocol_version=1,
                    request_id=request_id,
                    session_id=self.descriptor.session_id,
                    generation_id=evidence.generation_id,
                )
            )
        )
        event = await self._expect(GenerationCanceledEvent)
        if (
            event.request_id != request_id
            or event.generation_id != evidence.generation_id
            or event.pipeline_id != evidence.pipeline_id
        ):
            raise RouteValidationError("generation.canceled identity is invalid")
        self._finished_generation = evidence.generation_id
        await asyncio.sleep(stale_grace_seconds)
        self.trace.add_result(
            "generation_2_cancel",
            passed=True,
            evidence={
                "generation_id": 2,
                "sent_frames_before_cancel": cancel_frames,
                "local_output_gate_closed_before_cancel_send": True,
                "server_acknowledged_cancel": True,
                "accepted_output_after_cancel": 0,
                "stale_output_frames_excluded": self._excluded_by_generation[2],
                "stale_output_frames_accepted": 0,
            },
        )

    async def close(self) -> None:
        if self._active is not None:
            raise RouteValidationError("cannot close while a generation is active")
        request_id = self._request_id("close")
        await self._send(
            encode_control_message(
                SessionClose(
                    protocol_version=1,
                    request_id=request_id,
                    session_id=self.descriptor.session_id,
                )
            )
        )
        event = await self._expect(SessionClosedEvent)
        if (
            event.request_id != request_id
            or event.session_id != self.descriptor.session_id
        ):
            raise RouteValidationError("session.closed identity is invalid")
        await self._stop_reader()
        await self.websocket.close()

    async def abort(self) -> None:
        await self._stop_reader()
        with contextlib.suppress(Exception):
            await self.websocket.close()
