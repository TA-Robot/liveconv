#!/usr/bin/env python3
"""Publish EXP-027 X-VC horizons on the actual 8.17-second ChatGPT input.

The runner loads the base plus EXP-026 epoch 4/8/12 adapters and applies the
pinned upstream streaming implementation with one fixed window.  It records
CUDA-synchronized per-chunk compute latency and publishes one plain-label
comparison on port 8878.  This is listen-now/system evidence, not promotion.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import wave
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import listen_now as base
import numpy as np

ACTUAL_SOURCE_SHA256 = (
    "78b15cd5e9d25ee10d8cb27084c63275221d773a04b21d11e4e3ba2be8056da6"
)
TARGET_REFERENCE_SHA256 = (
    "76f5a4a9b989ed692a55343a7681623fa4f18e354ca04026f022e3e449195ca2"
)
EXP026_RESULT_SHA256 = (
    "74066982f053bdafa96bae030f9d0361f3ccd9320aaebba0e5db903e663f7263"
)
UPSTREAM_STREAM_RUNNER_SHA256 = (
    "f2fb77f226e4c5d106089a382a14cf38b1b99aebe45b4acd82b9aa48dd76eb77"
)
ADAPTER_HASHES = {
    4: "227e84b658e43b6d06eb32beaca391783f063e615876d39cbbdd0f34e18b09fc",
    8: "e0ae0240f70968202c9214641e4a3052ad7277cc4b3ed2ac833f2394b22ea7cf",
    12: "221817b6842b43ec79bb569fd6a33a6c181d5340245753e00cdbb4b0399044de",
}
CHUNK_MS = 2400
CURRENT_MS = 120
SMOOTH_MS = 20
FUTURE_MS = 100
HISTORY_MS = CHUNK_MS - CURRENT_MS - SMOOTH_MS - FUTURE_MS
ORIGINAL_SOURCE_SECONDS = 8.170667
EXPECTED_MODEL_SOURCE_SAMPLES = 131_840
EXPECTED_OUTPUT_SAMPLES = 130_731


def latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    samples = np.asarray(values, dtype=np.float64)
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise base.ListenNowError("stream latency samples are missing or non-finite")
    return {
        "chunk_count": int(samples.size),
        "compute_ms_p50": float(np.percentile(samples, 50)),
        "compute_ms_p95": float(np.percentile(samples, 95)),
        "compute_ms_max": float(samples.max()),
        "failure_count": 0,
    }


def listening_index(
    *, output_hashes: Mapping[int, str], source_duration_seconds: float
) -> dict[str, object]:
    labels = {
        0: "X-VC base / upstream streaming / adapterなし",
        4: "X-VC human87 / 4 epochs / upstream streaming",
        8: "X-VC human87 / 8 epochs / upstream streaming",
        12: "X-VC human87 / 12 epochs / upstream streaming",
    }
    variants: list[dict[str, object]] = []
    for order, epoch in enumerate((0, 4, 8, 12), start=1):
        filename = (
            "10-xvc-base-stream.wav"
            if epoch == 0
            else f"{order}0-xvc-human87-e{epoch:02d}-stream.wav"
        )
        variants.append(
            {
                "variant_id": (
                    "xvc-base-stream" if epoch == 0 else f"xvc-e{epoch:02d}-stream"
                ),
                "display_name": labels[epoch],
                "display_order": order,
                "output_file": filename,
                "status": "passed",
                "profile_id": (
                    "xvc.base.upstream-stream.listen-now"
                    if epoch == 0
                    else f"xvc.exp027.human87.e{epoch:02d}.upstream-stream"
                ),
                "family_id": "x-vc",
                "output_sha256": output_hashes[epoch],
                "parameters": {
                    "chunk_ms": CHUNK_MS,
                    "current_ms": CURRENT_MS,
                    "smooth_ms": SMOOTH_MS,
                    "future_ms": FUTURE_MS,
                },
            }
        )
    return {
        "schema_version": 1,
        "run_kind": "EXP-027 actual-input X-VC upstream-stream horizon",
        "status": "completed-listen-now-unselected",
        "source_file": "Native / 変換前のChatGPTタブ音声（2026-08-11収録）",
        "source_duration_seconds": source_duration_seconds,
        "source_output_file": "00-native-source.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": "Native actual ChatGPT-tab input / 8.17 seconds",
                "output_file": "00-native-source.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": "Amitaro runrun train-role reference / EMOTION100_003",
                "output_file": "01-target-reference.wav",
                "excluded_from_preference": True,
            },
        ],
        "variants": variants,
    }


def _validate_exp026(exp026_work_dir: Path) -> dict[str, Any]:
    result_path = exp026_work_dir / "listen-now-result.json"
    if base.sha256_file(result_path) != EXP026_RESULT_SHA256:
        raise base.ListenNowError("EXP-026 result identity drifted")
    result = base._load_json(result_path, "EXP-026 result")
    if (
        result.get("status") != "completed-listen-now-unselected"
        or result.get("checkpoint_epochs") != [4, 8, 12]
        or result.get("updates") != 1044
        or result.get("epoch4_control_reproduced") is not True
        or result.get("heldout_target_access_count") != 0
    ):
        raise base.ListenNowError("EXP-026 result is not the admitted horizon run")
    for epoch, expected in ADAPTER_HASHES.items():
        adapter = exp026_work_dir / f"adapter-{epoch * base.EXPECTED_TRAIN_PAIRS:04d}"
        if adapter.is_symlink() or not adapter.is_dir():
            raise base.ListenNowError(f"EXP-026 epoch {epoch} adapter is unavailable")
        model_path = adapter / "adapter_model.safetensors"
        config_path = adapter / "adapter_config.json"
        if (
            model_path.is_symlink()
            or config_path.is_symlink()
            or base.sha256_file(model_path) != expected
        ):
            raise base.ListenNowError(f"EXP-026 epoch {epoch} adapter drifted")
    return result


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest, rows = base.validate_inputs(arguments)
    _validate_exp026(arguments.exp026_work_dir)
    if (
        arguments.actual_source.is_symlink()
        or base.sha256_file(arguments.actual_source) != ACTUAL_SOURCE_SHA256
    ):
        raise base.ListenNowError("actual ChatGPT source identity drifted")
    target_reference = (
        arguments.exp026_work_dir
        / "train-pairs"
        / "EMOTION100_003"
        / "target-48k.wav"
    )
    if (
        target_reference.is_symlink()
        or base.sha256_file(target_reference) != TARGET_REFERENCE_SHA256
    ):
        raise base.ListenNowError("EXP-027 target reference identity drifted")
    stream_runner = arguments.xvc_source_root / "bins" / "infer_utils.py"
    if base.sha256_file(stream_runner) != UPSTREAM_STREAM_RUNNER_SHA256:
        raise base.ListenNowError("pinned upstream streaming implementation drifted")
    return manifest, rows


def _write_output(path: Path, rendered: Any, sample_rate: int) -> str:
    values = rendered.detach().to("cpu", dtype=rendered.dtype).reshape(-1).numpy()
    if (
        values.size != EXPECTED_MODEL_SOURCE_SAMPLES
        or not np.isfinite(values).all()
    ):
        raise base.ListenNowError("streamed output is malformed")
    values = values[:EXPECTED_OUTPUT_SAMPLES]
    pcm = (np.clip(values, -1.0, 1.0) * 32767.0).round().astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())
    return base.sha256_file(path)


def _measured_stream(
    infer_utils: Any,
    model: Any,
    source_wav: Any,
    target_wav: Any,
    target_wav_cond: Any,
    *,
    sample_rate: int,
    torch: Any,
    device: Any,
    chunk_ms: int = CHUNK_MS,
    current_ms: int = CURRENT_MS,
    future_ms: int = FUTURE_MS,
    smooth_ms: int = SMOOTH_MS,
) -> tuple[Any, list[float], float, float]:
    torch.cuda.synchronize(device)
    condition_started = time.perf_counter()
    speaker_condition, frame_condition = infer_utils.precompute_conditions(
        model, target_wav, target_wav_cond
    )
    torch.cuda.synchronize(device)
    condition_ms = (time.perf_counter() - condition_started) * 1000.0

    original = infer_utils.run_stream_chunk_forward
    chunk_latencies: list[float] = []

    def measured_forward(*args: Any, **kwargs: Any) -> Any:
        torch.cuda.synchronize(device)
        started = time.perf_counter()
        output = original(*args, **kwargs)
        torch.cuda.synchronize(device)
        chunk_latencies.append((time.perf_counter() - started) * 1000.0)
        return output

    infer_utils.run_stream_chunk_forward = measured_forward
    torch.cuda.synchronize(device)
    wall_started = time.perf_counter()
    try:
        rendered, _upstream_unsynchronized = infer_utils.run_streaming(
            model=model,
            source_wav=source_wav,
            speaker_condition=speaker_condition,
            frame_condition=frame_condition,
            sample_rate=sample_rate,
            chunk_ms=chunk_ms,
            current_ms=current_ms,
            future_ms=future_ms,
            smooth_ms=smooth_ms,
        )
        torch.cuda.synchronize(device)
    finally:
        infer_utils.run_stream_chunk_forward = original
    wall_ms = (time.perf_counter() - wall_started) * 1000.0
    if rendered.shape != source_wav.shape or not bool(torch.isfinite(rendered).all()):
        raise base.ListenNowError("upstream streaming output shape or values drifted")
    return rendered, chunk_latencies, condition_ms, wall_ms


def run(arguments: argparse.Namespace) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise base.ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise base.ListenNowError("EXP-027 requires the explicit gpu0 lease")

    started = time.monotonic()
    arguments.work_dir.mkdir()
    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise base.ListenNowError("CUDA is unavailable")
    device = torch.device(arguments.device)
    base._configure_deterministic_cuda(torch, device)
    torch.cuda.reset_peak_memory_stats(device)
    xvc_root = str(arguments.xvc_source_root.resolve())
    if xvc_root not in sys.path:
        sys.path.insert(0, xvc_root)
    from bins import infer_utils
    from models.codec.sac.model import XVC
    from models.codec.sac.utils import process_audio
    from utils.file import load_config

    config = load_config(str(arguments.xvc_config))
    if "config" in config:
        config = config["config"]
    sample_rate = int(config["sample_rate"])
    source_array = np.asarray(
        process_audio(
            str(arguments.actual_source), config, int(config["latent_hop_length"])
        ),
        dtype=np.float32,
    )
    target_path = (
        arguments.exp026_work_dir
        / "train-pairs"
        / "EMOTION100_003"
        / "target-48k.wav"
    )
    target_array = np.asarray(
        process_audio(str(target_path), config, int(config["latent_hop_length"])),
        dtype=np.float32,
    )
    if (
        source_array.ndim != 1
        or target_array.ndim != 1
        or not np.isfinite(source_array).all()
        or not np.isfinite(target_array).all()
    ):
        raise base.ListenNowError("EXP-027 model audio is malformed")
    source_wav = torch.from_numpy(source_array).reshape(1, 1, -1).to(device)
    target_wav = torch.from_numpy(target_array).reshape(1, 1, -1).to(device)
    target_wav_cond = torch.zeros_like(target_wav)
    if source_wav.shape[-1] != EXPECTED_MODEL_SOURCE_SAMPLES:
        raise base.ListenNowError(
            "actual source sample count drifted after preprocessing"
        )
    source_duration_seconds = ORIGINAL_SOURCE_SECONDS

    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config),
        str(arguments.checkpoint),
        device,
        ema_load=False,
    )
    rendered_by_epoch: dict[int, Any] = {}
    timings: dict[int, dict[str, float | int]] = {}

    rendered, chunk_ms, condition_ms, wall_ms = _measured_stream(
        infer_utils,
        model,
        source_wav,
        target_wav,
        target_wav_cond,
        sample_rate=sample_rate,
        torch=torch,
        device=device,
    )
    rendered_by_epoch[0] = rendered.detach().cpu()
    timings[0] = {
        **latency_summary(chunk_ms),
        "condition_compute_ms": condition_ms,
        "stream_wall_ms": wall_ms,
    }

    first_adapter = arguments.exp026_work_dir / "adapter-0348"
    model = PeftModel.from_pretrained(
        model, first_adapter, adapter_name="e04", is_trainable=False
    )
    for epoch in (8, 12):
        model.load_adapter(
            arguments.exp026_work_dir
            / f"adapter-{epoch * base.EXPECTED_TRAIN_PAIRS:04d}",
            adapter_name=f"e{epoch:02d}",
            is_trainable=False,
        )
    for epoch in (4, 8, 12):
        model.set_adapter(f"e{epoch:02d}")
        model.eval()
        rendered, chunk_ms, condition_ms, wall_ms = _measured_stream(
            infer_utils,
            model,
            source_wav,
            target_wav,
            target_wav_cond,
            sample_rate=sample_rate,
            torch=torch,
            device=device,
        )
        rendered_by_epoch[epoch] = rendered.detach().cpu()
        timings[epoch] = {
            **latency_summary(chunk_ms),
            "condition_compute_ms": condition_ms,
            "stream_wall_ms": wall_ms,
        }

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(arguments.actual_source, staging / "00-native-source.wav")
    shutil.copyfile(target_path, staging / "01-target-reference.wav")
    output_hashes: dict[int, str] = {}
    for order, epoch in enumerate((0, 4, 8, 12), start=1):
        filename = (
            "10-xvc-base-stream.wav"
            if epoch == 0
            else f"{order}0-xvc-human87-e{epoch:02d}-stream.wav"
        )
        output_hashes[epoch] = _write_output(
            staging / filename, rendered_by_epoch[epoch], sample_rate
        )
    base._write_json(
        staging / "index.json",
        listening_index(
            output_hashes=output_hashes,
            source_duration_seconds=source_duration_seconds,
        ),
    )

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp027-actual-input-upstream-stream-result",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "source_sha256": ACTUAL_SOURCE_SHA256,
        "source_duration_seconds": source_duration_seconds,
        "model_input_samples": EXPECTED_MODEL_SOURCE_SAMPLES,
        "listener_output_samples": EXPECTED_OUTPUT_SAMPLES,
        "target_reference_id": "EMOTION100_003",
        "adapter_epochs": [4, 8, 12],
        "stream_window": {
            "chunk_ms": CHUNK_MS,
            "current_ms": CURRENT_MS,
            "smooth_ms": SMOOTH_MS,
            "future_ms": FUTURE_MS,
            "history_ms": HISTORY_MS,
        },
        "timings_by_epoch": {str(key): value for key, value in timings.items()},
        "output_hashes_by_epoch": {
            str(key): value for key, value in output_hashes.items()
        },
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "conversational_latency_measured": False,
        },
    }
    base._write_json(arguments.work_dir / "listen-now-result.json", result)
    staging.rename(arguments.listener_dir)
    print(
        json.dumps(
            {
                "status": result["status"],
                "listener_dir": str(arguments.listener_dir),
                "variants": len(output_hashes),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-archive", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--exp026-work-dir", type=Path, required=True)
    parser.add_argument("--actual-source", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=(
            base.REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--listener-dir", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        manifest, rows = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "manifest_sha256": manifest["manifest_sha256"],
                        "row_count": len(rows),
                        "stream_window": {
                            "chunk_ms": CHUNK_MS,
                            "current_ms": CURRENT_MS,
                            "smooth_ms": SMOOTH_MS,
                            "future_ms": FUTURE_MS,
                            "history_ms": HISTORY_MS,
                        },
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments)
    except (base.ListenNowError, OSError, ValueError) as error:
        print(f"actual-input stream failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
