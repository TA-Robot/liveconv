from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from liveconv_protocol import (
    ErrorCode,
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
    IngressLimits,
    ModelSelect,
    ModelSelectedEvent,
    PcmFrame,
    Ping,
    PongEvent,
    RequiredAction,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_server_event,
    parse_control_message,
)

from liveconv_router_experiment.errors import WebSocketClosed
from liveconv_router_experiment.transport import HttpResult

PASSTHROUGH = "test.passthrough.v1"
GAIN = "test.gain.v1"
PROFILE_HASH = f"sha256:{'a' * 64}"
PASSTHROUGH_CONFIG_HASH = f"sha256:{'b' * 64}"
GAIN_CONFIG_HASH = f"sha256:{'c' * 64}"


def _uuid(value: int) -> str:
    return str(UUID(int=value))


@dataclass(slots=True)
class FakeSession:
    session_id: str
    pipeline_id: str
    profile_id: str
    configuration_hash: str
    ticket: str
    consumed: bool = False
    deleted: bool = False
    active_generation_id: int | None = None
    next_sequence: int = 0
    last_generation_id: int | None = None
    connection: FakeWebSocket | None = None


class FakeGatewayState:
    def __init__(
        self,
        *,
        token: str = "test-token",
        output_sequence_offset: int = 0,
        wrong_generation_pipeline: bool = False,
    ) -> None:
        self.token = token
        self.output_sequence_offset = output_sequence_offset
        self.wrong_generation_pipeline = wrong_generation_pipeline
        self.sessions: dict[str, FakeSession] = {}
        self.next_session = 1
        self.server_clock_id = "fake-server-clock"
        self.server_monotonic_ns = 5_000_000_000

    def create_session(self, profile_id: str) -> FakeSession:
        index = self.next_session
        self.next_session += 1
        session = FakeSession(
            session_id=_uuid(index),
            pipeline_id=_uuid(10_000 + index),
            profile_id=profile_id,
            configuration_hash=(
                GAIN_CONFIG_HASH if profile_id == GAIN else PASSTHROUGH_CONFIG_HASH
            ),
            ticket=f"fake-ticket-{index}",
        )
        self.sessions[session.session_id] = session
        return session


class FakeHttpAdapter:
    def __init__(self, state: FakeGatewayState) -> None:
        self.state = state
        self.closed = False

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> HttpResult:
        del timeout_seconds
        if headers.get("Authorization") != f"Bearer {self.state.token}":
            return HttpResult(401, {"detail": "invalid bearer credential"})
        path = urlsplit(url).path
        if method == "POST" and path == "/v1/sessions":
            assert json_body is not None
            profile_id = json_body["profile_id"]
            assert isinstance(profile_id, str)
            session = self.state.create_session(profile_id)
            return HttpResult(
                201,
                {
                    "protocol_version": 1,
                    "session_id": session.session_id,
                    "pipeline_id": session.pipeline_id,
                    "profile_id": session.profile_id,
                    "profile_hash": PROFILE_HASH,
                    "configuration_hash": session.configuration_hash,
                    "status": "created",
                    "active_generation_id": None,
                    "limits": {
                        "ingress_budget_ms": 500,
                        "max_ingress_frames": 25,
                    },
                    "input": {
                        "sample_rate": 48_000,
                        "channels": 1,
                        "sample_format": "f32le",
                        "frame_ms": 20,
                    },
                    "websocket_path": "/v1/ws",
                    "ticket": session.ticket,
                    "ticket_expires_in_seconds": 30,
                },
            )
        prefix = "/v1/sessions/"
        if path.startswith(prefix):
            session_id = path.removeprefix(prefix)
            session = self.state.sessions.get(session_id)
            if session is None or session.deleted:
                return HttpResult(404, {"detail": "session not found"})
            if method == "DELETE":
                session.deleted = True
                if session.connection is not None:
                    session.connection.server_closed = True
                return HttpResult(204, None)
            if method == "GET":
                return HttpResult(200, {"session_id": session_id})
        raise AssertionError(f"unexpected fake HTTP request: {method} {path}")

    async def close(self) -> None:
        self.closed = True


class FakeConnector:
    def __init__(self, state: FakeGatewayState) -> None:
        self.state = state

    async def connect(
        self,
        url: str,
        *,
        origin: str,
        timeout_seconds: float,
    ) -> FakeWebSocket:
        del origin, timeout_seconds
        assert urlsplit(url).path == "/v1/ws"
        return FakeWebSocket(self.state)


class FakeWebSocket:
    def __init__(self, state: FakeGatewayState) -> None:
        self.state = state
        self.session: FakeSession | None = None
        self.outbound: deque[str | bytes] = deque()
        self.server_closed = False
        self.client_closed = False

    async def send(self, message: str | bytes) -> None:
        if self.server_closed or self.client_closed:
            raise WebSocketClosed("fake socket is closed")
        if isinstance(message, bytes):
            self._receive_frame(message)
            return
        control = parse_control_message(message)
        if self.session is None:
            self._attach(control)
            return
        self._control(control)

    def _attach(self, control: object) -> None:
        if not isinstance(control, SessionAttach):
            raise AssertionError("first fake message must attach")
        session = self.state.sessions.get(control.session_id)
        if (
            session is None
            or session.deleted
            or session.consumed
            or control.ticket != session.ticket
        ):
            self.outbound.append(
                encode_server_event(
                    ErrorEvent(
                        protocol_version=1,
                        code=ErrorCode.AUTH_FAILED,
                        recoverable=False,
                        required_action=RequiredAction.CLOSE_SESSION,
                        message="attachment authentication failed",
                    )
                )
            )
            self.server_closed = True
            return
        session.consumed = True
        session.connection = self
        self.session = session
        self.outbound.append(
            encode_server_event(
                SessionReadyEvent(
                    protocol_version=1,
                    session_id=session.session_id,
                    request_id=control.request_id,
                    profile_id=session.profile_id,
                    profile_hash=PROFILE_HASH,
                    configuration_hash=session.configuration_hash,
                    pipeline_id=session.pipeline_id,
                    clock_id=self.state.server_clock_id,
                    limits=IngressLimits(500, 25),
                )
            )
        )

    def _control(self, control: object) -> None:
        session = self._required_session()
        if isinstance(control, GenerationStart):
            if session.active_generation_id is not None:
                self._error(control, ErrorCode.INVALID_STATE)
                return
            session.active_generation_id = control.generation_id
            session.last_generation_id = control.generation_id
            session.next_sequence = 0
            pipeline_id = (
                _uuid(99_999)
                if self.state.wrong_generation_pipeline
                else session.pipeline_id
            )
            self.outbound.append(
                encode_server_event(
                    GenerationReadyEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        profile_id=session.profile_id,
                        profile_hash=PROFILE_HASH,
                        configuration_hash=session.configuration_hash,
                        pipeline_id=pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, ModelSelect):
            if session.active_generation_id is not None:
                self._error(control, ErrorCode.INVALID_STATE)
                return
            session.profile_id = control.profile_id
            session.pipeline_id = _uuid(20_000 + self.state.next_session)
            session.configuration_hash = (
                GAIN_CONFIG_HASH
                if control.profile_id == GAIN
                else PASSTHROUGH_CONFIG_HASH
            )
            self.outbound.append(
                encode_server_event(
                    ModelSelectedEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                        profile_id=session.profile_id,
                        profile_hash=PROFILE_HASH,
                        configuration_hash=session.configuration_hash,
                        pipeline_id=session.pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, GenerationCancel):
            if session.active_generation_id != control.generation_id:
                self._error(control, ErrorCode.STALE_GENERATION)
                return
            pipeline_id = session.pipeline_id
            session.active_generation_id = None
            self.outbound.append(
                encode_server_event(
                    GenerationCanceledEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, GenerationEnd):
            if session.active_generation_id != control.generation_id:
                self._error(control, ErrorCode.STALE_GENERATION)
                return
            pipeline_id = session.pipeline_id
            session.active_generation_id = None
            self.outbound.append(
                encode_server_event(
                    GenerationCompletedEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, Ping):
            self.state.server_monotonic_ns += 1_000_000
            self.outbound.append(
                encode_server_event(
                    PongEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                        client_clock_id=control.clock_id,
                        client_monotonic_ns=control.client_monotonic_ns,
                        clock_id=self.state.server_clock_id,
                        server_monotonic_ns=self.state.server_monotonic_ns,
                    )
                )
            )
            return
        if isinstance(control, SessionClose):
            self.outbound.append(
                encode_server_event(
                    SessionClosedEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        request_id=control.request_id,
                    )
                )
            )
            session.deleted = True
            return
        raise AssertionError(f"unsupported fake control: {type(control).__name__}")

    def _receive_frame(self, encoded: bytes) -> None:
        session = self._required_session()
        frame = PcmFrame.decode(encoded)
        header = frame.header
        if session.active_generation_id != header.generation_id:
            self._frame_error(header.generation_id, ErrorCode.STALE_GENERATION)
            return
        if header.sequence != session.next_sequence:
            generation_id = header.generation_id
            self._frame_error(generation_id, ErrorCode.SEQUENCE_GAP)
            self.outbound.append(
                encode_server_event(
                    FallbackRequiredEvent(
                        protocol_version=1,
                        session_id=session.session_id,
                        generation_id=generation_id,
                        pipeline_id=session.pipeline_id,
                        reason_code=ErrorCode.SEQUENCE_GAP,
                    )
                )
            )
            session.active_generation_id = None
            return
        session.next_sequence += 1
        samples = frame.unpack_samples()
        if session.profile_id == GAIN:
            samples = tuple(sample * 0.5 for sample in samples)
        output = PcmFrame.from_samples(
            FrameHeader(
                kind=FrameKind.OUTPUT,
                generation_id=header.generation_id,
                sequence=header.sequence + self.state.output_sequence_offset,
                source_monotonic_ns=header.source_monotonic_ns,
            ),
            samples,
        )
        self.outbound.append(output.encode())

    def _required_session(self) -> FakeSession:
        if self.session is None:
            raise AssertionError("fake connection is not attached")
        return self.session

    def _error(self, control: object, code: ErrorCode) -> None:
        session = self._required_session()
        self.outbound.append(
            encode_server_event(
                ErrorEvent(
                    protocol_version=1,
                    session_id=session.session_id,
                    request_id=getattr(control, "request_id"),
                    generation_id=getattr(control, "generation_id", None),
                    code=code,
                    recoverable=True,
                    required_action=RequiredAction.NONE,
                    message="injected fake state error",
                )
            )
        )

    def _frame_error(self, generation_id: int, code: ErrorCode) -> None:
        session = self._required_session()
        action = (
            RequiredAction.FALLBACK
            if code is ErrorCode.SEQUENCE_GAP
            else RequiredAction.NONE
        )
        self.outbound.append(
            encode_server_event(
                ErrorEvent(
                    protocol_version=1,
                    session_id=session.session_id,
                    generation_id=generation_id,
                    code=code,
                    recoverable=True,
                    required_action=action,
                    message="injected fake frame error",
                )
            )
        )

    async def recv(self) -> str | bytes:
        if self.outbound:
            return self.outbound.popleft()
        if self.server_closed or self.client_closed:
            raise WebSocketClosed("fake socket is closed")
        raise AssertionError("fake socket has no queued server message")

    async def close(self) -> None:
        self.client_closed = True
