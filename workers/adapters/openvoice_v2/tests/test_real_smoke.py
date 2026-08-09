from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import os
import select
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import workers.adapters.openvoice_v2.engine as engine_module
import workers.runtime.codec as codec_module
from workers.adapters.openvoice_v2.engine import EngineConfiguration
from workers.adapters.openvoice_v2.worker import IMPLEMENTATION_REVISION
from workers.runtime.codec import (
    WORKER_PROTOCOL_VERSION,
    decode_message,
    encode_message,
)

RUN_REAL_SMOKE = os.environ.get("LIVECONV_OPENVOICE_V2_RUN_REAL_SMOKE") == "1"


def _receive(process: subprocess.Popen[bytes], timeout: float = 120.0):
    assert process.stdout is not None
    readable, _, _ = select.select([process.stdout], [], [], timeout)
    if not readable:
        raise TimeoutError("OpenVoice worker output deadline expired")
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("OpenVoice worker exited before its response")
    return decode_message(line)


@pytest.mark.skipif(
    not RUN_REAL_SMOKE,
    reason="set LIVECONV_OPENVOICE_V2_RUN_REAL_SMOKE=1 with pinned artifacts",
)
def test_real_worker_is_offline_reproducible_and_network_isolated() -> None:
    assert Path.cwd().resolve() == Path("/tmp")
    assert not os.environ.get("PYTHONPATH")
    try:
        import numpy
        import soundfile
    except ModuleNotFoundError:
        pytest.fail(
            "real smoke must run with the digest-locked OpenVoice runtime",
            pytrace=False,
        )
    input_path = Path(os.environ["LIVECONV_OPENVOICE_V2_SMOKE_INPUT_PATH"])
    expected_input_digest = os.environ["LIVECONV_OPENVOICE_V2_SMOKE_INPUT_SHA256"]
    expected_pcm_input_digest = os.environ[
        "LIVECONV_OPENVOICE_V2_SMOKE_PCM_INPUT_SHA256"
    ]
    expected_output_digest = os.environ["LIVECONV_OPENVOICE_V2_SMOKE_OUTPUT_SHA256"]
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == expected_input_digest
    configuration = EngineConfiguration.from_environment()
    audio, sample_rate = soundfile.read(
        input_path,
        dtype="float32",
        always_2d=False,
    )
    assert audio.ndim == 1
    samples_per_frame = sample_rate // 50
    assert sample_rate % 50 == 0
    assert len(audio) >= samples_per_frame * 25

    chunks = tuple(
        struct.pack(
            f"<{samples_per_frame}f",
            *audio[sequence * samples_per_frame : (sequence + 1) * samples_per_frame],
        )
        for sequence in range(25)
    )
    pcm_input = b"".join(chunks)
    assert hashlib.sha256(pcm_input).hexdigest() == expected_pcm_input_digest

    wrapper = """
import _socket
import hashlib
import os
import runpy
import sys
from pathlib import Path

from workers.adapters.openvoice_v2.network_isolation import deny_non_unix_sockets

expected_prefix = Path(os.environ["LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX"]).resolve()
if Path(sys.prefix).resolve() != expected_prefix:
    raise RuntimeError("worker did not execute from the declared runtime prefix")
if os.environ.get("PYTHONPATH"):
    raise RuntimeError("worker inherited PYTHONPATH")
pyvenv = expected_prefix / "pyvenv.cfg"
if hashlib.sha256(pyvenv.read_bytes()).hexdigest() != os.environ[
    "LIVECONV_OPENVOICE_V2_PYVENV_SHA256"
]:
    raise RuntimeError("worker pyvenv.cfg digest mismatch")
deny_non_unix_sockets()
for domain in (_socket.AF_INET, _socket.AF_INET6):
    try:
        _socket.socket(domain, _socket.SOCK_DGRAM)
    except PermissionError:
        pass
    else:
        raise RuntimeError("seccomp network isolation was not enforced")
runpy.run_module("workers.adapters.openvoice_v2", run_name="__main__")
"""
    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    environment.pop("PYTHONPATH", None)
    worker_python = Path(os.environ["LIVECONV_OPENVOICE_V2_WORKER_PYTHON"]).absolute()
    assert worker_python.is_file()
    assert worker_python == Path(sys.executable).absolute(), (
        "real smoke pytest and worker must use the same venv entry point"
    )
    runtime_prefix = Path(os.environ["LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX"]).resolve()
    assert Path(sys.prefix).resolve() == runtime_prefix
    assert Path(sys.base_prefix).resolve() != runtime_prefix
    assert worker_python.parent.parent == runtime_prefix
    pyvenv_path = runtime_prefix / "pyvenv.cfg"
    assert "include-system-site-packages = false" in pyvenv_path.read_text(
        encoding="utf-8"
    )
    assert (
        hashlib.sha256(pyvenv_path.read_bytes()).hexdigest()
        == (os.environ["LIVECONV_OPENVOICE_V2_PYVENV_SHA256"])
    )
    distribution = importlib.metadata.distribution("liveconv-worker-runtime")
    assert Path(distribution.locate_file("")).resolve().is_relative_to(runtime_prefix)
    assert Path(engine_module.__file__).resolve().is_relative_to(runtime_prefix)
    assert Path(codec_module.__file__).resolve().is_relative_to(runtime_prefix)
    process = subprocess.Popen(
        [str(worker_python), "-I", "-c", wrapper],
        cwd="/tmp",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        bufsize=0,
    )
    assert process.stdin is not None

    def send(message: dict[str, object]) -> None:
        process.stdin.write(encode_message(message))
        process.stdin.flush()

    def render(generation_id: int, rpc_base: int) -> bytes:
        send(
            {
                "type": "generation.start",
                "worker_protocol_version": WORKER_PROTOCOL_VERSION,
                "rpc_id": rpc_base,
                "generation_id": generation_id,
            }
        )
        assert _receive(process)["type"] == "generation.started"
        for sequence, raw in enumerate(chunks):
            send(
                {
                    "type": "audio.push",
                    "worker_protocol_version": WORKER_PROTOCOL_VERSION,
                    "generation_id": generation_id,
                    "sequence": sequence,
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "samples_per_channel": samples_per_frame,
                    "source_monotonic_ns": sequence * 20_000_000,
                    "pcm_f32le_base64": base64.b64encode(raw).decode("ascii"),
                }
            )
        send(
            {
                "type": "generation.end",
                "worker_protocol_version": WORKER_PROTOCOL_VERSION,
                "rpc_id": rpc_base + 1,
                "generation_id": generation_id,
            }
        )
        output = bytearray()
        sequences: list[int] = []
        while True:
            message = _receive(process)
            if message["type"] == "generation.completed":
                break
            assert message["type"] == "audio.output"
            sequences.append(int(message["sequence"]))
            output.extend(base64.b64decode(str(message["pcm_f32le_base64"])))
        assert sequences == list(range(25))
        assert len(output) == len(pcm_input)
        assert output != pcm_input
        assert numpy.isfinite(struct.unpack(f"<{len(output) // 4}f", output)).all()
        return bytes(output)

    try:
        send(
            {
                "type": "worker.hello",
                "worker_protocol_version": WORKER_PROTOCOL_VERSION,
                "rpc_id": 1,
                "profile_id": "vc.openvoice-v2-offline.v1",
                "pipeline_id": "real-smoke",
                "configuration_hash": configuration.configuration_hash,
            }
        )
        ready = _receive(process)
        assert ready["type"] == "worker.ready"
        assert ready["implementation_revision"] == (
            f"{IMPLEMENTATION_REVISION}+sha256:"
            f"{configuration.runtime_identity.implementation_sha256}"
        )
        assert ready["weight_revision"] == configuration.weight_revision
        first = render(1, 10)
        second = render(2, 20)
        assert first == second
        assert hashlib.sha256(first).hexdigest() == expected_output_digest
        send(
            {
                "type": "worker.close",
                "worker_protocol_version": WORKER_PROTOCOL_VERSION,
                "rpc_id": 30,
            }
        )
        assert _receive(process)["type"] == "worker.closed"
        process.stdin.close()
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
