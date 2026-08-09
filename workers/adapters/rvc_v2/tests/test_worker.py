from __future__ import annotations

import base64
import struct
import time

from workers.adapters.rvc_v2.backend import (
    CooperativeConversionCanceled,
    DeterministicTestBackend,
)
from workers.adapters.rvc_v2.worker import RvcWorker
from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)


def control(message_type: str, rpc_id: int, **fields: object) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": rpc_id,
        **fields,
    }


def frame(sequence: int, *, generation_id: int = 1) -> dict[str, object]:
    samples = [0.25] * 320
    return {
        "type": "audio.push",
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "generation_id": generation_id,
        "sequence": sequence,
        "sample_rate": 16_000,
        "channels": 1,
        "samples_per_channel": len(samples),
        "source_monotonic_ns": sequence * 20_000_000,
        "pcm_f32le_base64": base64.b64encode(
            struct.pack(f"<{len(samples)}f", *samples)
        ).decode("ascii"),
    }


def test_codec_accepts_adapter_messages() -> None:
    message = frame(0)
    assert decode_message(encode_message(message)) == message


def test_generation_transforms_and_preserves_frame_identity() -> None:
    emitted: list[dict[str, object]] = []
    worker = RvcWorker(DeterministicTestBackend(), emitted.append)
    worker.handle(control("generation.start", 1, generation_id=1))
    for sequence in range(4):
        worker.handle(frame(sequence))
    worker.handle(control("generation.end", 2, generation_id=1))
    assert worker.wait_for_idle(2)

    outputs = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["sequence"] for item in outputs] == [0, 1, 2, 3]
    assert [item["source_monotonic_ns"] for item in outputs] == [
        0,
        20_000_000,
        40_000_000,
        60_000_000,
    ]
    decoded = struct.unpack(
        "<320f", base64.b64decode(str(outputs[0]["pcm_f32le_base64"]))
    )
    assert decoded == (-0.125,) * 320
    assert emitted[-1]["type"] == "generation.completed"


class BlockingBackend(DeterministicTestBackend):
    def __init__(self) -> None:
        super().__init__()
        import threading

        self.started = threading.Event()
        self.release = threading.Event()

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        self.started.set()
        assert self.release.wait(2)
        return super().convert(samples, sample_rate)


def test_cancel_acknowledges_during_inference_and_drops_stale_output() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = RvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)

    started = time.monotonic()
    worker.handle(control("generation.cancel", 2, generation_id=7))
    assert time.monotonic() - started < 0.1
    assert emitted[-1]["type"] == "generation.canceled"
    backend.release.set()
    time.sleep(0.05)
    assert not any(item["type"] == "audio.output" for item in emitted)


def test_double_buffer_accepts_two_batches_and_rejects_51st_resident_frame() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = RvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)
    for sequence in range(25, 50):
        worker.handle(frame(sequence, generation_id=7))

    worker.handle(control("worker.health", 2))
    assert emitted[-1]["queue_depth_frames"] == 50
    assert emitted[-1]["capacity_frames"] == 50
    try:
        worker.handle(frame(50, generation_id=7))
    except BufferError as error:
        assert "capacity" in str(error)
    else:
        raise AssertionError("51st resident frame was accepted")

    worker.handle(control("generation.end", 3, generation_id=7))
    backend.release.set()
    assert worker.wait_for_idle(2)
    outputs = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["sequence"] for item in outputs] == list(range(50))
    assert emitted[-1]["type"] == "generation.completed"


def test_end_drains_a_partial_tail_after_a_full_inference_batch() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = RvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)
    worker.handle(frame(25, generation_id=7))
    worker.handle(control("generation.end", 2, generation_id=7))

    backend.release.set()
    assert worker.wait_for_idle(2)
    outputs = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["sequence"] for item in outputs] == list(range(26))
    assert emitted[-1]["type"] == "generation.completed"


def test_new_generation_waits_for_canceled_inference_capacity() -> None:
    emitted: list[dict[str, object]] = []
    backend = BlockingBackend()
    worker = RvcWorker(backend, emitted.append)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)

    worker.handle(control("generation.cancel", 2, generation_id=7))
    worker.handle(control("generation.start", 3, generation_id=8))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=8))
    worker.handle(control("worker.health", 4))
    assert emitted[-1]["queue_depth_frames"] == 50
    try:
        worker.handle(frame(25, generation_id=8))
    except BufferError as error:
        assert "capacity" in str(error)
    else:
        raise AssertionError("new generation exceeded remaining capacity")

    backend.release.set()
    time.sleep(0.05)
    worker.handle(control("generation.end", 5, generation_id=8))
    assert worker.wait_for_idle(2)
    outputs = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["generation_id"] for item in outputs] == [8] * 25
    assert emitted[-1]["type"] == "generation.completed"


class FailingBackend(DeterministicTestBackend):
    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        del samples, sample_rate
        raise RuntimeError("injected conversion failure")


def test_active_conversion_failure_invokes_fatal_callback() -> None:
    import threading

    fatal = threading.Event()
    worker = RvcWorker(FailingBackend(), lambda message: None, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=1))
    worker.handle(frame(0))
    worker.handle(control("generation.end", 2, generation_id=1))

    assert fatal.wait(1)
    assert worker.wait_for_idle(1)


class BlockingFailureBackend(BlockingBackend):
    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        self.started.set()
        assert self.release.wait(2)
        raise RuntimeError("injected stale conversion failure")


def test_canceled_conversion_unexpected_failure_is_fatal() -> None:
    import threading

    fatal = threading.Event()
    backend = BlockingFailureBackend()
    worker = RvcWorker(backend, lambda message: None, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)
    worker.handle(control("generation.cancel", 2, generation_id=7))

    backend.release.set()
    assert fatal.wait(1)


class OneShotCooperativeCancelBackend(BlockingBackend):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            assert self.release.wait(2)
            raise CooperativeConversionCanceled
        return DeterministicTestBackend.convert(self, samples, sample_rate)


def test_explicit_cooperative_cancel_allows_next_generation() -> None:
    import threading

    emitted: list[dict[str, object]] = []
    fatal = threading.Event()
    backend = OneShotCooperativeCancelBackend()
    worker = RvcWorker(backend, emitted.append, fatal=fatal.set)
    worker.handle(control("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence, generation_id=7))
    assert backend.started.wait(1)
    worker.handle(control("generation.cancel", 2, generation_id=7))
    worker.handle(control("generation.start", 3, generation_id=8))

    backend.release.set()
    time.sleep(0.05)
    worker.handle(frame(0, generation_id=8))
    worker.handle(control("generation.end", 4, generation_id=8))
    assert worker.wait_for_idle(2)
    assert not fatal.is_set()
    outputs = [item for item in emitted if item["type"] == "audio.output"]
    assert [item["generation_id"] for item in outputs] == [8]


def test_rejects_non_monotonic_sequence() -> None:
    worker = RvcWorker(DeterministicTestBackend(), lambda message: None)
    worker.handle(control("generation.start", 1, generation_id=1))
    worker.handle(frame(1))
    try:
        worker.handle(frame(1))
    except ValueError as error:
        assert "sequence" in str(error)
    else:
        raise AssertionError("duplicate sequence was accepted")
