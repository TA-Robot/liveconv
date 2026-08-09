from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .errors import ExperimentFailure, TransportFailure, WebSocketClosed
from .trace import TraceRecorder

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class HttpResult:
    status_code: int
    body: object | None


class HttpAdapter(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> HttpResult: ...

    async def close(self) -> None: ...


class WebSocketConnection(Protocol):
    async def send(self, message: str | bytes) -> None: ...

    async def recv(self) -> str | bytes: ...

    async def close(self) -> None: ...


class WebSocketConnector(Protocol):
    async def connect(
        self,
        url: str,
        *,
        origin: str,
        timeout_seconds: float,
    ) -> WebSocketConnection: ...


class HttpxAdapter:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(follow_redirects=False)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, object] | None,
        timeout_seconds: float,
    ) -> HttpResult:
        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise TransportFailure(
                f"HTTP {method} failed for {urlsplit(url).path}"
            ) from exc
        body: object | None = None
        if response.content:
            try:
                body = response.json()
            except ValueError as exc:
                raise TransportFailure(
                    f"HTTP {method} returned non-JSON content at {urlsplit(url).path}"
                ) from exc
        return HttpResult(response.status_code, body)

    async def close(self) -> None:
        await self._client.aclose()


class _WebsocketsConnection:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    async def send(self, message: str | bytes) -> None:
        try:
            await self._connection.send(message)  # type: ignore[attr-defined]
        except ConnectionClosed as exc:
            raise WebSocketClosed("WebSocket closed during send") from exc

    async def recv(self) -> str | bytes:
        try:
            message = await self._connection.recv()  # type: ignore[attr-defined]
        except ConnectionClosed as exc:
            raise WebSocketClosed("WebSocket closed during receive") from exc
        if not isinstance(message, (str, bytes)):
            raise TransportFailure("WebSocket returned an unsupported message type")
        return message

    async def close(self) -> None:
        try:
            await self._connection.close()  # type: ignore[attr-defined]
        except ConnectionClosed:
            return


class WebsocketsConnector:
    async def connect(
        self,
        url: str,
        *,
        origin: str,
        timeout_seconds: float,
    ) -> WebSocketConnection:
        try:
            connection = await connect(
                url,
                origin=origin,
                compression=None,
                max_size=16_384,
                open_timeout=timeout_seconds,
                close_timeout=timeout_seconds,
            )
        except (OSError, TimeoutError, ConnectionClosed) as exc:
            raise TransportFailure("WebSocket connection failed") from exc
        return _WebsocketsConnection(connection)


@dataclass(frozen=True, slots=True)
class SessionDescriptor:
    session_id: str
    pipeline_id: str
    profile_id: str
    profile_hash: str
    configuration_hash: str
    websocket_path: str
    ticket: str = field(repr=False)


def _canonical_uuid(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ExperimentFailure(f"session response {field_name} must be text")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise ExperimentFailure(
            f"session response {field_name} must be a UUID"
        ) from exc
    if canonical != value:
        raise ExperimentFailure(
            f"session response {field_name} must use canonical UUID form"
        )
    return canonical


def parse_session_descriptor(
    body: object, expected_profile_id: str
) -> SessionDescriptor:
    if not isinstance(body, dict) or any(not isinstance(key, str) for key in body):
        raise ExperimentFailure("session creation response must be an object")

    profile_id = body.get("profile_id")
    if profile_id != expected_profile_id:
        raise ExperimentFailure("session response profile_id does not match request")
    profile_hash = body.get("profile_hash")
    configuration_hash = body.get("configuration_hash")
    if not isinstance(profile_hash, str) or _HASH_RE.fullmatch(profile_hash) is None:
        raise ExperimentFailure("session response profile_hash is invalid")
    if (
        not isinstance(configuration_hash, str)
        or _HASH_RE.fullmatch(configuration_hash) is None
    ):
        raise ExperimentFailure("session response configuration_hash is invalid")

    path = body.get("websocket_path")
    if not isinstance(path, str):
        raise ExperimentFailure("session response websocket_path must be text")
    parsed_path = urlsplit(path)
    if (
        not path.startswith("/")
        or parsed_path.scheme
        or parsed_path.netloc
        or parsed_path.query
        or parsed_path.fragment
    ):
        raise ExperimentFailure("session response websocket_path is not a safe path")
    ticket = body.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        raise ExperimentFailure("session response ticket is missing")

    return SessionDescriptor(
        session_id=_canonical_uuid(body.get("session_id"), "session_id"),
        pipeline_id=_canonical_uuid(body.get("pipeline_id"), "pipeline_id"),
        profile_id=profile_id,
        profile_hash=profile_hash,
        configuration_hash=configuration_hash,
        websocket_path=path,
        ticket=ticket,
    )


def _is_loopback(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_gateway_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("gateway URL must use http or https with a hostname")
    if parsed.username or parsed.password:
        raise ValueError("gateway URL must not contain credentials")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError(
            "gateway URL must be an origin without path, query, or fragment"
        )
    if parsed.scheme == "http" and not _is_loopback(parsed.hostname):
        raise ValueError("plain HTTP is allowed only for loopback gateways")
    authority = parsed.netloc
    return urlunsplit((parsed.scheme, authority, "", "", "")).rstrip("/")


class GatewayApi:
    def __init__(
        self,
        base_url: str,
        token: str,
        origin: str,
        trace: TraceRecorder,
        *,
        timeout_seconds: float = 3.0,
        http: HttpAdapter | None = None,
        websocket_connector: WebSocketConnector | None = None,
    ) -> None:
        if not token:
            raise ValueError("gateway bearer credential must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = validate_gateway_url(base_url)
        self._token = token
        self.origin = origin
        self.trace = trace
        self.timeout_seconds = timeout_seconds
        self.http = http or HttpxAdapter()
        self.websocket_connector = websocket_connector or WebsocketsConnector()

    async def close(self) -> None:
        await self.http.close()

    async def request(
        self,
        case_id: str,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
        token_override: str | None = None,
    ) -> HttpResult:
        if not path.startswith("/") or urlsplit(path).netloc:
            raise ValueError("HTTP API path must be absolute and host-free")
        self.trace.record(
            case_id,
            "client_to_server",
            "http.request",
            {"method": method, "path": path, "body_present": json_body is not None},
        )
        result = await self.http.request(
            method,
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {token_override or self._token}"},
            json_body=json_body,
            timeout_seconds=self.timeout_seconds,
        )
        self.trace.record(
            case_id,
            "server_to_client",
            "http.response",
            {"method": method, "path": path, "status_code": result.status_code},
        )
        return result

    async def create_session(
        self,
        case_id: str,
        profile_id: str,
        *,
        token_override: str | None = None,
    ) -> tuple[HttpResult, SessionDescriptor | None]:
        result = await self.request(
            case_id,
            "POST",
            "/v1/sessions",
            json_body={
                "protocol_version": 1,
                "profile_id": profile_id,
                "input": {
                    "sample_rate": 48_000,
                    "channels": 1,
                    "sample_format": "f32le",
                    "frame_ms": 20,
                },
                "voice_id": None,
            },
            token_override=token_override,
        )
        if result.status_code != 201:
            return result, None
        return result, parse_session_descriptor(result.body, profile_id)

    async def require_session(self, case_id: str, profile_id: str) -> SessionDescriptor:
        response, descriptor = await self.create_session(case_id, profile_id)
        if response.status_code != 201 or descriptor is None:
            raise ExperimentFailure(
                f"session creation returned HTTP {response.status_code}"
            )
        return descriptor

    async def delete_session(self, case_id: str, session_id: str) -> HttpResult:
        return await self.request(
            case_id,
            "DELETE",
            f"/v1/sessions/{session_id}",
        )

    async def get_session(self, case_id: str, session_id: str) -> HttpResult:
        return await self.request(case_id, "GET", f"/v1/sessions/{session_id}")

    async def open_websocket(
        self, case_id: str, descriptor: SessionDescriptor
    ) -> WebSocketConnection:
        scheme = "wss" if urlsplit(self.base_url).scheme == "https" else "ws"
        authority = urlsplit(self.base_url).netloc
        url = urlunsplit((scheme, authority, descriptor.websocket_path, "", ""))
        self.trace.record(
            case_id,
            "client_to_server",
            "websocket.connect",
            {"path": descriptor.websocket_path, "origin": self.origin},
        )
        connection = await self.websocket_connector.connect(
            url,
            origin=self.origin,
            timeout_seconds=self.timeout_seconds,
        )
        self.trace.record(
            case_id,
            "server_to_client",
            "websocket.connected",
            {"path": descriptor.websocket_path},
        )
        return connection
