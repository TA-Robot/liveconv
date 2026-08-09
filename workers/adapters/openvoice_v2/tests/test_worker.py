from __future__ import annotations

import base64
import os
import select
import struct
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from workers.adapters.openvoice_v2.worker import OfflineWorker
from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)


class FakeBuffer:
    def __init__(self) -> None:
        self.lines: list[bytes] = []

    def write(self, value: bytes) -> None:
        self.lines.append(value)

    def flush(self) -> None:
        pass


class FakeEngine:
    weight_revision = "sha256:" + "a" * 64
    configuration_hash = "sha256:" + "b" * 64
    implementation_sha256 = "c" * 64

    def convert(self, samples, sample_rate):
        assert sample_rate == 1_000
        return tuple(-sample for sample in samples)


class BlockingEngine(FakeEngine):
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def convert(self, samples, sample_rate):
        self.calls += 1
        self.started.set()
        if not self.release.wait(2):
            raise TimeoutError("test did not release conversion")
        return super().convert(samples, sample_rate)


def _receive(process: subprocess.Popen[bytes], timeout: float = 30.0):
    assert process.stdout is not None
    readable, _, _ = select.select([process.stdout], [], [], timeout)
    if not readable:
        raise TimeoutError("worker output deadline expired")
    line = process.stdout.readline()
    if not line:
        stderr = b"" if process.stderr is None else process.stderr.read()
        raise RuntimeError(f"worker exited before response: {stderr!r}")
    return line, decode_message(line)


def request(message_type: str, rpc_id: int, **fields):
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": rpc_id,
        **fields,
    }


def frame(
    sequence: int,
    *,
    generation_id: int = 7,
    source_monotonic_ns: int | None = None,
):
    samples = (0.25, -0.5) * 10
    return {
        "type": "audio.push",
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "generation_id": generation_id,
        "sequence": sequence,
        "sample_rate": 1_000,
        "channels": 1,
        "samples_per_channel": 20,
        "source_monotonic_ns": (
            sequence * 20_000_000
            if source_monotonic_ns is None
            else source_monotonic_ns
        ),
        "pcm_f32le_base64": base64.b64encode(struct.pack("<20f", *samples)).decode(),
    }


def hello(worker: OfflineWorker, rpc_id: int = 0) -> None:
    worker.handle(
        request(
            "worker.hello",
            rpc_id,
            profile_id="openvoice-v2.offline",
            pipeline_id="fixture",
            configuration_hash=FakeEngine.configuration_hash,
        )
    )


def _assert_worker_subprocess_keeps_stdout_protocol_only(
    worker_python: Path,
    script: str,
    *,
    working_directory: Path,
    expected_boundaries: tuple[bytes, ...],
) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    process = subprocess.Popen(
        [str(worker_python), "-I", "-c", script],
        cwd=working_directory,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert process.stdin is not None

    raw_lines: list[bytes] = []

    def send(message: dict[str, object]) -> None:
        process.stdin.write(encode_message(message))
        process.stdin.flush()

    try:
        send(
            request(
                "worker.hello",
                1,
                profile_id="openvoice-v2.offline",
                pipeline_id="stdout-boundaries",
                configuration_hash=FakeEngine.configuration_hash,
            )
        )
        raw, message = _receive(process)
        raw_lines.append(raw)
        assert message["type"] == "worker.ready"
        send(request("generation.start", 2, generation_id=7))
        raw, message = _receive(process)
        raw_lines.append(raw)
        assert message["type"] == "generation.started"
        for sequence in range(3):
            send(frame(sequence))
        send(request("generation.end", 3, generation_id=7))
        for rpc_id in range(10, 60):
            send(request("worker.health", rpc_id))

        completed = False
        health_count = 0
        output_count = 0
        while not completed or health_count < 50:
            raw, message = _receive(process)
            raw_lines.append(raw)
            if message["type"] == "worker.health.result":
                health_count += 1
            elif message["type"] == "audio.output":
                output_count += 1
            elif message["type"] == "generation.completed":
                completed = True
            else:
                pytest.fail(f"unexpected protocol message: {message}")
        assert output_count == 3

        send(request("worker.close", 70))
        raw, message = _receive(process)
        raw_lines.append(raw)
        assert message["type"] == "worker.closed"
        process.stdin.close()
        assert process.wait(timeout=10) == 0
        assert process.stderr is not None
        stderr = process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert b"NOISE" not in b"".join(raw_lines)
    for boundary in expected_boundaries:
        assert b"OBSERVED " + boundary in stderr


def test_workspace_worker_subprocess_keeps_fd1_protocol_only(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    script = f"""
import os
import sys
import threading

sys.path.insert(0, {str(repository_root)!r})

from workers.adapters.openvoice_v2 import worker as worker_module


def noise(label):
    os.write(2, f"OBSERVED {{label}}\\n".encode("ascii"))
    print(f"PRINT NOISE {{label}}", flush=True)
    os.write(1, f"WRITE NOISE {{label}}\\n".encode("ascii"))


class FakeEngine:
    weight_revision = "sha256:" + "a" * 64
    configuration_hash = "sha256:" + "b" * 64
    implementation_sha256 = "c" * 64

    def __init__(self):
        noise("engine_factory")

    def convert(self, samples, sample_rate):
        assert sample_rate == 1_000
        noise("convert")
        thread = threading.Thread(
            target=lambda: noise("concurrent_convert"), daemon=True
        )
        thread.start()
        thread.join()
        return tuple(-sample for sample in samples)


worker_module.OpenVoiceV2Engine.from_environment = classmethod(
    lambda _cls: FakeEngine()
)
raise SystemExit(worker_module.run())
"""
    _assert_worker_subprocess_keeps_stdout_protocol_only(
        Path(sys.executable).absolute(),
        script,
        working_directory=tmp_path,
        expected_boundaries=(
            b"engine_factory",
            b"convert",
            b"concurrent_convert",
        ),
    )


def test_configured_runtime_keeps_fd1_isolated_at_upstream_boundaries(
    tmp_path: Path,
) -> None:
    configured_python = os.environ.get("LIVECONV_OPENVOICE_V2_TEST_PYTHON")
    if not configured_python:
        pytest.skip(
            "set LIVECONV_OPENVOICE_V2_TEST_PYTHON to exercise the OpenVoice runtime"
        )
    worker_python = Path(configured_python).absolute()
    assert worker_python.is_file()
    script = r"""
import importlib
import os
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

from workers.adapters.openvoice_v2 import engine as engine_module
from workers.adapters.openvoice_v2 import worker as worker_module


observed = set()


def noise(label):
    if label not in observed:
        observed.add(label)
        os.write(2, f"OBSERVED {label}\n".encode("ascii"))
    print(f"PRINT NOISE {label}", flush=True)
    os.write(1, f"WRITE NOISE {label}\n".encode("ascii"))


real_import = importlib.import_module
api = ModuleType("openvoice.api")


class Base:
    def __init__(self, *_args, **_kwargs):
        noise("construction")
        self.hps = SimpleNamespace(
            data=SimpleNamespace(sampling_rate=1000),
            _version_="v2",
        )


class Converter(Base):
    def load_ckpt(self, _path):
        noise("load_ckpt")

    def extract_se(self, path):
        label = (
            "target_extract_se"
            if path.endswith("target.wav")
            else "source_extract_se"
        )
        noise(label)
        return (label,)

    def convert(self, *_args, **_kwargs):
        noise("convert")

        def concurrent_noise():
            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                noise("concurrent_convert")
                time.sleep(0.001)

        threading.Thread(target=concurrent_noise, daemon=True).start()
        return [0.125] * 60


api.OpenVoiceBaseClass = Base
api.ToneColorConverter = Converter


def noisy_import(name, package=None):
    if name == "openvoice.api":
        noise("openvoice_import")
        return api
    if name in {"numpy", "soundfile", "librosa", "torch"}:
        noise(f"runtime_import_{name}")
    return real_import(name, package)


engine_module.importlib.import_module = noisy_import


def factory():
    runtime = engine_module.RuntimeIdentity(
        prefix=Path(os.sys.prefix),
        pyvenv_sha256="1" * 64,
        worker_wheel_path=Path("/tmp/fake.whl"),
        worker_wheel_sha256="2" * 64,
        wheel_record_sha256="3" * 64,
        installed_record_sha256="4" * 64,
        distribution_manifest_sha256="5" * 64,
        implementation_sha256="6" * 64,
        distribution_version="0.1.0",
    )
    configuration = engine_module.EngineConfiguration(
        source_root=Path("/tmp"),
        source_tree_sha256="7" * 64,
        config_path=Path("/tmp/config.json"),
        config_sha256="8" * 64,
        checkpoint_path=Path("/tmp/checkpoint.pth"),
        checkpoint_sha256="9" * 64,
        target_reference_path=Path("/tmp/target.wav"),
        target_reference_sha256="a" * 64,
        runtime_identity=runtime,
        runtime_lock_sha256="b" * 64,
        device="cpu",
    )
    actual = engine_module.OpenVoiceV2Engine(configuration)

    class Proxy:
        weight_revision = "sha256:" + "a" * 64
        configuration_hash = "sha256:" + "b" * 64
        implementation_sha256 = "c" * 64

        def convert(self, samples, sample_rate):
            return actual.convert(samples, sample_rate)

    return Proxy()


worker_module.OpenVoiceV2Engine.from_environment = classmethod(lambda _cls: factory())
raise SystemExit(worker_module.run())
"""
    _assert_worker_subprocess_keeps_stdout_protocol_only(
        worker_python,
        script,
        working_directory=tmp_path,
        expected_boundaries=(
            b"openvoice_import",
            b"construction",
            b"load_ckpt",
            b"target_extract_se",
            b"runtime_import_numpy",
            b"runtime_import_soundfile",
            b"runtime_import_librosa",
            b"source_extract_se",
            b"runtime_import_torch",
            b"convert",
            b"concurrent_convert",
        ),
    )


def test_offline_worker_emits_ordered_transformed_frames() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker, 1)
    worker.handle(request("generation.start", 2, generation_id=7))
    worker.handle(frame(0))
    worker.handle(frame(1))
    worker.handle(frame(2))
    worker.handle(request("generation.end", 3, generation_id=7))
    assert worker._future is not None
    worker._future.result(timeout=2)

    messages = [decode_message(line) for line in output.lines]
    assert [message["type"] for message in messages] == [
        "worker.ready",
        "generation.started",
        "audio.output",
        "audio.output",
        "audio.output",
        "generation.completed",
    ]
    assert [message["sequence"] for message in messages[2:5]] == [0, 1, 2]
    raw = base64.b64decode(messages[2]["pcm_f32le_base64"])
    assert struct.unpack("<2f", raw[:8]) == (-0.25, 0.5)


def test_cancel_acknowledgement_is_an_atomic_output_barrier(monkeypatch) -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    for sequence in range(3):
        worker.handle(frame(sequence))

    publication_started = threading.Event()
    release_publication = threading.Event()
    original_emit = worker.emit

    def delayed_emit(message) -> None:
        if message["type"] == "audio.output" and not publication_started.is_set():
            publication_started.set()
            assert release_publication.wait(2)
        original_emit(message)

    monkeypatch.setattr(worker, "emit", delayed_emit)
    worker.handle(request("generation.end", 2, generation_id=7))
    assert publication_started.wait(1)

    cancel_started = threading.Event()
    cancel_returned = threading.Event()

    def cancel() -> None:
        cancel_started.set()
        worker.handle(request("generation.cancel", 3, generation_id=7))
        cancel_returned.set()

    cancel_thread = threading.Thread(target=cancel)
    cancel_thread.start()
    assert cancel_started.wait(1)
    assert not cancel_returned.wait(0.1)
    release_publication.set()
    cancel_thread.join(timeout=1)
    assert not cancel_thread.is_alive()
    assert worker._future is not None
    worker._future.result(timeout=1)

    messages = [decode_message(line) for line in output.lines]
    terminal_index = next(
        index
        for index, message in enumerate(messages)
        if message["type"] in {"generation.canceled", "generation.completed"}
    )
    assert not any(
        message["type"] in {"audio.output", "generation.completed"}
        for message in messages[terminal_index + 1 :]
    )


def test_rejects_non_twenty_millisecond_audio() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    malformed = frame(0)
    malformed["samples_per_channel"] = 19
    malformed["pcm_f32le_base64"] = base64.b64encode(
        struct.pack("<19f", *((0.1,) * 19))
    ).decode()
    with pytest.raises(ValueError, match="one 20 ms frame"):
        worker.handle(malformed)


def test_rejects_reused_generation_id() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    worker.handle(request("generation.cancel", 2, generation_id=7))
    worker.handle(request("generation.start", 3, generation_id=7))
    messages = [decode_message(line) for line in output.lines]
    assert messages[-1]["type"] == "worker.error"
    assert messages[-1]["code"] == "INVALID_STATE"


def test_end_seals_frames_and_cannot_schedule_twice(monkeypatch) -> None:
    output = FakeBuffer()
    engine = BlockingEngine()
    worker = OfflineWorker(engine, output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    for sequence in range(3):
        worker.handle(frame(sequence))
    worker.handle(request("generation.end", 2, generation_id=7))
    assert engine.started.wait(1)

    with pytest.raises(ValueError, match="forbidden after generation.end"):
        worker.handle(frame(3))
    with pytest.raises(ValueError, match="end has no matching"):
        worker.handle(request("generation.end", 3, generation_id=7))

    completion_started = threading.Event()
    release_completion = threading.Event()
    original_emit = worker.emit

    def delayed_emit(message) -> None:
        if message["type"] == "generation.completed":
            completion_started.set()
            assert release_completion.wait(2)
        original_emit(message)

    monkeypatch.setattr(worker, "emit", delayed_emit)
    engine.release.set()
    assert completion_started.wait(1)

    cancel_started = threading.Event()
    cancel_returned = threading.Event()

    def cancel() -> None:
        cancel_started.set()
        worker.handle(request("generation.cancel", 4, generation_id=7))
        cancel_returned.set()

    cancel_thread = threading.Thread(target=cancel)
    cancel_thread.start()
    assert cancel_started.wait(1)
    assert not cancel_returned.wait(0.1)
    release_completion.set()
    cancel_thread.join(timeout=1)
    assert not cancel_thread.is_alive()
    assert worker._future is not None
    worker._future.result(timeout=1)
    messages = [decode_message(line) for line in output.lines]
    assert engine.calls == 1
    assert [message["type"] for message in messages].count("generation.completed") == 1
    assert [message["type"] for message in messages[-2:]] == [
        "generation.completed",
        "worker.error",
    ]
    assert messages[-1]["code"] == "INVALID_STATE"


def test_cancel_during_inference_reports_not_ready_until_call_returns() -> None:
    output = FakeBuffer()
    engine = BlockingEngine()
    worker = OfflineWorker(engine, output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    for sequence in range(3):
        worker.handle(frame(sequence))
    worker.handle(request("generation.end", 2, generation_id=7))
    assert engine.started.wait(1)

    worker.handle(request("generation.cancel", 3, generation_id=7))
    worker.handle(request("worker.health", 4))
    worker.handle(request("generation.start", 5, generation_id=8))
    messages = [decode_message(line) for line in output.lines]
    health = next(
        message for message in messages if message["type"] == "worker.health.result"
    )
    assert health["ready"] is False
    assert health["active_generation_id"] is None
    assert messages[-1]["type"] == "worker.error"
    assert messages[-1]["code"] == "MODEL_UNAVAILABLE"

    engine.release.set()
    assert worker._future is not None
    worker._future.result(timeout=1)
    worker.handle(request("worker.health", 6))
    worker.handle(request("generation.start", 7, generation_id=8))
    messages = [decode_message(line) for line in output.lines]
    assert messages[-2]["type"] == "worker.health.result"
    assert messages[-2]["ready"] is True
    assert messages[-1]["type"] == "generation.started"
    worker.handle(request("generation.cancel", 8, generation_id=8))


def test_rejects_decreasing_audio_timestamp() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    worker.handle(frame(0, source_monotonic_ns=100))
    with pytest.raises(ValueError, match="timestamp must not decrease"):
        worker.handle(frame(1, source_monotonic_ns=99))


def test_rejects_queue_overflow() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    for sequence in range(25):
        worker.handle(frame(sequence))
    with pytest.raises(ValueError, match="500 ms worker budget"):
        worker.handle(frame(25))


def test_short_nonempty_generation_returns_recoverable_error() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    hello(worker)
    worker.handle(request("generation.start", 1, generation_id=7))
    worker.handle(frame(0))
    worker.handle(request("generation.end", 2, generation_id=7))
    messages = [decode_message(line) for line in output.lines]
    assert messages[-1]["type"] == "worker.error"
    assert messages[-1]["code"] == "INVALID_STATE"
    assert messages[-1]["recoverable"] is True


def test_hello_rejects_configuration_identity_mismatch() -> None:
    output = FakeBuffer()
    worker = OfflineWorker(FakeEngine(), output)
    keep_running = worker.handle(
        request(
            "worker.hello",
            1,
            profile_id="openvoice-v2.offline",
            pipeline_id="fixture",
            configuration_hash="sha256:" + "c" * 64,
        )
    )
    messages = [decode_message(line) for line in output.lines]
    assert keep_running is False
    assert messages == [
        {
            "type": "worker.error",
            "worker_protocol_version": WORKER_PROTOCOL_VERSION,
            "rpc_id": 1,
            "code": "MODEL_UNAVAILABLE",
            "message": "OpenVoice configuration identity mismatch",
            "recoverable": False,
        }
    ]
