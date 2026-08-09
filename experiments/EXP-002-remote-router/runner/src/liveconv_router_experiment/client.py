from __future__ import annotations

import asyncio
import hashlib
from dataclasses import fields, is_dataclass
from typing import TypeVar

from liveconv_protocol import (
    ErrorCode,
    ErrorEvent,
    FallbackRequiredEvent,
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
    Ping,
    PongEvent,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_control_message,
    parse_server_event,
)

from .errors import ExperimentFailure, TransportFailure, WebSocketClosed
from .transport import GatewayApi, SessionDescriptor, WebSocketConnection

_EventT = TypeVar("_EventT", bound=ParsedServerEvent)


def _event_details(event: ParsedServerEvent) -> dict[str, object]:
    """Return only contract metadata; intentionally omit free-form messages."""

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
        "client_clock_id",
        "client_monotonic_ns",
        "code",
        "recoverable",
        "required_action",
        "field",
        "reason_code",
        "limits",
    }
    details: dict[str, object] = {"type": event.message_type}
    if not is_dataclass(event):
        return details
    for item in fields(event):
        if item.name not in allowed:
            continue
        value = getattr(event, item.name)
        if value is not None:
            if is_dataclass(value):
                value = {
                    child.name: getattr(value, child.name) for child in fields(value)
                }
            details[item.name] = value
    return details


class ProtocolSession:
    """A strict version 1 client with generation and output acceptance gates."""

    def __init__(
        self,
        api: GatewayApi,
        descriptor: SessionDescriptor,
        case_id: str,
        websocket: WebSocketConnection,
    ) -> None:
        self.api = api
        self.descriptor = descriptor
        self.case_id = case_id
        self.websocket = websocket
        self.pipeline_id = descriptor.pipeline_id
        self.profile_id = descriptor.profile_id
        self.server_clock_id: str | None = None
        self.active_generation_id: int | None = None
        self.active_pipeline_id: str | None = None
        self.next_input_sequence = 0
        self.next_output_sequence = 0
        self.last_source_monotonic_ns: int | None = None
        self._expected_source_times: dict[int, int] = {}
        self._request_counter = 0
        self.closed = False

    @classmethod
    async def attach(
        cls,
        api: GatewayApi,
        descriptor: SessionDescriptor,
        case_id: str,
    ) -> ProtocolSession:
        websocket = await api.open_websocket(case_id, descriptor)
        session = cls(api, descriptor, case_id, websocket)
        request_id = session._next_request_id("attach")
        await session._send_control(
            SessionAttach(
                protocol_version=1,
                request_id=request_id,
                session_id=descriptor.session_id,
                ticket=descriptor.ticket,
            ),
            extra_trace={"ticket_present": True},
        )
        ready = await session._expect_event(SessionReadyEvent)
        if ready.request_id != request_id:
            raise ExperimentFailure("session.ready request_id does not match attach")
        if ready.session_id != descriptor.session_id:
            raise ExperimentFailure("session.ready session_id does not match session")
        if ready.profile_id != descriptor.profile_id:
            raise ExperimentFailure("session.ready profile_id does not match session")
        if ready.profile_hash != descriptor.profile_hash:
            raise ExperimentFailure("session.ready profile_hash does not match session")
        if ready.configuration_hash != descriptor.configuration_hash:
            raise ExperimentFailure(
                "session.ready configuration_hash does not match session"
            )
        if ready.pipeline_id != descriptor.pipeline_id:
            raise ExperimentFailure("session.ready pipeline_id does not match session")
        session.server_clock_id = ready.clock_id
        api.trace.register_server_clock(ready.clock_id)
        return session

    def _next_request_id(self, action: str) -> str:
        self._request_counter += 1
        request_id = f"{self.case_id}.{action}.{self._request_counter}"
        if len(request_id) > 128:
            raise ExperimentFailure("generated request_id exceeds protocol limit")
        return request_id

    async def _send(self, message: str | bytes) -> None:
        try:
            async with asyncio.timeout(self.api.timeout_seconds):
                await self.websocket.send(message)
        except TimeoutError as exc:
            raise TransportFailure("WebSocket send timed out") from exc

    async def _receive(self) -> str | bytes:
        try:
            async with asyncio.timeout(self.api.timeout_seconds):
                return await self.websocket.recv()
        except TimeoutError as exc:
            raise TransportFailure("WebSocket receive timed out") from exc

    async def _send_control(
        self,
        message: ParsedControlMessage,
        *,
        extra_trace: dict[str, object] | None = None,
    ) -> None:
        details: dict[str, object] = {
            "type": message.message_type,
            "request_id": message.request_id,
            "session_id": message.session_id,
        }
        for name in ("generation_id", "profile_id", "client_monotonic_ns", "clock_id"):
            value = getattr(message, name, None)
            if value is not None:
                details[name] = value
        if extra_trace:
            details.update(extra_trace)
        self.api.trace.record(
            self.case_id,
            "client_to_server",
            "control",
            details,
        )
        await self._send(encode_control_message(message))

    async def receive_event(self) -> ParsedServerEvent:
        message = await self._receive()
        if not isinstance(message, str):
            raise ExperimentFailure("expected a text server event, received binary PCM")
        event = parse_server_event(message)
        server_clock_id: str | None = None
        server_monotonic_ns: int | None = None
        if isinstance(event, SessionReadyEvent):
            self.api.trace.register_server_clock(event.clock_id)
        if isinstance(event, PongEvent):
            server_clock_id = event.clock_id
            server_monotonic_ns = event.server_monotonic_ns
        self.api.trace.record(
            self.case_id,
            "server_to_client",
            "event",
            _event_details(event),
            server_clock_id=server_clock_id,
            server_monotonic_ns=server_monotonic_ns,
        )
        event_session_id = getattr(event, "session_id", None)
        if (
            event_session_id is not None
            and event_session_id != self.descriptor.session_id
        ):
            raise ExperimentFailure("server event belongs to a different session")
        return event

    async def _expect_event(self, event_type: type[_EventT]) -> _EventT:
        event = await self.receive_event()
        if isinstance(event, ErrorEvent):
            expectation = event_type.message_type
            raise ExperimentFailure(
                f"gateway returned {event.code} while expecting {expectation}"
            )
        if not isinstance(event, event_type):
            raise ExperimentFailure(
                f"expected {event_type.message_type}, received {event.message_type}"
            )
        return event

    async def start_generation(self, generation_id: int) -> GenerationReadyEvent:
        if self.active_generation_id is not None:
            raise ExperimentFailure("client already has an active generation")
        request_id = self._next_request_id("start")
        await self._send_control(
            GenerationStart(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            )
        )
        ready = await self._expect_event(GenerationReadyEvent)
        if ready.request_id != request_id or ready.generation_id != generation_id:
            raise ExperimentFailure("generation.ready does not match generation.start")
        if ready.pipeline_id != self.pipeline_id:
            raise ExperimentFailure("generation.ready uses the wrong pipeline")
        if ready.profile_id != self.profile_id:
            raise ExperimentFailure("generation.ready uses the wrong profile")
        self.active_generation_id = generation_id
        self.active_pipeline_id = ready.pipeline_id
        self.next_input_sequence = 0
        self.next_output_sequence = 0
        self.last_source_monotonic_ns = None
        self._expected_source_times.clear()
        return ready

    async def select_model(self, profile_id: str) -> ModelSelectedEvent:
        if self.active_generation_id is not None:
            raise ExperimentFailure(
                "safe client forbids model switch during generation"
            )
        request_id = self._next_request_id("select")
        await self._send_control(
            ModelSelect(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                profile_id=profile_id,
            )
        )
        selected = await self._expect_event(ModelSelectedEvent)
        if selected.request_id != request_id or selected.profile_id != profile_id:
            raise ExperimentFailure("model.selected does not match model.select")
        if selected.pipeline_id == self.pipeline_id:
            raise ExperimentFailure("model switch did not create a new pipeline")
        self.profile_id = profile_id
        self.pipeline_id = selected.pipeline_id
        return selected

    async def inject_model_select(self, profile_id: str) -> str:
        request_id = self._next_request_id("illegal-select")
        await self._send_control(
            ModelSelect(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                profile_id=profile_id,
            ),
            extra_trace={"fault_injected": True},
        )
        return request_id

    async def end_generation(self) -> GenerationCompletedEvent:
        generation_id = self.active_generation_id
        pipeline_id = self.active_pipeline_id
        if generation_id is None or pipeline_id is None:
            raise ExperimentFailure("no active generation to end")
        request_id = self._next_request_id("end")
        await self._send_control(
            GenerationEnd(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            )
        )
        completed = await self._expect_event(GenerationCompletedEvent)
        if (
            completed.request_id != request_id
            or completed.generation_id != generation_id
            or completed.pipeline_id != pipeline_id
        ):
            raise ExperimentFailure(
                "generation.completed does not match active pipeline"
            )
        self._clear_generation()
        return completed

    async def cancel_generation(self) -> GenerationCanceledEvent:
        generation_id = self.active_generation_id
        pipeline_id = self.active_pipeline_id
        if generation_id is None or pipeline_id is None:
            raise ExperimentFailure("no active generation to cancel")
        request_id = self._next_request_id("cancel")
        await self._send_control(
            GenerationCancel(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                generation_id=generation_id,
            )
        )
        canceled = await self._expect_event(GenerationCanceledEvent)
        if (
            canceled.request_id != request_id
            or canceled.generation_id != generation_id
            or canceled.pipeline_id != pipeline_id
        ):
            raise ExperimentFailure(
                "generation.canceled does not match active pipeline"
            )
        self._clear_generation()
        return canceled

    def _clear_generation(self) -> None:
        self.active_generation_id = None
        self.active_pipeline_id = None
        self._expected_source_times.clear()

    async def send_frame(self, frame: PcmFrame) -> None:
        header = frame.header
        if header.kind is not FrameKind.INPUT:
            raise ExperimentFailure("client can send only INPUT PCM frames")
        if self.active_generation_id != header.generation_id:
            raise ExperimentFailure("input frame generation is not active")
        if self.active_pipeline_id != self.pipeline_id:
            raise ExperimentFailure("active generation pipeline has changed")
        if header.sequence != self.next_input_sequence:
            raise ExperimentFailure("input frame sequence is not contiguous")
        if (
            self.last_source_monotonic_ns is not None
            and header.source_monotonic_ns < self.last_source_monotonic_ns
        ):
            raise ExperimentFailure("input source_monotonic_ns decreased")
        self._expected_source_times[header.sequence] = header.source_monotonic_ns
        self.next_input_sequence += 1
        self.last_source_monotonic_ns = header.source_monotonic_ns
        await self._send_frame(frame, fault_injected=False)

    async def inject_frame(self, frame: PcmFrame) -> None:
        await self._send_frame(frame, fault_injected=True)

    async def _send_frame(self, frame: PcmFrame, *, fault_injected: bool) -> None:
        header = frame.header
        self.api.trace.record(
            self.case_id,
            "client_to_server",
            "pcm.frame",
            {
                "kind": "input",
                "generation_id": header.generation_id,
                "sequence": header.sequence,
                "sample_rate": header.sample_rate,
                "channels": header.channels,
                "samples_per_channel": header.samples_per_channel,
                "source_monotonic_ns": header.source_monotonic_ns,
                "payload_bytes": len(frame.payload),
                "payload_sha256": hashlib.sha256(frame.payload).hexdigest(),
                "pipeline_id": self.active_pipeline_id,
                "fault_injected": fault_injected,
            },
        )
        await self._send(frame.encode())

    async def receive_output(self) -> PcmFrame:
        message = await self._receive()
        if not isinstance(message, bytes):
            event = parse_server_event(message)
            raise ExperimentFailure(
                f"expected output PCM, received {event.message_type}"
            )
        frame = PcmFrame.decode(message)
        header = frame.header
        if header.kind is not FrameKind.OUTPUT:
            raise ExperimentFailure("gateway output frame kind is not OUTPUT")
        if self.active_generation_id is None or self.active_pipeline_id is None:
            raise ExperimentFailure("output arrived without an active generation")
        if self.active_pipeline_id != self.pipeline_id:
            raise ExperimentFailure("output was accepted against a changed pipeline")
        if header.generation_id != self.active_generation_id:
            raise ExperimentFailure("output belongs to a stale or future generation")
        if header.sequence != self.next_output_sequence:
            raise ExperimentFailure(
                "output frame sequence is duplicate or discontinuous"
            )
        expected_source = self._expected_source_times.pop(header.sequence, None)
        if expected_source is None or header.source_monotonic_ns != expected_source:
            raise ExperimentFailure("output source timestamp does not match input")
        self.next_output_sequence += 1
        self.api.trace.record(
            self.case_id,
            "server_to_client",
            "pcm.frame",
            {
                "kind": "output",
                "generation_id": header.generation_id,
                "sequence": header.sequence,
                "sample_rate": header.sample_rate,
                "channels": header.channels,
                "samples_per_channel": header.samples_per_channel,
                "source_monotonic_ns": header.source_monotonic_ns,
                "payload_bytes": len(frame.payload),
                "payload_sha256": hashlib.sha256(frame.payload).hexdigest(),
                "pipeline_id": self.active_pipeline_id,
            },
        )
        return frame

    async def expect_error(
        self,
        code: ErrorCode,
        *,
        request_id: str | None = None,
        generation_id: int | None = None,
    ) -> ErrorEvent:
        event = await self.receive_event()
        if not isinstance(event, ErrorEvent):
            raise ExperimentFailure(f"expected error, received {event.message_type}")
        if event.code is not code:
            raise ExperimentFailure(f"expected {code}, received {event.code}")
        if request_id is not None and event.request_id != request_id:
            raise ExperimentFailure("error request_id does not match fault command")
        if generation_id is not None and event.generation_id != generation_id:
            raise ExperimentFailure("error generation_id does not match fault frame")
        return event

    async def expect_fallback(
        self, code: ErrorCode, generation_id: int
    ) -> FallbackRequiredEvent:
        event = await self.receive_event()
        if not isinstance(event, FallbackRequiredEvent):
            raise ExperimentFailure(
                f"expected fallback.required, received {event.message_type}"
            )
        if event.reason_code is not code or event.generation_id != generation_id:
            raise ExperimentFailure("fallback.required does not match injected failure")
        if event.pipeline_id != self.active_pipeline_id:
            raise ExperimentFailure("fallback.required uses the wrong pipeline")
        self._clear_generation()
        return event

    async def ping(self) -> PongEvent:
        request_id = self._next_request_id("ping")
        client_monotonic_ns = self.api.trace.clock.monotonic_ns()
        await self._send_control(
            Ping(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
                client_monotonic_ns=client_monotonic_ns,
                clock_id=self.api.trace.client_clock_id,
            )
        )
        pong = await self._expect_event(PongEvent)
        if (
            pong.request_id != request_id
            or pong.client_clock_id != self.api.trace.client_clock_id
            or pong.client_monotonic_ns != client_monotonic_ns
        ):
            raise ExperimentFailure("pong does not echo the client clock reading")
        if self.server_clock_id is not None and pong.clock_id != self.server_clock_id:
            raise ExperimentFailure("pong changed the server clock domain")
        return pong

    async def close(self) -> None:
        if self.closed:
            return
        request_id = self._next_request_id("close")
        await self._send_control(
            SessionClose(
                protocol_version=1,
                request_id=request_id,
                session_id=self.descriptor.session_id,
            )
        )
        closed = await self._expect_event(SessionClosedEvent)
        if closed.request_id != request_id:
            raise ExperimentFailure("session.closed does not match session.close")
        self.closed = True
        await self.websocket.close()

    async def expect_transport_closed(self) -> None:
        try:
            await self._receive()
        except WebSocketClosed:
            self.closed = True
            return
        raise ExperimentFailure("WebSocket remained readable after session deletion")

    async def abort(self) -> None:
        self.closed = True
        await self.websocket.close()


async def attempt_ticket_replay(
    api: GatewayApi,
    descriptor: SessionDescriptor,
    case_id: str,
) -> ErrorEvent:
    websocket = await api.open_websocket(case_id, descriptor)
    attach = SessionAttach(
        protocol_version=1,
        request_id=f"{case_id}.replay.attach",
        session_id=descriptor.session_id,
        ticket=descriptor.ticket,
    )
    api.trace.record(
        case_id,
        "client_to_server",
        "control",
        {
            "type": attach.message_type,
            "request_id": attach.request_id,
            "session_id": attach.session_id,
            "ticket_present": True,
            "fault_injected": True,
        },
    )
    try:
        async with asyncio.timeout(api.timeout_seconds):
            await websocket.send(encode_control_message(attach))
            response = await websocket.recv()
    except TimeoutError as exc:
        raise TransportFailure("ticket replay response timed out") from exc
    finally:
        await websocket.close()
    if not isinstance(response, str):
        raise ExperimentFailure("ticket replay returned binary data")
    event = parse_server_event(response)
    api.trace.record(
        case_id,
        "server_to_client",
        "event",
        _event_details(event),
    )
    if not isinstance(event, ErrorEvent) or event.code is not ErrorCode.AUTH_FAILED:
        raise ExperimentFailure("one-use ticket replay was not rejected")
    return event


__all__ = ["ProtocolSession", "SessionDescriptor", "attempt_ticket_replay"]
