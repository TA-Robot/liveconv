from __future__ import annotations

import argparse
import base64
import binascii
import os
import struct
import sys
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

from .backend import (
    CAPACITY_FRAMES,
    FRAME_SAMPLES,
    INFERENCE_FRAMES,
    INPUT_SAMPLE_RATE,
    ConversionBackend,
    DeterministicTestBackend,
    Meanvc2Configuration,
    OfficialMeanvc2Backend,
    validate_pcm,
)
from .network_isolation import deny_non_unix_sockets


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


class Meanvc2Worker:
    """Worker-v1 lifecycle with bounded 160 ms MeanVC2 inference batches."""

    def __init__(
        self,
        backend: ConversionBackend,
        emit: Callable[[Mapping[str, object]], None],
        fatal: Callable[[], None] | None = None,
        *,
        initial_rpc_id: int | None = None,
    ) -> None:
        self._backend = backend
        self._emit = emit
        self._fatal = fatal
        self._lock = threading.RLock()
        self._active_generation_id: int | None = None
        self._last_generation_id: int | None = None
        self._last_rpc_id = initial_rpc_id
        self._generation_epoch = 0
        self._pending: list[_QueuedFrame] = []
        self._accepted: deque[_QueuedFrame] = deque()
        self._output_samples: deque[float] = deque()
        self._ended = False
        self._end_request: Mapping[str, object] | None = None
        self._last_sequence: int | None = None
        self._last_timestamp: int | None = None
        self._inference_epoch: int | None = None
        self._reset_required = False
        self._closed = False
        self._idle = threading.Event()
        self._idle.set()

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
                self._emit(
                    _control(
                        "worker.health.result",
                        message,
                        ready=not self._closed,
                        active_generation_id=self._active_generation_id,
                        queue_depth_frames=len(self._accepted),
                        capacity_frames=CAPACITY_FRAMES,
                    )
                )
            elif message_type == "worker.close":
                self._closed = True
                self._generation_epoch += 1
                self._active_generation_id = None
                self._clear_generation()
                self._idle.set()
                self._emit(_control("worker.closed", message))
                if self._inference_epoch is None:
                    self._backend.close()
                return False
            else:
                raise ValueError("unexpected worker-v1 message type")
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
        self._clear_generation()
        self._last_sequence = None
        self._last_timestamp = None
        self._idle.clear()
        if self._inference_epoch is None:
            self._backend.start_generation()
        else:
            self._reset_required = True
        self._emit(_control("generation.started", message, generation_id=generation_id))

    def _push(self, message: dict[str, object]) -> None:
        generation_id = int(message["generation_id"])
        sequence = int(message["sequence"])
        timestamp = int(message["source_monotonic_ns"])
        if generation_id != self._active_generation_id or self._ended:
            raise ValueError("audio is not for an active writable generation")
        if self._last_sequence is not None and sequence <= self._last_sequence:
            raise ValueError("audio sequence must strictly increase")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("audio timestamp must not decrease")
        if len(self._accepted) >= CAPACITY_FRAMES:
            raise BufferError("MeanVC2 pending queue reached its 500 ms limit")
        frame = self._decode_frame(message)
        self._last_sequence = sequence
        self._last_timestamp = timestamp
        self._pending.append(frame)
        self._accepted.append(frame)
        self._schedule_if_ready()

    @staticmethod
    def _decode_frame(message: dict[str, object]) -> _QueuedFrame:
        if int(message["sample_rate"]) != INPUT_SAMPLE_RATE:
            raise ValueError("MeanVC2 worker requires 48 kHz PCM")
        if int(message["channels"]) != 1:
            raise ValueError("MeanVC2 worker requires mono PCM")
        if int(message["samples_per_channel"]) != FRAME_SAMPLES:
            raise ValueError("MeanVC2 worker requires one 20 ms PCM frame")
        encoded = message["pcm_f32le_base64"]
        if not isinstance(encoded, str):
            raise ValueError("PCM must be base64 text")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("PCM is not valid base64") from error
        if len(raw) != FRAME_SAMPLES * 4:
            raise ValueError("PCM byte length does not match frame metadata")
        samples = struct.unpack(f"<{FRAME_SAMPLES}f", raw)
        validate_pcm(samples)
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
        self._clear_generation()
        self._idle.set()
        self._emit(
            _control("generation.canceled", message, generation_id=generation_id)
        )

    def _clear_generation(self) -> None:
        self._pending.clear()
        self._accepted.clear()
        self._output_samples.clear()
        self._ended = False
        self._end_request = None

    def _schedule_if_ready(self) -> None:
        if self._inference_epoch is not None or self._active_generation_id is None:
            return
        if self._reset_required:
            self._backend.start_generation()
            self._reset_required = False
        if len(self._pending) >= INFERENCE_FRAMES:
            frames = tuple(self._pending[:INFERENCE_FRAMES])
            final = self._ended and len(self._pending) == INFERENCE_FRAMES
        elif self._ended:
            frames = tuple(self._pending)
            final = True
        else:
            return
        if not frames and not self._accepted:
            self._complete_if_drained()
            return
        samples = tuple(sample for frame in frames for sample in frame.samples)
        epoch = self._generation_epoch
        self._inference_epoch = epoch
        thread = threading.Thread(
            target=self._convert_batch,
            args=(epoch, frames, samples, final),
            name="liveconv-meanvc2-inference",
            daemon=True,
        )
        thread.start()

    def _convert_batch(
        self,
        epoch: int,
        frames: tuple[_QueuedFrame, ...],
        samples: Sequence[float],
        final: bool,
    ) -> None:
        try:
            output = self._backend.process_batch(
                samples, INPUT_SAMPLE_RATE, final=final
            )
            validate_pcm(output)
        except Exception:
            with self._lock:
                self._finish_inference(epoch)
                active_failure = (
                    epoch == self._generation_epoch
                    and self._active_generation_id is not None
                )
                if active_failure:
                    self._generation_epoch += 1
                    self._active_generation_id = None
                    self._clear_generation()
                    self._closed = True
                    self._idle.set()
                else:
                    self._reset_required = self._active_generation_id is not None
                    self._schedule_if_ready()
            if active_failure and self._fatal is not None:
                self._fatal()
            return

        with self._lock:
            self._finish_inference(epoch)
            if epoch != self._generation_epoch or self._active_generation_id is None:
                self._reset_required = self._active_generation_id is not None
                self._schedule_if_ready()
                return
            if tuple(self._pending[: len(frames)]) != frames:
                self._generation_epoch += 1
                self._active_generation_id = None
                self._clear_generation()
                self._closed = True
                self._idle.set()
                if self._fatal is not None:
                    self._fatal()
                return
            del self._pending[: len(frames)]
            self._output_samples.extend(float(value) for value in output)
            self._emit_available()
            if final and not self._pending:
                self._finish_output()
            self._schedule_if_ready()
            self._complete_if_drained()

    def _finish_inference(self, epoch: int) -> None:
        if self._inference_epoch == epoch:
            self._inference_epoch = None

    def _emit_available(self) -> None:
        while len(self._output_samples) >= FRAME_SAMPLES and self._accepted:
            samples = tuple(
                self._output_samples.popleft() for _ in range(FRAME_SAMPLES)
            )
            frame = self._accepted.popleft()
            encoded = base64.b64encode(
                struct.pack(f"<{FRAME_SAMPLES}f", *samples)
            ).decode("ascii")
            self._emit(
                {
                    **frame.message,
                    "type": "audio.output",
                    "pcm_f32le_base64": encoded,
                }
            )

    def _finish_output(self) -> None:
        required = len(self._accepted) * FRAME_SAMPLES
        if len(self._output_samples) > required:
            while len(self._output_samples) > required:
                self._output_samples.pop()
        elif len(self._output_samples) < required:
            missing = required - len(self._output_samples)
            start = self._output_samples[-1] if self._output_samples else 0.0
            self._output_samples.extend(
                start * (1.0 - (index + 1) / missing) for index in range(missing)
            )
        self._emit_available()

    def _complete_if_drained(self) -> None:
        if (
            not self._ended
            or self._inference_epoch is not None
            or self._pending
            or self._accepted
            or self._active_generation_id is None
        ):
            return
        request = self._end_request
        assert request is not None
        generation_id = self._active_generation_id
        self._active_generation_id = None
        self._clear_generation()
        self._idle.set()
        self._emit(
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


def _test_backend() -> DeterministicTestBackend:
    if os.environ.get("LIVECONV_ENABLE_TEST_BACKEND") != "1":
        raise ValueError("test backend is disabled")
    return DeterministicTestBackend()


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
        if test_backend:
            backend = _test_backend()
        else:
            configuration = Meanvc2Configuration.from_environment()
            if hello["configuration_hash"] != configuration.configuration_hash:
                emitter(
                    _control(
                        "worker.error",
                        hello,
                        code="MODEL_UNAVAILABLE",
                        message="MeanVC2 configuration identity mismatch",
                        recoverable=False,
                    )
                )
                return 2
            backend = OfficialMeanvc2Backend(configuration)
        if hello["configuration_hash"] != backend.configuration_hash:
            raise ValueError("MeanVC2 configuration identity mismatch")
    except Exception:
        if "hello" in locals():
            emitter(
                _control(
                    "worker.error",
                    hello,
                    code="MODEL_UNAVAILABLE",
                    message="MeanVC2 initialization failed",
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
    worker = Meanvc2Worker(
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
        if worker._inference_epoch is None:  # noqa: SLF001
            backend.close()


def main(argv: list[str] | None = None) -> int:
    deny_non_unix_sockets()
    parser = argparse.ArgumentParser(description="MeanVC2 worker-v1 adapter")
    parser.add_argument("--test-backend", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    return run(test_backend=arguments.test_backend)


if __name__ == "__main__":
    raise SystemExit(main())
