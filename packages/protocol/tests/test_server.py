from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from liveconv_protocol import (
    ErrorCode,
    ErrorEvent,
    FallbackRequiredEvent,
    GenerationCanceledEvent,
    GenerationCompletedEvent,
    GenerationReadyEvent,
    ModelSelectedEvent,
    PongEvent,
    ProtocolValidationError,
    RequiredAction,
    SessionClosedEvent,
    SessionReadyEvent,
    encode_server_event,
    parse_server_event,
    validate_server_event,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
SESSION_ID = "123e4567-e89b-12d3-a456-426614174000"
PIPELINE_ID = "987e6543-e21b-12d3-a456-426614174000"
PROFILE_HASH = "sha256:" + ("a" * 64)
CONFIGURATION_HASH = "sha256:" + ("b" * 64)


def session_ready() -> dict[str, object]:
    return {
        "type": "session.ready",
        "protocol_version": 1,
        "session_id": SESSION_ID,
        "request_id": "ready-1",
        "profile_id": "test.passthrough.v1",
        "profile_hash": PROFILE_HASH,
        "configuration_hash": CONFIGURATION_HASH,
        "pipeline_id": PIPELINE_ID,
        "clock_id": "gateway-clock-1",
        "limits": {"ingress_budget_ms": 500, "max_ingress_frames": 25},
    }


def error_for(value: object) -> ProtocolValidationError:
    data = value if isinstance(value, (str, bytes)) else json.dumps(value)
    with pytest.raises(ProtocolValidationError) as raised:
        parse_server_event(data)
    return raised.value


def test_all_golden_events_parse_and_round_trip() -> None:
    values = json.loads((FIXTURES / "server_events.json").read_text())
    expected_types = [
        SessionReadyEvent,
        ModelSelectedEvent,
        GenerationReadyEvent,
        GenerationCompletedEvent,
        GenerationCanceledEvent,
        SessionClosedEvent,
        FallbackRequiredEvent,
        ErrorEvent,
        PongEvent,
    ]

    for value, expected_type in zip(values, expected_types, strict=True):
        event = parse_server_event(json.dumps(value))
        assert isinstance(event, expected_type)
        assert json.loads(encode_server_event(event)) == value


def test_error_request_and_session_are_optional_before_attachment() -> None:
    value = {
        "type": "error",
        "protocol_version": 1,
        "code": "AUTH_FAILED",
        "recoverable": False,
        "required_action": "close_session",
        "message": "attachment authentication failed",
    }
    event = parse_server_event(json.dumps(value).encode())
    assert isinstance(event, ErrorEvent)
    assert event.session_id is None
    assert event.request_id is None
    assert json.loads(encode_server_event(event)) == value


def test_direct_event_encoding_is_revalidated() -> None:
    event = ErrorEvent(
        protocol_version=1,
        code=ErrorCode.AUTH_FAILED,
        recoverable=False,
        required_action=RequiredAction.CLOSE_SESSION,
        message="attachment failed",
    )
    assert parse_server_event(encode_server_event(event)) == event

    invalid = ErrorEvent(
        protocol_version=2,
        code=ErrorCode.AUTH_FAILED,
        recoverable=False,
        required_action=RequiredAction.CLOSE_SESSION,
        message="attachment failed",
    )
    with pytest.raises(ProtocolValidationError) as raised:
        encode_server_event(invalid)
    assert raised.value.code is ErrorCode.UNSUPPORTED_PROTOCOL


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ({"type": "unknown"}, "type"),
        ({"session_id": "not-a-uuid"}, "session_id"),
        ({"session_id": SESSION_ID.upper()}, "session_id"),
        ({"pipeline_id": "not-a-uuid"}, "pipeline_id"),
        ({"profile_hash": "sha256:ABC"}, "profile_hash"),
        ({"configuration_hash": "a" * 64}, "configuration_hash"),
        ({"clock_id": "bad clock"}, "clock_id"),
        ({"request_id": "bad request"}, "request_id"),
    ],
)
def test_rejects_invalid_identity_fields(
    mutation: dict[str, object],
    field: str,
) -> None:
    value = {**session_ready(), **mutation}
    error = error_for(value)
    assert error.code is ErrorCode.INVALID_STATE
    assert error.field == field


@pytest.mark.parametrize("protocol_version", [2, 1.0, True])
def test_rejects_unsupported_protocol_version(protocol_version: object) -> None:
    error = error_for({**session_ready(), "protocol_version": protocol_version})
    assert error.code is ErrorCode.UNSUPPORTED_PROTOCOL
    assert error.field == "protocol_version"


def test_rejects_missing_and_unknown_fields() -> None:
    missing = session_ready()
    del missing["pipeline_id"]
    assert error_for(missing).field == "pipeline_id"
    assert error_for({**session_ready(), "extra": True}).field == "extra"


@pytest.mark.parametrize(
    "limits",
    [
        None,
        {"ingress_budget_ms": 500},
        {"ingress_budget_ms": 500, "max_ingress_frames": 25, "extra": 1},
        {"ingress_budget_ms": 0, "max_ingress_frames": 25},
        {"ingress_budget_ms": 500, "max_ingress_frames": True},
    ],
)
def test_rejects_invalid_limits(limits: object) -> None:
    error = error_for({**session_ready(), "limits": limits})
    assert error.code is ErrorCode.INVALID_STATE
    assert error.field is not None and error.field.startswith("limits")


@pytest.mark.parametrize("generation_id", [-1, 2**32, True, 1.0])
def test_rejects_generation_outside_u32(generation_id: object) -> None:
    value = {
        "type": "generation.completed",
        "protocol_version": 1,
        "session_id": SESSION_ID,
        "request_id": "end-1",
        "generation_id": generation_id,
        "pipeline_id": PIPELINE_ID,
    }
    assert error_for(value).field == "generation_id"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("client_monotonic_ns", -1),
        ("client_monotonic_ns", True),
        ("server_monotonic_ns", 2**64),
        ("client_clock_id", "bad clock"),
        ("clock_id", ""),
    ],
)
def test_rejects_invalid_pong_fields(field: str, value: object) -> None:
    event = {
        "type": "pong",
        "protocol_version": 1,
        "session_id": SESSION_ID,
        "request_id": "ping-1",
        "client_clock_id": "extension-clock-1",
        "client_monotonic_ns": 1,
        "clock_id": "gateway-clock-1",
        "server_monotonic_ns": 2,
    }
    event[field] = value
    assert error_for(event).field == field


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", "NOT_A_CODE"),
        ("recoverable", 1),
        ("required_action", "continue"),
        ("message", ""),
        ("field", "bad field"),
        ("generation_id", -1),
        ("session_id", "bad"),
        ("request_id", "bad request"),
    ],
)
def test_rejects_invalid_error_fields(field: str, value: object) -> None:
    event = {
        "type": "error",
        "protocol_version": 1,
        "session_id": SESSION_ID,
        "request_id": "request-1",
        "generation_id": 1,
        "code": "UNSUPPORTED_AUDIO",
        "recoverable": True,
        "required_action": "fallback",
        "message": "invalid audio",
        "field": "payload",
    }
    event[field] = value
    assert error_for(event).field == field


def test_rejects_invalid_reason_code() -> None:
    event = {
        "type": "fallback.required",
        "protocol_version": 1,
        "session_id": SESSION_ID,
        "generation_id": 1,
        "pipeline_id": PIPELINE_ID,
        "reason_code": "NOT_A_CODE",
    }
    assert error_for(event).field == "reason_code"


def test_rejects_duplicate_nonfinite_and_nonobject_json() -> None:
    duplicate = (
        '{"type":"session.closed","type":"pong","protocol_version":1,'
        f'"session_id":"{SESSION_ID}","request_id":"close-1"}}'
    )
    assert error_for(duplicate).field == "type"
    nonfinite = json.dumps(
        {
            "type": "pong",
            "protocol_version": 1,
            "session_id": SESSION_ID,
            "request_id": "ping-1",
            "client_clock_id": "extension-clock-1",
            "client_monotonic_ns": math.nan,
            "clock_id": "gateway-clock-1",
            "server_monotonic_ns": 2,
        }
    )
    assert error_for(nonfinite).code is ErrorCode.INVALID_STATE
    assert error_for("[]").code is ErrorCode.INVALID_STATE


def test_rejects_oversized_and_invalid_utf8_events() -> None:
    assert error_for(" " * 16_385).code is ErrorCode.INVALID_STATE
    assert error_for(b"\xff").code is ErrorCode.INVALID_STATE


def test_validate_rejects_non_string_mapping_keys() -> None:
    with pytest.raises(ProtocolValidationError):
        validate_server_event({1: "value"})  # type: ignore[dict-item]


def test_validate_rejects_non_string_limits_keys() -> None:
    value = session_ready()
    value["limits"] = {
        "ingress_budget_ms": 500,
        "max_ingress_frames": 25,
        1: 2,
    }
    with pytest.raises(ProtocolValidationError) as raised:
        validate_server_event(value)
    assert raised.value.field == "limits"
