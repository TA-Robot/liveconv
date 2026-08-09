from __future__ import annotations

import asyncio
import contextlib
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field, fields, is_dataclass
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
    ModelSelect,
    ModelSelectedEvent,
    ParsedControlMessage,
    ParsedServerEvent,
    PcmFrame,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_control_message,
    parse_server_event,
)

from .errors import RouteValidationError, TransportError
from .registry import RegistryProfile
from .trace import TraceRecorder
from .transport import GatewayApi, SessionDescriptor, WebSocketConnection

_EventT = TypeVar("_EventT", bound=ParsedServerEvent)
_FRAME_NS = 20_000_000


class Pacer(Protocol):
    def monotonic_ns(self) -> int: ...

    async def sleep(self, seconds: float) -> None: ...


class RealtimePacer:
    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class CreditWindow:
    """One generation's server-advertised outstanding-frame bound."""

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
                raise RouteValidationError("output exceeded reserved ingress credit")
            self.in_flight -= 1
            self._condition.notify_all()

    async def abort(self, failure: Exception) -> None:
        async with self._condition:
            self._failure = failure
            self.in_flight = 0
            self._condition.notify_all()


@dataclass(slots=True)
class GenerationEvidence:
    case_id: str
    generation_id: int
    profile: RegistryProfile
    pipeline_id: str
    credit: CreditWindow
    inputs: dict[int, tuple[int, bytes]] = field(default_factory=dict)
    next_output_sequence: int = 0
    accepted_output_frames: int = 0
    finite_sample_count: int = 0
    changed_sample_count: int = 0
    absolute_peak: float = 0.0
    maximum_send_lateness_ns: int = 0


def _event_metadata(event: ParsedServerEvent) -> dict[str, object]:
    allowed = {
        "protocol_version",
        "session_id",
        "request_id",
        "generation_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "pipeline_id",
        "clock_id",
        "code",
        "recoverable",
        "required_action",
        "field",
        "reason_code",
        "limits",
    }
    metadata: dict[str, object] = {"message_type": event.message_type}
    if is_dataclass(event):
        for item in fields(event):
            if item.name not in allowed:
                continue
            value = getattr(event, item.name)
            if value is None:
                continue
            if is_dataclass(value):
                value = {
                    child.name: getattr(value, child.name) for child in fields(value)
                }
            metadata[item.name] = value
    return metadata


def _synthetic_frame(
    generation_id: int, sequence: int, source_monotonic_ns: int
) -> PcmFrame:
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
            source_monotonic_ns=source_monotonic_ns,
        ),
        samples,
    )


class GatewayRoute:
    """Strict version 1 route with local stale gating and bounded pacing."""

    def __init__(
        self,
        api: GatewayApi,
        trace: TraceRecorder,
        descriptor: SessionDescriptor,
        websocket: WebSocketConnection,
        *,
        timeout_seconds: float,
        batch_frames: int,
        pacer: Pacer | None = None,
    ) -> None:
        self.api = api
        self.trace = trace
        self.descriptor = descriptor
        self.websocket = websocket
        self.timeout_seconds = timeout_seconds
        self.batch_frames = batch_frames
        self.pacer = pacer or RealtimePacer()
        self.profile_id = descriptor.profile_id
        self.pipeline_id = descriptor.pipeline_id
        self.server_clock_id: str | None = None
        self.credit_frames = 0
        self._active: GenerationEvidence | None = None
        self._finished_generation_id = 0
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
        batch_frames: int,
        pacer: Pacer | None = None,
    ) -> GatewayRoute:
        websocket = await api.connect(descriptor)
        route = cls(
            api,
            trace,
            descriptor,
            websocket,
            timeout_seconds=timeout_seconds,
            batch_frames=batch_frames,
            pacer=pacer,
        )
        try:
            await route._complete_attach()
        except Exception:
            await websocket.close()
            raise
        return route

    async def _complete_attach(self) -> None:
        request_id = self._request_id("attach")
        attach = SessionAttach(
            protocol_version=1,
            request_id=request_id,
            session_id=self.descriptor.session_id,
            ticket=self.descriptor.ticket,
        )
        await self._send_control(
            "session",
            attach,
            extra={"authentication_material_redacted": True},
        )
        message = await self._receive_raw()
        if not isinstance(message, str):
            raise RouteValidationError("session attach returned binary data")
        ready = parse_server_event(message)
        self.trace.record("session", "server.event", _event_metadata(ready))
        if not isinstance(ready, SessionReadyEvent):
            raise RouteValidationError(
                f"expected session.ready, received {ready.message_type}"
            )
        if (
            ready.request_id != request_id
            or ready.session_id != self.descriptor.session_id
            or ready.profile_id != self.descriptor.profile_id
            or ready.pipeline_id != self.descriptor.pipeline_id
            or ready.profile_hash != self.descriptor.profile_hash
            or ready.configuration_hash != self.descriptor.configuration_hash
        ):
            raise RouteValidationError("session.ready identity does not match creation")
        budget_frames = ready.limits.ingress_budget_ms // 20
        self.credit_frames = min(ready.limits.max_ingress_frames, budget_frames)
        if self.credit_frames <= 0:
            raise RouteValidationError(
                "session.ready advertised no usable ingress credit"
            )
        if self.credit_frames < self.batch_frames:
            raise RouteValidationError(
                "server-advertised ingress credit cannot hold one configured batch"
            )
        self.server_clock_id = ready.clock_id
        self.trace.add_result(
            "session",
            passed=True,
            evidence={
                "server_advertised_ingress_budget_ms": ready.limits.ingress_budget_ms,
                "server_advertised_max_ingress_frames": ready.limits.max_ingress_frames,
                "effective_credit_frames": self.credit_frames,
                "configured_batch_frames": self.batch_frames,
                "credit_can_hold_batch": True,
            },
        )
        self._reader_task = asyncio.create_task(self._reader())

    def _request_id(self, action: str) -> str:
        self._request_counter += 1
        return f"exp003.{action}.{self._request_counter}"

    async def _send_raw(self, message: str | bytes) -> None:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self.websocket.send(message)
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket send timed out") from exc

    async def _receive_raw(self) -> str | bytes:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self.websocket.recv()
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket receive timed out") from exc

    async def _send_control(
        self,
        case_id: str,
        message: ParsedControlMessage,
        *,
        extra: dict[str, object] | None = None,
    ) -> None:
        details: dict[str, object] = {
            "message_type": message.message_type,
            "request_id": message.request_id,
            "session_id": message.session_id,
        }
        for name in ("generation_id", "profile_id"):
            value = getattr(message, name, None)
            if value is not None:
                details[name] = value
        if extra:
            details.update(extra)
        self.trace.record(case_id, "client.control", details)
        await self._send_raw(encode_control_message(message))

    async def _reader(self) -> None:
        try:
            while True:
                message = await self._receive_raw()
                if isinstance(message, bytes):
                    await self._handle_output(message)
                    continue
                event = parse_server_event(message)
                self.trace.record("route", "server.event", _event_metadata(event))
                await self._events.put(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._active is not None:
                await self._active.credit.abort(exc)
            await self._events.put(exc)

    async def _handle_output(self, message: bytes) -> None:
        frame = PcmFrame.decode(message)
        header = frame.header
        if header.kind is not FrameKind.OUTPUT:
            raise RouteValidationError("Gateway returned a non-output PCM frame")
        active = self._active
        if active is None or header.generation_id != active.generation_id:
            if (
                header.generation_id in self._invalidated
                or header.generation_id <= self._finished_generation_id
            ):
                self._excluded_by_generation[header.generation_id] += 1
                self.trace.record(
                    "stale_exclusion",
                    "output.excluded",
                    {
                        "generation_id": header.generation_id,
                        "sequence": header.sequence,
                        "reason": "locally_invalidated_generation",
                    },
                )
                return
            raise RouteValidationError(
                "output belongs to a future or unknown generation"
            )
        if header.sequence != active.next_output_sequence:
            raise RouteValidationError(
                "output sequence is duplicate, gapped, or out of order"
            )
        expected = active.inputs.pop(header.sequence, None)
        if expected is None:
            raise RouteValidationError("output has no credit-reserved input frame")
        expected_timestamp, input_payload = expected
        if header.source_monotonic_ns != expected_timestamp:
            raise RouteValidationError("output source timestamp differs from input")
        output_samples = frame.unpack_samples()
        input_samples = PcmFrame(
            FrameHeader(
                kind=FrameKind.INPUT,
                generation_id=header.generation_id,
                sequence=header.sequence,
                source_monotonic_ns=header.source_monotonic_ns,
            ),
            input_payload,
        ).unpack_samples()
        if any(not math.isfinite(value) for value in output_samples):
            raise RouteValidationError("output PCM contains non-finite samples")
        peak = max(abs(value) for value in output_samples)
        if peak > 1.0:
            raise RouteValidationError("output PCM is outside normalized [-1, 1]")
        changed = sum(
            abs(output - source) > 1e-7
            for output, source in zip(output_samples, input_samples, strict=True)
        )
        active.next_output_sequence += 1
        active.accepted_output_frames += 1
        active.finite_sample_count += len(output_samples)
        active.changed_sample_count += changed
        active.absolute_peak = max(active.absolute_peak, peak)
        await active.credit.release()
        self.trace.record(
            active.case_id,
            "output.accepted",
            {
                "generation_id": header.generation_id,
                "sequence": header.sequence,
                "source_monotonic_ns": header.source_monotonic_ns,
                "finite": True,
                "normalized": True,
                "changed_sample_count": changed,
            },
        )

    async def _next_event(self) -> ParsedServerEvent:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                item = await self._events.get()
        except TimeoutError as exc:
            raise TransportError("Gateway server event timed out") from exc
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ErrorEvent):
            raise RouteValidationError(f"Gateway error event: {item.code}")
        if isinstance(item, FallbackRequiredEvent):
            raise RouteValidationError(f"Gateway required fallback: {item.reason_code}")
        return item

    async def _expect(self, event_type: type[_EventT]) -> _EventT:
        event = await self._next_event()
        if not isinstance(event, event_type):
            raise RouteValidationError(
                f"expected {event_type.message_type}, received {event.message_type}"
            )
        return event

    async def select_model(self, profile: RegistryProfile) -> None:
        if self._active is not None:
            raise RouteValidationError("model selection attempted during a generation")
        previous_profile = self.profile_id
        previous_pipeline = self.pipeline_id
        request_id = self._request_id("select")
        await self._send_control(
            f"switch.{previous_profile}.to.{profile.profile_id}",
            ModelSelect(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                profile_id=profile.profile_id,
            ),
        )
        selected = await self._expect(ModelSelectedEvent)
        if (
            selected.request_id != request_id
            or selected.profile_id != profile.profile_id
            or selected.profile_hash != profile.profile_hash
            or selected.configuration_hash != profile.configuration_hash
            or selected.pipeline_id == previous_pipeline
        ):
            raise RouteValidationError("model.selected identity or pipeline is invalid")
        self.profile_id = selected.profile_id
        self.pipeline_id = selected.pipeline_id
        case_id = f"switch.{previous_profile}.to.{profile.profile_id}"
        self.trace.add_result(
            case_id,
            passed=True,
            evidence={
                "from_profile_id": previous_profile,
                "to_profile_id": profile.profile_id,
                "generation_active_during_switch": False,
                "pipeline_changed": True,
                "registry_identity_matched": True,
            },
        )

    async def _start_generation(
        self, case_id: str, generation_id: int, profile: RegistryProfile
    ) -> GenerationEvidence:
        if self._active is not None or generation_id <= self._finished_generation_id:
            raise RouteValidationError("generation ID is not strictly increasing")
        request_id = self._request_id("start")
        await self._send_control(
            case_id,
            GenerationStart(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            ),
        )
        ready = await self._expect(GenerationReadyEvent)
        if (
            ready.request_id != request_id
            or ready.generation_id != generation_id
            or ready.profile_id != profile.profile_id
            or ready.profile_hash != profile.profile_hash
            or ready.configuration_hash != profile.configuration_hash
            or ready.pipeline_id != self.pipeline_id
        ):
            raise RouteValidationError("generation.ready identity is invalid")
        evidence = GenerationEvidence(
            case_id=case_id,
            generation_id=generation_id,
            profile=profile,
            pipeline_id=self.pipeline_id,
            credit=CreditWindow(self.credit_frames),
        )
        self._active = evidence
        return evidence

    async def _send_paced_frames(
        self, evidence: GenerationEvidence, frame_count: int
    ) -> None:
        epoch_ns = self.pacer.monotonic_ns()
        previous_send_ns: int | None = None
        for sequence in range(frame_count):
            source_ns = epoch_ns + sequence * _FRAME_NS
            await evidence.credit.reserve()
            send_target_ns = source_ns
            if previous_send_ns is not None:
                send_target_ns = max(send_target_ns, previous_send_ns + _FRAME_NS)
            delay = (send_target_ns - self.pacer.monotonic_ns()) / 1_000_000_000
            if delay > 0:
                await self.pacer.sleep(delay)
            sent_ns = self.pacer.monotonic_ns()
            previous_send_ns = sent_ns
            evidence.maximum_send_lateness_ns = max(
                evidence.maximum_send_lateness_ns, max(0, sent_ns - source_ns)
            )
            frame = _synthetic_frame(
                evidence.generation_id, sequence, source_monotonic_ns=source_ns
            )
            evidence.inputs[sequence] = (source_ns, frame.payload)
            self.trace.record(
                evidence.case_id,
                "input.sent",
                {
                    "generation_id": evidence.generation_id,
                    "sequence": sequence,
                    "source_monotonic_ns": source_ns,
                    "frame_bytes": len(frame.payload),
                    "credit_in_flight": evidence.credit.in_flight,
                    "credit_limit": evidence.credit.maximum,
                },
            )
            try:
                await self._send_raw(frame.encode())
            except Exception as exc:
                await evidence.credit.abort(exc)
                raise

    async def run_partial_flush(
        self,
        profile: RegistryProfile,
        generation_id: int,
        partial_frames: int,
    ) -> None:
        case_id = f"route.{profile.profile_id}.partial_flush"
        evidence = await self._start_generation(case_id, generation_id, profile)
        frame_count = self.batch_frames + partial_frames
        await self._send_paced_frames(evidence, frame_count)
        request_id = self._request_id("end")
        await self._send_control(
            case_id,
            GenerationEnd(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            ),
        )
        completed = await self._expect(GenerationCompletedEvent)
        if (
            completed.request_id != request_id
            or completed.generation_id != generation_id
            or completed.pipeline_id != evidence.pipeline_id
        ):
            raise RouteValidationError("generation.completed identity is invalid")
        if evidence.accepted_output_frames != frame_count or evidence.inputs:
            raise RouteValidationError("generation did not flush every accepted frame")
        if evidence.credit.in_flight != 0:
            raise RouteValidationError("generation completed with unreleased credit")
        if evidence.changed_sample_count <= 0:
            raise RouteValidationError("real-model output did not change any sample")
        self._active = None
        self._finished_generation_id = generation_id
        self.trace.add_result(
            case_id,
            passed=True,
            evidence={
                "profile_id": profile.profile_id,
                "generation_id": generation_id,
                "input_frames": frame_count,
                "accepted_output_frames": evidence.accepted_output_frames,
                "partial_end_frames": partial_frames,
                "sequence_contiguous": True,
                "timestamps_echoed": True,
                "all_output_finite": True,
                "all_output_normalized": True,
                "output_changed": True,
                "changed_sample_count": evidence.changed_sample_count,
                "finite_sample_count": evidence.finite_sample_count,
                "absolute_peak": evidence.absolute_peak,
                "real_time_frame_interval_ms": 20,
                "maximum_send_lateness_ns": evidence.maximum_send_lateness_ns,
                "advertised_credit_limit": evidence.credit.maximum,
                "credit_high_water": evidence.credit.high_water,
                "credit_bound_respected": (
                    evidence.credit.high_water <= evidence.credit.maximum
                ),
            },
        )

    async def run_cancel(
        self, profile: RegistryProfile, generation_id: int, cancel_frames: int
    ) -> None:
        case_id = f"route.{profile.profile_id}.cancel"
        evidence = await self._start_generation(case_id, generation_id, profile)
        await self._send_paced_frames(evidence, cancel_frames)
        self._active = None
        self._invalidated.add(generation_id)
        await evidence.credit.abort(
            RouteValidationError("generation locally invalidated by cancel")
        )
        request_id = self._request_id("cancel")
        await self._send_control(
            case_id,
            GenerationCancel(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            ),
            extra={"local_output_gate_closed_before_send": True},
        )
        canceled = await self._expect(GenerationCanceledEvent)
        if (
            canceled.request_id != request_id
            or canceled.generation_id != generation_id
            or canceled.pipeline_id != evidence.pipeline_id
        ):
            raise RouteValidationError("generation.canceled identity is invalid")
        self._finished_generation_id = generation_id
        self.trace.add_result(
            case_id,
            passed=True,
            evidence={
                "profile_id": profile.profile_id,
                "generation_id": generation_id,
                "sent_frames_before_cancel": cancel_frames,
                "local_output_gate_closed_before_cancel_send": True,
                "server_acknowledged_cancel": True,
                "accepted_output_after_local_cancel": 0,
            },
        )

    async def finish_stale_exclusion(self) -> None:
        for _ in range(3):
            await asyncio.sleep(0)
        excluded = sum(self._excluded_by_generation.values())
        self.trace.add_result(
            "stale_exclusion",
            passed=True,
            evidence={
                "locally_invalidated_generations": len(self._invalidated),
                "stale_output_frames_excluded": excluded,
                "stale_output_frames_accepted": 0,
                "gate_remained_generation_bound": True,
            },
        )

    async def close(self) -> None:
        if self._active is not None:
            raise RouteValidationError("cannot close with an active generation")
        request_id = self._request_id("close")
        await self._send_control(
            "session.close",
            SessionClose(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
            ),
        )
        closed = await self._expect(SessionClosedEvent)
        if closed.request_id != request_id:
            raise RouteValidationError("session.closed request ID is invalid")
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        await self.websocket.close()

    async def abort(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        with contextlib.suppress(Exception):
            await self.websocket.close()
