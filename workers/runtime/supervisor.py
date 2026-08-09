from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import signal
import sys
import time
from collections import deque
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from .codec import (
    MAX_LINE_BYTES,
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)
from .errors import WorkerProtocolError, WorkerRuntimeError
from .models import (
    AudioFrame,
    GenerationResult,
    WorkerHealth,
    WorkerProfile,
    WorkerReady,
)

_T = TypeVar("_T")
_INSPECT_ARTIFACT_PROGRAM = "\n".join(
    (
        "import hashlib, json, pathlib, sys",
        "path = pathlib.Path(sys.argv[1]).resolve(strict=True)",
        "if not path.is_file(): raise SystemExit(2)",
        "digest = hashlib.sha256()",
        "with path.open('rb') as stream:",
        "    for chunk in iter(lambda: stream.read(1048576), b''):",
        "        digest.update(chunk)",
        "print(json.dumps({'path': str(path), 'sha256': digest.hexdigest()},"
        " separators=(',', ':')))",
    )
)


class MonotonicClock(Protocol):
    def now_ns(self) -> int: ...

    async def wait_until_ns(self, deadline_ns: int) -> None: ...


class _SystemClock:
    def now_ns(self) -> int:
        return time.monotonic_ns()

    async def wait_until_ns(self, deadline_ns: int) -> None:
        delay = max(0, deadline_ns - self.now_ns()) / 1_000_000_000
        await asyncio.sleep(delay)


@dataclass(slots=True)
class _PendingRpc:
    expected_type: str
    future: asyncio.Future[dict[str, object]]


class WorkerSupervisor:
    """Own one worker subprocess and enforce the private worker-v1 contract."""

    def __init__(
        self, profile: WorkerProfile, *, clock: MonotonicClock | None = None
    ) -> None:
        self._profile = profile
        self._clock = clock or _SystemClock()
        self._process: asyncio.subprocess.Process | None = None
        self._process_group_id: int | None = None
        self._epoch = 0
        self._failed_epochs: set[int] = set()
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._restart_task: asyncio.Task[WorkerReady] | None = None
        self._start_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._failure_lock = asyncio.Lock()
        self._pending: dict[int, _PendingRpc] = {}
        self._next_rpc_id = 1

        self._ready: WorkerReady | None = None
        self._available = False
        self._closing = False
        self._closed = False
        self._restart_exhausted = False
        self._restart_times_ns: deque[int] = deque()
        self._restart_count = 0

        self._active_generation_id: int | None = None
        self._last_generation_id: int | None = None
        self._accepted_frames: dict[int, AudioFrame] = {}
        self._canceled_generations: set[int] = set()
        self._first_accepted_ns: int | None = None
        self._pending_since_ns: int | None = None
        self._last_output_ns: int | None = None
        self._output_seen = False
        self._output_queue: asyncio.Queue[AudioFrame | WorkerRuntimeError] = (
            asyncio.Queue(maxsize=profile.input_capacity_frames + 1)
        )

    @property
    def available(self) -> bool:
        return self._available

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def process_group_id(self) -> int | None:
        return self._process_group_id

    @property
    def input_capacity_frames(self) -> int:
        return self._profile.input_capacity_frames

    @property
    def queued_input_frames(self) -> int:
        return len(self._accepted_frames)

    @property
    def restart_count(self) -> int:
        return self._restart_count

    async def start(self) -> WorkerReady:
        while True:
            restart_task = self._restart_task
            if restart_task is not None and not restart_task.done():
                return await asyncio.shield(restart_task)
            async with self._start_lock:
                if self._closing or self._closed:
                    raise self._error("INVALID_STATE", "worker supervisor is closed")
                if self._ready is not None and self._available:
                    return self._ready
                if self._restart_exhausted:
                    raise self._error(
                        "MODEL_UNAVAILABLE", "worker restart budget exhausted"
                    )
                restart_task = self._restart_task
                if restart_task is not None and not restart_task.done():
                    continue
                return await self._spawn_and_handshake()

    async def wait_until_ready(self) -> WorkerReady:
        if self._ready is not None and self._available:
            return self._ready
        task = self._restart_task
        if task is not None:
            return await asyncio.shield(task)
        if self._restart_exhausted:
            raise self._error("MODEL_UNAVAILABLE", "worker restart budget exhausted")
        raise self._error("MODEL_UNAVAILABLE", "worker is not becoming ready")

    async def start_generation(self, generation_id: int) -> GenerationResult:
        self._require_ready()
        self._validate_uint("generation_id", generation_id)
        if self._active_generation_id is not None:
            raise self._error("INVALID_STATE", "a generation is already active")
        if not self._output_queue.empty():
            raise self._error(
                "INVALID_STATE",
                "prior generation output must be consumed before restart",
            )
        if (
            self._last_generation_id is not None
            and generation_id <= self._last_generation_id
        ):
            raise self._error(
                "INVALID_STATE", "generation_id must increase monotonically"
            )

        message = self._control_message("generation.start", generation_id=generation_id)
        try:
            response = await self._request(
                message,
                expected_type="generation.started",
                timeout_ms=self._profile.startup_timeout_ms,
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker generation start deadline expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        self._require_echoed_generation(response, generation_id)
        self._active_generation_id = generation_id
        self._last_generation_id = generation_id
        self._accepted_frames.clear()
        self._first_accepted_ns = None
        self._pending_since_ns = None
        self._last_output_ns = None
        self._output_seen = False
        return GenerationResult(generation_id)

    async def push_audio(self, frame: AudioFrame) -> None:
        self._require_ready()
        if self._active_generation_id is None:
            raise self._error("INVALID_STATE", "no generation is active")
        if frame.generation_id != self._active_generation_id:
            raise self._error("INVALID_STATE", "audio generation_id is not active")
        expected_samples = frame.sample_rate * self._profile.frame_ms // 1000
        if (
            frame.sample_rate * self._profile.frame_ms % 1000
            or frame.samples_per_channel != expected_samples
        ):
            raise self._error("INVALID_STATE", "audio is not one negotiated frame")
        if frame.sequence in self._accepted_frames:
            raise self._error("INVALID_STATE", "audio sequence was already accepted")
        if self._accepted_frames:
            prior = next(reversed(self._accepted_frames.values()))
            if frame.sequence <= prior.sequence:
                raise self._error("INVALID_STATE", "audio sequence must increase")
            if frame.source_monotonic_ns < prior.source_monotonic_ns:
                raise self._error("INVALID_STATE", "source timestamp must not decrease")
        if len(self._accepted_frames) >= self.input_capacity_frames:
            raise self._error(
                "QUEUE_OVERFLOW", "worker input queue reached its 500 ms budget", True
            )

        accepted_at_ns = self._clock.now_ns()
        self._accepted_frames[frame.sequence] = frame
        if self._first_accepted_ns is None:
            self._first_accepted_ns = accepted_at_ns
        if self._pending_since_ns is None:
            self._pending_since_ns = accepted_at_ns
        message = {
            "type": "audio.push",
            "worker_protocol_version": WORKER_PROTOCOL_VERSION,
            "generation_id": frame.generation_id,
            "sequence": frame.sequence,
            "sample_rate": frame.sample_rate,
            "channels": frame.channels,
            "samples_per_channel": frame.samples_per_channel,
            "source_monotonic_ns": frame.source_monotonic_ns,
            "pcm_f32le_base64": base64.b64encode(frame.pcm_f32le).decode("ascii"),
        }
        try:
            write_deadline_ns = (
                self._clock.now_ns() + self._profile.stall_timeout_ms * 1_000_000
            )
            await self._wait_until(self._send(message), deadline_ns=write_deadline_ns)
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker input write deadline expired", True
            )
            await self._terminate_failed_process(
                runtime_error,
                restart=True,
                notify_output=True,
            )
            raise runtime_error from error
        except BaseException:
            self._accepted_frames.pop(frame.sequence, None)
            if not self._accepted_frames:
                self._pending_since_ns = None
                if not self._output_seen:
                    self._first_accepted_ns = None
            raise

    async def next_output(self) -> AudioFrame:
        immediate = self.take_output_nowait()
        if immediate is not None:
            return immediate
        if not self._accepted_frames:
            raise self._error("INVALID_STATE", "no worker output is pending")

        if self._output_seen:
            assert self._last_output_ns is not None
            assert self._pending_since_ns is not None
            timeout_ms = self._profile.stall_timeout_ms
            deadline_ns = (
                max(self._last_output_ns, self._pending_since_ns)
                + timeout_ms * 1_000_000
            )
        else:
            assert self._first_accepted_ns is not None
            timeout_ms = self._profile.first_output_timeout_ms
            deadline_ns = self._first_accepted_ns + timeout_ms * 1_000_000

        try:
            value = await self._wait_until(
                self._output_queue.get(), deadline_ns=deadline_ns
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker output deadline expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        if isinstance(value, WorkerRuntimeError):
            raise value
        return value

    def take_output_nowait(self) -> AudioFrame | None:
        try:
            value = self._output_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        if isinstance(value, WorkerRuntimeError):
            raise value
        return value

    async def end_generation(self, generation_id: int) -> GenerationResult:
        self._require_active_generation(generation_id)
        try:
            response = await self._request(
                self._control_message("generation.end", generation_id=generation_id),
                expected_type="generation.completed",
                timeout_ms=max(
                    self._profile.first_output_timeout_ms,
                    self._profile.stall_timeout_ms,
                ),
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker generation end deadline expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        self._require_echoed_generation(response, generation_id)
        if self._accepted_frames:
            error = self._error(
                "WORKER_PROTOCOL", "worker completed with accepted audio outstanding"
            )
            await self._terminate_failed_process(error, restart=True)
            raise error
        self._active_generation_id = None
        return GenerationResult(generation_id)

    async def cancel_generation(self, generation_id: int) -> GenerationResult:
        self._require_active_generation(generation_id)
        self._canceled_generations.add(generation_id)
        if len(self._canceled_generations) > 64:
            self._canceled_generations.remove(min(self._canceled_generations))
        self._active_generation_id = None
        self._accepted_frames.clear()
        self._first_accepted_ns = None
        self._pending_since_ns = None
        self._clear_output_queue()

        try:
            response = await self._request(
                self._control_message("generation.cancel", generation_id=generation_id),
                expected_type="generation.canceled",
                timeout_ms=self._profile.cancel_timeout_ms,
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker cancellation acknowledgement expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        self._require_echoed_generation(response, generation_id)
        return GenerationResult(generation_id)

    async def health(self) -> WorkerHealth:
        self._require_ready()
        try:
            response = await self._request(
                self._control_message("worker.health"),
                expected_type="worker.health.result",
                timeout_ms=self._profile.startup_timeout_ms,
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker health deadline expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        return WorkerHealth(
            ready=bool(response["ready"]),
            active_generation_id=response["active_generation_id"],  # type: ignore[arg-type]
            queue_depth_frames=int(response["queue_depth_frames"]),
            capacity_frames=int(response["capacity_frames"]),
        )

    async def close(self) -> None:
        self._closing = True
        async with self._start_lock:
            async with self._failure_lock:
                await self._close_locked()

    async def _close_locked(self) -> None:
        if self._closed and self._process is None:
            return
        restart_task = self._restart_task
        self._restart_task = None
        if restart_task is not None and not restart_task.done():
            restart_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, WorkerRuntimeError):
                await restart_task

        process = self._process
        process_group_id = self._process_group_id
        if process is not None and process.returncode is None:
            clean = False
            try:
                await self._request(
                    self._control_message("worker.close"),
                    expected_type="worker.closed",
                    timeout_ms=self._profile.close_grace_ms,
                )
                clean = True
            except (TimeoutError, WorkerRuntimeError, BrokenPipeError):
                clean = False

            if clean:
                deadline = (
                    self._clock.now_ns() + self._profile.close_grace_ms * 1_000_000
                )
                try:
                    await self._wait_until(process.wait(), deadline_ns=deadline)
                except TimeoutError:
                    clean = False
            if not clean:
                self._signal_group(process_group_id, signal.SIGTERM)
                await self._clock.wait_until_ns(
                    self._clock.now_ns() + self._profile.terminate_grace_ms * 1_000_000
                )
                if self._group_exists(process_group_id):
                    self._signal_group(process_group_id, signal.SIGKILL)

        if process is not None:
            await self._close_process_stdin(process)
            if process.returncode is None:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=1.0)
            if self._group_exists(process_group_id):
                self._signal_group(process_group_id, signal.SIGKILL)
                await asyncio.sleep(0)

        await self._cancel_background_tasks()
        if process is not None:
            await self._release_process_transport(process)
        self._fail_pending(self._error("INVALID_STATE", "worker supervisor closed"))
        self._clear_output_queue()
        self._accepted_frames.clear()
        self._pending_since_ns = None
        self._active_generation_id = None
        self._ready = None
        self._available = False
        self._process = None
        self._process_group_id = None
        self._closed = True

    async def _spawn_and_handshake(self) -> WorkerReady:
        startup_deadline_ns = (
            self._clock.now_ns() + self._profile.startup_timeout_ms * 1_000_000
        )
        if self._profile.artifacts:
            try:
                verified_environment = await self._wait_until(
                    self._verify_artifacts(), deadline_ns=startup_deadline_ns
                )
            except TimeoutError as error:
                raise self._error(
                    "MODEL_TIMEOUT", "artifact verification deadline expired", True
                ) from error
        else:
            verified_environment = dict(self._profile.environment)
        child_environment = {
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
            **verified_environment,
        }
        try:
            process = await self._wait_until(
                asyncio.create_subprocess_exec(
                    *self._profile.command,
                    cwd=self._profile.cwd,
                    env=child_environment,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                    limit=MAX_LINE_BYTES + 1,
                ),
                deadline_ns=startup_deadline_ns,
            )
        except TimeoutError as error:
            raise self._error(
                "MODEL_TIMEOUT", "worker process startup deadline expired", True
            ) from error
        except (OSError, ValueError) as error:
            raise self._error(
                "MODEL_UNAVAILABLE", "worker process could not be started"
            ) from error

        self._epoch += 1
        epoch = self._epoch
        self._process = process
        self._process_group_id = process.pid
        self._ready = None
        self._available = False
        self._reader_task = asyncio.create_task(self._reader_loop(process, epoch))
        self._stderr_task = asyncio.create_task(self._drain_stderr(process))

        message = self._control_message(
            "worker.hello",
            profile_id=self._profile.profile_id,
            pipeline_id=self._profile.pipeline_id,
            configuration_hash=self._profile.configuration_hash,
        )
        try:
            response = await self._request(
                message,
                expected_type="worker.ready",
                timeout_ms=self._profile.startup_timeout_ms,
                deadline_ns=startup_deadline_ns,
            )
        except TimeoutError as error:
            runtime_error = self._error(
                "MODEL_TIMEOUT", "worker readiness deadline expired", True
            )
            await self._terminate_failed_process(runtime_error, restart=False)
            raise runtime_error from error
        ready = WorkerReady(
            profile_id=str(response["profile_id"]),
            pipeline_id=str(response["pipeline_id"]),
            implementation_revision=str(response["implementation_revision"]),
            weight_revision=response["weight_revision"],  # type: ignore[arg-type]
            configuration_hash=str(response["configuration_hash"]),
        )
        expected = WorkerReady(
            profile_id=self._profile.profile_id,
            pipeline_id=self._profile.pipeline_id,
            implementation_revision=self._profile.implementation_revision,
            weight_revision=self._profile.weight_revision,
            configuration_hash=self._profile.configuration_hash,
        )
        if ready != expected:
            error = self._error(
                "WORKER_PROTOCOL", "worker identity did not match profile"
            )
            await self._terminate_failed_process(error, restart=False)
            raise error
        self._ready = ready
        self._available = True
        return ready

    async def _request(
        self,
        message: dict[str, object],
        *,
        expected_type: str,
        timeout_ms: int,
        deadline_ns: int | None = None,
    ) -> dict[str, object]:
        rpc_id = message["rpc_id"]
        assert isinstance(rpc_id, int)
        future: asyncio.Future[dict[str, object]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[rpc_id] = _PendingRpc(expected_type, future)
        if deadline_ns is None:
            deadline_ns = self._clock.now_ns() + timeout_ms * 1_000_000
        try:
            await self._wait_until(self._send(message), deadline_ns=deadline_ns)
            return await self._wait_until(
                asyncio.shield(future), deadline_ns=deadline_ns
            )
        finally:
            self._pending.pop(rpc_id, None)
            if not future.done():
                future.cancel()

    async def _send(self, message: dict[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None or process.returncode is not None:
            raise self._error("WORKER_CRASH", "worker process is not running", True)
        line = encode_message(message)
        async with self._write_lock:
            try:
                process.stdin.write(line)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as error:
                raise self._error(
                    "WORKER_CRASH", "worker input pipe closed", True
                ) from error

    async def _reader_loop(
        self, process: asyncio.subprocess.Process, epoch: int
    ) -> None:
        assert process.stdout is not None
        try:
            while True:
                try:
                    line = await process.stdout.readline()
                except (ValueError, asyncio.LimitOverrunError) as error:
                    raise WorkerProtocolError(
                        "worker output exceeded the line limit", field="line"
                    ) from error
                if not line:
                    break
                message = decode_message(line)
                await self._dispatch(message, epoch)
        except (WorkerProtocolError, WorkerRuntimeError) as error:
            if not self._closing and epoch == self._epoch:
                runtime_error = self._error(
                    "WORKER_PROTOCOL", str(error), recoverable=True
                )
                await self._terminate_failed_process(
                    runtime_error, restart=True, notify_output=True
                )
            return

        await process.wait()
        if self._closing or epoch != self._epoch or epoch in self._failed_epochs:
            return
        error = self._error("WORKER_CRASH", "worker exited unexpectedly", True)
        await self._record_failure(epoch, error, restart=True)

    async def _dispatch(self, message: dict[str, object], epoch: int) -> None:
        if epoch != self._epoch or epoch in self._failed_epochs:
            return
        message_type = str(message["type"])
        if message_type == "audio.output":
            await self._dispatch_audio(message)
            return
        rpc_id = message.get("rpc_id")
        assert isinstance(rpc_id, int)
        pending = self._pending.get(rpc_id)
        if pending is None:
            raise WorkerProtocolError("response has an unknown rpc_id", field="rpc_id")
        if message_type == "worker.error":
            pending.future.set_exception(
                self._error(
                    str(message["code"]),
                    str(message["message"]),
                    bool(message["recoverable"]),
                )
            )
            return
        if message_type != pending.expected_type:
            raise WorkerProtocolError(
                f"expected {pending.expected_type}, received {message_type}",
                field="type",
            )
        if not pending.future.done():
            pending.future.set_result(message)

    async def _dispatch_audio(self, message: dict[str, object]) -> None:
        generation_id = int(message["generation_id"])
        if generation_id in self._canceled_generations:
            return
        if generation_id != self._active_generation_id:
            raise WorkerProtocolError(
                "audio output belongs to an inactive generation", field="generation_id"
            )
        sequence = int(message["sequence"])
        source = self._accepted_frames.get(sequence)
        if source is None:
            raise WorkerProtocolError(
                "audio output sequence was not accepted", field="sequence"
            )
        expected_sequence = next(iter(self._accepted_frames))
        if sequence != expected_sequence:
            raise WorkerProtocolError(
                "audio output was emitted out of accepted order", field="sequence"
            )
        for field in (
            "sample_rate",
            "channels",
            "samples_per_channel",
            "source_monotonic_ns",
        ):
            if message[field] != getattr(source, field):
                raise WorkerProtocolError(f"audio output changed {field}", field=field)
        encoded = str(message["pcm_f32le_base64"])
        frame = AudioFrame(
            generation_id=generation_id,
            sequence=sequence,
            sample_rate=int(message["sample_rate"]),
            channels=int(message["channels"]),
            samples_per_channel=int(message["samples_per_channel"]),
            source_monotonic_ns=int(message["source_monotonic_ns"]),
            pcm_f32le=base64.b64decode(encoded, validate=True),
        )
        self._accepted_frames.pop(sequence)
        if not self._accepted_frames:
            self._pending_since_ns = None
        self._output_seen = True
        self._last_output_ns = self._clock.now_ns()
        try:
            self._output_queue.put_nowait(frame)
        except asyncio.QueueFull as error:
            raise WorkerProtocolError(
                "worker output queue overflowed", field="audio"
            ) from error

    async def _drain_stderr(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        with contextlib.suppress(Exception):
            while await process.stderr.read(4096):
                pass

    @staticmethod
    async def _close_process_stdin(process: asyncio.subprocess.Process) -> None:
        writer = process.stdin
        if writer is None:
            return
        writer.close()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            await writer.wait_closed()

    @staticmethod
    async def _release_process_transport(process: asyncio.subprocess.Process) -> None:
        # asyncio.Process has no public close API in Python 3.12. The supervisor
        # owns this transport and must release its pipe handles before loop teardown.
        transport = getattr(process, "_transport", None)
        close = getattr(transport, "close", None)
        if close is not None:
            close()
            await asyncio.sleep(0)

    async def _record_failure(
        self,
        epoch: int,
        error: WorkerRuntimeError,
        *,
        restart: bool,
        notify_output: bool = True,
    ) -> None:
        async with self._failure_lock:
            if epoch != self._epoch or epoch in self._failed_epochs:
                return
            self._failed_epochs.add(epoch)
            self._available = False
            self._ready = None
            self._active_generation_id = None
            had_pending_output = bool(self._accepted_frames)
            self._accepted_frames.clear()
            self._pending_since_ns = None
            self._clear_output_queue()
            if notify_output and had_pending_output:
                self._put_failure_nowait(error)
            self._fail_pending(error)

            process = self._process
            if process is not None and process.returncode is None:
                self._signal_group(self._process_group_id, signal.SIGKILL)
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=1.0)
            if process is not None:
                await self._close_process_stdin(process)
                await self._release_process_transport(process)
            self._process = None
            self._process_group_id = None

            if restart and not self._closing and self._reserve_restart():
                self._restart_task = asyncio.create_task(self._restart())

    async def _terminate_failed_process(
        self,
        error: WorkerRuntimeError,
        *,
        restart: bool,
        notify_output: bool = False,
    ) -> None:
        await self._record_failure(
            self._epoch,
            error,
            restart=restart,
            notify_output=notify_output,
        )

    async def _restart(self) -> WorkerReady:
        try:
            await asyncio.sleep(0)
            async with self._start_lock:
                if self._closing:
                    raise self._error("MODEL_UNAVAILABLE", "worker is closing")
                if self._ready is not None and self._available:
                    return self._ready
                ready = await self._spawn_and_handshake()
                return ready
        except BaseException:
            self._available = False
            raise
        finally:
            if self._restart_task is asyncio.current_task():
                self._restart_task = None

    def _reserve_restart(self) -> bool:
        now_ns = self._clock.now_ns()
        window_ns = self._profile.restart_window_ms * 1_000_000
        while (
            self._restart_times_ns and now_ns - self._restart_times_ns[0] >= window_ns
        ):
            self._restart_times_ns.popleft()
        if len(self._restart_times_ns) >= self._profile.restart_limit:
            self._restart_exhausted = True
            return False
        self._restart_times_ns.append(now_ns)
        self._restart_count += 1
        return True

    async def _verify_artifacts(self) -> dict[str, str]:
        verified_environment = dict(self._profile.environment)
        for artifact in self._profile.artifacts:
            raw_path = self._profile.environment.get(artifact.env_var)
            if not raw_path:
                raise self._error(
                    "MODEL_UNAVAILABLE",
                    f"required artifact {artifact.env_var} is not configured",
                )
            path = Path(raw_path)
            if not path.is_absolute():
                raise self._error(
                    "MODEL_UNAVAILABLE",
                    f"required artifact {artifact.env_var} must use an absolute path",
                )
            try:
                resolved_path, digest = await self._inspect_artifact(path)
            except (OSError, UnicodeError, ValueError) as error:
                raise self._error(
                    "MODEL_UNAVAILABLE",
                    f"required artifact {artifact.env_var} is unavailable",
                ) from error
            if digest != artifact.sha256:
                raise self._error(
                    "MODEL_UNAVAILABLE",
                    f"required artifact {artifact.env_var} failed SHA-256 verification",
                )
            verified_environment[artifact.env_var] = str(resolved_path)
        return verified_environment

    @staticmethod
    async def _inspect_artifact(path: Path) -> tuple[Path, str]:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            _INSPECT_ARTIFACT_PROGRAM,
            str(path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={"PYTHONUTF8": "1"},
            start_new_session=True,
        )
        try:
            stdout, _ = await process.communicate()
        except BaseException:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            raise
        if process.returncode != 0:
            raise OSError("artifact inspection process failed")
        value = json.loads(stdout.decode("utf-8", errors="strict"))
        if not isinstance(value, dict):
            raise OSError("artifact inspection returned an invalid result")
        resolved_path = Path(value.get("path", ""))
        digest = value.get("sha256")
        if (
            not resolved_path.is_absolute()
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise OSError("artifact inspection returned an invalid result")
        return resolved_path, digest

    async def _wait_until(self, awaitable: Awaitable[_T], *, deadline_ns: int) -> _T:
        operation = asyncio.ensure_future(awaitable)
        timer = asyncio.create_task(self._clock.wait_until_ns(deadline_ns))
        try:
            done, _ = await asyncio.wait(
                {operation, timer}, return_when=asyncio.FIRST_COMPLETED
            )
            if operation in done:
                return operation.result()
            if operation.done():
                return operation.result()
            operation.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await operation
            raise TimeoutError
        finally:
            if not operation.done():
                operation.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await operation
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timer

    def _control_message(
        self, message_type: str, **fields: object
    ) -> dict[str, object]:
        rpc_id = self._next_rpc_id
        self._next_rpc_id += 1
        return {
            "type": message_type,
            "worker_protocol_version": WORKER_PROTOCOL_VERSION,
            "rpc_id": rpc_id,
            **fields,
        }

    def _require_ready(self) -> None:
        if not self._available or self._ready is None:
            raise self._error("INVALID_STATE", "worker is not ready")

    def _require_active_generation(self, generation_id: int) -> None:
        self._require_ready()
        self._validate_uint("generation_id", generation_id)
        if self._active_generation_id != generation_id:
            raise self._error("INVALID_STATE", "generation is not active")

    @staticmethod
    def _validate_uint(name: str, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise WorkerRuntimeError("INVALID_STATE", f"{name} must be unsigned")

    @staticmethod
    def _require_echoed_generation(
        response: dict[str, object], generation_id: int
    ) -> None:
        if response["generation_id"] != generation_id:
            raise WorkerProtocolError(
                "worker changed generation_id", field="generation_id"
            )

    def _fail_pending(self, error: WorkerRuntimeError) -> None:
        for pending in tuple(self._pending.values()):
            if not pending.future.done():
                pending.future.set_exception(error)

    def _put_failure_nowait(self, error: WorkerRuntimeError) -> None:
        with contextlib.suppress(asyncio.QueueFull):
            self._output_queue.put_nowait(error)

    def _clear_output_queue(self) -> None:
        while True:
            try:
                self._output_queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def _cancel_background_tasks(self) -> None:
        current = asyncio.current_task()
        for task in (self._reader_task, self._stderr_task):
            if task is not None and task is not current and not task.done():
                task.cancel()
        for task in (self._reader_task, self._stderr_task):
            if task is not None and task is not current:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._reader_task = None
        self._stderr_task = None

    @staticmethod
    def _signal_group(process_group_id: int | None, sig: signal.Signals) -> None:
        if process_group_id is None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process_group_id, sig)

    @staticmethod
    def _group_exists(process_group_id: int | None) -> bool:
        if process_group_id is None:
            return False
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _error(
        code: str, message: str, recoverable: bool = False
    ) -> WorkerRuntimeError:
        return WorkerRuntimeError(code, message, recoverable=recoverable)
