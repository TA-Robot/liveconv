from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

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
    ModelSelect,
    ModelSelectedEvent,
    PcmFrame,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_server_event,
    parse_control_message,
)

from liveconv_real_model_route.registry import RegistryProfile
from liveconv_real_model_route.transport import HttpResult

type BadOutput = Literal[
    "none", "sequence", "timestamp", "nonfinite", "unnormalized", "unchanged"
]


@dataclass(slots=True)
class VirtualPacer:
    current_ns: int = 5_000_000_000

    def monotonic_ns(self) -> int:
        return self.current_ns

    async def sleep(self, seconds: float) -> None:
        self.current_ns += round(seconds * 1_000_000_000)
        await asyncio.sleep(0)


class FakeHttp:
    def __init__(self, profiles: tuple[RegistryProfile, ...]) -> None:
        self.profiles = profiles
        self.closed = False
        self.requests: list[tuple[str, str]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> HttpResult:
        assert headers["Authorization"] == "Bearer deterministic-test-token"
        assert timeout_seconds > 0
        self.requests.append((method, url))
        if method == "GET" and url.endswith("/v1/models"):
            return HttpResult(
                200,
                {
                    "protocol_version": 1,
                    "profiles": [profile.safe_metadata() for profile in self.profiles],
                },
            )
        if method == "DELETE" and "/v1/sessions/" in url:
            return HttpResult(204, None)
        assert method == "POST" and url.endswith("/v1/sessions")
        assert json_body is not None
        profile = next(
            profile
            for profile in self.profiles
            if profile.profile_id == json_body["profile_id"]
        )
        return HttpResult(
            201,
            {
                "session_id": "00000000-0000-4000-8000-000000000001",
                "profile_id": profile.profile_id,
                "pipeline_id": "00000000-0000-4000-8000-000000000011",
                "profile_hash": profile.profile_hash,
                "configuration_hash": profile.configuration_hash,
                "websocket_path": "/v1/ws",
                "ticket": "must-never-enter-trace",
            },
        )

    async def close(self) -> None:
        self.closed = True


class FakeWebSocket:
    def __init__(
        self,
        profiles: tuple[RegistryProfile, ...],
        *,
        batch_frames: int = 3,
        credit_frames: int | None = None,
        bad_output: BadOutput = "none",
        send_clock: VirtualPacer | None = None,
        full_batch_delay_seconds: float = 0.0,
    ) -> None:
        self.profiles = {profile.profile_id: profile for profile in profiles}
        self.profile = max(profiles, key=lambda item: item.minimum_context_ms)
        self.pipeline_id = "00000000-0000-4000-8000-000000000011"
        self.batch_frames = batch_frames
        self.credit_frames = credit_frames or batch_frames
        self.bad_output = bad_output
        self.send_clock = send_clock
        self.full_batch_delay_seconds = full_batch_delay_seconds
        self._bad_output_emitted = False
        self._responses: asyncio.Queue[str | bytes] = asyncio.Queue()
        self._active_generation: int | None = None
        self._pending: list[PcmFrame] = []
        self.closed = False
        self.max_unreturned_frames = 0
        self.observed_inputs: dict[int, list[FrameHeader]] = {}
        self.observed_send_times: dict[int, list[int]] = {}
        self._pipeline_counter = 11

    async def send(self, message: str | bytes) -> None:
        if isinstance(message, bytes):
            frame = PcmFrame.decode(message)
            assert frame.header.kind is FrameKind.INPUT
            assert frame.header.generation_id == self._active_generation
            self._pending.append(frame)
            self.observed_inputs.setdefault(frame.header.generation_id, []).append(
                frame.header
            )
            if self.send_clock is not None:
                self.observed_send_times.setdefault(
                    frame.header.generation_id, []
                ).append(self.send_clock.monotonic_ns())
            self.max_unreturned_frames = max(
                self.max_unreturned_frames, len(self._pending)
            )
            if len(self._pending) == self.batch_frames:
                if self.full_batch_delay_seconds:
                    assert self.send_clock is not None
                    await self.send_clock.sleep(self.full_batch_delay_seconds)
                self._flush()
            return

        control = parse_control_message(message)
        if isinstance(control, SessionAttach):
            await self._responses.put(
                encode_server_event(
                    SessionReadyEvent(
                        protocol_version=1,
                        session_id=control.session_id,
                        request_id=control.request_id,
                        profile_id=self.profile.profile_id,
                        profile_hash=self.profile.profile_hash,
                        configuration_hash=self.profile.configuration_hash,
                        pipeline_id=self.pipeline_id,
                        clock_id="fake-gateway-monotonic",
                        limits=IngressLimits(
                            ingress_budget_ms=self.credit_frames * 20,
                            max_ingress_frames=self.credit_frames,
                        ),
                    )
                )
            )
            return
        if isinstance(control, ModelSelect):
            self.profile = self.profiles[control.profile_id]
            self._pipeline_counter += 1
            self.pipeline_id = f"00000000-0000-4000-8000-{self._pipeline_counter:012d}"
            await self._responses.put(
                encode_server_event(
                    ModelSelectedEvent(
                        protocol_version=1,
                        session_id=control.session_id,
                        request_id=control.request_id,
                        profile_id=self.profile.profile_id,
                        profile_hash=self.profile.profile_hash,
                        configuration_hash=self.profile.configuration_hash,
                        pipeline_id=self.pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, GenerationStart):
            assert self._active_generation is None
            self._active_generation = control.generation_id
            self._pending.clear()
            await self._responses.put(
                encode_server_event(
                    GenerationReadyEvent(
                        protocol_version=1,
                        session_id=control.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        profile_id=self.profile.profile_id,
                        profile_hash=self.profile.profile_hash,
                        configuration_hash=self.profile.configuration_hash,
                        pipeline_id=self.pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, GenerationEnd):
            self._flush()
            self._active_generation = None
            await self._responses.put(
                encode_server_event(
                    GenerationCompletedEvent(
                        protocol_version=1,
                        session_id=control.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=self.pipeline_id,
                    )
                )
            )
            return
        if isinstance(control, GenerationCancel):
            stale = self._pending[0] if self._pending else None
            self._pending.clear()
            self._active_generation = None
            await self._responses.put(
                encode_server_event(
                    GenerationCanceledEvent(
                        protocol_version=1,
                        session_id=control.session_id,
                        request_id=control.request_id,
                        generation_id=control.generation_id,
                        pipeline_id=self.pipeline_id,
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
                        session_id=control.session_id,
                        request_id=control.request_id,
                    )
                )
            )
            return
        raise AssertionError(f"unexpected control: {type(control).__name__}")

    def _convert(self, source: PcmFrame) -> PcmFrame:
        header = source.header
        output_sequence = header.sequence
        output_timestamp = header.source_monotonic_ns
        samples = tuple(value * 0.5 for value in source.unpack_samples())
        if self.bad_output == "unchanged":
            samples = source.unpack_samples()
        elif not self._bad_output_emitted:
            if self.bad_output == "sequence":
                output_sequence += 1
            elif self.bad_output == "timestamp":
                output_timestamp += 1
            elif self.bad_output == "nonfinite":
                samples = (float("nan"), *samples[1:])
            elif self.bad_output == "unnormalized":
                samples = (1.1, *samples[1:])
            self._bad_output_emitted = True
        return PcmFrame.from_samples(
            FrameHeader(
                kind=FrameKind.OUTPUT,
                generation_id=header.generation_id,
                sequence=output_sequence,
                source_monotonic_ns=output_timestamp,
            ),
            samples,
        )

    def _flush(self) -> None:
        pending, self._pending = self._pending, []
        for frame in pending:
            self._responses.put_nowait(self._convert(frame).encode())

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
