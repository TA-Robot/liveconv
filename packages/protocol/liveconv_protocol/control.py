from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, ClassVar
from uuid import UUID

from .errors import ErrorCode, ProtocolValidationError
from .frame import PROTOCOL_VERSION

MAX_CONTROL_MESSAGE_BYTES = 16_384
_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_CLOCK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@dataclass(frozen=True, slots=True)
class ControlMessage:
    protocol_version: int
    request_id: str
    session_id: str
    message_type: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.message_type, **asdict(self)}


@dataclass(frozen=True, slots=True)
class SessionAttach(ControlMessage):
    message_type: ClassVar[str] = "session.attach"
    ticket: str


@dataclass(frozen=True, slots=True)
class ModelSelect(ControlMessage):
    message_type: ClassVar[str] = "model.select"
    profile_id: str


@dataclass(frozen=True, slots=True)
class GenerationStart(ControlMessage):
    message_type: ClassVar[str] = "generation.start"
    generation_id: int


@dataclass(frozen=True, slots=True)
class GenerationEnd(ControlMessage):
    message_type: ClassVar[str] = "generation.end"
    generation_id: int


@dataclass(frozen=True, slots=True)
class GenerationCancel(ControlMessage):
    message_type: ClassVar[str] = "generation.cancel"
    generation_id: int


@dataclass(frozen=True, slots=True)
class Ping(ControlMessage):
    message_type: ClassVar[str] = "ping"
    client_monotonic_ns: int
    clock_id: str


@dataclass(frozen=True, slots=True)
class SessionClose(ControlMessage):
    message_type: ClassVar[str] = "session.close"


type ParsedControlMessage = (
    SessionAttach
    | ModelSelect
    | GenerationStart
    | GenerationEnd
    | GenerationCancel
    | Ping
    | SessionClose
)

_COMMON_FIELDS = frozenset({"type", "protocol_version", "request_id", "session_id"})
_FIELDS_BY_TYPE: dict[str, frozenset[str]] = {
    "session.attach": _COMMON_FIELDS | {"ticket"},
    "model.select": _COMMON_FIELDS | {"profile_id"},
    "generation.start": _COMMON_FIELDS | {"generation_id"},
    "generation.end": _COMMON_FIELDS | {"generation_id"},
    "generation.cancel": _COMMON_FIELDS | {"generation_id"},
    "ping": _COMMON_FIELDS | {"client_monotonic_ns", "clock_id"},
    "session.close": _COMMON_FIELDS,
}


def _invalid(message: str, *, field: str | None = None) -> ProtocolValidationError:
    return ProtocolValidationError(ErrorCode.INVALID_STATE, message, field=field)


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _invalid(f"duplicate control field {key!r}", field=key)
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise _invalid(f"non-finite JSON number {value!r} is not allowed")


def _require_text(
    value: object,
    *,
    field: str,
    pattern: re.Pattern[str] | None = None,
    maximum_bytes: int = 4096,
) -> str:
    if not isinstance(value, str) or not value:
        raise _invalid(f"{field} must be a non-empty string", field=field)
    if len(value.encode("utf-8")) > maximum_bytes:
        raise _invalid(f"{field} is too long", field=field)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise _invalid(f"{field} contains unsupported characters", field=field)
    return value


def _require_uint(value: object, *, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(f"{field} must be an integer", field=field)
    if not 0 <= value <= maximum:
        raise _invalid(f"{field} is outside its wire range", field=field)
    return value


def _require_generation_id(value: object) -> int:
    return _require_uint(value, field="generation_id", maximum=_UINT32_MAX)


def _require_session_id(value: object) -> str:
    text = _require_text(value, field="session_id", maximum_bytes=36)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as exc:
        raise _invalid("session_id must be a UUID", field="session_id") from exc
    return str(parsed)


def validate_control_message(value: Mapping[str, Any]) -> ParsedControlMessage:
    if not isinstance(value, Mapping):
        raise _invalid("control message must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise _invalid("control message field names must be strings")
    message_type = value.get("type")
    if not isinstance(message_type, str) or message_type not in _FIELDS_BY_TYPE:
        raise _invalid("unsupported control message type", field="type")

    expected_fields = _FIELDS_BY_TYPE[message_type]
    actual_fields = frozenset(value.keys())
    missing = expected_fields - actual_fields
    unknown = actual_fields - expected_fields
    if missing:
        field = min(missing)
        raise _invalid(f"missing required control field {field!r}", field=field)
    if unknown:
        field = min(unknown)
        raise _invalid(f"unknown control field {field!r}", field=field)

    protocol_version = value["protocol_version"]
    if type(protocol_version) is not int or protocol_version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            ErrorCode.UNSUPPORTED_PROTOCOL,
            f"unsupported control protocol version {protocol_version!r}",
            field="protocol_version",
        )

    common = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": _require_text(
            value["request_id"],
            field="request_id",
            pattern=_REQUEST_ID_RE,
            maximum_bytes=128,
        ),
        "session_id": _require_session_id(value["session_id"]),
    }

    if message_type == "session.attach":
        return SessionAttach(
            **common,
            ticket=_require_text(value["ticket"], field="ticket"),
        )
    if message_type == "model.select":
        return ModelSelect(
            **common,
            profile_id=_require_text(
                value["profile_id"],
                field="profile_id",
                pattern=_PROFILE_ID_RE,
                maximum_bytes=128,
            ),
        )
    if message_type == "generation.start":
        return GenerationStart(
            **common, generation_id=_require_generation_id(value["generation_id"])
        )
    if message_type == "generation.end":
        return GenerationEnd(
            **common, generation_id=_require_generation_id(value["generation_id"])
        )
    if message_type == "generation.cancel":
        return GenerationCancel(
            **common, generation_id=_require_generation_id(value["generation_id"])
        )
    if message_type == "ping":
        return Ping(
            **common,
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
        )
    return SessionClose(**common)


def parse_control_message(
    data: str | bytes | bytearray | memoryview,
) -> ParsedControlMessage:
    if isinstance(data, str):
        encoded = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray, memoryview)):
        encoded = bytes(data)
    else:
        raise TypeError("control message must be str or bytes-like")
    if len(encoded) > MAX_CONTROL_MESSAGE_BYTES:
        raise _invalid("control message exceeds the version 1 size limit")

    try:
        decoded = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _invalid("control message must be UTF-8 JSON") from exc
    try:
        value = json.loads(
            decoded,
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except ProtocolValidationError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise _invalid("control message must be valid JSON") from exc
    if not isinstance(value, Mapping):
        raise _invalid("control message must be a JSON object")
    return validate_control_message(value)


def encode_control_message(message: ParsedControlMessage) -> str:
    validated = validate_control_message(message.to_dict())
    return json.dumps(
        validated.to_dict(),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
