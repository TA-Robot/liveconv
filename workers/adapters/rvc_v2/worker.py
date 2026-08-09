from __future__ import annotations

import argparse
import base64
import math
import os
import struct
import sys
import threading
from collections.abc import Callable, Mapping, Sequence

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

from .backend import (
    INFERENCE_BATCH_FRAMES,
    RESIDENT_CAPACITY_FRAMES,
    TEST_CONFIGURATION_HASH,
    ConversionBackend,
    CooperativeConversionCanceled,
    DeterministicTestBackend,
    RvcConfiguration,
    UpstreamRvcBackend,
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


class RvcWorker:
    def __init__(
        self,
        backend: ConversionBackend,
        emit: Callable[[Mapping[str, object]], None],
        fatal: Callable[[], None] | None = None,
    ) -> None:
        self._backend = backend
        self._emit_callback = emit
        self._fatal_callback = fatal
        self._lock = threading.RLock()
        self._active_generation_id: int | None = None
        self._generation_epoch = 0
        self._start_request: Mapping[str, object] | None = None
        self._end_request: Mapping[str, object] | None = None
        self._pending: list[dict[str, object]] = []
        self._inference_epoch: int | None = None
        self._inference_frames = 0
        self._ended = False
        self._last_sequence: int | None = None
        self._last_timestamp: int | None = None
        self._closed = False
        self._idle = threading.Event()
        self._idle.set()

    def _emit_locked(self, message: Mapping[str, object]) -> None:
        self._emit_callback(message)

    def _occupied_frames(self) -> int:
        return self._inference_frames + len(self._pending)

    def handle(self, message: dict[str, object]) -> bool:
        message_type = str(message["type"])
        with self._lock:
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
                        queue_depth_frames=self._occupied_frames(),
                        capacity_frames=RESIDENT_CAPACITY_FRAMES,
                    )
                )
            elif message_type == "worker.close":
                self._closed = True
                self._generation_epoch += 1
                self._active_generation_id = None
                self._pending.clear()
                self._emit_locked(_control("worker.closed", message))
                self._backend.close()
                return False
            else:
                raise ValueError("unexpected message type")
        return True

    def _start(self, message: Mapping[str, object]) -> None:
        generation_id = int(message["generation_id"])
        if self._closed or self._active_generation_id is not None:
            raise ValueError("generation cannot start in the current state")
        self._generation_epoch += 1
        self._active_generation_id = generation_id
        self._start_request = message
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
        if self._occupied_frames() >= RESIDENT_CAPACITY_FRAMES:
            raise BufferError("RVC worker frame capacity is full")
        self._last_sequence = sequence
        self._last_timestamp = timestamp
        self._pending.append(message)
        self._schedule_if_ready()

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
        self._start_request = None
        self._idle.set()
        self._emit_locked(
            _control("generation.canceled", message, generation_id=generation_id)
        )

    def _schedule_if_ready(self) -> None:
        if self._inference_epoch is not None or self._active_generation_id is None:
            return
        if len(self._pending) < INFERENCE_BATCH_FRAMES and not self._ended:
            return
        if not self._pending:
            self._complete_if_drained()
            return
        frames = self._pending[:INFERENCE_BATCH_FRAMES]
        del self._pending[: len(frames)]
        epoch = self._generation_epoch
        self._inference_epoch = epoch
        self._inference_frames = len(frames)
        thread = threading.Thread(
            target=self._convert_batch,
            args=(epoch, frames),
            name="liveconv-rvc-inference",
            daemon=True,
        )
        thread.start()

    def _convert_batch(self, epoch: int, frames: list[dict[str, object]]) -> None:
        try:
            sample_rate = int(frames[0]["sample_rate"])
            samples: list[float] = []
            for frame in frames:
                if int(frame["sample_rate"]) != sample_rate:
                    raise ValueError("sample rate changed within a generation")
                raw = base64.b64decode(str(frame["pcm_f32le_base64"]), validate=True)
                count = int(frame["samples_per_channel"])
                samples.extend(struct.unpack(f"<{count}f", raw))
            converted = self._backend.convert(samples, sample_rate)
            outputs = self._build_outputs(frames, converted)
        except CooperativeConversionCanceled:
            self._conversion_failed(epoch, cooperative_cancel=True)
            return
        except Exception:
            self._conversion_failed(epoch, cooperative_cancel=False)
            return

        with self._lock:
            if self._inference_epoch == epoch:
                self._inference_epoch = None
                self._inference_frames = 0
            if epoch != self._generation_epoch or self._active_generation_id is None:
                self._schedule_if_ready()
                return
            for output in outputs:
                self._emit_locked(output)
            self._schedule_if_ready()
            self._complete_if_drained()

    def _conversion_failed(self, epoch: int, *, cooperative_cancel: bool) -> None:
        fatal = False
        with self._lock:
            if self._inference_epoch == epoch:
                self._inference_epoch = None
                self._inference_frames = 0
            generation_was_canceled = epoch != self._generation_epoch
            if cooperative_cancel and generation_was_canceled:
                self._schedule_if_ready()
                return
            self._generation_epoch += 1
            self._active_generation_id = None
            self._pending.clear()
            self._ended = False
            self._end_request = None
            self._start_request = None
            self._closed = True
            self._idle.set()
            fatal = True
        if fatal and self._fatal_callback is not None:
            self._fatal_callback()

    @staticmethod
    def _build_outputs(
        frames: Sequence[dict[str, object]], converted: Sequence[float]
    ) -> list[dict[str, object]]:
        expected = sum(int(frame["samples_per_channel"]) for frame in frames)
        values = [float(value) for value in converted]
        if not values or any(not math.isfinite(value) for value in values):
            raise ValueError("RVC returned invalid samples")
        if len(values) < expected:
            values.extend([0.0] * (expected - len(values)))
        elif len(values) > expected:
            del values[expected:]
        outputs: list[dict[str, object]] = []
        offset = 0
        for frame in frames:
            count = int(frame["samples_per_channel"])
            chunk = values[offset : offset + count]
            offset += count
            encoded = base64.b64encode(struct.pack(f"<{count}f", *chunk)).decode(
                "ascii"
            )
            outputs.append(
                {
                    **frame,
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
        self._start_request = None
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


def _load_backend(
    test_backend: bool, expected_configuration_hash: str
) -> ConversionBackend:
    if test_backend:
        if os.environ.get("LIVECONV_ENABLE_TEST_BACKEND") != "1":
            raise ValueError("test backend is disabled")
        if expected_configuration_hash != TEST_CONFIGURATION_HASH:
            raise ValueError("test backend configuration hash does not match")
        return DeterministicTestBackend()
    configuration = RvcConfiguration.from_environment()
    if expected_configuration_hash != configuration.configuration_hash:
        raise ValueError("RVC configuration hash does not match worker.hello")
    return UpstreamRvcBackend(configuration)


def run(*, test_backend: bool = False) -> int:
    emitter = _Emitter()
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return 2
    try:
        hello = decode_message(first_line)
        if hello["type"] != "worker.hello":
            return 2
        backend = _load_backend(test_backend, str(hello["configuration_hash"]))
    except Exception as error:
        print(
            f"RVC initialization failed: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        if "hello" in locals():
            emitter(
                _control(
                    "worker.error",
                    hello,
                    code="MODEL_UNAVAILABLE",
                    message="RVC initialization failed",
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
    worker = RvcWorker(backend, emitter, fatal=lambda: os._exit(70))
    for line in sys.stdin.buffer:
        try:
            message = decode_message(line)
            if not worker.handle(message):
                return 0
        except (BufferError, ValueError):
            return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    deny_non_unix_sockets()
    parser = argparse.ArgumentParser(description="RVC v2 worker-v1 adapter")
    parser.add_argument("--test-backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return run(test_backend=args.test_backend)


if __name__ == "__main__":
    raise SystemExit(main())
