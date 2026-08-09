from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path

import pytest
from liveconv_protocol import (
    HEADER_LENGTH,
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def make_frame() -> PcmFrame:
    return PcmFrame.from_samples(
        FrameHeader(
            kind=FrameKind.INPUT,
            generation_id=7,
            sequence=42,
            source_monotonic_ns=1_234_567_890_123,
        ),
        [((index % 32) - 16) / 16 for index in range(960)],
    )


def mutate(message: bytes, offset: int, replacement: bytes) -> bytes:
    return message[:offset] + replacement + message[offset + len(replacement) :]


def assert_error(
    code: ErrorCode,
    field: str,
    function: object,
    *args: object,
) -> None:
    with pytest.raises(ProtocolValidationError) as raised:
        function(*args)  # type: ignore[operator]
    assert raised.value.code is code
    assert raised.value.field == field


def test_frame_matches_golden_fixture_and_round_trips() -> None:
    golden = json.loads((FIXTURES / "pcm_frame_v1.json").read_text())
    frame = make_frame()
    encoded = frame.encode()

    assert len(frame.header.encode()) == HEADER_LENGTH
    assert frame.header.encode().hex() == golden["encoded_header_hex"]
    assert hashlib.sha256(frame.payload).hexdigest() == golden["payload_sha256"]
    assert hashlib.sha256(encoded).hexdigest() == golden["frame_sha256"]
    assert len(encoded) == golden["frame_length"]
    assert PcmFrame.decode(encoded) == frame
    assert frame.unpack_samples()[:4] == pytest.approx((-1.0, -0.9375, -0.875, -0.8125))


def test_output_frame_round_trips() -> None:
    frame = make_frame()
    output = PcmFrame(
        header=FrameHeader(
            kind=FrameKind.OUTPUT,
            generation_id=frame.header.generation_id,
            sequence=frame.header.sequence,
            source_monotonic_ns=frame.header.source_monotonic_ns,
        ),
        payload=frame.payload,
    )
    assert PcmFrame.decode(memoryview(output.encode())) == output


def test_rejects_bad_magic() -> None:
    message = mutate(make_frame().encode(), 0, b"NO")
    assert_error(ErrorCode.UNSUPPORTED_PROTOCOL, "magic", PcmFrame.decode, message)


def test_rejects_bad_version() -> None:
    message = mutate(make_frame().encode(), 2, b"\x02")
    assert_error(
        ErrorCode.UNSUPPORTED_PROTOCOL, "protocol_version", PcmFrame.decode, message
    )


def test_rejects_bad_header_length() -> None:
    message = mutate(make_frame().encode(), 6, struct.pack("!H", 31))
    assert_error(
        ErrorCode.UNSUPPORTED_PROTOCOL, "header_length", PcmFrame.decode, message
    )


@pytest.mark.parametrize("delta", [-4, 4])
def test_rejects_short_or_extra_payload(delta: int) -> None:
    message = make_frame().encode()
    changed = message[:delta] if delta < 0 else message + (b"\x00" * delta)
    assert_error(ErrorCode.UNSUPPORTED_AUDIO, "payload", PcmFrame.decode, changed)


def test_rejects_header_without_payload() -> None:
    assert_error(
        ErrorCode.UNSUPPORTED_AUDIO,
        "payload",
        PcmFrame.decode,
        make_frame().header.encode(),
    )


def test_rejects_unknown_kind_and_flags() -> None:
    message = make_frame().encode()
    assert_error(
        ErrorCode.UNSUPPORTED_AUDIO,
        "kind",
        PcmFrame.decode,
        mutate(message, 3, b"\x03"),
    )
    assert_error(
        ErrorCode.UNSUPPORTED_AUDIO,
        "flags",
        PcmFrame.decode,
        mutate(message, 4, struct.pack("!H", 1)),
    )


@pytest.mark.parametrize(("field", "value"), [("kind", True), ("flags", False)])
def test_header_rejects_boolean_enum_values(field: str, value: bool) -> None:
    values = {
        "kind": FrameKind.INPUT,
        "generation_id": 1,
        "sequence": 0,
        "source_monotonic_ns": 1,
        "flags": 0,
    }
    values[field] = value
    with pytest.raises(ProtocolValidationError) as raised:
        FrameHeader(**values)  # type: ignore[arg-type]
    assert raised.value.code is ErrorCode.UNSUPPORTED_AUDIO
    assert raised.value.field == field


@pytest.mark.parametrize(
    ("offset", "replacement", "field"),
    [
        (16, struct.pack("!I", 24_000), "sample_rate"),
        (20, struct.pack("!H", 2), "channels"),
        (22, struct.pack("!H", 480), "samples_per_channel"),
    ],
)
def test_rejects_unnegotiated_audio_format(
    offset: int,
    replacement: bytes,
    field: str,
) -> None:
    assert_error(
        ErrorCode.UNSUPPORTED_AUDIO,
        field,
        PcmFrame.decode,
        mutate(make_frame().encode(), offset, replacement),
    )


def test_from_samples_rejects_wrong_sample_count() -> None:
    header = make_frame().header
    assert_error(
        ErrorCode.UNSUPPORTED_AUDIO,
        "payload",
        PcmFrame.from_samples,
        header,
        [0.0] * 959,
    )


@pytest.mark.parametrize("sample", [math.nan, math.inf, -math.inf])
def test_transport_accepts_nonfinite_float32_for_gateway_validation(
    sample: float,
) -> None:
    header = FrameHeader(
        kind=FrameKind.INPUT,
        generation_id=1,
        sequence=0,
        source_monotonic_ns=1,
    )
    encoded = PcmFrame.from_samples(header, [sample] * 960).encode()
    decoded = PcmFrame.decode(encoded)
    first = decoded.unpack_samples()[0]
    assert math.isnan(first) if math.isnan(sample) else first == sample
