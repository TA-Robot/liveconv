from __future__ import annotations

import argparse
import base64
import binascii
import math
import os
import struct
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

from .backend import (
    BeatriceConfiguration,
    ConversionBackend,
    DeterministicTestBackend,
    UpstreamBeatriceBackend,
)

_SAMPLE_RATE = 48_000
_FRAME_MS = 20
_FRAME_SAMPLES = _SAMPLE_RATE * _FRAME_MS // 1000
_CAPACITY_FRAMES = 500 // _FRAME_MS


def _control(
    message_type: str, request: Mapping[str, object], **fields: object
) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": request["rpc_id"],
        **fields,
    }


@dataclass(frozen=True, slots=True)
class _QueuedFrame:
    message: dict[str, object]
    samples: tuple[float, ...]


class BeatriceWorker:
    """Strict worker-v1 lifecycle around one Beatrice inference backend."""

    def __init__(
        self,
        backend: ConversionBackend,
        emit: Callable[[Mapping[str, object]], None],
        fatal: Callable[[], None] | None = None,
        *,
        initial_rpc_id: int | None = None,
    ) -> None:
        self._backend = backend
        self._emit_callback = emit
        self._fatal_callback = fatal
        self._lock = threading.RLock()
        self._active_generation_id: int | None = None
        self._last_generation_id: int | None = None
        self._last_rpc_id = initial_rpc_id
        self._generation_epoch = 0
        self._end_request: Mapping[str, object] | None = None
        self._pending: list[_QueuedFrame] = []
        self._inference_epoch: int | None = None
        self._inference_frame_count = 0
        self._ended = False
        self._last_sequence: int | None = None
        self._last_timestamp: int | None = None
        self._closed = False
        self._idle = threading.Event()
        self._idle.set()

    def _emit_locked(self, message: Mapping[str, object]) -> None:
        self._emit_callback(message)

    def handle(self, message: dict[str, object]) -> bool:
        message_type = str(message["type"])
        with self._lock:
            if message_type != "audio.push":
                self._observe_rpc(message)
            if message_type == "generation.start":
                self._start(message)
            elif message_type == "audio.push":
                self._push(message)
            elif message_type == "generation.end":
                self._end(message)
            elif message_type == "generation.cancel":
                self._cancel(message)
            elif message_type == "worker.health":
                self._emit_locked(
                    _control(
                        "worker.health.result",
                        message,
                        ready=not self._closed,
                        active_generation_id=self._active_generation_id,
                        queue_depth_frames=(len(self._pending) + self._active_inflight),
                        capacity_frames=_CAPACITY_FRAMES,
                    )
                )
            elif message_type == "worker.close":
                self._closed = True
                self._generation_epoch += 1
                self._active_generation_id = None
                self._pending.clear()
                self._ended = False
                self._end_request = None
                self._idle.set()
                self._emit_locked(_control("worker.closed", message))
                self._backend.close()
                return False
            else:
                raise ValueError("unexpected message type")
        return True

    def _observe_rpc(self, message: Mapping[str, object]) -> None:
        rpc_id = int(message["rpc_id"])
        if self._last_rpc_id is not None and rpc_id <= self._last_rpc_id:
            raise ValueError("rpc_id must strictly increase")
        self._last_rpc_id = rpc_id

    def _start(self, message: Mapping[str, object]) -> None:
        generation_id = int(message["generation_id"])
        if self._closed or self._active_generation_id is not None:
            raise ValueError("generation cannot start in the current state")
        if (
            self._last_generation_id is not None
            and generation_id <= self._last_generation_id
        ):
            raise ValueError("generation_id must strictly increase")
        self._generation_epoch += 1
        self._active_generation_id = generation_id
        self._last_generation_id = generation_id
        self._end_request = None
        self._pending.clear()
        self._ended = False
        self._last_sequence = None
        self._last_timestamp = None
        self._idle.clear()
        self._backend.reset()
        self._emit_locked(
            _control("generation.started", message, generation_id=generation_id)
        )

    def _push(self, message: dict[str, object]) -> None:
        generation_id = int(message["generation_id"])
        sequence = int(message["sequence"])
        timestamp = int(message["source_monotonic_ns"])
        if generation_id != self._active_generation_id or self._ended:
            raise ValueError("audio is not for an active writable generation")
        if self._last_sequence is not None and sequence <= self._last_sequence:
            raise ValueError("audio sequence must increase")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("audio timestamp must not decrease")
        if len(self._pending) + self._active_inflight >= _CAPACITY_FRAMES:
            raise BufferError("Beatrice pending queue reached its 500 ms limit")

        frame = self._decode_frame(message)
        self._last_sequence = sequence
        self._last_timestamp = timestamp
        self._pending.append(frame)
        self._schedule_if_ready()

    @property
    def _active_inflight(self) -> int:
        if self._inference_epoch != self._generation_epoch:
            return 0
        return self._inference_frame_count

    @staticmethod
    def _decode_frame(message: dict[str, object]) -> _QueuedFrame:
        if int(message["sample_rate"]) != _SAMPLE_RATE:
            raise ValueError("Beatrice worker requires 48 kHz PCM")
        if int(message["channels"]) != 1:
            raise ValueError("Beatrice worker requires mono PCM")
        if int(message["samples_per_channel"]) != _FRAME_SAMPLES:
            raise ValueError("Beatrice worker requires one 20 ms PCM frame")
        encoded = message["pcm_f32le_base64"]
        if not isinstance(encoded, str):
            raise ValueError("PCM must be base64 text")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("PCM is not valid base64") from error
        if len(raw) != _FRAME_SAMPLES * 4:
            raise ValueError("PCM byte length does not match its frame metadata")
        samples = struct.unpack(f"<{_FRAME_SAMPLES}f", raw)
        if any(not math.isfinite(value) or abs(value) > 1.0 for value in samples):
            raise ValueError("PCM must contain finite normalized float32 samples")
        return _QueuedFrame(message, samples)

    def _end(self, message: Mapping[str, object]) -> None:
        if int(message["generation_id"]) != self._active_generation_id or self._ended:
            raise ValueError("generation is not active")
        self._ended = True
        self._end_request = message
        self._schedule_if_ready()

    def _cancel(self, message: Mapping[str, object]) -> None:
        generation_id = int(message["generation_id"])
        if generation_id != self._active_generation_id:
            raise ValueError("generation is not active")
        self._generation_epoch += 1
        self._active_generation_id = None
        self._pending.clear()
        self._ended = False
        self._end_request = None
        self._idle.set()
        self._emit_locked(
            _control("generation.canceled", message, generation_id=generation_id)
        )

    def _schedule_if_ready(self) -> None:
        if self._inference_epoch is not None or self._active_generation_id is None:
            return
        if len(self._pending) < _CAPACITY_FRAMES and not self._ended:
            return
        if not self._pending:
            self._complete_if_drained()
            return
        frames = self._pending[:_CAPACITY_FRAMES]
        del self._pending[: len(frames)]
        epoch = self._generation_epoch
        self._inference_epoch = epoch
        self._inference_frame_count = len(frames)
        thread = threading.Thread(
            target=self._convert_batch,
            args=(epoch, frames),
            name="liveconv-beatrice-inference",
            daemon=True,
        )
        thread.start()

    def _convert_batch(self, epoch: int, frames: list[_QueuedFrame]) -> None:
        try:
            samples = [sample for frame in frames for sample in frame.samples]
            converted = self._backend.convert(samples, _SAMPLE_RATE)
            outputs = self._build_outputs(frames, converted)
        except Exception:
            # Beatrice exposes no cooperative-cancel exception. A backend failure
            # therefore invalidates this worker even after its generation was canceled.
            with self._lock:
                self._finish_inference(epoch)
                self._invalidate_active_generation(close=True)
            if self._fatal_callback is not None:
                self._fatal_callback()
            return

        with self._lock:
            self._finish_inference(epoch)
            if epoch != self._generation_epoch or self._active_generation_id is None:
                self._schedule_if_ready()
                return
            for output in outputs:
                self._emit_locked(output)
            self._schedule_if_ready()
            self._complete_if_drained()

    def _finish_inference(self, epoch: int) -> None:
        if self._inference_epoch == epoch:
            self._inference_epoch = None
            self._inference_frame_count = 0

    def _invalidate_active_generation(self, *, close: bool) -> None:
        self._generation_epoch += 1
        self._active_generation_id = None
        self._pending.clear()
        self._ended = False
        self._end_request = None
        self._closed = close
        self._idle.set()

    @staticmethod
    def _build_outputs(
        frames: Sequence[_QueuedFrame], converted: Sequence[float]
    ) -> list[dict[str, object]]:
        expected = len(frames) * _FRAME_SAMPLES
        values = [float(value) for value in converted]
        if len(values) != expected:
            raise ValueError("Beatrice returned the wrong PCM length")
        if any(not math.isfinite(value) or abs(value) > 1.0 for value in values):
            raise ValueError("Beatrice returned invalid normalized PCM")

        outputs: list[dict[str, object]] = []
        for index, frame in enumerate(frames):
            offset = index * _FRAME_SAMPLES
            chunk = values[offset : offset + _FRAME_SAMPLES]
            encoded = base64.b64encode(
                struct.pack(f"<{_FRAME_SAMPLES}f", *chunk)
            ).decode("ascii")
            outputs.append(
                {
                    **frame.message,
                    "type": "audio.output",
                    "pcm_f32le_base64": encoded,
                }
            )
        return outputs

    def _complete_if_drained(self) -> None:
        if (
            not self._ended
            or self._inference_epoch is not None
            or self._pending
            or self._active_generation_id is None
        ):
            return
        request = self._end_request
        assert request is not None
        generation_id = self._active_generation_id
        self._active_generation_id = None
        self._end_request = None
        self._ended = False
        self._idle.set()
        self._emit_locked(
            _control("generation.completed", request, generation_id=generation_id)
        )

    def wait_for_idle(self, timeout: float) -> bool:
        return self._idle.wait(timeout)


class _Emitter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream = sys.stdout.buffer

    def __call__(self, message: Mapping[str, object]) -> None:
        with self._lock:
            self._stream.write(encode_message(message))
            self._stream.flush()


def _load_backend(test_backend: bool) -> ConversionBackend:
    if test_backend:
        if os.environ.get("LIVECONV_ENABLE_TEST_BACKEND") != "1":
            raise ValueError("test backend is disabled")
        return DeterministicTestBackend()
    return UpstreamBeatriceBackend(BeatriceConfiguration.from_environment())


def run(*, test_backend: bool = False) -> int:
    emitter = _Emitter()
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return 2
    backend: ConversionBackend | None = None
    try:
        hello = decode_message(first_line)
        if hello["type"] != "worker.hello":
            return 2
        backend = _load_backend(test_backend)
        if hello["configuration_hash"] != backend.configuration_hash:
            raise ValueError("Beatrice configuration hash does not match worker.hello")
    except Exception:
        if "hello" in locals():
            emitter(
                _control(
                    "worker.error",
                    hello,
                    code="MODEL_UNAVAILABLE",
                    message="Beatrice initialization failed",
                    recoverable=False,
                )
            )
        return 2

    emitter(
        _control(
            "worker.ready",
            hello,
            profile_id=hello["profile_id"],
            pipeline_id=hello["pipeline_id"],
            implementation_revision=backend.implementation_revision,
            weight_revision=backend.weight_revision,
            configuration_hash=backend.configuration_hash,
        )
    )
    worker = BeatriceWorker(
        backend,
        emitter,
        fatal=lambda: os._exit(70),
        initial_rpc_id=int(hello["rpc_id"]),
    )
    try:
        for line in sys.stdin.buffer:
            try:
                message = decode_message(line)
                if not worker.handle(message):
                    return 0
            except (BufferError, ValueError):
                return 2
        return 0
    finally:
        backend.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Beatrice 2 worker-v1 adapter")
    parser.add_argument("--test-backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(test_backend=args.test_backend)


if __name__ == "__main__":
    raise SystemExit(main())
