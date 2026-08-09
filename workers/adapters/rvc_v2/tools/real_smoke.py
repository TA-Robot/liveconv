from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from workers.adapters.rvc_v2.backend import (
    ADAPTER_REVISION,
    INFERENCE_BATCH_FRAMES,
    RESIDENT_CAPACITY_FRAMES,
    AdapterRuntimeBinding,
    RvcConfiguration,
)
from workers.runtime import ArtifactSpec, AudioFrame, WorkerProfile, WorkerSupervisor

FRAME_MS = 20
_LOCKED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def locked_packages(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LOCKED_REQUIREMENT.match(line)
        if match is not None:
            packages[canonical_package_name(match.group(1))] = match.group(2)
    if not packages:
        raise ValueError("runtime lock contains no pinned packages")
    return packages


def runtime_binding_sha256(
    dependency_lock: Path, worker_wheel: Path, worker_package_version: str
) -> str:
    material = {
        "dependency_lock_sha256": sha256_file(dependency_lock),
        "worker_package_version": worker_package_version,
        "worker_wheel_sha256": sha256_file(worker_wheel),
    }
    encoded = json.dumps(material, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return hashlib.sha256(encoded).hexdigest()


def read_pcm16_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2:
            raise ValueError("source must be mono PCM16 WAV")
        sample_rate = stream.getframerate()
        samples = np.frombuffer(
            stream.readframes(stream.getnframes()), dtype="<i2"
        ).astype(np.float32)
    return samples / 32768.0, sample_rate


def resample_linear(
    samples: np.ndarray, source_rate: int, target_rate: int
) -> np.ndarray:
    if source_rate == target_rate:
        return samples.copy()
    output_size = round(samples.size * target_rate / source_rate)
    return np.interp(
        np.arange(output_size) * source_rate / target_rate,
        np.arange(samples.size),
        samples,
    ).astype(np.float32)


def write_pcm16_mono(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm16 = (np.clip(samples, -1.0, 0.999969) * 32768.0).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm16.tobytes())


def runtime_inventory(
    runtime_python: Path, worker_wheel: Path, worker_wheel_sha256: str
) -> dict[str, Any]:
    program = """
import importlib.metadata, json, platform, sys, torch
import workers.adapters.rvc_v2.worker as worker_module
from pathlib import Path
from workers.adapters.rvc_v2.backend import AdapterRuntimeBinding
binding = AdapterRuntimeBinding.inspect(Path(sys.argv[1]), sys.argv[2])
packages = {
    d.metadata['Name'].lower(): d.version
    for d in importlib.metadata.distributions()
}
gpu = None
if torch.cuda.is_available():
    index = torch.cuda.current_device()
    properties = torch.cuda.get_device_properties(index)
    gpu = {
        'name': properties.name,
        'capability': list(torch.cuda.get_device_capability(index)),
        'total_memory_bytes': properties.total_memory,
    }
print(json.dumps({
    'python': platform.python_version(),
    'torch': torch.__version__,
    'torch_cuda': torch.version.cuda,
    'packages': dict(sorted(packages.items())),
    'gpu': gpu,
    'worker_module_path': worker_module.__file__,
    'adapter_runtime': {
        'worker_wheel_path': str(binding.worker_wheel_path),
        'worker_wheel_sha256': binding.worker_wheel_sha256,
        'worker_wheel_record_sha256': binding.worker_wheel_record_sha256,
        'worker_module_sha256': binding.worker_module_sha256,
        'backend_module_sha256': binding.backend_module_sha256,
        'network_isolation_module_sha256': binding.network_isolation_module_sha256,
        'requirements_lock_sha256': binding.requirements_lock_sha256,
    },
}, sort_keys=True))
"""
    environment = {
        name: value for name, value in os.environ.items() if name != "PYTHONPATH"
    }
    output = subprocess.run(
        [
            str(runtime_python),
            "-I",
            "-c",
            program,
            str(worker_wheel),
            worker_wheel_sha256,
        ],
        check=True,
        capture_output=True,
        cwd="/tmp",
        env=environment,
        text=True,
        timeout=30,
    ).stdout
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("runtime inventory was not an object")
    return value


def verify_network_isolation(runtime_python: Path) -> dict[str, bool]:
    program = """
from workers.adapters.rvc_v2.network_isolation import deny_non_unix_sockets
deny_non_unix_sockets()
import _socket
results = {}
for name, domain in (
    ('af_inet_denied', _socket.AF_INET),
    ('af_inet6_denied', _socket.AF_INET6),
):
    try:
        _socket.socket(domain, _socket.SOCK_DGRAM)
    except PermissionError:
        results[name] = True
    else:
        results[name] = False
unix_socket = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
unix_socket.close()
results['af_unix_allowed'] = True
import json
print(json.dumps(results, sort_keys=True))
"""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PYTHONPATH", "PYTHONHOME"}
    }
    completed = subprocess.run(
        [str(runtime_python), "-I", "-c", program],
        check=True,
        capture_output=True,
        cwd="/tmp",
        env=environment,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    expected = {
        "af_inet6_denied": True,
        "af_inet_denied": True,
        "af_unix_allowed": True,
    }
    if result != expected:
        raise ValueError("RVC seccomp socket policy did not fail closed")
    return result


def frames_for(
    samples: np.ndarray, *, generation_id: int, sample_rate: int
) -> tuple[list[AudioFrame], np.ndarray]:
    frame_size = sample_rate * FRAME_MS // 1000
    padded_size = ((samples.size + frame_size - 1) // frame_size) * frame_size
    padded = np.pad(samples, (0, padded_size - samples.size))
    frames = [
        AudioFrame.from_samples(
            generation_id=generation_id,
            sequence=sequence,
            sample_rate=sample_rate,
            channels=1,
            samples_per_channel=frame_size,
            source_monotonic_ns=sequence * FRAME_MS * 1_000_000,
            samples=padded[offset : offset + frame_size],
        )
        for sequence, offset in enumerate(range(0, padded.size, frame_size))
    ]
    return frames, padded


async def run_generation(
    supervisor: WorkerSupervisor,
    frames: list[AudioFrame],
) -> tuple[list[AudioFrame], float, int]:
    generation_id = frames[0].generation_id
    await supervisor.start_generation(generation_id)
    outputs: list[AudioFrame] = []
    started = time.perf_counter()
    maximum_observed_resident_frames = 0
    for offset in range(0, len(frames), INFERENCE_BATCH_FRAMES):
        batch = frames[offset : offset + INFERENCE_BATCH_FRAMES]
        for frame in batch:
            await supervisor.push_audio(frame)
        health = await supervisor.health()
        maximum_observed_resident_frames = max(
            maximum_observed_resident_frames, health.queue_depth_frames
        )
        end_task = None
        if offset + len(batch) == len(frames):
            end_task = asyncio.create_task(supervisor.end_generation(generation_id))
        for _ in batch:
            outputs.append(await supervisor.next_output())
        if end_task is not None:
            await end_task
    return (
        outputs,
        time.perf_counter() - started,
        maximum_observed_resident_frames,
    )


def profile_for(
    configuration: RvcConfiguration,
    runtime_python: Path,
    worker_cwd: Path,
) -> WorkerProfile:
    environment = configuration.worker_environment()
    environment["PATH"] = os.environ["PATH"]
    for name in ("LD_LIBRARY_PATH", "LANG", "LC_ALL"):
        if name in os.environ:
            environment[name] = os.environ[name]
    artifacts = [
        ArtifactSpec(
            "LIVECONV_RVC_V2_CHECKPOINT_PATH", configuration.checkpoint_sha256
        ),
        ArtifactSpec(
            "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
            configuration.adapter_runtime.worker_wheel_sha256,
        ),
    ]
    if configuration.index_path is not None:
        assert configuration.index_sha256 is not None
        artifacts.append(
            ArtifactSpec("LIVECONV_RVC_V2_INDEX_PATH", configuration.index_sha256)
        )
    return WorkerProfile(
        profile_id="rvc-v2.real-smoke",
        pipeline_id="00000000-0000-0000-0000-000000000002",
        configuration_hash=configuration.configuration_hash,
        command=(str(runtime_python), "-m", "workers.adapters.rvc_v2.worker"),
        cwd=worker_cwd,
        environment=environment,
        implementation_revision=(
            f"{ADAPTER_REVISION}+rvc.{configuration.source_revision}"
        ),
        weight_revision=f"sha256:{configuration.checkpoint_sha256}",
        frame_ms=FRAME_MS,
        queue_budget_ms=FRAME_MS * INFERENCE_BATCH_FRAMES,
        startup_timeout_ms=180_000,
        first_output_timeout_ms=10_000,
        stall_timeout_ms=10_000,
        cancel_timeout_ms=1_000,
        close_grace_ms=3_000,
        terminate_grace_ms=1_000,
        artifacts=tuple(artifacts),
    )


async def run(arguments: argparse.Namespace) -> dict[str, Any]:
    runtime_python = arguments.runtime_python.absolute()
    if not runtime_python.is_file():
        raise ValueError("runtime-python must identify a file")
    runtime_lock = arguments.runtime_lock.resolve(strict=True)
    worker_wheel = arguments.worker_wheel.resolve(strict=True)
    worker_cwd = arguments.worker_cwd.resolve(strict=True)
    if not worker_cwd.is_dir():
        raise ValueError("worker-cwd must identify a directory")
    inventory = runtime_inventory(
        runtime_python, worker_wheel, arguments.worker_wheel_sha256
    )
    network_isolation = verify_network_isolation(runtime_python)
    binding_value = inventory["adapter_runtime"]
    adapter_runtime = AdapterRuntimeBinding(
        worker_wheel_path=Path(binding_value["worker_wheel_path"]),
        worker_wheel_sha256=binding_value["worker_wheel_sha256"],
        worker_wheel_record_sha256=binding_value["worker_wheel_record_sha256"],
        worker_module_sha256=binding_value["worker_module_sha256"],
        backend_module_sha256=binding_value["backend_module_sha256"],
        network_isolation_module_sha256=binding_value[
            "network_isolation_module_sha256"
        ],
        requirements_lock_sha256=binding_value["requirements_lock_sha256"],
    )
    configuration = RvcConfiguration(
        source_root=arguments.source_root.resolve(),
        checkpoint_path=arguments.checkpoint.resolve(),
        source_revision=arguments.source_revision,
        checkpoint_sha256=arguments.checkpoint_sha256,
        adapter_runtime=adapter_runtime,
        index_path=arguments.index.resolve() if arguments.index else None,
        index_sha256=arguments.index_sha256,
        speaker_id=arguments.speaker_id,
        pitch_shift=arguments.pitch_shift,
        f0_method=arguments.f0_method,
        index_rate=arguments.index_rate,
        rms_mix_rate=arguments.rms_mix_rate,
        sample_rate=arguments.sample_rate,
        block_ms=500,
        crossfade_ms=arguments.crossfade_ms,
        context_ms=arguments.context_ms,
    )
    configuration.validate(verify_adapter_runtime=False)
    actual_wheel_sha256 = sha256_file(worker_wheel)
    if actual_wheel_sha256 != arguments.worker_wheel_sha256:
        raise ValueError("worker wheel SHA-256 does not match")
    installed_worker_version = inventory["packages"].get("liveconv-worker-runtime")
    if installed_worker_version != arguments.worker_package_version:
        raise ValueError("installed worker package version does not match")
    expected_packages = locked_packages(runtime_lock)
    expected_packages["liveconv-worker-runtime"] = arguments.worker_package_version
    installed_packages = {
        canonical_package_name(name): version
        for name, version in inventory["packages"].items()
    }
    if installed_packages != expected_packages:
        missing = sorted(expected_packages.keys() - installed_packages.keys())
        extra = sorted(installed_packages.keys() - expected_packages.keys())
        mismatched = sorted(
            name
            for name in expected_packages.keys() & installed_packages.keys()
            if expected_packages[name] != installed_packages[name]
        )
        raise ValueError(
            "runtime inventory differs from lock plus worker wheel: "
            f"missing={missing}, extra={extra}, mismatched={mismatched}"
        )
    runtime_root = runtime_python.parent.parent.resolve()
    worker_module_path = Path(inventory["worker_module_path"]).resolve(strict=True)
    if not worker_module_path.is_relative_to(runtime_root):
        raise ValueError("worker module was not imported from the isolated runtime")
    source, source_rate = read_pcm16_mono(arguments.source_wav)
    source = resample_linear(source, source_rate, configuration.sample_rate)
    supervisor = WorkerSupervisor(
        profile_for(configuration, runtime_python, worker_cwd)
    )
    try:
        startup_started = time.perf_counter()
        ready = await supervisor.start()
        cold_start_seconds = time.perf_counter() - startup_started
        health = await supervisor.health()
        next_generation = 1
        for _ in range(arguments.warmup_runs):
            frames, _ = frames_for(
                source,
                generation_id=next_generation,
                sample_rate=configuration.sample_rate,
            )
            await run_generation(supervisor, frames)
            next_generation += 1

        measured: list[float] = []
        outputs: list[AudioFrame] = []
        maximum_observed_resident_frames = 0
        padded = source
        for _ in range(arguments.measured_runs):
            frames, padded = frames_for(
                source,
                generation_id=next_generation,
                sample_rate=configuration.sample_rate,
            )
            outputs, elapsed, resident_frames = await run_generation(supervisor, frames)
            measured.append(elapsed)
            maximum_observed_resident_frames = max(
                maximum_observed_resident_frames, resident_frames
            )
            next_generation += 1

        cancel_frames, _ = frames_for(
            source,
            generation_id=next_generation,
            sample_rate=configuration.sample_rate,
        )
        await supervisor.start_generation(next_generation)
        for frame in cancel_frames[:INFERENCE_BATCH_FRAMES]:
            await supervisor.push_audio(frame)
        cancel_started = time.perf_counter()
        canceled = await supervisor.cancel_generation(next_generation)
        cancel_seconds = time.perf_counter() - cancel_started
        await asyncio.sleep(0.2)
        stale_output = supervisor.take_output_nowait()
    finally:
        await supervisor.close()

    output = np.concatenate(
        [np.asarray(frame.unpack_samples(), dtype=np.float32) for frame in outputs]
    )
    write_pcm16_mono(arguments.output_wav, output, configuration.sample_rate)
    duration = output.size / configuration.sample_rate
    report = {
        "schema_version": "liveconv-rvc-v2-real-smoke-v1",
        "timing_rules": {
            "cold_start": (
                "fresh worker spawn through worker.ready; includes upstream prewarm"
            ),
            "warmup": f"{arguments.warmup_runs} complete generation(s), excluded",
            "warm": f"{arguments.measured_runs} complete generation(s) after warmup",
        },
        "identity": {
            "configuration_hash": configuration.configuration_hash,
            "canonical_material": configuration.identity_material(),
            "implementation_revision": ready.implementation_revision,
            "weight_revision": ready.weight_revision,
        },
        "runtime": {
            "lock_sha256": sha256_file(runtime_lock),
            "lock_path": str(runtime_lock),
            "worker_wheel_sha256": actual_wheel_sha256,
            "worker_wheel_path": str(worker_wheel),
            "worker_package_version": arguments.worker_package_version,
            "runtime_binding_sha256": runtime_binding_sha256(
                runtime_lock, worker_wheel, arguments.worker_package_version
            ),
            "worker_cwd": str(worker_cwd),
            "worker_pythonpath_unset": True,
            "inventory_matches_lock_plus_worker_wheel": True,
            "host": {
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            **inventory,
        },
        "network_isolation": {
            **network_isolation,
            "mechanism": "seccomp-deny-socket-domain-ne-AF_UNIX",
            "installed_before_model_imports": True,
        },
        "operations": {
            "health_ready": health.ready,
            "capacity_frames": health.capacity_frames,
            "inference_batch_frames": INFERENCE_BATCH_FRAMES,
            "supervisor_queue_capacity_frames": supervisor.input_capacity_frames,
            "maximum_observed_resident_frames": maximum_observed_resident_frames,
            "continuous_generation_frames": len(outputs),
            "frame_count": len(outputs),
            "sequence_exact": [frame.sequence for frame in outputs]
            == list(range(len(outputs))),
            "timestamp_exact": all(
                frame.source_monotonic_ns == frame.sequence * FRAME_MS * 1_000_000
                for frame in outputs
            ),
            "cancel_generation_id": canceled.generation_id,
            "cancel_seconds": cancel_seconds,
            "stale_output_after_cancel": stale_output is not None,
        },
        "latency": {
            "cold_start_seconds": cold_start_seconds,
            "warm_seconds": measured,
            "warm_p50_seconds": statistics.median(measured),
            "warm_p95_seconds": float(np.percentile(measured, 95)),
            "warm_rtf_p50": statistics.median(measured) / duration,
            "warm_rtf_p95": float(np.percentile(measured, 95)) / duration,
        },
        "audio": {
            "source_sha256": sha256_file(arguments.source_wav),
            "output_sha256": sha256_file(arguments.output_wav),
            "sample_rate": configuration.sample_rate,
            "samples": int(output.size),
            "duration_seconds": duration,
            "finite": bool(np.isfinite(output).all()),
            "peak": float(np.abs(output).max()),
            "rms": float(np.sqrt(np.mean(np.square(output)))),
            "clipped_fraction": float(np.mean(np.abs(output) >= 0.999)),
            "different_fraction": float(np.mean(output != padded[: output.size])),
            "mean_absolute_difference": float(
                np.mean(np.abs(output - padded[: output.size]))
            ),
        },
    }
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if arguments.streaming_report is not None:
        checks = {
            "bounded_queues": health.capacity_frames == RESIDENT_CAPACITY_FRAMES,
            "supervisor_queue_bound": (
                supervisor.input_capacity_frames == INFERENCE_BATCH_FRAMES
            ),
            "continuous_generation_over_inference_batch": (
                len(outputs) > INFERENCE_BATCH_FRAMES
            ),
            "stale_generation_discard": stale_output is None,
            "interruption_cancel": cancel_seconds <= 1.0,
        }
        passed = all(checks.values())
        streaming = {
            "schema_version": 1,
            "report_type": "streaming-operations-evidence",
            "evaluator": {
                "implementation": "workers.adapters.rvc_v2.tools.real_smoke",
                "revision": "liveconv-rvc-v2-real-smoke==1.0.0",
                "runtime_lock": {
                    "revision": "liveconv-rvc-v2-hash-locked-runtime-v1",
                    "sha256": report["runtime"]["runtime_binding_sha256"],
                    "packages": inventory["packages"],
                },
            },
            "artifacts": {
                "source_sha256": report["audio"]["source_sha256"],
                "output_sha256": report["audio"]["output_sha256"],
            },
            "policy": {
                "label": "ADR-0002-worker-v1-operational-invariants",
                "status": "approved",
            },
            "streaming_operations": {
                "trace_sha256": sha256_file(arguments.report),
                "checks": checks,
            },
            "evaluation_lane": {
                "status": "pass" if passed else "fail",
                "summary": (
                    "The wheel-bound RVC worker passed worker-v1 operations."
                    if passed
                    else "The wheel-bound RVC worker failed worker-v1 operations."
                ),
                "evidence": [
                    f"{len(outputs)}/{len(outputs)} output frames retained identity",
                    f"warm RTF P50/P95={report['latency']['warm_rtf_p50']:.5f}/"
                    f"{report['latency']['warm_rtf_p95']:.5f}",
                    f"cancel acknowledgment={cancel_seconds:.6f} seconds; "
                    f"stale output={stale_output is not None}",
                    "worker imported from the retained wheel with PYTHONPATH unset",
                ],
            },
            "limitations": [
                "This bounded smoke covers one synthetic utterance, not soak behavior.",
                "The upstream engine converts 500 ms batches, not each 20 ms frame.",
            ],
        }
        arguments.streaming_report.parent.mkdir(parents=True, exist_ok=True)
        arguments.streaming_report.write_text(
            json.dumps(streaming, indent=2) + "\n", encoding="utf-8"
        )
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run pinned real RVC worker evidence")
    result.add_argument("--runtime-python", type=Path, required=True)
    result.add_argument("--runtime-lock", type=Path, required=True)
    result.add_argument("--worker-wheel", type=Path, required=True)
    result.add_argument("--worker-wheel-sha256", required=True)
    result.add_argument("--worker-package-version", required=True)
    result.add_argument("--worker-cwd", type=Path, default=Path("/tmp"))
    result.add_argument("--source-root", type=Path, required=True)
    result.add_argument("--source-revision", required=True)
    result.add_argument("--checkpoint", type=Path, required=True)
    result.add_argument("--checkpoint-sha256", required=True)
    result.add_argument("--index", type=Path)
    result.add_argument("--index-sha256")
    result.add_argument("--source-wav", type=Path, required=True)
    result.add_argument("--output-wav", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--streaming-report", type=Path)
    result.add_argument("--speaker-id", type=int, default=0)
    result.add_argument("--pitch-shift", type=int, default=0)
    result.add_argument("--f0-method", choices=("rmvpe", "pm"), default="rmvpe")
    result.add_argument("--index-rate", type=float, default=0.0)
    result.add_argument("--rms-mix-rate", type=float, default=1.0)
    result.add_argument("--sample-rate", type=int, default=48_000)
    result.add_argument("--crossfade-ms", type=int, default=50)
    result.add_argument("--context-ms", type=int, default=2_500)
    result.add_argument("--warmup-runs", type=int, default=1)
    result.add_argument("--measured-runs", type=int, default=5)
    return result


def main() -> int:
    arguments = parser().parse_args()
    if arguments.warmup_runs < 1 or arguments.measured_runs < 2:
        raise SystemExit("warmup-runs must be >=1 and measured-runs must be >=2")
    if bool(arguments.index) != bool(arguments.index_sha256):
        raise SystemExit("index and index-sha256 must be supplied together")
    report = asyncio.run(run(arguments))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
