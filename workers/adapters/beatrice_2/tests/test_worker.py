from __future__ import annotations

import base64
import struct
import threading
import time

import pytest

from workers.adapters.beatrice_2.backend import DeterministicTestBackend
from workers.adapters.beatrice_2.worker import BeatriceWorker
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
    sample_rate: int = 48_000,
    samples: tuple[float, ...] = (0.25,) * 960,
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


def test_full_500_ms_batch_transforms_and_preserves_identity() -> None:
    emitted: list[dict[str, object]] = []
    worker = BeatriceWorker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))

    deadline = time.monotonic() + 2
    while len(outputs(emitted)) != 25 and time.monotonic() < deadline:
        time.sleep(0.005)
    worker.handle(control("generation.end", 2, generation_id=7))
    assert worker.wait_for_idle(2)

    transformed = outputs(emitted)
    assert [message["sequence"] for message in transformed] == list(range(25))
    assert [message["source_monotonic_ns"] for message in transformed] == [
        sequence * 20_000_000 for sequence in range(25)
    ]
    decoded = struct.unpack(
        "<960f", base64.b64decode(str(transformed[0]["pcm_f32le_base64"]))
    )
    assert decoded == (-0.125,) * 960
    assert emitted[-1]["type"] == "generation.completed"


@pytest.mark.parametrize("frame_count", [1, 2, 3])
def test_end_drains_a_partial_batch_without_padding_output(frame_count: int) -> None:
    emitted: list[dict[str, object]] = []
    worker = BeatriceWorker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(frame_count):
        worker.handle(frame(sequence))
    worker.handle(control("generation.end", 2, generation_id=1))

    assert worker.wait_for_idle(2)
    assert [message["sequence"] for message in outputs(emitted)] == list(
        range(frame_count)
    )
    assert emitted[-1]["type"] == "generation.completed"


class BlockingBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        self.started.set()
        assert self.release.wait(2)
        return super().convert(samples, sample_rate)


def test_cancel_wins_end_race_and_drops_inflight_output() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = BeatriceWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    worker.handle(frame(0, generation_id=7))
    worker.handle(control("generation.end", 2, generation_id=7))
    assert backend.started.wait(1)

    started = time.monotonic()
    worker.handle(control("generation.cancel", 3, generation_id=7))
    assert time.monotonic() - started < 0.1
    assert emitted[-1]["type"] == "generation.canceled"

    backend.release.set()
    time.sleep(0.05)
    assert not outputs(emitted)
    assert not any(item["type"] == "generation.completed" for item in emitted)


def test_next_generation_queues_behind_canceled_inference() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = BeatriceWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    worker.handle(frame(0, generation_id=7))
    worker.handle(control("generation.end", 2, generation_id=7))
    assert backend.started.wait(1)

    worker.handle(control("generation.cancel", 3, generation_id=7))
    worker.handle(control("generation.start", 4, generation_id=8))
    worker.handle(frame(0, generation_id=8))
    worker.handle(control("generation.end", 5, generation_id=8))
    assert not outputs(emitted)

    backend.release.set()
    assert worker.wait_for_idle(2)
    assert [message["generation_id"] for message in outputs(emitted)] == [8]
    assert emitted[-1]["type"] == "generation.completed"


@pytest.mark.parametrize(
    ("bad_frame", "error_text"),
    [
        (frame(0, sample_rate=16_000), "48 kHz"),
        (frame(0, samples=(0.25,) * 959), "20 ms"),
        (frame(0, samples=(1.01,) * 960), "normalized"),
    ],
)
def test_rejects_pcm_outside_the_profile_contract(
    bad_frame: dict[str, object], error_text: str
) -> None:
    worker = BeatriceWorker(DeterministicTestBackend(), lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    with pytest.raises(ValueError, match=error_text):
        worker.handle(bad_frame)


def test_rejects_more_than_500_ms_of_outstanding_audio() -> None:
    backend = BlockingBackend()
    worker = BeatriceWorker(backend, lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(25):
        worker.handle(frame(sequence))
    assert backend.started.wait(1)

    with pytest.raises(BufferError, match="500 ms"):
        worker.handle(frame(25))
    backend.release.set()


def test_enforces_monotonic_generation_rpc_sequence_and_timestamp() -> None:
    worker = BeatriceWorker(DeterministicTestBackend(), lambda message: None)
    worker.handle(control("generation.start", 2, generation_id=3))
    with pytest.raises(ValueError, match="rpc_id"):
        worker.handle(control("worker.health", 2))

    first = frame(1, generation_id=3)
    worker.handle(first)
    with pytest.raises(ValueError, match="sequence"):
        worker.handle(frame(1, generation_id=3))
    older = frame(2, generation_id=3)
    older["source_monotonic_ns"] = 0
    with pytest.raises(ValueError, match="timestamp"):
        worker.handle(older)

    worker.handle(control("generation.cancel", 3, generation_id=3))
    with pytest.raises(ValueError, match="generation_id"):
        worker.handle(control("generation.start", 4, generation_id=3))


class WrongLengthBackend(DeterministicTestBackend):
    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        return super().convert(samples, sample_rate)[:-1]


def test_invalid_backend_pcm_is_fatal() -> None:
    fatal = threading.Event()
    worker = BeatriceWorker(WrongLengthBackend(), lambda message: None, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=1))
    worker.handle(frame(0))
    worker.handle(control("generation.end", 2, generation_id=1))

    assert fatal.wait(1)
    assert worker.wait_for_idle(1)


class CancelThenFailBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        del samples, sample_rate
        self.started.set()
        assert self.release.wait(2)
        raise RuntimeError("injected failure after cancel")


def test_canceled_conversion_unexpected_failure_is_fatal() -> None:
    emitted: list[dict[str, object]] = []
    fatal = threading.Event()
    backend = CancelThenFailBackend()
    worker = BeatriceWorker(backend, emitted.append, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=7))
    worker.handle(frame(0, generation_id=7))
    worker.handle(control("generation.end", 2, generation_id=7))
    assert backend.started.wait(1)

    worker.handle(control("generation.cancel", 3, generation_id=7))
    assert emitted[-1]["type"] == "generation.canceled"
    backend.release.set()

    assert fatal.wait(1)
    assert worker.wait_for_idle(1)
    with pytest.raises(ValueError, match="generation cannot start"):
        worker.handle(control("generation.start", 4, generation_id=8))
