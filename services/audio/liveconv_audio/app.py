from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import anyio
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from liveconv_protocol import (
    MAX_CONTROL_MESSAGE_BYTES,
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
    ParsedServerEvent,
    PcmFrame,
    Ping,
    PongEvent,
    ProtocolValidationError,
    RequiredAction,
    SessionAttach,
    SessionClose,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_control_message,
    encode_server_event,
    parse_control_message,
)
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ._adapter_registry import (
    DeliveryMode,
    buffered_input_capacity_frames,
    delivery_mode_for_profile,
)
from .profiles import ModelProfile, ProfileRegistry
from .roster import ModelRoster
from .sessions import CachedResponse, Session, SessionCapacityError, SessionStore
from .settings import Settings
from .worker_bridge import (
    WorkerBridge,
    WorkerSupervisorFactory,
    builtin_supervisor_factory,
)

_bearer = HTTPBearer(auto_error=False)
MAX_HTTP_BODY_BYTES = 16 * 1024


class HttpIngressGuard:
    """Authenticate and bound HTTP API bodies before FastAPI parses them."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/v1/"):
            await self.app(scope, receive, send)
            return
        if not self.settings.token_is_acceptable:
            await self._reject(
                scope,
                receive,
                send,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "gateway credential is not safely configured",
            )
            return
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"")
        try:
            scheme, credential = authorization.split(b" ", 1)
        except ValueError:
            scheme, credential = b"", b""
        if scheme.lower() != b"bearer" or not secrets.compare_digest(
            credential,
            self.settings.api_token.encode("utf-8"),
        ):
            await self._reject(
                scope,
                receive,
                send,
                status.HTTP_401_UNAUTHORIZED,
                "invalid bearer credential",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return

        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = MAX_HTTP_BODY_BYTES + 1
            if declared_length < 0 or declared_length > MAX_HTTP_BODY_BYTES:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "request body exceeds 16 KiB",
                )
                return

        buffered: list[Message] = []
        body_bytes = 0
        while True:
            message = await receive()
            buffered.append(message)
            if message["type"] != "http.request":
                break
            body = message.get("body", b"")
            body_bytes += len(body)
            if body_bytes > MAX_HTTP_BODY_BYTES:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "request body exceeds 16 KiB",
                )
                return
            if not message.get("more_body", False):
                break

        messages = iter(buffered)

        async def replay() -> Message:
            return next(messages, {"type": "http.disconnect"})

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        detail: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        response = JSONResponse(
            {"detail": detail},
            status_code=status_code,
            headers=headers,
        )
        await response(scope, receive, send)


class AudioFormat(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sample_rate: Literal[48_000]
    channels: Literal[1]
    sample_format: Literal["f32le"]
    frame_ms: Literal[20]


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    protocol_version: Literal[1]
    profile_id: StrictStr = Field(min_length=1, max_length=128)
    input: AudioFormat
    voice_id: StrictStr | None = Field(default=None, min_length=1, max_length=128)


async def require_bearer(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    settings: Settings = request.app.state.gateway.settings
    if not settings.token_is_acceptable:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "gateway credential is not safely configured",
        )
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(
            credentials.credentials.encode("utf-8"),
            settings.api_token.encode("utf-8"),
        )
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid bearer credential",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _error_policy(code: ErrorCode) -> tuple[bool, RequiredAction]:
    if code in {ErrorCode.AUTH_FAILED, ErrorCode.UNSUPPORTED_PROTOCOL}:
        return False, RequiredAction.CLOSE_SESSION
    if code in {
        ErrorCode.MODEL_TIMEOUT,
        ErrorCode.QUEUE_OVERFLOW,
        ErrorCode.SEQUENCE_GAP,
        ErrorCode.UNSUPPORTED_AUDIO,
        ErrorCode.WORKER_CRASH,
    }:
        return True, RequiredAction.FALLBACK
    if code is ErrorCode.MODEL_UNAVAILABLE:
        return True, RequiredAction.RETRY
    return True, RequiredAction.NONE


class Connection:
    def __init__(
        self,
        gateway: Gateway,
        websocket: WebSocket,
        session: Session,
    ) -> None:
        self.gateway = gateway
        self.websocket = websocket
        self.session = session
        self.ingress: asyncio.Queue[PcmFrame] = asyncio.Queue(
            maxsize=session.max_ingress_frames
        )
        self.send_lock = asyncio.Lock()
        self.terminal_event = asyncio.Event()
        self.worker_task: asyncio.Task[None] | None = None
        self.output_task: asyncio.Task[None] | None = None
        self.drain_task: asyncio.Task[None] | None = None
        self.active_frame_task: asyncio.Task[None] | None = None
        self.active_frame_generation_id: int | None = None
        self.worker_bridge = WorkerBridge(
            gateway.worker_supervisor_factory,
            queue_budget_ms=session.ingress_budget_ms,
        )
        self.pending_ingress_frames = 0
        self.generation_input_frames = 0
        self.generation_output_frames = 0
        self.generation_delivery_mode: DeliveryMode | None = None
        self.generation_ingress_limit_frames = session.max_ingress_frames
        self.output_available = asyncio.Event()
        self.output_drained = asyncio.Event()
        self.output_drained.set()
        self.closed = False
        self.stopping = False
        self.silent_terminal = False
        self.generation_failures: dict[int, ProtocolValidationError] = {}
        self.pending_end: tuple[str, str, int, str] | None = None

    async def send_event(self, event: ParsedServerEvent) -> None:
        encoded = encode_server_event(event)
        async with self.send_lock:
            if not self.silent_terminal and not self.session.deleted:
                try:
                    await asyncio.wait_for(
                        self.websocket.send_text(encoded),
                        timeout=self.gateway.settings.send_timeout_seconds,
                    )
                except TimeoutError as error:
                    self._mark_terminal(silent=True)
                    raise ProtocolValidationError(
                        ErrorCode.INVALID_STATE,
                        "outbound WebSocket send deadline expired",
                    ) from error

    async def send_frame_if_current(self, frame: PcmFrame) -> None:
        async with self.send_lock:
            if self._generation_is_current(frame.header.generation_id):
                try:
                    await asyncio.wait_for(
                        self.websocket.send_bytes(frame.encode()),
                        timeout=self.gateway.settings.send_timeout_seconds,
                    )
                except TimeoutError as error:
                    self._mark_terminal(silent=True)
                    raise ProtocolValidationError(
                        ErrorCode.INVALID_STATE,
                        "outbound WebSocket send deadline expired",
                    ) from error

    def _mark_terminal(self, *, silent: bool) -> None:
        self.silent_terminal = self.silent_terminal or silent
        self.closed = True
        self.terminal_event.set()

    async def receive_or_terminal(
        self, websocket: WebSocket
    ) -> dict[str, object] | None:
        receive_task = asyncio.create_task(websocket.receive())
        terminal_task = asyncio.create_task(self.terminal_event.wait())
        try:
            done, _ = await asyncio.wait(
                {receive_task, terminal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if terminal_task in done:
                return None
            return receive_task.result()
        finally:
            for task in (receive_task, terminal_task):
                if not task.done():
                    task.cancel()
            for task in (receive_task, terminal_task):
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    def error_event(
        self,
        error: ProtocolValidationError,
        *,
        request_id: str | None = None,
        generation_id: int | None = None,
        required_action: RequiredAction | None = None,
        recoverable: bool | None = None,
    ) -> ErrorEvent:
        default_recoverable, default_action = _error_policy(error.code)
        return ErrorEvent(
            protocol_version=1,
            session_id=self.session.session_id,
            request_id=request_id,
            generation_id=generation_id,
            code=error.code,
            recoverable=(default_recoverable if recoverable is None else recoverable),
            required_action=required_action or default_action,
            message=str(error),
            field=error.field,
        )

    async def send_error(
        self,
        error: ProtocolValidationError,
        *,
        request_id: str | None = None,
        generation_id: int | None = None,
        required_action: RequiredAction | None = None,
        recoverable: bool | None = None,
    ) -> ErrorEvent:
        event = self.error_event(
            error,
            request_id=request_id,
            generation_id=generation_id,
            required_action=required_action,
            recoverable=recoverable,
        )
        await self.send_event(event)
        return event

    async def send_generation_failure(
        self,
        error: ProtocolValidationError,
        generation_id: int,
        *,
        request_id: str | None = None,
    ) -> ErrorEvent:
        pipeline_id = self.session.active_pipeline_id
        if pipeline_id is None:
            return await self.send_error(
                error,
                request_id=request_id,
                generation_id=generation_id,
            )
        self.generation_failures[generation_id] = error
        self.invalidate_generation(generation_id)
        await self.abort_generation(generation_id)
        error_event = await self.send_error(
            error,
            request_id=request_id,
            generation_id=generation_id,
            required_action=RequiredAction.FALLBACK,
            recoverable=True,
        )
        await self.send_event(
            FallbackRequiredEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                generation_id=generation_id,
                pipeline_id=pipeline_id,
                reason_code=error.code,
            )
        )
        pending_end = self.pending_end
        if pending_end is not None and pending_end[2] == generation_id:
            end_request_id, end_fingerprint, _, _ = pending_end
            if error_event.request_id == end_request_id:
                correlated = error_event
            else:
                correlated = self.error_event(
                    error,
                    request_id=end_request_id,
                    generation_id=generation_id,
                    required_action=RequiredAction.FALLBACK,
                    recoverable=True,
                )
                await self.send_event(correlated)
            self._set_cached_response(
                end_request_id,
                end_fingerprint,
                correlated,
            )
            self.pending_end = None
        return error_event

    def _generation_is_current(self, generation_id: int) -> bool:
        return (
            not self.silent_terminal
            and not self.session.deleted
            and generation_id not in self.session.invalidated_generations
            and self.session.order.active_generation_id == generation_id
        )

    def invalidate_generation(self, generation_id: int) -> None:
        self.session.invalidated_generations.add(generation_id)
        self._discard_queued_ingress()
        self.pending_ingress_frames = 0
        if self.session.order.active_generation_id == generation_id or (
            self.session.order.active_generation_id is None
            and self.session.order.last_generation_id == generation_id
        ):
            self.session.order.active_generation_id = None
            self.session.active_pipeline_id = None
            self.session.active_profile_id = None
            self.session.draining_generation_id = None
            self.session.last_source_monotonic_ns = None
            self.generation_delivery_mode = None

    async def enqueue_frame(self, data: bytes) -> None:
        active_before_validation = self.session.order.active_generation_id
        if len(data) > MAX_CONTROL_MESSAGE_BYTES:
            error = ProtocolValidationError(
                ErrorCode.UNSUPPORTED_AUDIO,
                "binary WebSocket message exceeds 16 KiB",
                field="payload",
            )
            if active_before_validation is not None:
                await self.send_generation_failure(error, active_before_validation)
            else:
                await self.send_error(error)
            return

        try:
            frame = PcmFrame.decode(data)
            if frame.header.kind is not FrameKind.INPUT:
                raise ProtocolValidationError(
                    ErrorCode.UNSUPPORTED_AUDIO,
                    "client binary frames must have kind=INPUT",
                    field="kind",
                )
            if self.session.draining_generation_id == frame.header.generation_id:
                raise ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "input is forbidden after generation.end",
                    field="generation_id",
                )
            self.session.order.observe(
                frame.header.generation_id,
                frame.header.sequence,
            )
            last_timestamp = self.session.last_source_monotonic_ns
            if (
                last_timestamp is not None
                and frame.header.source_monotonic_ns < last_timestamp
            ):
                raise ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "source_monotonic_ns must not decrease",
                    field="source_monotonic_ns",
                )
            self.session.last_source_monotonic_ns = frame.header.source_monotonic_ns
        except ProtocolValidationError as error:
            generation_id = self._generation_from_frame(data)
            if error.code is ErrorCode.STALE_GENERATION:
                await self.send_error(error, generation_id=generation_id)
            elif active_before_validation is not None:
                await self.send_generation_failure(error, active_before_validation)
            else:
                await self.send_error(error, generation_id=generation_id)
            return

        try:
            if self.pending_ingress_frames >= self.generation_ingress_limit_frames:
                raise asyncio.QueueFull
            self.ingress.put_nowait(frame)
            self.pending_ingress_frames += 1
        except asyncio.QueueFull:
            error = ProtocolValidationError(
                ErrorCode.QUEUE_OVERFLOW,
                "gateway ingress frame budget exceeded",
            )
            await self.send_generation_failure(error, frame.header.generation_id)

    @staticmethod
    def _generation_from_frame(data: bytes) -> int | None:
        try:
            return FrameHeader.decode(data).generation_id
        except ProtocolValidationError:
            return None

    async def worker(self) -> None:
        while True:
            frame = await self.ingress.get()
            expects_output = False
            try:
                generation_id = frame.header.generation_id
                if not self._generation_is_current(generation_id):
                    continue
                profile_id = self.session.active_profile_id
                profile = (
                    self.gateway.registry.get_selectable(profile_id)
                    if profile_id is not None
                    else None
                )
                if profile is None:
                    raise ProtocolValidationError(
                        ErrorCode.MODEL_UNAVAILABLE,
                        "active profile is not ready",
                    )
                frame_task = asyncio.create_task(self.worker_bridge.push_frame(frame))
                self.active_frame_task = frame_task
                self.active_frame_generation_id = generation_id
                try:
                    await frame_task
                finally:
                    if self.active_frame_task is frame_task:
                        self.active_frame_task = None
                        self.active_frame_generation_id = None
                expects_output = True
                self.generation_input_frames += 1
                self.output_drained.clear()
                self.output_available.set()
            except asyncio.CancelledError:
                if self.stopping or self._generation_is_current(
                    frame.header.generation_id
                ):
                    raise
            except ProtocolValidationError as error:
                if self._generation_is_current(frame.header.generation_id):
                    await self.send_generation_failure(
                        error,
                        frame.header.generation_id,
                    )
            finally:
                self.ingress.task_done()
                if not expects_output:
                    self._release_pending_frame()

    async def output_worker(self, generation_id: int) -> None:
        while True:
            while self.generation_output_frames >= self.generation_input_frames:
                self.output_available.clear()
                if self.generation_output_frames < self.generation_input_frames:
                    break
                await self.output_available.wait()
            try:
                output = await self.worker_bridge.next_frame(generation_id)
                await self.send_frame_if_current(output)
                self.generation_output_frames += 1
                self._release_pending_frame()
                if self.generation_output_frames == self.generation_input_frames:
                    self.output_drained.set()
            except asyncio.CancelledError:
                raise
            except ProtocolValidationError as error:
                if self._generation_is_current(generation_id):
                    await self.send_generation_failure(error, generation_id)
                return
            except RuntimeError:
                self._mark_terminal(silent=True)
                return

    async def handle_control(self, message: object) -> None:
        request_id = getattr(message, "request_id", None)
        if not isinstance(request_id, str):
            raise ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "control message has no request_id",
                field="request_id",
            )
        fingerprint = encode_control_message(message)
        cached = self.session.request_cache.get(request_id)
        if cached is not None:
            if cached.command_fingerprint != fingerprint:
                await self.send_error(
                    ProtocolValidationError(
                        ErrorCode.INVALID_STATE,
                        "request_id was reused for a different command",
                        field="request_id",
                    ),
                    request_id=request_id,
                    generation_id=getattr(message, "generation_id", None),
                )
                return
            if cached.response is not None:
                await self.send_event(cached.response)
            return

        if len(self.session.request_cache) >= self.session.request_cache_limit:
            await self.send_error(
                ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "request cache capacity exceeded",
                    field="request_id",
                ),
                request_id=request_id,
                generation_id=getattr(message, "generation_id", None),
                required_action=RequiredAction.CLOSE_SESSION,
                recoverable=False,
            )
            self.closed = True
            return

        try:
            response = await self._apply_control(message, fingerprint)
        except ProtocolValidationError as error:
            response = self.error_event(
                error,
                request_id=request_id,
                generation_id=getattr(message, "generation_id", None),
            )
        self.session.request_cache[request_id] = CachedResponse(
            command_fingerprint=fingerprint,
            response=response,
        )
        if response is not None:
            await self.send_event(response)
        if isinstance(message, SessionClose):
            self.closed = True

    async def _apply_control(
        self,
        message: object,
        fingerprint: str,
    ) -> ParsedServerEvent | None:
        if (
            not hasattr(message, "session_id")
            or message.session_id != self.session.session_id
        ):
            raise ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "control message session_id does not match the attached session",
                field="session_id",
            )
        if isinstance(message, SessionAttach):
            raise ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "session is already attached",
                field="type",
            )
        if isinstance(message, ModelSelect):
            if self.session.order.active_generation_id is not None:
                raise ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "model.select is forbidden while a generation is active",
                    field="type",
                )
            profile = self.gateway.registry.get_selectable(message.profile_id)
            if profile is None:
                raise ProtocolValidationError(
                    ErrorCode.MODEL_UNAVAILABLE,
                    "requested profile is not ready",
                    field="profile_id",
                )
            voice_error = self.gateway.voice_error(profile, self.session.voice_id)
            if voice_error is not None:
                raise voice_error
            await self.worker_bridge.close()
            self.session.profile_id = profile.profile_id
            self.session.profile_hash = profile.profile_hash
            self.session.configuration_hash = profile.configuration_hash
            self.session.pipeline_id = str(uuid4())
            return ModelSelectedEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                request_id=message.request_id,
                profile_id=self.session.profile_id,
                profile_hash=self.session.profile_hash,
                configuration_hash=self.session.configuration_hash,
                pipeline_id=self.session.pipeline_id,
            )

        if isinstance(message, GenerationStart):
            self.session.order.start_generation(message.generation_id)
            self.session.invalidated_generations.clear()
            self.generation_failures.clear()
            self.session.active_pipeline_id = self.session.pipeline_id
            self.session.active_profile_id = self.session.profile_id
            self.session.last_source_monotonic_ns = None
            profile = self.gateway.registry.get_selectable(
                self.session.active_profile_id
            )
            pipeline_id = self.session.active_pipeline_id
            if profile is None or pipeline_id is None:
                self.invalidate_generation(message.generation_id)
                raise ProtocolValidationError(
                    ErrorCode.MODEL_UNAVAILABLE,
                    "active profile is not ready",
                )
            try:
                await self.worker_bridge.start_generation(
                    profile,
                    pipeline_id,
                    message.generation_id,
                )
            except ProtocolValidationError:
                self.invalidate_generation(message.generation_id)
                raise
            self.generation_input_frames = 0
            self.generation_output_frames = 0
            self.generation_delivery_mode = delivery_mode_for_profile(profile)
            self.generation_ingress_limit_frames = self.session.max_ingress_frames
            if self.generation_delivery_mode == "end_buffered":
                self.generation_ingress_limit_frames = min(
                    self.session.max_ingress_frames,
                    buffered_input_capacity_frames(
                        profile,
                        self.session.ingress_budget_ms,
                    ),
                )
            self.output_available.clear()
            self.output_drained.set()
            if self.generation_delivery_mode == "live_frame_echo":
                self.output_task = asyncio.create_task(
                    self.output_worker(message.generation_id)
                )
            return GenerationReadyEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                request_id=message.request_id,
                generation_id=message.generation_id,
                profile_id=self.session.active_profile_id,
                profile_hash=self.session.profile_hash,
                configuration_hash=self.session.configuration_hash,
                pipeline_id=self.session.active_pipeline_id,
            )

        if isinstance(message, GenerationEnd):
            if self.session.order.active_generation_id != message.generation_id:
                self.session.order.finish_generation(message.generation_id)
            if self.session.draining_generation_id is not None:
                raise ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "a generation is already draining",
                    field="generation_id",
                )
            self.session.draining_generation_id = message.generation_id
            profile = self.gateway.registry.get_selectable(
                self.session.active_profile_id or ""
            )
            if profile is None:
                raise ProtocolValidationError(
                    ErrorCode.MODEL_UNAVAILABLE,
                    "active profile is not ready",
                )
            self.drain_task = asyncio.create_task(
                self._drain_generation(
                    message.generation_id,
                    message.request_id,
                    fingerprint,
                    profile.timeouts.stall_ms / 1000,
                )
            )
            self.pending_end = (
                message.request_id,
                fingerprint,
                message.generation_id,
                self.session.active_pipeline_id,
            )
            return None

        if isinstance(message, GenerationCancel):
            pipeline_id = self.session.active_pipeline_id
            if pipeline_id is None:
                raise ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "active generation has no pipeline",
                    field="generation_id",
                )
            self.session.order.cancel_generation(message.generation_id)
            self.invalidate_generation(message.generation_id)
            await self.abort_generation(message.generation_id)
            if self.drain_task is not None and not self.drain_task.done():
                self.drain_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.drain_task
            self.drain_task = None
            if self.pending_end is not None:
                end_request_id, end_fingerprint, end_generation_id, end_pipeline_id = (
                    self.pending_end
                )
                end_event = GenerationCanceledEvent(
                    protocol_version=1,
                    session_id=self.session.session_id,
                    request_id=end_request_id,
                    generation_id=end_generation_id,
                    pipeline_id=end_pipeline_id,
                )
                self._set_cached_response(
                    end_request_id,
                    end_fingerprint,
                    end_event,
                )
                self.pending_end = None
            return GenerationCanceledEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                request_id=message.request_id,
                generation_id=message.generation_id,
                pipeline_id=pipeline_id,
            )

        if isinstance(message, Ping):
            return PongEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                request_id=message.request_id,
                client_clock_id=message.clock_id,
                client_monotonic_ns=message.client_monotonic_ns,
                clock_id=self.gateway.clock_id,
                server_monotonic_ns=time.monotonic_ns(),
            )

        if isinstance(message, SessionClose):
            if self.drain_task is not None and not self.drain_task.done():
                self.drain_task.cancel()
                with contextlib.suppress(
                    asyncio.CancelledError,
                    ProtocolValidationError,
                    RuntimeError,
                ):
                    await self.drain_task
            self.drain_task = None
            active = self.session.order.active_generation_id
            if active is not None:
                self.invalidate_generation(active)
                await self.abort_generation(active)
            await self.worker_bridge.close()
            return SessionClosedEvent(
                protocol_version=1,
                session_id=self.session.session_id,
                request_id=message.request_id,
            )

        raise ProtocolValidationError(
            ErrorCode.INVALID_STATE,
            "unsupported control message",
            field="type",
        )

    async def _drain_generation(
        self,
        generation_id: int,
        request_id: str,
        fingerprint: str,
        stall_seconds: float,
    ) -> None:
        try:
            await asyncio.wait_for(
                self.ingress.join(),
                timeout=max(0.1, stall_seconds * 2),
            )
        except asyncio.CancelledError:
            return
        except TimeoutError:
            if self._generation_is_current(generation_id):
                error = ProtocolValidationError(
                    ErrorCode.MODEL_TIMEOUT,
                    "generation drain exceeded the profile stall timeout",
                )
                event = await self.send_generation_failure(
                    error,
                    generation_id,
                    request_id=request_id,
                )
                self._set_cached_response(request_id, fingerprint, event)
                self.pending_end = None
            return

        if not self._generation_is_current(generation_id):
            pending_end = self.pending_end
            if (
                pending_end is None
                or pending_end[0] != request_id
                or pending_end[2] != generation_id
            ):
                return
            failure = self.generation_failures.get(generation_id)
            if failure is not None:
                event = self.error_event(
                    failure,
                    request_id=request_id,
                    generation_id=generation_id,
                    required_action=RequiredAction.FALLBACK,
                    recoverable=True,
                )
                self._set_cached_response(request_id, fingerprint, event)
                self.pending_end = None
                await self.send_event(event)
            return
        if self.session.draining_generation_id != generation_id:
            return

        try:
            await self.worker_bridge.end_generation(generation_id)
        except ProtocolValidationError as error:
            if self._generation_is_current(generation_id):
                event = await self.send_generation_failure(
                    error,
                    generation_id,
                    request_id=request_id,
                )
                self._set_cached_response(request_id, fingerprint, event)
                self.pending_end = None
            return

        if (
            self.generation_delivery_mode == "end_buffered"
            and self.generation_input_frames > 0
        ):
            self.output_task = asyncio.create_task(self.output_worker(generation_id))

        try:
            await asyncio.wait_for(
                self.output_drained.wait(),
                timeout=max(0.1, stall_seconds),
            )
        except TimeoutError:
            if self._generation_is_current(generation_id):
                error = ProtocolValidationError(
                    ErrorCode.MODEL_TIMEOUT,
                    "generation output drain exceeded the profile stall timeout",
                )
                event = await self.send_generation_failure(
                    error,
                    generation_id,
                    request_id=request_id,
                )
                self._set_cached_response(request_id, fingerprint, event)
                self.pending_end = None
            return

        await self._stop_output_task()

        if (
            not self._generation_is_current(generation_id)
            or self.session.draining_generation_id != generation_id
        ):
            return

        await self.worker_bridge.finish_generation(generation_id)

        self.session.order.finish_generation(generation_id)
        pipeline_id = self.session.active_pipeline_id
        if pipeline_id is None:
            return
        self.session.active_pipeline_id = None
        self.session.active_profile_id = None
        self.session.draining_generation_id = None
        self.session.last_source_monotonic_ns = None
        self.generation_delivery_mode = None
        self.generation_ingress_limit_frames = self.session.max_ingress_frames
        event = GenerationCompletedEvent(
            protocol_version=1,
            session_id=self.session.session_id,
            request_id=request_id,
            generation_id=generation_id,
            pipeline_id=pipeline_id,
        )
        self._set_cached_response(request_id, fingerprint, event)
        self.pending_end = None
        await self.send_event(event)

    def _set_cached_response(
        self,
        request_id: str,
        fingerprint: str,
        response: ParsedServerEvent,
    ) -> None:
        cached = self.session.request_cache.get(request_id)
        if cached is not None and cached.command_fingerprint == fingerprint:
            cached.response = response

    def _discard_queued_ingress(self) -> None:
        while True:
            try:
                self.ingress.get_nowait()
            except asyncio.QueueEmpty:
                return
            self.ingress.task_done()
            self._release_pending_frame()

    def _release_pending_frame(self) -> None:
        self.pending_ingress_frames = max(0, self.pending_ingress_frames - 1)

    async def _stop_output_task(self) -> None:
        task = self.output_task
        if task is None or task is asyncio.current_task():
            return
        self.output_task = None
        if not task.done():
            task.cancel()
        with contextlib.suppress(
            asyncio.CancelledError,
            ProtocolValidationError,
            RuntimeError,
        ):
            await task

    async def abort_generation(self, generation_id: int) -> None:
        await self._stop_output_task()
        self.output_drained.set()
        self.output_available.set()
        frame_task = self.active_frame_task
        if (
            frame_task is not None
            and self.active_frame_generation_id == generation_id
            and not frame_task.done()
        ):
            frame_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await frame_task
        try:
            await self.worker_bridge.cancel_generation(generation_id)
        except ProtocolValidationError:
            await self.worker_bridge.close()

    async def terminate(self, *, silent: bool) -> None:
        self._mark_terminal(silent=silent)
        active = self.session.order.active_generation_id
        if active is not None:
            self.invalidate_generation(active)
        await self.stop_tasks()
        with contextlib.suppress(RuntimeError, TimeoutError):
            await asyncio.wait_for(
                self.websocket.close(code=1000),
                timeout=self.gateway.settings.send_timeout_seconds,
            )

    async def stop_tasks(self) -> None:
        self.stopping = True
        for task in (self.drain_task, self.worker_task, self.output_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self.drain_task, self.worker_task, self.output_task):
            if task is not None:
                with contextlib.suppress(
                    asyncio.CancelledError,
                    ProtocolValidationError,
                    RuntimeError,
                ):
                    await task
        self._discard_queued_ingress()
        self.pending_ingress_frames = 0
        self.output_task = None
        await self.worker_bridge.close()


class Gateway:
    def __init__(
        self,
        settings: Settings,
        *,
        worker_supervisor_factory: WorkerSupervisorFactory = (
            builtin_supervisor_factory
        ),
    ) -> None:
        self.settings = settings
        self.worker_supervisor_factory = worker_supervisor_factory
        self.registry = ProfileRegistry.load(
            settings.profile_config,
            allow_technical_profiles=settings.allow_technical_profiles,
        )
        roster_path = settings.roster_config
        if roster_path is None:
            roster_path = Path(
                str(files("liveconv_audio").joinpath("default-model-roster.json"))
            )
        self.roster = ModelRoster.load(roster_path)
        self.store = SessionStore(
            ticket_ttl_seconds=settings.ticket_ttl_seconds,
            ingress_budget_ms=settings.ingress_budget_ms,
            max_sessions=settings.max_sessions,
            session_lifetime_seconds=settings.session_lifetime_seconds,
            request_cache_limit=settings.request_cache_max,
        )
        self.clock_id = str(uuid4())
        self.connections: dict[str, Connection] = {}
        self.pending_attachments = 0
        self.pending_attachment_lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        return not self.settings.configuration_errors and self.registry.ready

    @staticmethod
    def voice_error(
        profile: ModelProfile,
        voice_id: str | None,
    ) -> ProtocolValidationError | None:
        if profile.voice_requirement == "none" and voice_id is not None:
            return ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "selected profile does not accept voice_id",
                field="voice_id",
            )
        if (
            profile.voice_requirement == "authorized_target_required"
            and voice_id is None
        ):
            return ProtocolValidationError(
                ErrorCode.INVALID_STATE,
                "selected profile requires an authorized voice_id",
                field="voice_id",
            )
        return None

    async def reap_expired(self) -> None:
        for session in self.store.expired_attached():
            self.store.delete(session.session_id)
            connection = self.connections.pop(session.session_id, None)
            if connection is not None:
                await connection.terminate(silent=True)

    async def delete_session(self, session_id: str) -> bool:
        session = self.store.delete(session_id)
        if session is None:
            return False
        connection = self.connections.pop(session_id, None)
        if connection is not None:
            await connection.terminate(silent=True)
        return True

    async def websocket(self, websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        if (
            not self.settings.origins_are_acceptable
            or origin not in self.settings.allowed_origins
        ):
            await websocket.close(code=4403, reason="origin is not allowed")
            return

        connection: Connection | None = None
        pending_attachment = False
        try:
            async with self.pending_attachment_lock:
                if self.pending_attachments >= self.settings.max_pending_attachments:
                    has_capacity = False
                else:
                    self.pending_attachments += 1
                    pending_attachment = True
                    has_capacity = True
            if not has_capacity:
                await websocket.close(code=4429, reason="attachment capacity reached")
                return
            await websocket.accept()
            try:
                first = await asyncio.wait_for(
                    websocket.receive(), timeout=self.settings.attach_timeout_seconds
                )
            except TimeoutError:
                await self._attachment_failure(websocket, "attachment timed out")
                return
            if first.get("type") != "websocket.receive" or first.get("text") is None:
                await self._attachment_failure(
                    websocket, "first message must be session.attach"
                )
                return
            try:
                attach = parse_control_message(first["text"])
            except ProtocolValidationError:
                await self._attachment_failure(websocket, "invalid attachment")
                return
            if not isinstance(attach, SessionAttach):
                await self._attachment_failure(
                    websocket, "first message must be session.attach"
                )
                return
            session = self.store.consume_ticket(attach.session_id, attach.ticket)
            if session is None:
                await self._attachment_failure(
                    websocket, "attachment authentication failed"
                )
                return

            await self._release_pending_attachment()
            pending_attachment = False
            connection = Connection(self, websocket, session)
            self.connections[session.session_id] = connection
            await connection.send_event(
                SessionReadyEvent(
                    protocol_version=1,
                    session_id=session.session_id,
                    request_id=attach.request_id,
                    profile_id=session.profile_id,
                    profile_hash=session.profile_hash,
                    configuration_hash=session.configuration_hash,
                    pipeline_id=session.pipeline_id,
                    clock_id=self.clock_id,
                    limits=IngressLimits(
                        ingress_budget_ms=session.ingress_budget_ms,
                        max_ingress_frames=session.max_ingress_frames,
                    ),
                )
            )
            connection.worker_task = asyncio.create_task(connection.worker())

            while not connection.closed and not session.deleted:
                remaining = session.remaining_lifetime()
                if remaining <= 0:
                    await self._expire_connection(connection)
                    break
                try:
                    event = await asyncio.wait_for(
                        connection.receive_or_terminal(websocket), timeout=remaining
                    )
                except TimeoutError:
                    await self._expire_connection(connection)
                    break
                if event is None:
                    break
                if event["type"] == "websocket.disconnect":
                    break
                if session.deleted:
                    break
                if event.get("text") is not None:
                    message: object | None = None
                    try:
                        message = parse_control_message(event["text"])
                        await connection.handle_control(message)
                    except ProtocolValidationError as error:
                        await connection.send_error(
                            error,
                            request_id=getattr(message, "request_id", None),
                            generation_id=getattr(message, "generation_id", None),
                        )
                elif event.get("bytes") is not None:
                    await connection.enqueue_frame(event["bytes"])
                else:
                    await connection.send_error(
                        ProtocolValidationError(
                            ErrorCode.INVALID_STATE,
                            "WebSocket message must be text control or binary PCM",
                        )
                    )

            if connection.closed and not connection.silent_terminal:
                with contextlib.suppress(RuntimeError):
                    await websocket.close(code=1000)
        except WebSocketDisconnect:
            pass
        finally:
            if pending_attachment:
                await self._release_pending_attachment()
            if connection is not None:
                with anyio.CancelScope(shield=True):
                    await connection.stop_tasks()
                    if (
                        self.connections.get(connection.session.session_id)
                        is connection
                    ):
                        self.connections.pop(connection.session.session_id, None)
                    self.store.delete(connection.session.session_id)

    async def _release_pending_attachment(self) -> None:
        async with self.pending_attachment_lock:
            self.pending_attachments = max(0, self.pending_attachments - 1)

    async def _expire_connection(self, connection: Connection) -> None:
        active = connection.session.order.active_generation_id
        if active is not None:
            await connection.send_generation_failure(
                ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "session lifetime expired",
                ),
                active,
            )
        else:
            await connection.send_error(
                ProtocolValidationError(
                    ErrorCode.INVALID_STATE,
                    "session lifetime expired",
                ),
                required_action=RequiredAction.CLOSE_SESSION,
                recoverable=False,
            )
        connection.closed = True

    @staticmethod
    async def _attachment_failure(websocket: WebSocket, message: str) -> None:
        event = ErrorEvent(
            protocol_version=1,
            code=ErrorCode.AUTH_FAILED,
            recoverable=False,
            required_action=RequiredAction.CLOSE_SESSION,
            message=message,
        )
        await websocket.send_text(encode_server_event(event))
        await websocket.close(code=4401)


def create_app(
    settings: Settings | None = None,
    *,
    worker_supervisor_factory: WorkerSupervisorFactory = builtin_supervisor_factory,
) -> FastAPI:
    gateway = Gateway(
        settings or Settings.from_env(),
        worker_supervisor_factory=worker_supervisor_factory,
    )
    app = FastAPI(
        title="liveconv audio gateway",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.gateway = gateway
    app.add_middleware(HttpIngressGuard, settings=gateway.settings)

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready", dependencies=[Depends(require_bearer)])
    async def health_ready() -> dict[str, str]:
        if not gateway.ready:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "gateway is not ready"
            )
        return {"status": "ready"}

    @app.get("/v1/runtime-boundary", dependencies=[Depends(require_bearer)])
    async def runtime_boundary() -> dict[str, object]:
        """Expose non-secret personal-route limits for the MS-2 receipt."""

        transport_scope = (
            "loopback"
            if gateway.settings.bind_host in {"127.0.0.1", "::1", "localhost"}
            else "network"
        )
        return {
            "protocol_version": 1,
            "transport_scope": transport_scope,
            "max_sessions": gateway.settings.max_sessions,
            "ticket_one_use": True,
        }

    @app.get("/v1/models", dependencies=[Depends(require_bearer)])
    async def models() -> dict[str, object]:
        return {"protocol_version": 1, "profiles": gateway.registry.public_profiles()}

    @app.get("/v1/model-roster", dependencies=[Depends(require_bearer)])
    async def model_roster() -> dict[str, object]:
        return gateway.roster.public_document(gateway.registry)

    @app.post("/v1/sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(
        request: SessionCreate,
        _: Annotated[None, Depends(require_bearer)],
    ) -> dict[str, object]:
        if not gateway.ready:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "gateway is not ready"
            )
        await gateway.reap_expired()
        profile = gateway.registry.get_selectable(request.profile_id)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "profile is not ready")
        if (
            request.input.sample_rate not in profile.input_sample_rates
            or request.input.frame_ms != profile.frame_ms
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "profile does not support the negotiated audio format",
            )
        voice_error = gateway.voice_error(profile, request.voice_id)
        if voice_error is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                str(voice_error),
            )
        try:
            requested_ingress_budget_ms = max(
                gateway.settings.ingress_budget_ms,
                profile.minimum_context_ms * 2,
            )
            max_ingress_frames = None
            if delivery_mode_for_profile(profile) == "end_buffered":
                max_ingress_frames = buffered_input_capacity_frames(
                    profile, requested_ingress_budget_ms
                )
            session, ticket = gateway.store.create(
                profile.profile_id,
                profile.profile_hash,
                profile.configuration_hash,
                request.voice_id,
                request.input.frame_ms,
                requested_ingress_budget_ms,
                max_ingress_frames=max_ingress_frames,
            )
        except SessionCapacityError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "session capacity is exhausted",
            ) from exc
        return {
            **session.public_dict(),
            "input": request.input.model_dump(),
            "websocket_path": "/v1/ws",
            "ticket": ticket,
            "ticket_expires_in_seconds": gateway.store.ticket_ttl_seconds,
        }

    @app.get("/v1/sessions/{session_id}", dependencies=[Depends(require_bearer)])
    async def get_session(session_id: str) -> dict[str, object]:
        await gateway.reap_expired()
        session = gateway.store.get(session_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
        return session.public_dict()

    @app.delete(
        "/v1/sessions/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_bearer)],
    )
    async def delete_session(session_id: str) -> Response:
        if not await gateway.delete_session(session_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.websocket("/v1/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await gateway.websocket(websocket)

    return app
