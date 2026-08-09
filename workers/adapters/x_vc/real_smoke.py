from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import statistics
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from workers.runtime import ArtifactSpec, AudioFrame, WorkerProfile, WorkerSupervisor

from .backend import (
    CHECKPOINT_SHA256,
    CONFIG_SHA256,
    ERES_CONFIG_SHA256,
    ERES_MODEL_SHA256,
    GLM_CONFIG_SHA256,
    GLM_MODEL_SHA256,
    GLM_PREPROCESSOR_SHA256,
    INPUT_SAMPLE_RATE,
    OUTPUT_RESAMPLER_REVISION,
    SOURCE_PREPROCESSING_REVISION,
    WORKER_PACKAGE_NAME,
    XvcConfiguration,
    load_target_authorization,
    sha256_file,
)

FRAME_SAMPLES = 960
SOURCE_FRAMES = 25
_LOCKED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)")


def _canonical_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def locked_packages(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LOCKED_REQUIREMENT.match(line)
        if match is not None:
            packages[_canonical_package_name(match.group(1))] = match.group(2)
    if not packages:
        raise ValueError("X-VC runtime lock contains no pinned packages")
    return packages


def runtime_inventory() -> dict[str, Any]:
    packages = {
        _canonical_package_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
    }
    worker_spec = importlib.util.find_spec("workers.adapters.x_vc.worker")
    if worker_spec is None or worker_spec.origin is None:
        raise ValueError("installed X-VC worker module is unavailable")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "interpreter_path": str(Path(sys.executable).resolve(strict=True)),
        "interpreter_sha256": sha256_file(Path(sys.executable).resolve(strict=True)),
        "packages": dict(sorted(packages.items())),
        "worker_module_path": str(Path(worker_spec.origin).resolve(strict=True)),
    }


def verify_runtime(configuration: XvcConfiguration) -> dict[str, Any]:
    if Path.cwd() != Path("/tmp"):
        raise ValueError("X-VC real smoke must run with /tmp as cwd")
    if "PYTHONPATH" in os.environ:
        raise ValueError("X-VC real smoke requires PYTHONPATH to be unset")
    inventory = runtime_inventory()
    expected = locked_packages(configuration.runtime_lock_path)
    expected[WORKER_PACKAGE_NAME] = configuration.worker_package_version
    if inventory["packages"] != expected:
        installed = inventory["packages"]
        missing = sorted(expected.keys() - installed.keys())
        extra = sorted(installed.keys() - expected.keys())
        mismatched = sorted(
            name
            for name in expected.keys() & installed.keys()
            if expected[name] != installed[name]
        )
        raise ValueError(
            "X-VC runtime differs from lock plus worker wheel: "
            f"missing={missing}, extra={extra}, mismatched={mismatched}"
        )
    runtime_root = Path(sys.prefix).resolve(strict=True)
    if not Path(inventory["worker_module_path"]).is_relative_to(runtime_root):
        raise ValueError("X-VC worker was not imported from the isolated runtime")
    return inventory


def verify_network_isolation() -> dict[str, bool]:
    program = """
from workers.adapters.x_vc.network_isolation import deny_non_unix_sockets
deny_non_unix_sockets()
import _socket
results = {}
domains = (
    ("af_inet_denied", _socket.AF_INET),
    ("af_inet6_denied", _socket.AF_INET6),
)
for name, domain in domains:
    try:
        _socket.socket(domain, _socket.SOCK_DGRAM)
    except PermissionError:
        results[name] = True
    else:
        results[name] = False
unix_socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
unix_socket.close()
results["af_unix_allowed"] = True
import json
print(json.dumps(results, sort_keys=True))
"""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PYTHONPATH", "PYTHONHOME"}
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        check=True,
        capture_output=True,
        cwd="/tmp",
        env=environment,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    if result != {
        "af_inet6_denied": True,
        "af_inet_denied": True,
        "af_unix_allowed": True,
    }:
        raise ValueError("X-VC seccomp socket policy did not fail closed")
    return result


def verify_context_resampler() -> float:
    program = """
from workers.adapters.x_vc.network_isolation import deny_non_unix_sockets
deny_non_unix_sockets()
import torch
import torchaudio
from workers.adapters.x_vc.backend import (
    INPUT_SAMPLE_RATE,
    NATIVE_CURRENT_SAMPLES,
    NATIVE_LOOKAHEAD_SAMPLES,
    NATIVE_SAMPLE_RATE,
    NATIVE_SMOOTH_SAMPLES,
    resample_current_with_context,
)
count = 4 * NATIVE_CURRENT_SAMPLES
source = torch.sin(
    2 * torch.pi * 440 * torch.arange(count, dtype=torch.float32) / NATIVE_SAMPLE_RATE
).reshape(1, 1, -1)
continuous = torchaudio.functional.resample(
    source,
    NATIVE_SAMPLE_RATE,
    INPUT_SAMPLE_RATE,
    lowpass_filter_width=6,
    rolloff=0.99,
    resampling_method="sinc_interp_hann",
)
chunks = []
for index in range(4):
    start = index * NATIVE_CURRENT_SAMPLES
    current = source[..., start : start + NATIVE_CURRENT_SAMPLES]
    left = source[..., max(0, start - NATIVE_SMOOTH_SAMPLES) : start]
    if left.shape[-1] < NATIVE_SMOOTH_SAMPLES:
        left_padding = NATIVE_SMOOTH_SAMPLES - left.shape[-1]
        left = torch.nn.functional.pad(left, (left_padding, 0))
    right_start = start + NATIVE_CURRENT_SAMPLES
    right = source[
        ..., right_start : right_start + NATIVE_LOOKAHEAD_SAMPLES
    ]
    if right.shape[-1] < NATIVE_LOOKAHEAD_SAMPLES:
        right_padding = NATIVE_LOOKAHEAD_SAMPLES - right.shape[-1]
        right = torch.nn.functional.pad(right, (0, right_padding))
    chunks.append(
        resample_current_with_context(torch, torchaudio, current, right, left)
    )
chunked = torch.cat(chunks, dim=-1)
print(torch.max(torch.abs(continuous - chunked)).item())
"""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PYTHONPATH", "PYTHONHOME"}
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program],
        check=True,
        capture_output=True,
        cwd="/tmp",
        env=environment,
        text=True,
        timeout=60,
    )
    error = float(completed.stdout.strip())
    if error > 1e-6:
        raise ValueError("X-VC context resampler exceeded its error bound")
    return error


def _profile(configuration: XvcConfiguration) -> WorkerProfile:
    environment = configuration.worker_environment()
    environment.update(
        {
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "LIVECONV_XVC_GLM_CONFIG_PATH": str(configuration.glm_root / "config.json"),
            "LIVECONV_XVC_GLM_PREPROCESSOR_PATH": str(
                configuration.glm_root / "preprocessor_config.json"
            ),
            "LIVECONV_XVC_GLM_MODEL_PATH": str(
                configuration.glm_root / "model.safetensors"
            ),
            "LIVECONV_XVC_ERES_CONFIG_PATH": str(
                configuration.eres_root / "configuration.json"
            ),
            "LIVECONV_XVC_ERES_MODEL_PATH": str(
                configuration.eres_root / "pretrained_eres2net.ckpt"
            ),
        }
    )
    artifacts = (
        ArtifactSpec("LIVECONV_XVC_CONFIG_PATH", CONFIG_SHA256),
        ArtifactSpec("LIVECONV_XVC_CHECKPOINT_PATH", CHECKPOINT_SHA256),
        ArtifactSpec("LIVECONV_XVC_GLM_CONFIG_PATH", GLM_CONFIG_SHA256),
        ArtifactSpec("LIVECONV_XVC_GLM_PREPROCESSOR_PATH", GLM_PREPROCESSOR_SHA256),
        ArtifactSpec("LIVECONV_XVC_GLM_MODEL_PATH", GLM_MODEL_SHA256),
        ArtifactSpec("LIVECONV_XVC_ERES_CONFIG_PATH", ERES_CONFIG_SHA256),
        ArtifactSpec("LIVECONV_XVC_ERES_MODEL_PATH", ERES_MODEL_SHA256),
        ArtifactSpec(
            "LIVECONV_XVC_TARGET_REFERENCE_PATH",
            configuration.target_reference_sha256,
        ),
        ArtifactSpec(
            "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH",
            configuration.target_authorization_sha256,
        ),
        ArtifactSpec(
            "LIVECONV_XVC_RUNTIME_LOCK_PATH", configuration.runtime_lock_sha256
        ),
        ArtifactSpec(
            "LIVECONV_XVC_WORKER_WHEEL_PATH", configuration.worker_wheel_sha256
        ),
        ArtifactSpec("LIVECONV_XVC_INTERPRETER_PATH", configuration.interpreter_sha256),
    )
    return WorkerProfile(
        profile_id="x-vc.official-gpu-smoke",
        pipeline_id="00000000-0000-0000-0000-000000000005",
        configuration_hash=configuration.configuration_hash,
        command=(
            str(configuration.interpreter_path),
            "-I",
            "-B",
            "-m",
            "workers.adapters.x_vc",
        ),
        cwd=Path("/tmp"),
        environment=environment,
        implementation_revision=configuration.implementation_revision,
        weight_revision=configuration.weight_revision,
        frame_ms=20,
        queue_budget_ms=500,
        startup_timeout_ms=300_000,
        first_output_timeout_ms=60_000,
        stall_timeout_ms=60_000,
        cancel_timeout_ms=2_000,
        close_grace_ms=5_000,
        terminate_grace_ms=1_000,
        artifacts=artifacts,
    )


def _japanese_samples(path: Path, expected_sha256: str) -> list[float]:
    if sha256_file(path) != expected_sha256:
        raise ValueError("X-VC smoke source digest does not match")
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
            raise ValueError("X-VC smoke source must be mono PCM16")
        sample_rate = stream.getframerate()
        count = stream.getnframes()
        pcm = stream.readframes(count)
    values = [value / 32768 for value in struct.unpack(f"<{count}h", pcm)]
    if sample_rate == INPUT_SAMPLE_RATE:
        samples = values
    elif sample_rate == INPUT_SAMPLE_RATE // 2:
        samples = []
        for index, value in enumerate(values):
            following = values[min(index + 1, len(values) - 1)]
            samples.extend((value, (value + following) * 0.5))
    else:
        raise ValueError("X-VC smoke source must be 24 or 48 kHz")
    remainder = len(samples) % FRAME_SAMPLES
    if remainder:
        samples.extend([0.0] * (FRAME_SAMPLES - remainder))
    if len(samples) < SOURCE_FRAMES * FRAME_SAMPLES:
        raise ValueError("X-VC smoke source is too short")
    return samples[: SOURCE_FRAMES * FRAME_SAMPLES]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


async def run() -> dict[str, Any]:
    configuration = XvcConfiguration.from_environment()
    inventory = verify_runtime(configuration)
    network = verify_network_isolation()
    resampler_error = verify_context_resampler()
    source_path = Path(os.environ["LIVECONV_XVC_SOURCE_FIXTURE_PATH"]).resolve(
        strict=True
    )
    source_sha256 = os.environ["LIVECONV_XVC_SOURCE_FIXTURE_SHA256"]
    source = _japanese_samples(source_path, source_sha256)
    authorization = load_target_authorization(
        configuration.target_authorization_path,
        configuration.target_authorization_sha256,
        configuration.target_reference_sha256,
    )
    supervisor = WorkerSupervisor(_profile(configuration))
    converted: list[float] = []
    window_latencies: list[float] = []
    started_at = time.monotonic()
    try:
        ready = await supervisor.start()
        startup_seconds = time.monotonic() - started_at
        if ready.implementation_revision != configuration.implementation_revision:
            raise ValueError("X-VC Supervisor observed another adapter revision")
        if ready.weight_revision != configuration.weight_revision:
            raise ValueError("X-VC Supervisor observed another weight revision")
        if ready.configuration_hash != configuration.configuration_hash:
            raise ValueError("X-VC Supervisor observed another configuration")
        health = await supervisor.health()
        if not health.ready or health.capacity_frames != 25:
            raise ValueError("X-VC worker health contract failed")

        await supervisor.start_generation(1)
        output_count = 0
        for sequence in range(SOURCE_FRAMES):
            offset = sequence * FRAME_SAMPLES
            await supervisor.push_audio(
                AudioFrame.from_samples(
                    generation_id=1,
                    sequence=sequence,
                    sample_rate=INPUT_SAMPLE_RATE,
                    channels=1,
                    samples_per_channel=FRAME_SAMPLES,
                    source_monotonic_ns=sequence * 20_000_000,
                    samples=source[offset : offset + FRAME_SAMPLES],
                )
            )
            if sequence in {11, 17, 23}:
                batch_started = time.monotonic()
                for expected in range(output_count, output_count + 6):
                    output = await supervisor.next_output()
                    if output.sequence != expected:
                        raise ValueError("X-VC output sequence changed")
                    converted.extend(output.unpack_samples())
                window_latencies.append(time.monotonic() - batch_started)
                output_count += 6

        end_task = asyncio.create_task(supervisor.end_generation(1))
        batch_started = time.monotonic()
        while output_count < SOURCE_FRAMES:
            output = await supervisor.next_output()
            if output.sequence != output_count:
                raise ValueError("X-VC final output sequence changed")
            converted.extend(output.unpack_samples())
            output_count += 1
        await end_task
        window_latencies.append(time.monotonic() - batch_started)

        await supervisor.start_generation(2)
        for sequence in range(12):
            offset = sequence * FRAME_SAMPLES
            await supervisor.push_audio(
                AudioFrame.from_samples(
                    generation_id=2,
                    sequence=sequence,
                    sample_rate=INPUT_SAMPLE_RATE,
                    channels=1,
                    samples_per_channel=FRAME_SAMPLES,
                    source_monotonic_ns=sequence * 20_000_000,
                    samples=source[offset : offset + FRAME_SAMPLES],
                )
            )
        cancel_started = time.monotonic()
        await supervisor.cancel_generation(2)
        cancel_seconds = time.monotonic() - cancel_started
        if supervisor.take_output_nowait() is not None:
            raise ValueError("X-VC Supervisor exposed stale canceled output")

        await supervisor.start_generation(3)
        await supervisor.push_audio(
            AudioFrame.from_samples(
                generation_id=3,
                sequence=0,
                sample_rate=INPUT_SAMPLE_RATE,
                channels=1,
                samples_per_channel=FRAME_SAMPLES,
                source_monotonic_ns=0,
                samples=source[:FRAME_SAMPLES],
            )
        )
        post_cancel_end = asyncio.create_task(supervisor.end_generation(3))
        post_cancel_output = await supervisor.next_output()
        await post_cancel_end
        if post_cancel_output.generation_id != 3 or post_cancel_output.sequence != 0:
            raise ValueError("X-VC post-cancel generation identity changed")
        if supervisor.take_output_nowait() is not None:
            raise ValueError("X-VC post-cancel output queue was not empty")
    finally:
        await supervisor.close()

    if len(converted) != len(source):
        raise ValueError("X-VC output length changed")
    if not all(math.isfinite(value) and abs(value) <= 1 for value in converted):
        raise ValueError("X-VC output PCM was invalid")
    if not any(
        abs(output - original) > 1e-5 for output, original in zip(converted, source)
    ):
        raise ValueError("X-VC real model did not change PCM")
    raw = struct.pack(f"<{len(converted)}f", *converted)
    return {
        "schema_version": "liveconv-x-vc-worker-smoke-v2",
        "status": "technical-smoke-pass",
        "quality_status": "fail-nonselectable",
        "identity": {
            "configuration_hash": configuration.configuration_hash,
            "implementation_revision": configuration.implementation_revision,
            "weight_revision": configuration.weight_revision,
            "adapter_source_sha256": configuration.adapter_source_sha256,
            "runtime_lock_sha256": configuration.runtime_lock_sha256,
            "worker_wheel_sha256": configuration.worker_wheel_sha256,
            "interpreter_sha256": configuration.interpreter_sha256,
            "target_authorization_sha256": (configuration.target_authorization_sha256),
        },
        "runtime": {
            **inventory,
            "package_count": len(inventory["packages"]),
            "inventory_matches_lock_plus_worker_wheel": True,
            "worker_cwd": "/tmp",
            "worker_bytecode_disabled": True,
            "worker_pythonpath_unset": True,
            "worker_isolated_mode": True,
        },
        "authorization": {
            "record_path": str(configuration.target_authorization_path),
            "record_sha256": configuration.target_authorization_sha256,
            "authorization_id": authorization.authorization_id,
            "owner": authorization.owner,
            "authorization_record": authorization.authorization_record,
            "permitted_purpose": authorization.permitted_purpose,
            "retention_policy": authorization.retention_policy,
            "deletion_path": authorization.deletion_path,
            "classification": authorization.classification,
            "target_reference_sha256": authorization.target_reference_sha256,
        },
        "network_isolation": {
            **network,
            "mechanism": "seccomp-deny-socket-domain-ne-AF_UNIX",
            "installed_before_model_imports": True,
        },
        "source_fixture_sha256": source_sha256,
        "source_fixture_frames_used": SOURCE_FRAMES,
        "source_preprocessing_revision": SOURCE_PREPROCESSING_REVISION,
        "output_resampler_revision": OUTPUT_RESAMPLER_REVISION,
        "resampler_max_absolute_error": resampler_error,
        "startup_seconds": startup_seconds,
        "output_frames": output_count,
        "output_samples": len(converted),
        "finite_normalized_pcm": True,
        "output_sha256_f32le": hashlib.sha256(raw).hexdigest(),
        "window_latency_seconds": window_latencies,
        "window_latency_p50_seconds": statistics.median(window_latencies),
        "window_latency_p95_seconds": _percentile(window_latencies, 0.95),
        "cancel_ack_seconds": cancel_seconds,
        "supervisor_stale_output_after_cancel": False,
        "post_cancel_generation_completed": True,
        "deterministic_replay_assessed": False,
    }


def main() -> int:
    report = asyncio.run(asyncio.wait_for(run(), timeout=420))
    report_path = Path(os.environ["LIVECONV_XVC_SMOKE_REPORT_PATH"]).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
