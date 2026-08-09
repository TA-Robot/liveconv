from __future__ import annotations

import base64
import json
import math
import struct

import pytest

from workers.runtime.codec import MAX_LINE_BYTES, decode_message, encode_message
from workers.runtime.errors import WorkerProtocolError


def hello_message() -> dict[str, object]:
    return {
        "type": "worker.hello",
        "worker_protocol_version": 1,
        "rpc_id": 1,
        "profile_id": "test.gain.v1",
        "pipeline_id": "00000000-0000-4000-8000-000000000001",
        "configuration_hash": (
            "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        ),
    }


def audio_message(samples: tuple[float, ...] | None = None) -> dict[str, object]:
    values = samples if samples is not None else (0.0,) * 960
    pcm = struct.pack(f"<{len(values)}f", *values)
    return {
        "type": "audio.push",
        "worker_protocol_version": 1,
        "generation_id": 7,
        "sequence": 0,
        "sample_rate": 48000,
        "channels": 1,
        "samples_per_channel": 960,
        "source_monotonic_ns": 1234567890123,
        "pcm_f32le_base64": base64.b64encode(pcm).decode("ascii"),
    }


def assert_protocol_error(line: bytes, *, field: str) -> WorkerProtocolError:
    with pytest.raises(WorkerProtocolError) as raised:
        decode_message(line)
    assert raised.value.field == field
    return raised.value


def test_strict_ndjson_round_trip_has_one_terminal_newline() -> None:
    message = hello_message()
    encoded = encode_message(message)

    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert len(encoded) <= MAX_LINE_BYTES
    assert decode_message(encoded) == message


@pytest.mark.parametrize(
    ("line", "field"),
    [
        (b"{}", "line"),
        (b"{}\n{}\n", "line"),
        (b"[]\n", "message"),
        (b"\xff\n", "encoding"),
        (b'{"type":"worker.health",}\n', "json"),
    ],
)
def test_rejects_non_ndjson_or_non_object_input(line: bytes, field: str) -> None:
    assert_protocol_error(line, field=field)


def test_rejects_line_larger_than_16_kib_before_json_validation() -> None:
    line = b"{" + (b"x" * MAX_LINE_BYTES) + b"}\n"
    error = assert_protocol_error(line, field="line")
    assert "16384" in str(error)


@pytest.mark.parametrize(
    "line",
    [
        b'{"type":"worker.health","type":"worker.close",'
        b'"worker_protocol_version":1,"rpc_id":2}\n',
        b'{"type":"worker.hello","worker_protocol_version":1,"rpc_id":1,'
        b'"profile_id":"test.gain.v1","pipeline_id":"a","configuration_hash":'
        b'{"algorithm":"sha256","algorithm":"md5"}}\n',
    ],
)
def test_rejects_duplicate_keys_at_any_object_depth(line: bytes) -> None:
    assert_protocol_error(line, field="json")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_rejects_nonfinite_json_numbers(constant: str) -> None:
    line = (
        f'{{"type":"worker.health","worker_protocol_version":1,"rpc_id":{constant}}}\n'
    ).encode()
    assert_protocol_error(line, field="json")


def test_rejects_unknown_type_version_and_field() -> None:
    unknown_type = hello_message() | {"type": "test.release"}
    assert_protocol_error(encode_json(unknown_type), field="type")

    bad_version = hello_message() | {"worker_protocol_version": 2}
    assert_protocol_error(encode_json(bad_version), field="worker_protocol_version")

    unknown_field = hello_message() | {"weight_path": "/private/model.bin"}
    assert_protocol_error(encode_json(unknown_field), field="weight_path")


@pytest.mark.parametrize("value", [True, -1, 1.5])
def test_rejects_non_unsigned_integer_rpc_id(value: object) -> None:
    assert_protocol_error(
        encode_json(hello_message() | {"rpc_id": value}), field="rpc_id"
    )


@pytest.mark.parametrize("encoded", ["!!!!", "AAAA=", "AA A="])
def test_rejects_noncanonical_or_invalid_base64(encoded: str) -> None:
    assert_protocol_error(
        encode_json(audio_message() | {"pcm_f32le_base64": encoded}),
        field="pcm_f32le_base64",
    )


def test_rejects_pcm_size_mismatch() -> None:
    message = audio_message((0.0,) * 959)
    assert_protocol_error(encode_json(message), field="pcm_f32le_base64")


@pytest.mark.parametrize("sample", [math.nan, math.inf, -math.inf])
def test_rejects_nonfinite_pcm(sample: float) -> None:
    message = audio_message((sample,) + ((0.0,) * 959))
    assert_protocol_error(encode_json(message), field="pcm_f32le_base64")


def test_valid_audio_message_round_trips_without_rewriting_base64() -> None:
    message = audio_message()
    assert decode_message(encode_message(message)) == message


def test_encoder_applies_the_same_nonfinite_and_size_limits() -> None:
    with pytest.raises(WorkerProtocolError) as nonfinite:
        encode_message({"type": "worker.health", "value": math.nan})
    assert nonfinite.value.field == "json"

    with pytest.raises(WorkerProtocolError) as oversized:
        encode_message(hello_message() | {"profile_id": "x" * MAX_LINE_BYTES})
    assert oversized.value.field == "line"


def encode_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=True)
        + "\n"
    ).encode("utf-8")
