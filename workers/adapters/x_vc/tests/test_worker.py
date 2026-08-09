from __future__ import annotations

import base64
import struct
import threading
import time

import pytest

from workers.adapters.x_vc.backend import (
    CURRENT_SAMPLES,
    FRAME_SAMPLES,
    INPUT_SAMPLE_RATE,
    DeterministicTestBackend,
    WindowResult,
)
from workers.adapters.x_vc.worker import CAPACITY_FRAMES, XvcWorker
from workers.runtime.codec import WORKER_PROTOCOL_VERSION


def control(message_type: str, rpc_id: int, **fields: object) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": rpc_id,
        **fields,
    }


def frame(
    sequence: int,
    *,
    generation_id: int = 1,
    sample_rate: int = INPUT_SAMPLE_RATE,
    samples: tuple[float, ...] = (0.25,) * FRAME_SAMPLES,
) -> dict[str, object]:
    return {
        "type": "audio.push",
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "generation_id": generation_id,
        "sequence": sequence,
        "sample_rate": sample_rate,
        "channels": 1,
        "samples_per_channel": len(samples),
        "source_monotonic_ns": sequence * 20_000_000,
        "pcm_f32le_base64": base64.b64encode(
            struct.pack(f"<{len(samples)}f", *samples)
        ).decode("ascii"),
    }


def outputs(emitted: list[dict[str, object]]) -> list[dict[str, object]]:
    return [message for message in emitted if message["type"] == "audio.output"]


def wait_for_outputs(emitted: list[dict[str, object]], count: int) -> None:
    deadline = time.monotonic() + 2
    while len(outputs(emitted)) < count and time.monotonic() < deadline:
        time.sleep(0.005)
    assert len(outputs(emitted)) == count


def test_windowed_streaming_preserves_exact_frame_identity_and_order() -> None:
    emitted: list[dict[str, object]] = []
    worker = XvcWorker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(12):
        worker.handle(frame(sequence, generation_id=7))
    wait_for_outputs(emitted, 6)
    worker.handle(control("generation.end", 2, generation_id=7))

    assert worker.wait_for_idle(2)
    transformed = outputs(emitted)
    assert [message["sequence"] for message in transformed] == list(range(12))
    assert [message["source_monotonic_ns"] for message in transformed] == [
        sequence * 20_000_000 for sequence in range(12)
    ]
    assert all(message["sample_rate"] == INPUT_SAMPLE_RATE for message in transformed)
    assert all(
        message["samples_per_channel"] == FRAME_SAMPLES for message in transformed
    )
    decoded = struct.unpack(
        f"<{FRAME_SAMPLES}f",
        base64.b64decode(str(transformed[0]["pcm_f32le_base64"])),
    )
    assert decoded == (-0.125,) * FRAME_SAMPLES
    assert emitted[-1]["type"] == "generation.completed"


def test_end_seals_and_drains_short_generation_with_right_padding() -> None:
    emitted: list[dict[str, object]] = []
    worker = XvcWorker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(3):
        worker.handle(frame(sequence))
    worker.handle(control("generation.end", 2, generation_id=1))

    with pytest.raises(ValueError, match="active writable"):
        worker.handle(frame(3))
    with pytest.raises(ValueError, match="not active"):
        worker.handle(control("generation.end", 3, generation_id=1))
    assert worker.wait_for_idle(2)
    assert [message["sequence"] for message in outputs(emitted)] == [0, 1, 2]
    assert [item["type"] for item in emitted].count("generation.completed") == 1


class CapturingBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        super().__init__()
        self.windows: list[tuple[float, ...]] = []

    def convert_window(self, samples, sample_rate, prior_tail):
        self.windows.append(tuple(samples))
        return super().convert_window(samples, sample_rate, prior_tail)


def test_context_is_always_one_bounded_official_window() -> None:
    emitted: list[dict[str, object]] = []
    backend = CapturingBackend()
    worker = XvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(18):
        samples = (sequence / 100,) * FRAME_SAMPLES
        worker.handle(frame(sequence, samples=samples))
        if sequence == 11:
            wait_for_outputs(emitted, 6)
    wait_for_outputs(emitted, 12)
    worker.handle(control("generation.cancel", 2, generation_id=1))

    assert len(backend.windows) == 2
    assert all(
        len(window) == INPUT_SAMPLE_RATE * 24 // 10 for window in backend.windows
    )
    assert backend.windows[0][:FRAME_SAMPLES] == (0.0,) * FRAME_SAMPLES
    assert backend.windows[1][-FRAME_SAMPLES:] == pytest.approx((0.17,) * FRAME_SAMPLES)


class BlockingBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def convert_window(self, samples, sample_rate, prior_tail):
        self.started.set()
        assert self.release.wait(2)
        return super().convert_window(samples, sample_rate, prior_tail)


def test_cancel_is_prompt_and_suppresses_stale_output_and_completion() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = XvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    worker.handle(frame(0, generation_id=7))
    worker.handle(control("generation.end", 2, generation_id=7))
    assert backend.started.wait(1)

    started = time.monotonic()
    worker.handle(control("generation.cancel", 3, generation_id=7))
    assert time.monotonic() - started < 0.1
    assert emitted[-1]["type"] == "generation.canceled"

    worker.handle(control("generation.start", 4, generation_id=8))
    worker.handle(frame(0, generation_id=8))
    worker.handle(control("generation.end", 5, generation_id=8))
    backend.release.set()
    assert worker.wait_for_idle(2)

    assert [message["generation_id"] for message in outputs(emitted)] == [8]
    assert not any(
        message["type"] == "generation.completed" and message["generation_id"] == 7
        for message in emitted
    )


@pytest.mark.parametrize(
    ("bad_frame", "error_text"),
    [
        (frame(0, sample_rate=16_000), "48 kHz"),
        (frame(0, samples=(0.25,) * (FRAME_SAMPLES - 1)), "20 ms"),
        (frame(0, samples=(1.01,) * FRAME_SAMPLES), "normalized"),
    ],
)
def test_rejects_pcm_outside_profile_contract(
    bad_frame: dict[str, object], error_text: str
) -> None:
    worker = XvcWorker(DeterministicTestBackend(), lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))

    with pytest.raises(ValueError, match=error_text):
        worker.handle(bad_frame)


def test_queue_is_bounded_to_500_ms_without_eviction() -> None:
    backend = BlockingBackend()
    worker = XvcWorker(backend, lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(CAPACITY_FRAMES):
        worker.handle(frame(sequence))
    assert backend.started.wait(1)

    with pytest.raises(BufferError, match="500 ms"):
        worker.handle(frame(CAPACITY_FRAMES))
    backend.release.set()


def test_enforces_monotonic_rpc_generation_sequence_and_timestamp() -> None:
    worker = XvcWorker(DeterministicTestBackend(), lambda message: None)
    worker.handle(control("generation.start", 2, generation_id=3))
    with pytest.raises(ValueError, match="rpc_id"):
        worker.handle(control("worker.health", 2))
    worker.handle(frame(1, generation_id=3))
    with pytest.raises(ValueError, match="sequence"):
        worker.handle(frame(1, generation_id=3))
    older = frame(2, generation_id=3)
    older["source_monotonic_ns"] = 0
    with pytest.raises(ValueError, match="timestamp"):
        worker.handle(older)
    worker.handle(control("generation.cancel", 3, generation_id=3))
    with pytest.raises(ValueError, match="generation_id"):
        worker.handle(control("generation.start", 4, generation_id=3))


class InvalidOutputBackend(DeterministicTestBackend):
    def convert_window(self, samples, sample_rate, prior_tail):
        result = super().convert_window(samples, sample_rate, prior_tail)
        return WindowResult((float("nan"),) + result.samples[1:], result.tail)


def test_nonfinite_backend_pcm_is_fatal_and_never_emitted() -> None:
    emitted: list[dict[str, object]] = []
    fatal = threading.Event()
    worker = XvcWorker(InvalidOutputBackend(), emitted.append, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=1))
    worker.handle(frame(0))
    worker.handle(control("generation.end", 2, generation_id=1))

    assert fatal.wait(1)
    assert worker.wait_for_idle(1)
    assert not outputs(emitted)


def test_backend_contract_uses_full_current_result_even_for_partial_end() -> None:
    frames = [
        XvcWorker._decode_frame(frame(sequence))  # noqa: SLF001
        for sequence in range(2)
    ]
    result = WindowResult((-0.2,) * CURRENT_SAMPLES, None)

    built = XvcWorker._build_outputs(frames, result)  # noqa: SLF001

    assert len(built) == 2
