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
    CURRENT_MS,
    FRAME_MS,
    FRAME_SAMPLES,
    FUTURE_MS,
    HISTORY_MS,
    INPUT_SAMPLE_RATE,
    SMOOTH_MS,
    WINDOW_MS,
    ConversionBackend,
    DeterministicTestBackend,
    OfficialXvcBackend,
    WindowResult,
    XvcConfiguration,
)
from .network_isolation import deny_non_unix_sockets

CAPACITY_FRAMES = 500 // FRAME_MS
CURRENT_FRAMES = CURRENT_MS // FRAME_MS
LOOKAHEAD_FRAMES = (SMOOTH_MS + FUTURE_MS) // FRAME_MS
HISTORY_FRAMES = HISTORY_MS // FRAME_MS
WINDOW_FRAMES = WINDOW_MS // FRAME_MS


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


class XvcWorker:
    """Strict worker-v1 lifecycle for bounded official X-VC windows."""

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
        self._history: list[_QueuedFrame] = []
        self._smoothing_tail: object | None = None
        self._inference_epoch: int | None = None
        self._inference_frame_count = 0
        self._ended = False
        self._last_sequence: int | None = None
        self._last_timestamp: int | None = None
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
                self._emit_locked(
                    _control(
                        "worker.health.result",
                        message,
                        ready=not self._closed,
                        active_generation_id=self._active_generation_id,
                        queue_depth_frames=len(self._pending),
                        capacity_frames=CAPACITY_FRAMES,
                    )
                )
            elif message_type == "worker.close":
                self._closed = True
                self._generation_epoch += 1
                self._active_generation_id = None
                self._pending.clear()
                self._history.clear()
                self._smoothing_tail = None
                self._ended = False
                self._end_request = None
                self._idle.set()
                self._emit_locked(_control("worker.closed", message))
                if self._inference_epoch is None:
                    self._backend.close()
                return False
            else:
                raise ValueError("unexpected worker-v1 message type")
        return True

    def _emit_locked(self, message: Mapping[str, object]) -> None:
        self._emit_callback(message)

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
        self._history.clear()
        self._smoothing_tail = None
        self._ended = False
        self._last_sequence = None
        self._last_timestamp = None
        self._idle.clear()
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
            raise ValueError("audio sequence must strictly increase")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("audio timestamp must not decrease")
        if len(self._pending) >= CAPACITY_FRAMES:
            raise BufferError("X-VC pending queue reached its 500 ms limit")

        frame = self._decode_frame(message)
        self._last_sequence = sequence
        self._last_timestamp = timestamp
        self._pending.append(frame)
        self._schedule_if_ready()

    @staticmethod
    def _decode_frame(message: dict[str, object]) -> _QueuedFrame:
        if int(message["sample_rate"]) != INPUT_SAMPLE_RATE:
            raise ValueError("X-VC worker requires 48 kHz PCM")
        if int(message["channels"]) != 1:
            raise ValueError("X-VC worker requires mono PCM")
        if int(message["samples_per_channel"]) != FRAME_SAMPLES:
            raise ValueError("X-VC worker requires one 20 ms PCM frame")
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
        self._history.clear()
        self._smoothing_tail = None
        self._ended = False
        self._end_request = None
        self._idle.set()
        self._emit_locked(
            _control("generation.canceled", message, generation_id=generation_id)
        )

    def _schedule_if_ready(self) -> None:
        if self._inference_epoch is not None or self._active_generation_id is None:
            return
        required = CURRENT_FRAMES + LOOKAHEAD_FRAMES
        if len(self._pending) < required and not self._ended:
            return
        if not self._pending:
            self._complete_if_drained()
            return

        current_count = min(CURRENT_FRAMES, len(self._pending))
        source_frames = self._pending[:required]
        current_frames = tuple(self._pending[:current_count])
        window_samples = self._build_window(source_frames)
        epoch = self._generation_epoch
        prior_tail = self._smoothing_tail
        self._inference_epoch = epoch
        self._inference_frame_count = current_count
        thread = threading.Thread(
            target=self._convert_window,
            args=(epoch, current_frames, window_samples, prior_tail),
            name="liveconv-x-vc-inference",
            daemon=True,
        )
        thread.start()

    def _build_window(self, source_frames: Sequence[_QueuedFrame]) -> list[float]:
        history = self._history[-HISTORY_FRAMES:]
        left_padding = HISTORY_FRAMES - len(history)
        right_padding = CURRENT_FRAMES + LOOKAHEAD_FRAMES - len(source_frames)
        samples = [0.0] * (left_padding * FRAME_SAMPLES)
        for frame in history:
            samples.extend(frame.samples)
        for frame in source_frames:
            samples.extend(frame.samples)
        samples.extend([0.0] * (right_padding * FRAME_SAMPLES))
        if len(samples) != WINDOW_FRAMES * FRAME_SAMPLES:
            raise RuntimeError("X-VC window assembly violated its bound")
        return samples

    def _convert_window(
        self,
        epoch: int,
        current_frames: tuple[_QueuedFrame, ...],
        window_samples: Sequence[float],
        prior_tail: object | None,
    ) -> None:
        try:
            result = self._backend.convert_window(
                window_samples,
                INPUT_SAMPLE_RATE,
                prior_tail,
            )
            outputs = self._build_outputs(
                current_frames,
                result,
            )
        except Exception:
            fatal = False
            with self._lock:
                self._finish_inference(epoch)
                if (
                    epoch == self._generation_epoch
                    and self._active_generation_id is not None
                ):
                    self._invalidate_active_generation(close=True)
                    fatal = True
                else:
                    self._schedule_if_ready()
            if fatal and self._fatal_callback is not None:
                self._fatal_callback()
            return

        with self._lock:
            self._finish_inference(epoch)
            if epoch != self._generation_epoch or self._active_generation_id is None:
                self._schedule_if_ready()
                return
            current_count = len(current_frames)
            if tuple(self._pending[:current_count]) != current_frames:
                self._invalidate_active_generation(close=True)
                if self._fatal_callback is not None:
                    self._fatal_callback()
                return
            completed_frames = self._pending[:current_count]
            del self._pending[:current_count]
            self._history.extend(completed_frames)
            del self._history[:-HISTORY_FRAMES]
            self._smoothing_tail = result.tail
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
        self._history.clear()
        self._smoothing_tail = None
        self._ended = False
        self._end_request = None
        self._closed = close
        self._idle.set()

    @staticmethod
    def _build_outputs(
        frames: Sequence[_QueuedFrame], result: WindowResult
    ) -> list[dict[str, object]]:
        expected = CURRENT_FRAMES * FRAME_SAMPLES
        values = tuple(float(value) for value in result.samples)
        if len(values) != expected:
            raise ValueError("X-VC returned the wrong current-window PCM length")
        required = len(frames) * FRAME_SAMPLES
        values = values[:required]
        if any(not math.isfinite(value) or abs(value) > 1.0 for value in values):
            raise ValueError("X-VC returned invalid normalized PCM")

        outputs: list[dict[str, object]] = []
        for index, frame in enumerate(frames):
            offset = index * FRAME_SAMPLES
            chunk = values[offset : offset + FRAME_SAMPLES]
            encoded = base64.b64encode(
                struct.pack(f"<{FRAME_SAMPLES}f", *chunk)
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
        self._history.clear()
        self._smoothing_tail = None
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
            configuration = XvcConfiguration.from_environment()
            if hello["configuration_hash"] != configuration.configuration_hash:
                emitter(
                    _control(
                        "worker.error",
                        hello,
                        code="MODEL_UNAVAILABLE",
                        message="X-VC configuration identity mismatch",
                        recoverable=False,
                    )
                )
                return 2
            backend = OfficialXvcBackend(
                configuration,
                validate_configuration=False,
            )
        if hello["configuration_hash"] != backend.configuration_hash:
            emitter(
                _control(
                    "worker.error",
                    hello,
                    code="MODEL_UNAVAILABLE",
                    message="X-VC configuration identity mismatch",
                    recoverable=False,
                )
            )
            return 2
    except Exception:
        if "hello" in locals():
            emitter(
                _control(
                    "worker.error",
                    hello,
                    code="MODEL_UNAVAILABLE",
                    message="X-VC initialization failed",
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
    worker = XvcWorker(
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
    parser = argparse.ArgumentParser(description="X-VC worker-v1 adapter")
    parser.add_argument("--test-backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(test_backend=args.test_backend)


if __name__ == "__main__":
    raise SystemExit(main())
