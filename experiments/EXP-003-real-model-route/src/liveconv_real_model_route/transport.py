from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .config import validate_gateway_url
from .errors import RouteValidationError, TransportError
from .registry import RegistryProfile
from .trace import TraceRecorder


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
        self, url: str, *, origin: str, timeout_seconds: float
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
            raise TransportError(f"Gateway HTTP {method} failed") from exc
        body: object | None = None
        if response.content:
            try:
                body = response.json()
            except ValueError as exc:
                raise TransportError("Gateway returned non-JSON HTTP content") from exc
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
            raise TransportError("Gateway WebSocket closed during send") from exc

    async def recv(self) -> str | bytes:
        try:
            message = await self._connection.recv()  # type: ignore[attr-defined]
        except ConnectionClosed as exc:
            raise TransportError("Gateway WebSocket closed during receive") from exc
        if not isinstance(message, (str, bytes)):
            raise TransportError("Gateway WebSocket returned an unsupported message")
        return message

    async def close(self) -> None:
        try:
            await self._connection.close()  # type: ignore[attr-defined]
        except ConnectionClosed:
            return


class WebsocketsConnector:
    async def connect(
        self, url: str, *, origin: str, timeout_seconds: float
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
            raise TransportError("Gateway WebSocket connection failed") from exc
        return _WebsocketsConnection(connection)


@dataclass(frozen=True, slots=True)
class SessionDescriptor:
    session_id: str
    profile_id: str
    pipeline_id: str
    profile_hash: str
    configuration_hash: str
    websocket_path: str
    ticket: str = field(repr=False)


def _uuid(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise RouteValidationError(f"session {field_name} must be text")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise RouteValidationError(f"session {field_name} must be a UUID") from exc
    if canonical != value:
        raise RouteValidationError(f"session {field_name} must be canonical")
    return canonical


def _hash(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise RouteValidationError(f"session {field_name} is invalid")
    return value


def parse_session(body: object, expected: RegistryProfile) -> SessionDescriptor:
    if not isinstance(body, dict):
        raise RouteValidationError("session creation response must be an object")
    if body.get("profile_id") != expected.profile_id:
        raise RouteValidationError("session response selected the wrong profile")
    if body.get("profile_hash") != expected.profile_hash:
        raise RouteValidationError(
            "session response profile hash differs from registry"
        )
    if body.get("configuration_hash") != expected.configuration_hash:
        raise RouteValidationError(
            "session response configuration hash differs from registry"
        )
    path = body.get("websocket_path")
    if not isinstance(path, str):
        raise RouteValidationError("session WebSocket path must be text")
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise RouteValidationError("session WebSocket path is unsafe")
    ticket = body.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        raise RouteValidationError("session ticket is absent")
    return SessionDescriptor(
        session_id=_uuid(body.get("session_id"), "session_id"),
        profile_id=expected.profile_id,
        pipeline_id=_uuid(body.get("pipeline_id"), "pipeline_id"),
        profile_hash=_hash(body.get("profile_hash"), "profile_hash"),
        configuration_hash=_hash(body.get("configuration_hash"), "configuration_hash"),
        websocket_path=path,
        ticket=ticket,
    )


class GatewayApi:
    def __init__(
        self,
        gateway_url: str,
        api_token: str,
        origin: str,
        trace: TraceRecorder,
        *,
        timeout_seconds: float = 10.0,
        http: HttpAdapter | None = None,
        websockets: WebSocketConnector | None = None,
    ) -> None:
        self.gateway_url = validate_gateway_url(gateway_url)
        if not api_token:
            raise ValueError("api_token must not be empty")
        self._api_token = api_token
        self.origin = origin
        self.trace = trace
        self.timeout_seconds = timeout_seconds
        self.http = http or HttpxAdapter()
        self.websockets = websockets or WebsocketsConnector()

    async def _request(
        self,
        case_id: str,
        method: str,
        path: str,
        json_body: dict[str, object] | None = None,
    ) -> HttpResult:
        self.trace.record(
            case_id,
            "http.request",
            {"method": method, "endpoint": path, "body_present": json_body is not None},
        )
        result = await self.http.request(
            method,
            f"{self.gateway_url}{path}",
            headers={"Authorization": f"Bearer {self._api_token}"},
            json_body=json_body,
            timeout_seconds=self.timeout_seconds,
        )
        self.trace.record(
            case_id,
            "http.response",
            {"method": method, "endpoint": path, "status_code": result.status_code},
        )
        return result

    async def validate_catalog(self, profiles: tuple[RegistryProfile, ...]) -> None:
        result = await self._request("catalog", "GET", "/v1/models")
        if result.status_code != 200 or not isinstance(result.body, dict):
            raise RouteValidationError(
                f"Gateway model catalog returned HTTP {result.status_code}"
            )
        values = result.body.get("profiles")
        if result.body.get("protocol_version") != 1 or not isinstance(values, list):
            raise RouteValidationError("Gateway model catalog has an invalid shape")
        by_id = {
            item.get("profile_id"): item
            for item in values
            if isinstance(item, dict) and isinstance(item.get("profile_id"), str)
        }
        for profile in profiles:
            advertised = by_id.get(profile.profile_id)
            if advertised is None:
                raise RouteValidationError(
                    f"Gateway did not advertise profile {profile.profile_id}"
                )
            if (
                advertised.get("profile_hash") != profile.profile_hash
                or advertised.get("configuration_hash") != profile.configuration_hash
            ):
                raise RouteValidationError(
                    f"Gateway catalog identity differs for {profile.profile_id}"
                )
        self.trace.add_result(
            "catalog",
            passed=True,
            evidence={
                "selected_profiles": len(profiles),
                "identities_match_external_registry": True,
                "private_registry_fields_recorded": False,
            },
        )

    async def create_session(
        self, profile: RegistryProfile, voice_id: str | None
    ) -> SessionDescriptor:
        result = await self._request(
            "session",
            "POST",
            "/v1/sessions",
            {
                "protocol_version": 1,
                "profile_id": profile.profile_id,
                "input": {
                    "sample_rate": 48_000,
                    "channels": 1,
                    "sample_format": "f32le",
                    "frame_ms": 20,
                },
                "voice_id": voice_id,
            },
        )
        if result.status_code != 201:
            raise RouteValidationError(
                f"Gateway session creation returned HTTP {result.status_code}"
            )
        descriptor = parse_session(result.body, profile)
        self.trace.record(
            "session",
            "session.created",
            {
                "session_id": descriptor.session_id,
                "profile_id": descriptor.profile_id,
                "pipeline_id": descriptor.pipeline_id,
                "profile_hash": descriptor.profile_hash,
                "configuration_hash": descriptor.configuration_hash,
                "authentication_material_redacted": True,
            },
        )
        return descriptor

    async def connect(self, descriptor: SessionDescriptor) -> WebSocketConnection:
        parsed = urlsplit(self.gateway_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = urlunsplit((scheme, parsed.netloc, descriptor.websocket_path, "", ""))
        self.trace.record(
            "session",
            "websocket.connect",
            {
                "transport_security": "tls" if scheme == "wss" else "loopback",
                "authentication_material_redacted": True,
            },
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self.websockets.connect(
                    url, origin=self.origin, timeout_seconds=self.timeout_seconds
                )
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket connect timed out") from exc

    async def delete_session(self, descriptor: SessionDescriptor) -> None:
        result = await self._request(
            "session.cleanup",
            "DELETE",
            f"/v1/sessions/{descriptor.session_id}",
        )
        if result.status_code != 404:
            raise RouteValidationError(
                "Gateway session remained addressable after session.close"
            )
        self.trace.add_result(
            "session.cleanup",
            passed=True,
            evidence={"http_status_code": 404, "session_invalidated": True},
        )

    async def close(self) -> None:
        await self.http.close()
