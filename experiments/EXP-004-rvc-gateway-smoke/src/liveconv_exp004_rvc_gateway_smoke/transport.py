from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .config import validate_gateway_url
from .errors import RouteValidationError, TransportError

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")


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
            raise TransportError(f"Gateway HTTP {method} request failed") from exc
        body: object | None = None
        if response.content:
            try:
                body = response.json()
            except ValueError as exc:
                raise TransportError("Gateway HTTP response was not JSON") from exc
        return HttpResult(status_code=response.status_code, body=body)

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


def _canonical_uuid(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise RouteValidationError(f"{name} must be text")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise RouteValidationError(f"{name} must be a UUID") from exc
    if canonical != value:
        raise RouteValidationError(f"{name} must use canonical UUID form")
    return canonical


def _hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise RouteValidationError(f"{name} must be a sha256 identity")
    return value


@dataclass(frozen=True, slots=True)
class ProfileIdentity:
    profile_id: str
    profile_hash: str
    configuration_hash: str


@dataclass(frozen=True, slots=True)
class SessionDescriptor:
    session_id: str
    pipeline_id: str
    identity: ProfileIdentity
    websocket_path: str
    ticket: str = field(repr=False)


def _safe_websocket_path(value: object) -> str:
    if not isinstance(value, str):
        raise RouteValidationError("websocket_path must be text")
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise RouteValidationError("websocket_path must be an absolute host-free path")
    return value


class GatewayApi:
    """Small HTTP/WSS boundary for one metadata-bound RVC profile."""

    def __init__(
        self,
        gateway_url: str,
        api_token: str,
        origin: str,
        *,
        timeout_seconds: float,
        http: HttpAdapter | None = None,
        websockets: WebSocketConnector | None = None,
    ) -> None:
        if not api_token:
            raise ValueError("api_token must not be empty")
        self.gateway_url = validate_gateway_url(gateway_url)
        self._api_token = api_token
        self.origin = origin
        self.timeout_seconds = timeout_seconds
        self.http = http or HttpxAdapter()
        self.websockets = websockets or WebsocketsConnector()

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, object] | None = None,
    ) -> HttpResult:
        if not path.startswith("/") or urlsplit(path).netloc:
            raise ValueError("Gateway API path must be absolute and host-free")
        return await self.http.request(
            method,
            f"{self.gateway_url}{path}",
            headers={"Authorization": f"Bearer {self._api_token}"},
            json_body=json_body,
            timeout_seconds=self.timeout_seconds,
        )

    async def catalog_identity(
        self,
        profile_id: str,
        *,
        expected_profile_hash: str,
        expected_configuration_hash: str,
    ) -> ProfileIdentity:
        result = await self._request("GET", "/v1/models")
        if result.status_code != 200 or not isinstance(result.body, dict):
            raise RouteValidationError("Gateway catalog was not successful")
        profiles = result.body.get("profiles")
        if result.body.get("protocol_version") != 1 or not isinstance(profiles, list):
            raise RouteValidationError("Gateway catalog had an invalid protocol shape")
        if len(profiles) != 1:
            raise RouteValidationError(
                "Gateway catalog did not expose exactly one RVC profile"
            )
        profile = profiles[0]
        if not isinstance(profile, dict) or profile.get("profile_id") != profile_id:
            raise RouteValidationError(
                "Gateway catalog profile does not match the retained RVC profile"
            )
        identity = ProfileIdentity(
            profile_id=profile_id,
            profile_hash=_hash(profile.get("profile_hash"), "catalog profile_hash"),
            configuration_hash=_hash(
                profile.get("configuration_hash"), "catalog configuration_hash"
            ),
        )
        if (
            identity.profile_hash != expected_profile_hash
            or identity.configuration_hash != expected_configuration_hash
        ):
            raise RouteValidationError(
                "Gateway catalog hashes do not match the retained RVC profile"
            )
        return identity

    async def create_session(self, identity: ProfileIdentity) -> SessionDescriptor:
        result = await self._request(
            "POST",
            "/v1/sessions",
            {
                "protocol_version": 1,
                "profile_id": identity.profile_id,
                "input": {
                    "sample_rate": 48_000,
                    "channels": 1,
                    "sample_format": "f32le",
                    "frame_ms": 20,
                },
                "voice_id": None,
            },
        )
        if result.status_code != 201 or not isinstance(result.body, dict):
            raise RouteValidationError("Gateway session creation was not successful")
        body = result.body
        if body.get("protocol_version") != 1:
            raise RouteValidationError("session protocol version differs from v1")
        if body.get("profile_id") != identity.profile_id:
            raise RouteValidationError("session profile ID differs from catalog")
        if (
            _hash(body.get("profile_hash"), "session profile_hash")
            != identity.profile_hash
        ):
            raise RouteValidationError("session profile hash differs from catalog")
        if (
            _hash(body.get("configuration_hash"), "session configuration_hash")
            != identity.configuration_hash
        ):
            raise RouteValidationError(
                "session configuration hash differs from catalog"
            )
        ticket = body.get("ticket")
        if not isinstance(ticket, str) or not ticket:
            raise RouteValidationError("session ticket was missing")
        return SessionDescriptor(
            session_id=_canonical_uuid(body.get("session_id"), "session_id"),
            pipeline_id=_canonical_uuid(body.get("pipeline_id"), "pipeline_id"),
            identity=identity,
            websocket_path=_safe_websocket_path(body.get("websocket_path")),
            ticket=ticket,
        )

    async def connect(self, descriptor: SessionDescriptor) -> WebSocketConnection:
        parsed = urlsplit(self.gateway_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        websocket_url = urlunsplit(
            (scheme, parsed.netloc, descriptor.websocket_path, "", "")
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self.websockets.connect(
                    websocket_url,
                    origin=self.origin,
                    timeout_seconds=self.timeout_seconds,
                )
        except TimeoutError as exc:
            raise TransportError("Gateway WebSocket connection timed out") from exc

    async def delete_session(self, session_id: str) -> int:
        result = await self._request("DELETE", f"/v1/sessions/{session_id}")
        return result.status_code

    async def get_session(self, session_id: str) -> int:
        result = await self._request("GET", f"/v1/sessions/{session_id}")
        return result.status_code

    async def close(self) -> None:
        await self.http.close()
