#!/usr/bin/env python3
"""Run the EXP-032 candidate through the retained XvcWorker state machine.

This is a listen-now system-path probe.  It deliberately does not mint or bind
a Gateway profile: the retained worker identity remains unchanged until an
operator keep.  The probe temporarily supplies the measured 120 ms geometry to
the existing bounded queue/cancellation state machine, cancels one in-flight
generation, and retains the next real-time-paced generation as listening audio.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import workers.adapters.x_vc.backend as backend_module  # noqa: E402
import workers.adapters.x_vc.worker as worker_module  # noqa: E402
from workers.adapters.x_vc.network_isolation import (  # noqa: E402
    deny_non_unix_sockets,
    require_non_unix_socket_denial,
)
from workers.runtime.codec import WORKER_PROTOCOL_VERSION  # noqa: E402

INPUT_SAMPLE_RATE = 48_000
FRAME_MS = 20
FRAME_SAMPLES = 960
CURRENT_MS = 120
SMOOTH_MS = 20
FUTURE_MS = 120
WINDOW_MS = 2_400
EXPECTED_SOURCE_SHA256 = (
    "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
)
EXPECTED_TARGET_SHA256 = (
    "76f5a4a9b989ed692a55343a7681623fa4f18e354ca04026f022e3e449195ca2"
)
EXPECTED_ADAPTER_SHA256 = (
    "e0ae0240f70968202c9214641e4a3052ad7277cc4b3ed2ac833f2394b22ea7cf"
)
EXPECTED_ADAPTER_CONFIG_SHA256 = (
    "7b9df8ad7832d589ae4129c9da7fa052610379b7d4a4168ce381eb83fd08f12d"
)
CONTROL69_E12_ADAPTER_SHA256 = (
    "efa63bdec33bcfd2816bd267c9bfa7dfd42d6a39b5c872b720db74cff01fbffe"
)
CONTROL69_E12_ADAPTER_CONFIG_SHA256 = (
    "74611b93bbbe556b328aec6ec8ecc6cc1a029ee8307d98e35165523e4f24af07"
)
EXPECTED_CONFIG_SHA256 = backend_module.CONFIG_SHA256
EXPECTED_CHECKPOINT_SHA256 = backend_module.CHECKPOINT_SHA256
EXPECTED_UPSTREAM_STREAM_SHA256 = (
    "f2fb77f226e4c5d106089a382a14cf38b1b99aebe45b4acd82b9aa48dd76eb77"
)


class SystemPathError(RuntimeError):
    """The bounded candidate system probe cannot continue."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class GeometrySnapshot:
    backend_future_ms: int
    backend_history_ms: int
    backend_lookahead_samples: int
    worker_future_ms: int
    worker_history_ms: int
    worker_lookahead_frames: int
    worker_history_frames: int


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    candidate_id: str
    adapter_sha256: str
    adapter_config_sha256: str
    adapter_name: str
    display_name: str
    output_file: str
    profile_id: str


CANDIDATE_PROFILES = {
    "expanded79-e08": CandidateProfile(
        candidate_id="expanded79-e08",
        adapter_sha256=EXPECTED_ADAPTER_SHA256,
        adapter_config_sha256=EXPECTED_ADAPTER_CONFIG_SHA256,
        adapter_name="expanded79-e08",
        display_name="X-VC human87 expanded79 epoch 8 / future 120 ms / worker",
        output_file="10-xvc-e08-future-120-system.wav",
        profile_id="xvc.exp032.e08.future-120.system-path.listen-now",
    ),
    "control69-e12": CandidateProfile(
        candidate_id="control69-e12",
        adapter_sha256=CONTROL69_E12_ADAPTER_SHA256,
        adapter_config_sha256=CONTROL69_E12_ADAPTER_CONFIG_SHA256,
        adapter_name="control69-e12",
        display_name="X-VC human87 control69 epoch 12 / future 120 ms / worker",
        output_file="10-xvc-control69-e12-future-120-system.wav",
        profile_id="xvc.exp026.control69.e12.future-120.system-path.listen-now",
    ),
}


@contextlib.contextmanager
def candidate_geometry(future_ms: int = FUTURE_MS) -> Iterator[None]:
    """Temporarily parameterize the retained worker without changing its identity."""

    if future_ms < 0 or future_ms % FRAME_MS:
        raise ValueError("future_ms must be a nonnegative multiple of 20 ms")
    history_ms = WINDOW_MS - CURRENT_MS - SMOOTH_MS - future_ms
    if history_ms < 0 or history_ms % FRAME_MS:
        raise ValueError("candidate geometry must preserve 20 ms frame boundaries")
    snapshot = GeometrySnapshot(
        backend_future_ms=backend_module.FUTURE_MS,
        backend_history_ms=backend_module.HISTORY_MS,
        backend_lookahead_samples=backend_module.NATIVE_LOOKAHEAD_SAMPLES,
        worker_future_ms=worker_module.FUTURE_MS,
        worker_history_ms=worker_module.HISTORY_MS,
        worker_lookahead_frames=worker_module.LOOKAHEAD_FRAMES,
        worker_history_frames=worker_module.HISTORY_FRAMES,
    )
    backend_module.FUTURE_MS = future_ms
    backend_module.HISTORY_MS = history_ms
    backend_module.NATIVE_LOOKAHEAD_SAMPLES = (
        backend_module.NATIVE_SAMPLE_RATE * (SMOOTH_MS + future_ms) // 1_000
    )
    worker_module.FUTURE_MS = future_ms
    worker_module.HISTORY_MS = history_ms
    worker_module.LOOKAHEAD_FRAMES = (SMOOTH_MS + future_ms) // FRAME_MS
    worker_module.HISTORY_FRAMES = history_ms // FRAME_MS
    try:
        if (
            worker_module.HISTORY_FRAMES
            + worker_module.CURRENT_FRAMES
            + worker_module.LOOKAHEAD_FRAMES
            != worker_module.WINDOW_FRAMES
        ):
            raise ValueError("candidate geometry changed the bounded window size")
        yield
    finally:
        backend_module.FUTURE_MS = snapshot.backend_future_ms
        backend_module.HISTORY_MS = snapshot.backend_history_ms
        backend_module.NATIVE_LOOKAHEAD_SAMPLES = snapshot.backend_lookahead_samples
        worker_module.FUTURE_MS = snapshot.worker_future_ms
        worker_module.HISTORY_MS = snapshot.worker_history_ms
        worker_module.LOOKAHEAD_FRAMES = snapshot.worker_lookahead_frames
        worker_module.HISTORY_FRAMES = snapshot.worker_history_frames


def control(message_type: str, rpc_id: int, **fields: object) -> dict[str, object]:
    return {
        "type": message_type,
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "rpc_id": rpc_id,
        **fields,
    }


def audio_message(
    samples: np.ndarray, *, generation_id: int, sequence: int
) -> dict[str, object]:
    if samples.shape != (FRAME_SAMPLES,) or samples.dtype != np.float32:
        raise ValueError("one float32 20 ms frame is required")
    return {
        "type": "audio.push",
        "worker_protocol_version": WORKER_PROTOCOL_VERSION,
        "generation_id": generation_id,
        "sequence": sequence,
        "sample_rate": INPUT_SAMPLE_RATE,
        "channels": 1,
        "samples_per_channel": FRAME_SAMPLES,
        "source_monotonic_ns": sequence * FRAME_MS * 1_000_000,
        "pcm_f32le_base64": base64.b64encode(samples.astype("<f4").tobytes()).decode(
            "ascii"
        ),
    }


def decode_pcm24_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 3
            or source.getframerate() != INPUT_SAMPLE_RATE
        ):
            raise SystemPathError("actual source must be mono PCM24 at 48 kHz")
        raw = source.readframes(source.getnframes())
    octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    values = (
        octets[:, 0].astype(np.int32)
        | (octets[:, 1].astype(np.int32) << 8)
        | (octets[:, 2].astype(np.int32) << 16)
    )
    values = np.where(values & 0x800000, values - 0x1000000, values)
    return (values.astype(np.float32) / 8_388_608.0).astype(np.float32, copy=False)


def frame_audio(samples: np.ndarray) -> tuple[list[np.ndarray], int]:
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise SystemPathError("source PCM is empty or non-finite")
    original_samples = int(samples.size)
    padded_count = math.ceil(original_samples / FRAME_SAMPLES) * FRAME_SAMPLES
    padded = np.pad(samples, (0, padded_count - original_samples))
    frames = [
        padded[offset : offset + FRAME_SAMPLES].astype(np.float32, copy=True)
        for offset in range(0, padded_count, FRAME_SAMPLES)
    ]
    return frames, original_samples


class CandidateBackend(backend_module.OfficialXvcBackend):
    """One exact adapter using the official per-window conversion code."""

    def __init__(
        self,
        *,
        xvc_source_root: Path,
        xvc_config: Path,
        checkpoint: Path,
        adapter_dir: Path,
        target_reference: Path,
        device_name: str,
        profile: CandidateProfile,
    ) -> None:
        require_non_unix_socket_denial()
        self._closed = False
        self._inference_started = threading.Event()
        self.chunk_compute_ms: list[float] = []
        source_root = str(xvc_source_root.resolve())
        if source_root not in sys.path:
            sys.path.insert(0, source_root)

        import torch
        from bins import infer_utils
        from models.codec.sac.model import XVC
        from models.codec.sac.utils import process_audio
        from peft import PeftModel
        from utils.file import load_config

        device = torch.device(device_name)
        torch.cuda.set_device(device)
        config = load_config(str(xvc_config))
        if "config" in config:
            config = config["config"]
        if int(config["sample_rate"]) != backend_module.NATIVE_SAMPLE_RATE:
            raise SystemPathError("X-VC native sample rate drifted")
        model = XVC.load_from_checkpoint(
            str(xvc_config), str(checkpoint), device, ema_load=False
        )
        model = PeftModel.from_pretrained(
            model,
            adapter_dir,
            adapter_name=profile.adapter_name,
            is_trainable=False,
        )
        model.set_adapter(profile.adapter_name)
        model.eval()
        target = np.asarray(
            process_audio(
                str(target_reference), config, backend_module.LATENT_HOP_LENGTH
            ),
            dtype=np.float32,
        )
        target_wav = torch.from_numpy(target).reshape(1, 1, -1).to(device)
        with torch.inference_mode():
            speaker_condition, frame_condition = infer_utils.precompute_conditions(
                model, target_wav, torch.zeros_like(target_wav)
            )

        self.configuration = None
        self.implementation_revision = (
            "x-vc-human87-system-path-probe-v1/" + profile.candidate_id
        )
        self.weight_revision = "sha256:" + profile.adapter_sha256
        self.configuration_hash = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    {
                        "adapter_sha256": profile.adapter_sha256,
                        "current_ms": CURRENT_MS,
                        "future_ms": FUTURE_MS,
                        "smooth_ms": SMOOTH_MS,
                        "target_sha256": EXPECTED_TARGET_SHA256,
                        "window_ms": WINDOW_MS,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("ascii")
            ).hexdigest()
        )
        self._upstream_output = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        self._torch = torch
        self._device = device
        self._model = model
        self._run_stream_chunk_forward = infer_utils.run_stream_chunk_forward
        import torchaudio
        from utils.audio import audio_highpass_filter, audio_volume_normalize

        self._audio_highpass_filter = audio_highpass_filter
        self._audio_volume_normalize = audio_volume_normalize
        self._torchaudio = torchaudio
        self._speaker_condition = speaker_condition
        self._frame_condition = frame_condition

    def convert_window(
        self,
        samples: Sequence[float],
        sample_rate: int,
        prior_tail: object | None,
    ) -> backend_module.WindowResult:
        self._inference_started.set()
        self._torch.cuda.synchronize(self._device)
        started = time.perf_counter()
        result = super().convert_window(samples, sample_rate, prior_tail)
        self._torch.cuda.synchronize(self._device)
        self.chunk_compute_ms.append((time.perf_counter() - started) * 1_000.0)
        return result


class Capture:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[tuple[float, dict[str, object]]] = []

    def emit(self, message: Mapping[str, object]) -> None:
        with self._lock:
            self.events.append((time.perf_counter(), dict(message)))

    def messages(
        self, message_type: str, generation_id: int
    ) -> list[dict[str, object]]:
        with self._lock:
            return [
                message
                for _, message in self.events
                if message.get("type") == message_type
                and message.get("generation_id") == generation_id
            ]


def wait_for_credit(
    capture: Capture,
    *,
    generation_id: int,
    sent_frames: int,
    capacity_frames: int,
    timeout: float,
) -> float:
    """Apply the output-backed worker credit used by the Gateway bridge."""

    started = time.perf_counter()
    deadline = started + timeout
    while (
        sent_frames - len(capture.messages("audio.output", generation_id))
        >= capacity_frames
    ):
        if time.perf_counter() >= deadline:
            raise SystemPathError("worker credit did not recover")
        time.sleep(0.002)
    return (time.perf_counter() - started) * 1_000.0


def run_retained_generation(
    worker: worker_module.XvcWorker,
    capture: Capture,
    frames: Sequence[np.ndarray],
    *,
    generation_id: int,
    first_rpc_id: int,
    timeout: float,
) -> tuple[np.ndarray, dict[str, object]]:
    worker.handle(
        control("generation.start", first_rpc_id, generation_id=generation_id)
    )
    started = time.perf_counter()
    deadline = started
    credit_wait_ms = 0.0
    max_in_flight_frames = 0
    for sequence, frame in enumerate(frames):
        waited_ms = wait_for_credit(
            capture,
            generation_id=generation_id,
            sent_frames=sequence,
            capacity_frames=worker_module.CAPACITY_FRAMES,
            timeout=timeout,
        )
        credit_wait_ms += waited_ms
        if waited_ms >= 1.0:
            deadline = max(deadline, time.perf_counter())
        worker.handle(
            audio_message(frame, generation_id=generation_id, sequence=sequence)
        )
        output_count = len(capture.messages("audio.output", generation_id))
        max_in_flight_frames = max(max_in_flight_frames, sequence + 1 - output_count)
        deadline += FRAME_MS / 1_000
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
    worker.handle(
        control("generation.end", first_rpc_id + 1, generation_id=generation_id)
    )
    if not worker.wait_for_idle(timeout):
        raise SystemPathError("retained generation did not drain")
    outputs = capture.messages("audio.output", generation_id)
    if len(outputs) != len(frames):
        raise SystemPathError("retained generation output frame count drifted")
    outputs.sort(key=lambda item: int(item["sequence"]))
    if [int(item["sequence"]) for item in outputs] != list(range(len(frames))):
        raise SystemPathError("retained generation output sequence is not contiguous")
    if not capture.messages("generation.completed", generation_id):
        raise SystemPathError("retained generation did not complete")
    pcm = np.concatenate(
        [
            np.frombuffer(
                base64.b64decode(str(item["pcm_f32le_base64"])), dtype="<f4"
            ).copy()
            for item in outputs
        ]
    )
    if not np.isfinite(pcm).all() or float(np.max(np.abs(pcm))) > 1.0:
        raise SystemPathError("retained worker output is invalid PCM")
    return pcm, {
        "input_frames": len(frames),
        "output_frames": len(outputs),
        "wall_seconds": time.perf_counter() - started,
        "credit_wait_ms": credit_wait_ms,
        "max_in_flight_frames": max_in_flight_frames,
        "sequence_contiguous": True,
        "generation_completed": True,
    }


def write_pcm16(path: Path, samples: np.ndarray) -> str:
    pcm = (np.clip(samples, -1.0, 1.0) * 32_767.0).round().astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(INPUT_SAMPLE_RATE)
        output.writeframes(pcm.tobytes())
    return sha256_file(path)


def validate_inputs(args: argparse.Namespace, profile: CandidateProfile) -> None:
    checks = (
        (args.actual_source, EXPECTED_SOURCE_SHA256, "actual source"),
        (args.target_reference, EXPECTED_TARGET_SHA256, "target reference"),
        (
            args.adapter_dir / "adapter_model.safetensors",
            profile.adapter_sha256,
            f"{profile.candidate_id} adapter",
        ),
        (
            args.adapter_dir / "adapter_config.json",
            profile.adapter_config_sha256,
            f"{profile.candidate_id} adapter config",
        ),
        (args.xvc_config, EXPECTED_CONFIG_SHA256, "X-VC config"),
        (args.checkpoint, EXPECTED_CHECKPOINT_SHA256, "X-VC checkpoint"),
        (
            args.xvc_source_root / "bins/infer_utils.py",
            EXPECTED_UPSTREAM_STREAM_SHA256,
            "upstream stream code",
        ),
    )
    for path, expected, label in checks:
        if path.is_symlink() or not path.is_file() or sha256_file(path) != expected:
            raise SystemPathError(f"{label} identity drifted")
    if args.work_dir.exists() or args.listener_dir.exists():
        raise SystemPathError("work and listener outputs must be new")
    if args.confirm_gpu_lease != "gpu0" or args.device != "cuda:0":
        raise SystemPathError("the explicit gpu0/cuda:0 lease is required")
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise SystemPathError(f"{name}=1 is required")


def run(args: argparse.Namespace) -> int:
    profile = CANDIDATE_PROFILES[args.candidate]
    validate_inputs(args, profile)
    started = time.perf_counter()
    args.work_dir.mkdir(parents=True)
    source = decode_pcm24_wav(args.actual_source)
    frames, original_samples = frame_audio(source)

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch

    if not torch.cuda.is_available():
        raise SystemPathError("CUDA is unavailable")
    device = torch.device(args.device)
    torch.cuda.set_device(device)
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.cuda.reset_peak_memory_stats(device)
    deny_non_unix_sockets()

    with candidate_geometry(FUTURE_MS):
        backend = CandidateBackend(
            xvc_source_root=args.xvc_source_root,
            xvc_config=args.xvc_config,
            checkpoint=args.checkpoint,
            adapter_dir=args.adapter_dir,
            target_reference=args.target_reference,
            device_name=args.device,
            profile=profile,
        )
        capture = Capture()
        fatal = threading.Event()
        worker = worker_module.XvcWorker(backend, capture.emit, fatal=fatal.set)

        # Generation 1 reaches real model inference and is then canceled.  Its
        # output must never cross the worker boundary.
        worker.handle(control("generation.start", 1, generation_id=1))
        cancel_frame_count = (
            worker_module.CURRENT_FRAMES + worker_module.LOOKAHEAD_FRAMES
        )
        for sequence, frame in enumerate(frames[:cancel_frame_count]):
            worker.handle(audio_message(frame, generation_id=1, sequence=sequence))
        if not backend._inference_started.wait(args.timeout):  # noqa: SLF001
            raise SystemPathError("cancel probe never entered model inference")
        cancel_started = time.perf_counter()
        worker.handle(control("generation.cancel", 2, generation_id=1))
        cancel_ms = (time.perf_counter() - cancel_started) * 1_000.0
        if cancel_ms > 100.0:
            raise SystemPathError("generation cancellation exceeded 100 ms")

        retained, generation = run_retained_generation(
            worker,
            capture,
            frames,
            generation_id=2,
            first_rpc_id=3,
            timeout=args.timeout,
        )
        if fatal.is_set():
            raise SystemPathError("worker marked the candidate backend fatal")
        stale = capture.messages("audio.output", 1)
        if stale:
            raise SystemPathError("canceled generation emitted stale PCM")
        worker.handle(control("worker.close", 5))

    retained = retained[:original_samples]
    staging = args.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(args.actual_source, staging / "00-native-source.wav")
    output_sha256 = write_pcm16(staging / profile.output_file, retained)
    chunk_ms = np.asarray(backend.chunk_compute_ms, dtype=np.float64)
    timing = {
        "chunk_count": int(chunk_ms.size),
        "compute_ms_p50": float(np.percentile(chunk_ms, 50)),
        "compute_ms_p95": float(np.percentile(chunk_ms, 95)),
        "compute_ms_max": float(chunk_ms.max()),
        "failure_count": 0,
    }
    index = {
        "schema_version": 1,
        "run_kind": (
            f"{profile.candidate_id} future-120 candidate system-path probe"
        ),
        "status": "completed-listen-now-unselected",
        "source_file": "Native / 変換前のChatGPTタブ音声（2026-08-11収録）",
        "source_output_file": "00-native-source.wav",
        "source_duration_seconds": original_samples / INPUT_SAMPLE_RATE,
        "variants": [
            {
                "variant_id": f"xvc-{profile.candidate_id}-future-120-system-path",
                "display_name": profile.display_name,
                "display_order": 1,
                "output_file": profile.output_file,
                "status": "passed",
                "profile_id": profile.profile_id,
                "family_id": "x-vc",
                "output_sha256": output_sha256,
                "parameters": {
                    "current_ms": CURRENT_MS,
                    "future_ms": FUTURE_MS,
                    "smooth_ms": SMOOTH_MS,
                    "window_ms": WINDOW_MS,
                },
            }
        ],
    }
    (staging / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.copytree(staging, args.listener_dir)
    result = {
        "schema_version": 1,
        "kind": "liveconv-exp032-xvc-system-path-result",
        "status": "completed-listen-now-unselected",
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "target_reference_sha256": EXPECTED_TARGET_SHA256,
        "candidate_id": profile.candidate_id,
        "adapter_sha256": profile.adapter_sha256,
        "stream_window": {
            "window_ms": WINDOW_MS,
            "current_ms": CURRENT_MS,
            "smooth_ms": SMOOTH_MS,
            "future_ms": FUTURE_MS,
        },
        "cancel_probe": {
            "generation_id": 1,
            "ack_ms": cancel_ms,
            "stale_output_frames": 0,
        },
        "retained_generation": {"generation_id": 2, **generation},
        "timing": timing,
        "output_sha256": output_sha256,
        "elapsed_seconds": time.perf_counter() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "gateway_routed": False,
            "extension_played": False,
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
        },
    }
    (args.work_dir / "system-path-result.json").write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument("--adapter-dir", type=Path, required=True)
    value.add_argument(
        "--candidate",
        choices=tuple(CANDIDATE_PROFILES),
        default="expanded79-e08",
    )
    value.add_argument("--target-reference", type=Path, required=True)
    value.add_argument("--actual-source", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", required=True)
    value.add_argument("--device", default="cuda:0")
    value.add_argument("--timeout", type=float, default=180.0)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (OSError, SystemPathError, ValueError) as error:
        print(f"system_path_smoke: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
