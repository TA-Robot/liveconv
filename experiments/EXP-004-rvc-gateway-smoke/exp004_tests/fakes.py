from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from liveconv_protocol import (
    FrameHeader,
    FrameKind,
    GenerationCancel,
    GenerationCanceledEvent,
    GenerationCompletedEvent,
    GenerationEnd,
    GenerationReadyEvent,
    GenerationStart,
    IngressLimits,
    PcmFrame,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_server_event,
    parse_control_message,
)

from liveconv_exp004_rvc_gateway_smoke.transport import HttpResult

SESSION_ID = "00000000-0000-4000-8000-000000000001"
PIPELINE_ID = "00000000-0000-4000-8000-000000000002"
TICKET = "fake-one-use-ticket"


@dataclass(frozen=True, slots=True)
class Request:
    method: str
    path: str
    authorization: str | None
    json_body: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class FakeProfileIdentity:
    profile_id: str
    profile_hash: str
    configuration_hash: str


class FakeHttp:
    def __init__(
        self,
        identity: FakeProfileIdentity,
        *,
        extra_catalog_profile: bool = False,
        session_protocol_version: int = 1,
    ) -> None:
        self.identity = identity
        self.extra_catalog_profile = extra_catalog_profile
        self.session_protocol_version = session_protocol_version
        self.requests: list[Request] = []
        self.deleted = False
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
        path = urlsplit(url).path
        self.requests.append(
            Request(method, path, headers.get("Authorization"), json_body)
        )
        if method == "GET" and path == "/v1/models":
            profiles: list[dict[str, str]] = [
                {
                    "profile_id": self.identity.profile_id,
                    "profile_hash": self.identity.profile_hash,
                    "configuration_hash": self.identity.configuration_hash,
                }
            ]
            if self.extra_catalog_profile:
                profiles.append(
                    {
                        "profile_id": "vc.rvc.second-ja.v1",
                        "profile_hash": self.identity.profile_hash,
                        "configuration_hash": self.identity.configuration_hash,
                    }
                )
            return HttpResult(
                200,
                {
                    "protocol_version": 1,
                    "profiles": profiles,
                },
            )
        if method == "POST" and path == "/v1/sessions":
            return HttpResult(
                201,
                {
                    "protocol_version": self.session_protocol_version,
                    "session_id": SESSION_ID,
                    "pipeline_id": PIPELINE_ID,
                    "profile_id": self.identity.profile_id,
                    "profile_hash": self.identity.profile_hash,
                    "configuration_hash": self.identity.configuration_hash,
                    "websocket_path": f"/v1/ws/{SESSION_ID}",
                    "ticket": TICKET,
                },
            )
        if method == "DELETE" and path == f"/v1/sessions/{SESSION_ID}":
            self.deleted = True
            return HttpResult(204, None)
        if method == "GET" and path == f"/v1/sessions/{SESSION_ID}":
            return HttpResult(404 if self.deleted else 200, None)
        raise AssertionError(f"unexpected HTTP request: {method} {path}")

    async def close(self) -> None:
        self.closed = True


BadOutput = Literal["sequence", "timestamp", "nonfinite", "unnormalized", "unchanged"]


class FakeWebSocket:
    def __init__(
        self,
        identity: FakeProfileIdentity,
        *,
        bad_output: BadOutput | None = None,
        generation_ready_gate: asyncio.Event | None = None,
        ingress_budget_ms: int = 1_000,
        max_ingress_frames: int = 50,
    ) -> None:
        self.identity = identity
        self.bad_output = bad_output
        self.generation_ready_gate = generation_ready_gate
        self.ingress_budget_ms = ingress_budget_ms
        self.max_ingress_frames = max_ingress_frames
        self.closed = False
        self._responses: asyncio.Queue[str | bytes] = asyncio.Queue()
        self._active_generation: int | None = None
        self._pending: list[PcmFrame] = []
        self._bad_output_emitted = False

    async def send(self, message: str | bytes) -> None:
        if isinstance(message, bytes):
            frame = PcmFrame.decode(message)
            assert self._active_generation == frame.header.generation_id
            self._pending.append(frame)
            if len(self._pending) == 25:
                await self._flush()
            return

        control = parse_control_message(message)
        if isinstance(control, SessionAttach):
            assert control.ticket == TICKET
            await self._responses.put(
                encode_server_event(
                    SessionReadyEvent(
                        protocol_version=1,
                        session_id=SESSION_ID,
                        request_id=control.request_id,
                        profile_id=self.identity.profile_id,
                        profile_hash=self.identity.profile_hash,
                        configuration_hash=self.identity.configuration_hash,
                        pipeline_id=PIPELINE_ID,
                        clock_id="fake-gateway-monotonic",
                        limits=IngressLimits(
                            ingress_budget_ms=self.ingress_budget_ms,
                            max_ingress_frames=self.max_ingress_frames,
                        ),
                    )
                )
            )
            return
        if isinstance(control, GenerationStart):
            assert self._active_generation is None
            self._active_generation = control.generation_id
            self._pending.clear()
            if self.generation_ready_gate is not None:
                asyncio.create_task(self._wait_and_enqueue_generation_ready(control))
                return
            await self._responses.put(self._generation_ready_response(control))
            return
        if isinstance(control, GenerationEnd):
            assert control.generation_id == self._active_generation
            await self._flush()
            self._active_generation = None
            await self._responses.put(
                encode_server_event(
                    GenerationCompletedEvent(
                        protocol_version=1,
                        session_id=SESSION_ID,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=PIPELINE_ID,
                    )
                )
            )
            return
        if isinstance(control, GenerationCancel):
            assert control.generation_id == self._active_generation
            stale = self._pending[0] if self._pending else None
            self._pending.clear()
            self._active_generation = None
            await self._responses.put(
                encode_server_event(
                    GenerationCanceledEvent(
                        protocol_version=1,
                        session_id=SESSION_ID,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=PIPELINE_ID,
                    )
                )
            )
            if stale is not None:
                await self._responses.put(self._convert(stale).encode())
            return
        if isinstance(control, SessionClose):
            await self._responses.put(
                encode_server_event(
                    SessionClosedEvent(
                        protocol_version=1,
                        session_id=SESSION_ID,
                        request_id=control.request_id,
                    )
                )
            )
            return
        raise AssertionError(f"unexpected control: {type(control).__name__}")

    async def _wait_and_enqueue_generation_ready(
        self, control: GenerationStart
    ) -> None:
        assert self.generation_ready_gate is not None
        await self.generation_ready_gate.wait()
        await self._responses.put(self._generation_ready_response(control))

    def _generation_ready_response(self, control: GenerationStart) -> str:
        return encode_server_event(
            GenerationReadyEvent(
                protocol_version=1,
                session_id=SESSION_ID,
                request_id=control.request_id,
                generation_id=control.generation_id,
                profile_id=self.identity.profile_id,
                profile_hash=self.identity.profile_hash,
                configuration_hash=self.identity.configuration_hash,
                pipeline_id=PIPELINE_ID,
            )
        )

    async def _flush(self) -> None:
        pending, self._pending = self._pending, []
        for frame in pending:
            await self._responses.put(self._convert(frame).encode())

    def _convert(self, source: PcmFrame) -> PcmFrame:
        header = source.header
        sequence = header.sequence
        timestamp = header.source_monotonic_ns
        samples = tuple(value * 0.5 for value in source.unpack_samples())
        if self.bad_output == "unchanged":
            samples = source.unpack_samples()
        elif not self._bad_output_emitted:
            if self.bad_output == "sequence":
                sequence += 1
            elif self.bad_output == "timestamp":
                timestamp += 1
            elif self.bad_output == "nonfinite":
                samples = (float("nan"), *samples[1:])
            elif self.bad_output == "unnormalized":
                samples = (1.1, *samples[1:])
            self._bad_output_emitted = self.bad_output is not None
        return PcmFrame.from_samples(
            FrameHeader(
                kind=FrameKind.OUTPUT,
                generation_id=header.generation_id,
                sequence=sequence,
                source_monotonic_ns=timestamp,
            ),
            samples,
        )

    async def recv(self) -> str | bytes:
        return await self._responses.get()

    async def close(self) -> None:
        self.closed = True


class FakeConnector:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.calls: list[tuple[str, str, float]] = []

    async def connect(
        self, url: str, *, origin: str, timeout_seconds: float
    ) -> FakeWebSocket:
        self.calls.append((url, origin, timeout_seconds))
        return self.websocket


class VirtualPacer:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
