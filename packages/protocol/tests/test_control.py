from __future__ import annotations

import json
from pathlib import Path

import pytest
from liveconv_protocol import (
    ErrorCode,
    GenerationCancel,
    GenerationEnd,
    GenerationStart,
    ModelSelect,
    Ping,
    ProtocolValidationError,
    SessionAttach,
    SessionClose,
    encode_control_message,
    parse_control_message,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
SESSION_ID = "123e4567-e89b-12d3-a456-426614174000"
COMMON = {
    "protocol_version": 1,
    "request_id": "01K1V-TEST",
    "session_id": SESSION_ID,
}


def error_for(value: object) -> ProtocolValidationError:
    data = value if isinstance(value, (str, bytes)) else json.dumps(value)
    with pytest.raises(ProtocolValidationError) as raised:
        parse_control_message(data)
    return raised.value


def test_all_golden_control_messages_parse_and_round_trip() -> None:
    values = json.loads((FIXTURES / "control_messages.json").read_text())
    expected_types = [
        SessionAttach,
        ModelSelect,
        GenerationStart,
        GenerationEnd,
        GenerationCancel,
        Ping,
        SessionClose,
    ]

    for value, expected_type in zip(values, expected_types, strict=True):
        message = parse_control_message(json.dumps(value))
        assert isinstance(message, expected_type)
        assert json.loads(encode_control_message(message)) == value


def test_parses_utf8_bytes() -> None:
    value = {"type": "generation.start", **COMMON, "generation_id": 1}
    assert parse_control_message(json.dumps(value).encode()).generation_id == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"type": "unknown", **COMMON},
        {"type": "generation.start", **COMMON},
        {"type": "generation.start", **COMMON, "generation_id": 1, "extra": True},
        {"type": "generation.start", **COMMON, "generation_id": -1},
        {"type": "generation.start", **COMMON, "generation_id": True},
        {"type": "model.select", **COMMON, "profile_id": "Unsafe Profile"},
        {"type": "ping", **COMMON, "client_monotonic_ns": -1, "clock_id": "clock"},
        {"type": "ping", **COMMON, "client_monotonic_ns": 1, "clock_id": ""},
        {"type": "session.attach", **COMMON, "ticket": ""},
    ],
)
def test_rejects_malformed_control_objects(value: object) -> None:
    assert error_for(value).code is ErrorCode.INVALID_STATE


@pytest.mark.parametrize("protocol_version", [2, 1.0, True])
def test_rejects_unsupported_version(protocol_version: object) -> None:
    value = {
        "type": "generation.start",
        **COMMON,
        "protocol_version": protocol_version,
        "generation_id": 1,
    }
    error = error_for(value)
    assert error.code is ErrorCode.UNSUPPORTED_PROTOCOL
    assert error.field == "protocol_version"


def test_rejects_invalid_session_id() -> None:
    session_id = "not-a-uuid"
    value = {"type": "session.close", **COMMON, "session_id": session_id}
    error = error_for(value)
    assert error.code is ErrorCode.INVALID_STATE
    assert error.field == "session_id"


def test_accepts_zero_generation_and_normalizes_uuid() -> None:
    value = {
        "type": "generation.start",
        **COMMON,
        "session_id": SESSION_ID.upper(),
        "generation_id": 0,
    }
    message = parse_control_message(json.dumps(value))
    assert message.generation_id == 0
    assert message.session_id == SESSION_ID


def test_rejects_duplicate_json_keys() -> None:
    raw = (
        '{"type":"generation.start","type":"generation.end",'
        '"protocol_version":1,"request_id":"r","session_id":"'
        + SESSION_ID
        + '","generation_id":1}'
    )
    error = error_for(raw)
    assert error.field == "type"


@pytest.mark.parametrize("raw", ["{", b"\xff", "[NaN]"])
def test_rejects_invalid_json(raw: str | bytes) -> None:
    assert error_for(raw).code is ErrorCode.INVALID_STATE


def test_rejects_oversized_control_message() -> None:
    error = error_for(" " * 16_385)
    assert error.code is ErrorCode.INVALID_STATE


@pytest.mark.parametrize(
    "message,code,field",
    [
        (
            GenerationStart(
                protocol_version=2,
                request_id="request",
                session_id=SESSION_ID,
                generation_id=1,
            ),
            ErrorCode.UNSUPPORTED_PROTOCOL,
            "protocol_version",
        ),
        (
            GenerationStart(
                protocol_version=1,
                request_id="",
                session_id=SESSION_ID,
                generation_id=1,
            ),
            ErrorCode.INVALID_STATE,
            "request_id",
        ),
        (
            GenerationStart(
                protocol_version=1,
                request_id="request",
                session_id="not-a-uuid",
                generation_id=1,
            ),
            ErrorCode.INVALID_STATE,
            "session_id",
        ),
        (
            GenerationStart(
                protocol_version=1,
                request_id="request",
                session_id=SESSION_ID,
                generation_id=-1,
            ),
            ErrorCode.INVALID_STATE,
            "generation_id",
        ),
    ],
)
def test_encoder_revalidates_constructed_messages(
    message: GenerationStart, code: ErrorCode, field: str
) -> None:
    with pytest.raises(ProtocolValidationError) as raised:
        encode_control_message(message)

    assert raised.value.code is code
    assert raised.value.field == field


def test_encoder_normalizes_constructed_message() -> None:
    message = GenerationStart(
        protocol_version=1,
        request_id="request",
        session_id=SESSION_ID.upper(),
        generation_id=0,
    )
    encoded = json.loads(encode_control_message(message))

    assert encoded["session_id"] == SESSION_ID
