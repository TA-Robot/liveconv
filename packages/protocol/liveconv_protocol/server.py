from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, ClassVar
from uuid import UUID

from .control import MAX_CONTROL_MESSAGE_BYTES
from .errors import ErrorCode, ProtocolValidationError, RequiredAction
from .frame import PROTOCOL_VERSION

_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CLOCK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_FIELD_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@dataclass(frozen=True, slots=True)
class IngressLimits:
    ingress_budget_ms: int
    max_ingress_frames: int


@dataclass(frozen=True, slots=True)
class ServerEvent:
    protocol_version: int
    message_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.message_type,
            **{key: value for key, value in asdict(self).items() if value is not None},
        }


@dataclass(frozen=True, slots=True)
class SessionReadyEvent(ServerEvent):
    message_type: ClassVar[str] = "session.ready"
    session_id: str
    request_id: str
    profile_id: str
    profile_hash: str
    configuration_hash: str
    pipeline_id: str
    clock_id: str
    limits: IngressLimits


@dataclass(frozen=True, slots=True)
class ModelSelectedEvent(ServerEvent):
    message_type: ClassVar[str] = "model.selected"
    session_id: str
    request_id: str
    profile_id: str
    profile_hash: str
    configuration_hash: str
    pipeline_id: str


@dataclass(frozen=True, slots=True)
class GenerationReadyEvent(ServerEvent):
    message_type: ClassVar[str] = "generation.ready"
    session_id: str
    request_id: str
    generation_id: int
    profile_id: str
    profile_hash: str
    configuration_hash: str
    pipeline_id: str


@dataclass(frozen=True, slots=True)
class GenerationCompletedEvent(ServerEvent):
    message_type: ClassVar[str] = "generation.completed"
    session_id: str
    request_id: str
    generation_id: int
    pipeline_id: str


@dataclass(frozen=True, slots=True)
class GenerationCanceledEvent(ServerEvent):
    message_type: ClassVar[str] = "generation.canceled"
    session_id: str
    request_id: str
    generation_id: int
    pipeline_id: str


@dataclass(frozen=True, slots=True)
class SessionClosedEvent(ServerEvent):
    message_type: ClassVar[str] = "session.closed"
    session_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class FallbackRequiredEvent(ServerEvent):
    message_type: ClassVar[str] = "fallback.required"
    session_id: str
    generation_id: int
    pipeline_id: str
    reason_code: ErrorCode


@dataclass(frozen=True, slots=True)
class ErrorEvent(ServerEvent):
    message_type: ClassVar[str] = "error"
    code: ErrorCode
    recoverable: bool
    required_action: RequiredAction
    message: str
    session_id: str | None = None
    request_id: str | None = None
    generation_id: int | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class PongEvent(ServerEvent):
    message_type: ClassVar[str] = "pong"
    session_id: str
    request_id: str
    client_clock_id: str
    client_monotonic_ns: int
    clock_id: str
    server_monotonic_ns: int


type ParsedServerEvent = (
    SessionReadyEvent
    | ModelSelectedEvent
    | GenerationReadyEvent
    | GenerationCompletedEvent
    | GenerationCanceledEvent
    | SessionClosedEvent
    | FallbackRequiredEvent
    | ErrorEvent
    | PongEvent
)

_COMMON = frozenset({"type", "protocol_version", "session_id"})
_REQUEST = _COMMON | {"request_id"}
_PROFILE = {"profile_id", "profile_hash", "configuration_hash", "pipeline_id"}
_GENERATION = {"generation_id", "pipeline_id"}
_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "session.ready": _REQUEST | _PROFILE | {"clock_id", "limits"},
    "model.selected": _REQUEST | _PROFILE,
    "generation.ready": _REQUEST | _PROFILE | {"generation_id"},
    "generation.completed": _REQUEST | _GENERATION,
    "generation.canceled": _REQUEST | _GENERATION,
    "session.closed": _REQUEST,
    "fallback.required": _COMMON | _GENERATION | {"reason_code"},
    "error": frozenset(
        {
            "type",
            "protocol_version",
            "code",
            "recoverable",
            "required_action",
            "message",
        }
    ),
    "pong": _REQUEST
    | {"client_clock_id", "client_monotonic_ns", "clock_id", "server_monotonic_ns"},
}
_OPTIONAL_FIELDS: dict[str, frozenset[str]] = {
    "error": frozenset({"session_id", "request_id", "generation_id", "field"})
}


def _invalid(message: str, *, field: str | None = None) -> ProtocolValidationError:
    return ProtocolValidationError(ErrorCode.INVALID_STATE, message, field=field)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _invalid(f"duplicate server event field {key!r}", field=key)
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise _invalid(f"non-finite JSON number {value!r} is not allowed")


def _require_text(
    value: object,
    *,
    field: str,
    pattern: re.Pattern[str] | None = None,
    maximum_bytes: int = 1024,
) -> str:
    if not isinstance(value, str) or not value:
        raise _invalid(f"{field} must be a non-empty string", field=field)
    if len(value.encode("utf-8")) > maximum_bytes:
        raise _invalid(f"{field} is too long", field=field)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise _invalid(f"{field} has an invalid format", field=field)
    return value


def _require_uuid(value: object, *, field: str) -> str:
    text = _require_text(value, field=field, maximum_bytes=36)
    try:
        parsed = str(UUID(text))
    except (ValueError, AttributeError) as exc:
        raise _invalid(f"{field} must be a UUID", field=field) from exc
    if parsed != text:
        raise _invalid(f"{field} must use canonical UUID form", field=field)
    return parsed


def _require_uint(value: object, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(f"{field} must be an integer", field=field)
    if not 0 <= value <= maximum:
        raise _invalid(f"{field} is outside its wire range", field=field)
    return value


def _require_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise _invalid(f"{field} must be a boolean", field=field)
    return value


def _require_enum(
    value: object, enum_type: type[ErrorCode] | type[RequiredAction], *, field: str
):
    if not isinstance(value, str):
        raise _invalid(f"{field} must be a string", field=field)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise _invalid(f"{field} is not a version 1 value", field=field) from exc


def _require_limits(value: object) -> IngressLimits:
    if not isinstance(value, Mapping):
        raise _invalid("limits must be an object", field="limits")
    if any(not isinstance(key, str) for key in value):
        raise _invalid("limits field names must be strings", field="limits")
    expected = {"ingress_budget_ms", "max_ingress_frames"}
    actual = set(value)
    if actual != expected:
        missing = expected - actual
        unknown = actual - expected
        field = min(missing or unknown)
        issue = "missing" if missing else "unknown"
        raise _invalid(f"{issue} limits field {field!r}", field=f"limits.{field}")
    ingress_budget_ms = _require_uint(
        value["ingress_budget_ms"],
        field="limits.ingress_budget_ms",
        maximum=_UINT32_MAX,
    )
    max_ingress_frames = _require_uint(
        value["max_ingress_frames"],
        field="limits.max_ingress_frames",
        maximum=_UINT32_MAX,
    )
    if ingress_budget_ms == 0 or max_ingress_frames == 0:
        raise _invalid("limits must be greater than zero", field="limits")
    return IngressLimits(ingress_budget_ms, max_ingress_frames)


def _common(value: Mapping[str, Any]) -> dict[str, Any]:
    protocol_version = value["protocol_version"]
    if type(protocol_version) is not int or protocol_version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            ErrorCode.UNSUPPORTED_PROTOCOL,
            f"unsupported server event protocol version {protocol_version!r}",
            field="protocol_version",
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "session_id": _require_uuid(value["session_id"], field="session_id"),
    }


def _request(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_common(value),
        "request_id": _require_text(
            value["request_id"],
            field="request_id",
            pattern=_REQUEST_ID_RE,
            maximum_bytes=128,
        ),
    }


def _profile(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": _require_text(
            value["profile_id"],
            field="profile_id",
            pattern=_PROFILE_ID_RE,
            maximum_bytes=128,
        ),
        "profile_hash": _require_text(
            value["profile_hash"], field="profile_hash", pattern=_HASH_RE
        ),
        "configuration_hash": _require_text(
            value["configuration_hash"],
            field="configuration_hash",
            pattern=_HASH_RE,
        ),
        "pipeline_id": _require_uuid(value["pipeline_id"], field="pipeline_id"),
    }


def _generation(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generation_id": _require_uint(
            value["generation_id"], field="generation_id", maximum=_UINT32_MAX
        ),
        "pipeline_id": _require_uuid(value["pipeline_id"], field="pipeline_id"),
    }


def validate_server_event(value: Mapping[str, Any]) -> ParsedServerEvent:
    if not isinstance(value, Mapping):
        raise _invalid("server event must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise _invalid("server event field names must be strings")
    message_type = value.get("type")
    if not isinstance(message_type, str) or message_type not in _REQUIRED_FIELDS:
        raise _invalid("unsupported server event type", field="type")

    required = _REQUIRED_FIELDS[message_type]
    allowed = required | _OPTIONAL_FIELDS.get(message_type, frozenset())
    actual = frozenset(value)
    missing = required - actual
    unknown = actual - allowed
    if missing:
        field = min(missing)
        raise _invalid(f"missing required server event field {field!r}", field=field)
    if unknown:
        field = min(unknown)
        raise _invalid(f"unknown server event field {field!r}", field=field)

    if message_type == "session.ready":
        return SessionReadyEvent(
            **_request(value),
            **_profile(value),
            clock_id=_require_text(
                value["clock_id"],
                field="clock_id",
                pattern=_CLOCK_ID_RE,
                maximum_bytes=128,
            ),
            limits=_require_limits(value["limits"]),
        )
    if message_type == "model.selected":
        return ModelSelectedEvent(**_request(value), **_profile(value))
    if message_type == "generation.ready":
        return GenerationReadyEvent(
            **_request(value),
            **_profile(value),
            generation_id=_require_uint(
                value["generation_id"], field="generation_id", maximum=_UINT32_MAX
            ),
        )
    if message_type == "generation.completed":
        return GenerationCompletedEvent(**_request(value), **_generation(value))
    if message_type == "generation.canceled":
        return GenerationCanceledEvent(**_request(value), **_generation(value))
    if message_type == "session.closed":
        return SessionClosedEvent(**_request(value))
    if message_type == "fallback.required":
        return FallbackRequiredEvent(
            **_common(value),
            **_generation(value),
            reason_code=_require_enum(
                value["reason_code"], ErrorCode, field="reason_code"
            ),
        )
    if message_type == "pong":
        return PongEvent(
            **_request(value),
            client_clock_id=_require_text(
                value["client_clock_id"],
                field="client_clock_id",
                pattern=_CLOCK_ID_RE,
                maximum_bytes=128,
            ),
            client_monotonic_ns=_require_uint(
                value["client_monotonic_ns"],
                field="client_monotonic_ns",
                maximum=_UINT64_MAX,
            ),
            clock_id=_require_text(
                value["clock_id"],
                field="clock_id",
                pattern=_CLOCK_ID_RE,
                maximum_bytes=128,
            ),
            server_monotonic_ns=_require_uint(
                value["server_monotonic_ns"],
                field="server_monotonic_ns",
                maximum=_UINT64_MAX,
            ),
        )

    session_id = (
        _require_uuid(value["session_id"], field="session_id")
        if "session_id" in value
        else None
    )
    request_id = (
        _require_text(
            value["request_id"],
            field="request_id",
            pattern=_REQUEST_ID_RE,
            maximum_bytes=128,
        )
        if "request_id" in value
        else None
    )
    generation_id = (
        _require_uint(
            value["generation_id"], field="generation_id", maximum=_UINT32_MAX
        )
        if "generation_id" in value
        else None
    )
    field = (
        _require_text(
            value["field"], field="field", pattern=_FIELD_RE, maximum_bytes=128
        )
        if "field" in value
        else None
    )
    protocol_version = value["protocol_version"]
    if type(protocol_version) is not int or protocol_version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            ErrorCode.UNSUPPORTED_PROTOCOL,
            f"unsupported server event protocol version {protocol_version!r}",
            field="protocol_version",
        )
    return ErrorEvent(
        protocol_version=PROTOCOL_VERSION,
        code=_require_enum(value["code"], ErrorCode, field="code"),
        recoverable=_require_bool(value["recoverable"], field="recoverable"),
        required_action=_require_enum(
            value["required_action"], RequiredAction, field="required_action"
        ),
        message=_require_text(value["message"], field="message"),
        session_id=session_id,
        request_id=request_id,
        generation_id=generation_id,
        field=field,
    )


def parse_server_event(data: str | bytes | bytearray | memoryview) -> ParsedServerEvent:
    if isinstance(data, str):
        encoded = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray, memoryview)):
        encoded = bytes(data)
    else:
        raise TypeError("server event must be str or bytes-like")
    if len(encoded) > MAX_CONTROL_MESSAGE_BYTES:
        raise _invalid("server event exceeds the version 1 size limit")
    try:
        decoded = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _invalid("server event must be UTF-8 JSON") from exc
    try:
        value = json.loads(
            decoded,
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except ProtocolValidationError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise _invalid("server event must be valid JSON") from exc
    if not isinstance(value, Mapping):
        raise _invalid("server event must be a JSON object")
    return validate_server_event(value)


def encode_server_event(event: ParsedServerEvent) -> str:
    normalized = validate_server_event(event.to_dict())
    return json.dumps(
        normalized.to_dict(),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
