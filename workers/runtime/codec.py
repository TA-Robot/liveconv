from __future__ import annotations

import base64
import binascii
import json
import math
import struct
from collections.abc import Mapping
from typing import Any

from .errors import WorkerProtocolError

MAX_LINE_BYTES = 16 * 1024
WORKER_PROTOCOL_VERSION = 1

_AUDIO_FIELDS = {
    "type",
    "worker_protocol_version",
    "generation_id",
    "sequence",
    "sample_rate",
    "channels",
    "samples_per_channel",
    "source_monotonic_ns",
    "pcm_f32le_base64",
}

_SCHEMAS: dict[str, tuple[set[str], set[str]]] = {
    "worker.hello": (
        {
            "type",
            "worker_protocol_version",
            "rpc_id",
            "profile_id",
            "pipeline_id",
            "configuration_hash",
        },
        set(),
    ),
    "worker.ready": (
        {
            "type",
            "worker_protocol_version",
            "rpc_id",
            "profile_id",
            "pipeline_id",
            "implementation_revision",
            "weight_revision",
            "configuration_hash",
        },
        set(),
    ),
    "generation.start": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "generation.started": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "generation.end": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "generation.completed": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "generation.cancel": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "generation.canceled": (
        {"type", "worker_protocol_version", "rpc_id", "generation_id"},
        set(),
    ),
    "worker.health": (
        {"type", "worker_protocol_version", "rpc_id"},
        set(),
    ),
    "worker.health.result": (
        {
            "type",
            "worker_protocol_version",
            "rpc_id",
            "ready",
            "active_generation_id",
            "queue_depth_frames",
            "capacity_frames",
        },
        set(),
    ),
    "worker.close": (
        {"type", "worker_protocol_version", "rpc_id"},
        set(),
    ),
    "worker.closed": (
        {"type", "worker_protocol_version", "rpc_id"},
        set(),
    ),
    "worker.error": (
        {
            "type",
            "worker_protocol_version",
            "rpc_id",
            "code",
            "message",
            "recoverable",
        },
        set(),
    ),
    "audio.push": (_AUDIO_FIELDS, set()),
    "audio.output": (_AUDIO_FIELDS, set()),
}


def _protocol_error(message: str, field: str) -> WorkerProtocolError:
    return WorkerProtocolError(message, field=field)


def _reject_constant(value: str) -> None:
    raise _protocol_error(f"non-finite JSON number {value} is not allowed", "json")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _protocol_error(f"duplicate JSON key: {key}", "json")
        result[key] = value
    return result


def _is_uint(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_uint(
    message: Mapping[str, object], field: str, *, positive: bool = False
) -> int:
    value = message[field]
    if not _is_uint(value) or (positive and value == 0):
        qualifier = "positive" if positive else "unsigned"
        raise _protocol_error(f"{field} must be a {qualifier} integer", field)
    return value


def _require_string(
    message: Mapping[str, object], field: str, *, nullable: bool = False
) -> str | None:
    value = message[field]
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _protocol_error(f"{field} must be a non-empty string", field)
    return value


def _validate_audio(message: Mapping[str, object]) -> None:
    _require_uint(message, "generation_id")
    _require_uint(message, "sequence")
    _require_uint(message, "sample_rate", positive=True)
    channels = _require_uint(message, "channels", positive=True)
    samples = _require_uint(message, "samples_per_channel", positive=True)
    _require_uint(message, "source_monotonic_ns")
    if channels != 1:
        raise _protocol_error("worker audio must be mono", "channels")

    encoded = _require_string(message, "pcm_f32le_base64")
    assert encoded is not None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise _protocol_error("pcm is not valid base64", "pcm_f32le_base64") from error
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise _protocol_error("pcm base64 is not canonical", "pcm_f32le_base64")
    expected = channels * samples * 4
    if len(raw) != expected:
        raise _protocol_error(
            f"pcm must decode to exactly {expected} bytes", "pcm_f32le_base64"
        )
    values = struct.unpack(f"<{channels * samples}f", raw)
    if any(not math.isfinite(value) for value in values):
        raise _protocol_error("pcm contains a non-finite sample", "pcm_f32le_base64")


def _validate_message(message: Mapping[str, object]) -> None:
    message_type = message.get("type")
    if not isinstance(message_type, str) or message_type not in _SCHEMAS:
        raise _protocol_error("unknown worker message type", "type")
    required, optional = _SCHEMAS[message_type]
    missing = required - message.keys()
    if missing:
        raise _protocol_error(
            f"missing required field: {sorted(missing)[0]}", sorted(missing)[0]
        )
    unknown = message.keys() - required - optional
    if unknown:
        field = sorted(unknown)[0]
        raise _protocol_error(f"unknown field: {field}", field)
    if message["worker_protocol_version"] != WORKER_PROTOCOL_VERSION:
        raise _protocol_error(
            "unsupported worker protocol version", "worker_protocol_version"
        )

    if "rpc_id" in message:
        _require_uint(message, "rpc_id")
    if message_type.startswith("generation."):
        _require_uint(message, "generation_id")
    if message_type in {"audio.push", "audio.output"}:
        _validate_audio(message)
    elif message_type in {"worker.hello", "worker.ready"}:
        _require_string(message, "profile_id")
        _require_string(message, "pipeline_id")
        _require_string(message, "configuration_hash")
        if message_type == "worker.ready":
            _require_string(message, "implementation_revision")
            _require_string(message, "weight_revision", nullable=True)
    elif message_type == "worker.health.result":
        if not isinstance(message["ready"], bool):
            raise _protocol_error("ready must be boolean", "ready")
        active = message["active_generation_id"]
        if active is not None and not _is_uint(active):
            raise _protocol_error(
                "active_generation_id must be null or unsigned integer",
                "active_generation_id",
            )
        _require_uint(message, "queue_depth_frames")
        _require_uint(message, "capacity_frames")
    elif message_type == "worker.error":
        _require_string(message, "code")
        _require_string(message, "message")
        if not isinstance(message["recoverable"], bool):
            raise _protocol_error("recoverable must be boolean", "recoverable")


def decode_message(line: bytes) -> dict[str, object]:
    if not isinstance(line, bytes):
        raise _protocol_error("worker protocol input must be bytes", "line")
    if len(line) > MAX_LINE_BYTES:
        raise _protocol_error(
            f"worker protocol line exceeds {MAX_LINE_BYTES} bytes", "line"
        )
    if not line.endswith(b"\n") or line.count(b"\n") != 1 or b"\r" in line:
        raise _protocol_error("worker protocol requires one terminal newline", "line")
    try:
        text = line[:-1].decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise _protocol_error(
            "worker protocol line is not UTF-8", "encoding"
        ) from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except WorkerProtocolError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise _protocol_error(
            "worker protocol line is not valid JSON", "json"
        ) from error
    if not isinstance(value, dict):
        raise _protocol_error("worker protocol message must be an object", "message")
    _validate_message(value)
    return value


def encode_message(message: Mapping[str, object]) -> bytes:
    if not isinstance(message, Mapping):
        raise _protocol_error("worker protocol message must be an object", "message")
    value = dict(message)
    try:
        line = (
            json.dumps(
                value,
                ensure_ascii=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise _protocol_error("message is not finite JSON", "json") from error
    if len(line) > MAX_LINE_BYTES:
        raise _protocol_error(
            f"worker protocol line exceeds {MAX_LINE_BYTES} bytes", "line"
        )
    _validate_message(value)
    return line
