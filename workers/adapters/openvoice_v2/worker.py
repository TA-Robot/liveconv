from __future__ import annotations

import base64
import contextlib
import os
import struct
import sys
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol

from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

from .engine import EngineConfiguration, OpenVoiceV2Engine

IMPLEMENTATION_REVISION = "openvoice-v2-offline-adapter-v4"
CAPACITY_FRAMES = 25
MINIMUM_FRAMES = 3


class BinaryOutput(Protocol):
    def write(self, value: bytes) -> object: ...

    def flush(self) -> object: ...


class ProtocolOutput:
    """Unbuffered owner of the duplicated, pre-redirection protocol FD."""

    def __init__(self, file_descriptor: int) -> None:
        self._file_descriptor = file_descriptor
        self._lock = threading.Lock()
        self._closed = False

    def write(self, value: bytes) -> None:
        view = memoryview(value)
        with self._lock:
            if self._closed:
                raise ValueError("protocol output is closed")
            while view:
                try:
                    written = os.write(self._file_descriptor, view)
                except InterruptedError:
                    continue
                if written <= 0:
                    raise OSError("protocol output write made no progress")
                view = view[written:]

    def flush(self) -> None:
        return None

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                os.close(self._file_descriptor)
                self._closed = True


def isolate_protocol_stdout() -> ProtocolOutput:
    """Preserve protocol stdout, then make ordinary process FD 1 a sink."""

    sys.stdout.flush()
    protocol_fd = os.dup(1)
    os.set_inheritable(protocol_fd, False)
    sink_fd = os.open(os.devnull, os.O_WRONLY | os.O_CLOEXEC)
    try:
        os.dup2(sink_fd, 1, inheritable=False)
    except Exception:
        os.close(protocol_fd)
        raise
    finally:
        os.close(sink_fd)
    return ProtocolOutput(protocol_fd)


@dataclass(slots=True)
class Generation:
    generation_id: int
    frames: list[dict[str, object]] = field(default_factory=list)
    canceled: bool = False
    ended: bool = False


class OfflineWorker:
    def __init__(
        self,
        engine: OpenVoiceV2Engine | None,
        protocol_output: BinaryOutput,
        *,
        configuration_hash: str | None = None,
        engine_factory: Callable[[], OpenVoiceV2Engine] | None = None,
    ) -> None:
        if engine is None and (configuration_hash is None or engine_factory is None):
            raise ValueError("lazy worker initialization requires a factory and hash")
        self.engine = engine
        self._configuration_hash = (
            engine.configuration_hash if engine is not None else configuration_hash
        )
        assert self._configuration_hash is not None
        self._engine_factory = engine_factory
        self._protocol_output = protocol_output
        self.active: Generation | None = None
        self._last_generation_id: int | None = None
        self._future: Future[None] | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="openvoice"
        )
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = False
        self._hello_received = False

    def emit(self, message: dict[str, object]) -> None:
        with self._write_lock:
            self._protocol_output.write(encode_message(message))
            self._protocol_output.flush()

    @staticmethod
    def control(
        message_type: str, request: dict[str, object], **fields: object
    ) -> dict[str, object]:
        return {
            "type": message_type,
            "worker_protocol_version": WORKER_PROTOCOL_VERSION,
            "rpc_id": request["rpc_id"],
            **fields,
        }

    def error(
        self,
        request: dict[str, object],
        code: str,
        message: str,
        *,
        recoverable: bool,
    ) -> None:
        self.emit(
            self.control(
                "worker.error",
                request,
                code=code,
                message=message,
                recoverable=recoverable,
            )
        )

    def handle(self, message: dict[str, object]) -> bool:
        message_type = str(message["type"])
        if message_type == "worker.hello":
            if self._hello_received or self._closed:
                self.error(
                    message,
                    "INVALID_STATE",
                    "worker hello is not valid in the current state",
                    recoverable=False,
                )
                return True
            if message["configuration_hash"] != self._configuration_hash:
                self.error(
                    message,
                    "MODEL_UNAVAILABLE",
                    "OpenVoice configuration identity mismatch",
                    recoverable=False,
                )
                self._closed = True
                self._executor.shutdown(wait=False, cancel_futures=True)
                return False
            if self.engine is None:
                assert self._engine_factory is not None
                try:
                    self.engine = self._engine_factory()
                except Exception as error:
                    self.error(
                        message,
                        "MODEL_UNAVAILABLE",
                        "OpenVoice initialization failed: "
                        f"{_initialization_failure_category(error)}",
                        recoverable=False,
                    )
                    self._closed = True
                    self._executor.shutdown(wait=False, cancel_futures=True)
                    return False
                if self.engine.configuration_hash != self._configuration_hash:
                    self.error(
                        message,
                        "MODEL_UNAVAILABLE",
                        "OpenVoice configuration identity mismatch",
                        recoverable=False,
                    )
                    self._closed = True
                    self._executor.shutdown(wait=False, cancel_futures=True)
                    return False
            self._hello_received = True
            assert self.engine is not None
            self.emit(
                self.control(
                    "worker.ready",
                    message,
                    profile_id=message["profile_id"],
                    pipeline_id=message["pipeline_id"],
                    implementation_revision=(
                        f"{IMPLEMENTATION_REVISION}+sha256:"
                        f"{self.engine.implementation_sha256}"
                    ),
                    weight_revision=self.engine.weight_revision,
                    configuration_hash=self.engine.configuration_hash,
                )
            )
        elif not self._hello_received or self._closed:
            raise ValueError("worker is not ready")
        elif message_type == "generation.start":
            with self._state_lock:
                if self.active is not None or (
                    self._future is not None and not self._future.done()
                ):
                    self.error(
                        message,
                        "MODEL_UNAVAILABLE",
                        "offline converter is busy",
                        recoverable=True,
                    )
                    return True
                generation_id = int(message["generation_id"])
                if (
                    self._last_generation_id is not None
                    and generation_id <= self._last_generation_id
                ):
                    self.error(
                        message,
                        "INVALID_STATE",
                        "generation_id must increase",
                        recoverable=False,
                    )
                    return True
                self.active = Generation(generation_id)
                self._last_generation_id = generation_id
            self.emit(
                self.control(
                    "generation.started",
                    message,
                    generation_id=message["generation_id"],
                )
            )
        elif message_type == "audio.push":
            self._push(message)
        elif message_type == "generation.end":
            self._end(message)
        elif message_type == "generation.cancel":
            self._cancel(message)
        elif message_type == "worker.health":
            with self._state_lock:
                active = self.active
                depth = len(active.frames) if active is not None else 0
                busy = self._future is not None and not self._future.done()
            self.emit(
                self.control(
                    "worker.health.result",
                    message,
                    ready=not self._closed and not busy,
                    active_generation_id=(
                        active.generation_id if active is not None else None
                    ),
                    queue_depth_frames=depth,
                    capacity_frames=CAPACITY_FRAMES,
                )
            )
        elif message_type == "worker.close":
            with self._state_lock:
                self._closed = True
                if self.active is not None:
                    self.active.canceled = True
                    self.active = None
            self.emit(self.control("worker.closed", message))
            self._executor.shutdown(wait=False, cancel_futures=True)
            return False
        return True

    def _push(self, message: dict[str, object]) -> None:
        with self._state_lock:
            active = self.active
            if active is None or active.generation_id != message["generation_id"]:
                raise ValueError("audio has no matching active generation")
            if active.ended:
                raise ValueError("audio is forbidden after generation.end")
            if len(active.frames) >= CAPACITY_FRAMES:
                raise ValueError("offline input exceeds the 500 ms worker budget")
            sample_rate = int(message["sample_rate"])
            if (
                sample_rate % 50
                or int(message["samples_per_channel"]) != sample_rate // 50
            ):
                raise ValueError("audio must contain one 20 ms frame")
            if active.frames:
                previous = active.frames[-1]
                if int(message["sequence"]) <= int(previous["sequence"]):
                    raise ValueError("audio sequence must increase")
                if int(message["source_monotonic_ns"]) < int(
                    previous["source_monotonic_ns"]
                ):
                    raise ValueError("audio timestamp must not decrease")
                for field in ("sample_rate", "channels", "samples_per_channel"):
                    if message[field] != previous[field]:
                        raise ValueError(f"audio changed {field}")
            active.frames.append(message)

    def _end(self, message: dict[str, object]) -> None:
        with self._state_lock:
            generation = self.active
            if (
                generation is None
                or generation.generation_id != message["generation_id"]
                or generation.ended
            ):
                raise ValueError("end has no matching active generation")
            generation.ended = True
            if not generation.frames:
                self.active = None
                self.emit(
                    self.control(
                        "generation.completed",
                        message,
                        generation_id=message["generation_id"],
                    )
                )
                return
            if len(generation.frames) < MINIMUM_FRAMES:
                self.active = None
                self.error(
                    message,
                    "INVALID_STATE",
                    "OpenVoice requires at least 60 ms of source audio",
                    recoverable=True,
                )
                return
            self._future = self._executor.submit(self._convert, generation, message)

    def _convert(self, generation: Generation, end_message: dict[str, object]) -> None:
        try:
            assert self.engine is not None
            first = generation.frames[0]
            raw = b"".join(
                base64.b64decode(str(frame["pcm_f32le_base64"]), validate=True)
                for frame in generation.frames
            )
            samples = struct.unpack(f"<{len(raw) // 4}f", raw)
            output = self.engine.convert(samples, int(first["sample_rate"]))
            offset = 0
            for frame in generation.frames:
                count = int(frame["samples_per_channel"])
                chunk = output[offset : offset + count]
                offset += count
                with self._state_lock:
                    if generation.canceled or self._closed:
                        return
                    encoded = base64.b64encode(
                        struct.pack(f"<{count}f", *chunk)
                    ).decode("ascii")
                    self.emit(
                        {
                            **frame,
                            "type": "audio.output",
                            "pcm_f32le_base64": encoded,
                        }
                    )
            with self._state_lock:
                if generation.canceled or self._closed:
                    return
                self.active = None
                self.emit(
                    self.control(
                        "generation.completed",
                        end_message,
                        generation_id=generation.generation_id,
                    )
                )
        except Exception:
            with self._state_lock:
                if generation.canceled or self._closed:
                    return
                self.active = None
                self.error(
                    end_message,
                    "WORKER_CRASH",
                    "OpenVoice conversion failed",
                    recoverable=True,
                )

    def _cancel(self, message: dict[str, object]) -> None:
        with self._state_lock:
            generation = self.active
            if (
                generation is None
                or generation.generation_id != message["generation_id"]
            ):
                self.error(
                    message,
                    "INVALID_STATE",
                    "generation is not active",
                    recoverable=False,
                )
                return
            generation.canceled = True
            self.active = None
            self.emit(
                self.control(
                    "generation.canceled",
                    message,
                    generation_id=message["generation_id"],
                )
            )


def run() -> int:
    protocol_output = isolate_protocol_stdout()
    try:
        try:
            configuration = EngineConfiguration.from_environment()
        except Exception:
            return 2
        worker = OfflineWorker(
            None,
            protocol_output,
            configuration_hash=configuration.configuration_hash,
            engine_factory=OpenVoiceV2Engine.from_environment,
        )
        for line in sys.stdin.buffer:
            try:
                message = decode_message(line)
                if not worker.handle(message):
                    return 0
            except Exception:
                return 2
        return 0
    finally:
        protocol_output.close()


def _initialization_failure_category(error: Exception) -> str:
    if isinstance(error, AssertionError):
        return "assertion"
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "import"
    if isinstance(error, OSError):
        return "os"
    if isinstance(error, (RuntimeError, ValueError)):
        return "runtime"
    return "unexpected"


def main() -> int:
    with contextlib.suppress(KeyboardInterrupt):
        return run()
    return os.EX_OK


if __name__ == "__main__":
    raise SystemExit(main())
