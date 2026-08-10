from __future__ import annotations

import base64
import struct
import threading
import time

import pytest

from workers.adapters.meanvc2.backend import (
    CAPACITY_FRAMES,
    FRAME_SAMPLES,
    INPUT_SAMPLE_RATE,
    DeterministicTestBackend,
)
from workers.adapters.meanvc2.worker import Meanvc2Worker
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
    samples: tuple[float, ...] = (0.2,) * FRAME_SAMPLES,
) -> dict[str, object]:
    return {
        "type": "audio.push",
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "generation_id": generation_id,
        "sequence": sequence,
        "sample_rate": INPUT_SAMPLE_RATE,
        "channels": 1,
        "samples_per_channel": len(samples),
        "source_monotonic_ns": sequence * 20_000_000,
        "pcm_f32le_base64": base64.b64encode(
            struct.pack(f"<{len(samples)}f", *samples)
        ).decode("ascii"),
    }


def outputs(emitted: list[dict[str, object]]) -> list[dict[str, object]]:
    return [message for message in emitted if message["type"] == "audio.output"]


def wait_for_idle(worker: Meanvc2Worker) -> None:
    assert worker.wait_for_idle(2)


def test_streams_full_batches_and_drains_partial_end_in_order() -> None:
    emitted: list[dict[str, object]] = []
    worker = Meanvc2Worker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=4))
    for sequence in range(10):
        worker.handle(frame(sequence, generation_id=4))
    worker.handle(control("generation.end", 2, generation_id=4))
    wait_for_idle(worker)

    converted = outputs(emitted)
    assert [message["sequence"] for message in converted] == list(range(10))
    assert [message["source_monotonic_ns"] for message in converted] == [
        index * 20_000_000 for index in range(10)
    ]
    decoded = struct.unpack(
        f"<{FRAME_SAMPLES}f",
        base64.b64decode(str(converted[0]["pcm_f32le_base64"])),
    )
    assert decoded == pytest.approx((-0.1,) * FRAME_SAMPLES)
    assert emitted[-1]["type"] == "generation.completed"


class LookaheadBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        self.delayed: tuple[float, ...] = ()

    def process_batch(self, samples, sample_rate, *, final):
        converted = super().process_batch(samples, sample_rate, final=final)
        if not final:
            split = 2 * FRAME_SAMPLES
            self.delayed = converted[-split:]
            return converted[:-split]
        return self.delayed + converted


def test_lookahead_output_releases_credit_then_finishes_every_frame() -> None:
    emitted: list[dict[str, object]] = []
    worker = Meanvc2Worker(LookaheadBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(8):
        worker.handle(frame(sequence))
    deadline = time.monotonic() + 1
    while len(outputs(emitted)) < 6 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert len(outputs(emitted)) == 6

    worker.handle(control("generation.end", 2, generation_id=1))
    wait_for_idle(worker)
    assert [message["sequence"] for message in outputs(emitted)] == list(range(8))


class BlockingBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.starts = 0

    def start_generation(self) -> None:
        self.starts += 1

    def process_batch(self, samples, sample_rate, *, final):
        self.started.set()
        assert self.release.wait(2)
        return super().process_batch(samples, sample_rate, final=final)


def test_cancel_is_prompt_and_suppresses_stale_inference() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = Meanvc2Worker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(8):
        worker.handle(frame(sequence))
    assert backend.started.wait(1)

    started = time.monotonic()
    worker.handle(control("generation.cancel", 2, generation_id=1))
    assert time.monotonic() - started < 0.1
    worker.handle(control("generation.start", 3, generation_id=2))
    worker.handle(frame(0, generation_id=2))
    worker.handle(control("generation.end", 4, generation_id=2))
    backend.release.set()
    wait_for_idle(worker)

    assert [message["generation_id"] for message in outputs(emitted)] == [2]
    assert backend.starts >= 2
    assert not any(
        message["type"] == "generation.completed" and message["generation_id"] == 1
        for message in emitted
    )


def test_queue_is_bounded_to_500_ms() -> None:
    backend = BlockingBackend()
    worker = Meanvc2Worker(backend, lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(CAPACITY_FRAMES):
        worker.handle(frame(sequence))
    assert backend.started.wait(1)
    with pytest.raises(BufferError, match="500 ms"):
        worker.handle(frame(CAPACITY_FRAMES))
    worker.handle(control("generation.cancel", 2, generation_id=1))
    backend.release.set()


@pytest.mark.parametrize(
    ("bad_frame", "message"),
    [
        ({**frame(0), "sample_rate": 16_000}, "48 kHz"),
        (frame(0, samples=(0.2,) * (FRAME_SAMPLES - 1)), "20 ms"),
        (frame(0, samples=(1.1,) * FRAME_SAMPLES), "normalized"),
    ],
)
def test_rejects_invalid_pcm(bad_frame: dict[str, object], message: str) -> None:
    worker = Meanvc2Worker(DeterministicTestBackend(), lambda value: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    with pytest.raises(ValueError, match=message):
        worker.handle(bad_frame)
