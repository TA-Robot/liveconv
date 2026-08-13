#!/usr/bin/env python3
"""Publish EXP-029 e8 stream-position diagnostics on the actual input."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import listen_now as base
import numpy as np
import stream_actual_horizons as stream

FUTURE_VALUES_MS = (0, 100, 300, 500)
EXPECTED_FUTURE100_SHA256 = (
    "cedff001ee6254ea91efdc9f1b41ad42e7367ddab98ec5944f5e26d59261ab9e"
)


def listening_index(output_hashes: Mapping[int, str]) -> dict[str, object]:
    variants: list[dict[str, object]] = []
    for order, future_ms in enumerate(FUTURE_VALUES_MS, start=1):
        history_ms = (
            stream.CHUNK_MS
            - stream.CURRENT_MS
            - stream.SMOOTH_MS
            - future_ms
        )
        variants.append(
            {
                "variant_id": f"xvc-e08-future-{future_ms:03d}",
                "display_name": (
                    "X-VC human87 / 8 epochs / "
                    f"future {future_ms} ms / current位置 {history_ms} ms"
                ),
                "display_order": order,
                "output_file": f"{order}0-xvc-e08-future-{future_ms:03d}.wav",
                "status": "passed",
                "profile_id": f"xvc.exp029.e08.future-{future_ms:03d}",
                "family_id": "x-vc",
                "output_sha256": output_hashes[future_ms],
                "parameters": {
                    "chunk_ms": stream.CHUNK_MS,
                    "current_ms": stream.CURRENT_MS,
                    "smooth_ms": stream.SMOOTH_MS,
                    "future_ms": future_ms,
                    "history_ms": history_ms,
                },
            }
        )
    return {
        "schema_version": 1,
        "run_kind": "EXP-029 e8 X-VC stream-position diagnostic",
        "status": "completed-listen-now-unselected",
        "source_file": "Native / 変換前のChatGPTタブ音声（2026-08-11収録）",
        "source_duration_seconds": stream.ORIGINAL_SOURCE_SECONDS,
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


def run(arguments: argparse.Namespace) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise base.ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise base.ListenNowError("EXP-029 requires the explicit gpu0 lease")

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
    target_path = (
        arguments.exp026_work_dir
        / "train-pairs"
        / "EMOTION100_003"
        / "target-48k.wav"
    )
    source_array = np.asarray(
        process_audio(
            str(arguments.actual_source), config, int(config["latent_hop_length"])
        ),
        dtype=np.float32,
    )
    target_array = np.asarray(
        process_audio(str(target_path), config, int(config["latent_hop_length"])),
        dtype=np.float32,
    )
    if (
        source_array.size != stream.EXPECTED_MODEL_SOURCE_SAMPLES
        or target_array.size != base.MODEL_SAMPLES
        or not np.isfinite(source_array).all()
        or not np.isfinite(target_array).all()
    ):
        raise base.ListenNowError("EXP-029 model audio drifted")
    source_wav = torch.from_numpy(source_array).reshape(1, 1, -1).to(device)
    target_wav = torch.from_numpy(target_array).reshape(1, 1, -1).to(device)
    target_wav_cond = torch.zeros_like(target_wav)

    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config),
        str(arguments.checkpoint),
        device,
        ema_load=False,
    )
    model = PeftModel.from_pretrained(
        model,
        arguments.exp026_work_dir / "adapter-0696",
        adapter_name="e08",
        is_trainable=False,
    )
    model.set_adapter("e08")
    model.eval()
    rendered_by_future: dict[int, Any] = {}
    timings: dict[int, dict[str, float | int]] = {}
    for future_ms in FUTURE_VALUES_MS:
        rendered, chunk_ms, condition_ms, wall_ms = stream._measured_stream(
            infer_utils,
            model,
            source_wav,
            target_wav,
            target_wav_cond,
            sample_rate=sample_rate,
            torch=torch,
            device=device,
            future_ms=future_ms,
        )
        rendered_by_future[future_ms] = rendered.detach().cpu()
        timings[future_ms] = {
            **stream.latency_summary(chunk_ms),
            "condition_compute_ms": condition_ms,
            "stream_wall_ms": wall_ms,
        }

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(arguments.actual_source, staging / "00-native-source.wav")
    shutil.copyfile(target_path, staging / "01-target-reference.wav")
    output_hashes: dict[int, str] = {}
    for order, future_ms in enumerate(FUTURE_VALUES_MS, start=1):
        output_hashes[future_ms] = stream._write_output(
            staging / f"{order}0-xvc-e08-future-{future_ms:03d}.wav",
            rendered_by_future[future_ms],
            sample_rate,
        )
    if output_hashes[100] != EXPECTED_FUTURE100_SHA256:
        raise base.ListenNowError("EXP-029 future-100 control drifted from EXP-027")
    base._write_json(staging / "index.json", listening_index(output_hashes))

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp029-e8-stream-position-result",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "source_sha256": stream.ACTUAL_SOURCE_SHA256,
        "adapter_epoch": 8,
        "future_values_ms": list(FUTURE_VALUES_MS),
        "future100_control_reproduced": True,
        "timings_by_future_ms": {
            str(value): timings[value] for value in FUTURE_VALUES_MS
        },
        "output_hashes_by_future_ms": {
            str(value): output_hashes[value] for value in FUTURE_VALUES_MS
        },
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "position_hypothesis_confirmed": False,
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
        manifest, rows = stream.validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "manifest_sha256": manifest["manifest_sha256"],
                        "row_count": len(rows),
                        "adapter_epoch": 8,
                        "future_values_ms": list(FUTURE_VALUES_MS),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments)
    except (base.ListenNowError, OSError, ValueError) as error:
        print(f"stream-position diagnostic failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
