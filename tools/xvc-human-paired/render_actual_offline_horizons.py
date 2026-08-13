#!/usr/bin/env python3
"""Publish EXP-028 offline controls for the EXP-027 actual-input streams."""

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


def listening_index(output_hashes: Mapping[int, str]) -> dict[str, object]:
    labels = {
        0: "X-VC base / actual input / offline",
        4: "X-VC human87 / 4 epochs / actual input / offline",
        8: "X-VC human87 / 8 epochs / actual input / offline",
        12: "X-VC human87 / 12 epochs / actual input / offline",
    }
    variants: list[dict[str, object]] = []
    for order, epoch in enumerate((0, 4, 8, 12), start=1):
        filename = (
            "10-xvc-base-offline.wav"
            if epoch == 0
            else f"{order}0-xvc-human87-e{epoch:02d}-offline.wav"
        )
        variants.append(
            {
                "variant_id": (
                    "xvc-base-offline"
                    if epoch == 0
                    else f"xvc-e{epoch:02d}-offline"
                ),
                "display_name": labels[epoch],
                "display_order": order,
                "output_file": filename,
                "status": "passed",
                "profile_id": (
                    "xvc.base.actual.offline.listen-now"
                    if epoch == 0
                    else f"xvc.exp028.human87.e{epoch:02d}.actual.offline"
                ),
                "family_id": "x-vc",
                "output_sha256": output_hashes[epoch],
            }
        )
    return {
        "schema_version": 1,
        "run_kind": "EXP-028 actual-input X-VC offline horizon control",
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


def _offline(
    model: Any, source: Any, target: Any, *, torch: Any, device: Any
) -> tuple[Any, float]:
    batch = {
        "source_wav": source,
        "target_wav": target,
        "target_wav_cond": torch.zeros_like(target),
    }
    model.eval()
    torch.cuda.synchronize(device)
    started = time.perf_counter()
    with torch.inference_mode():
        rendered = model.inference(batch).get("recons")
    torch.cuda.synchronize(device)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if (
        rendered is None
        or rendered.shape != source.shape
        or not bool(torch.isfinite(rendered).all())
    ):
        raise base.ListenNowError("EXP-028 offline output is malformed")
    return rendered, elapsed_ms


def run(arguments: argparse.Namespace) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise base.ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise base.ListenNowError("EXP-028 requires the explicit gpu0 lease")

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
        raise base.ListenNowError("EXP-028 model audio drifted")
    source_wav = torch.from_numpy(source_array).reshape(1, 1, -1).to(device)
    target_wav = torch.from_numpy(target_array).reshape(1, 1, -1).to(device)

    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config),
        str(arguments.checkpoint),
        device,
        ema_load=False,
    )
    rendered_by_epoch: dict[int, Any] = {}
    compute_ms: dict[int, float] = {}
    rendered, elapsed_ms = _offline(
        model, source_wav, target_wav, torch=torch, device=device
    )
    rendered_by_epoch[0] = rendered.detach().cpu()
    compute_ms[0] = elapsed_ms

    model = PeftModel.from_pretrained(
        model,
        arguments.exp026_work_dir / "adapter-0348",
        adapter_name="e04",
        is_trainable=False,
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
        rendered, elapsed_ms = _offline(
            model, source_wav, target_wav, torch=torch, device=device
        )
        rendered_by_epoch[epoch] = rendered.detach().cpu()
        compute_ms[epoch] = elapsed_ms

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(arguments.actual_source, staging / "00-native-source.wav")
    shutil.copyfile(target_path, staging / "01-target-reference.wav")
    output_hashes: dict[int, str] = {}
    for order, epoch in enumerate((0, 4, 8, 12), start=1):
        filename = (
            "10-xvc-base-offline.wav"
            if epoch == 0
            else f"{order}0-xvc-human87-e{epoch:02d}-offline.wav"
        )
        output_hashes[epoch] = stream._write_output(
            staging / filename, rendered_by_epoch[epoch], sample_rate
        )
    base._write_json(staging / "index.json", listening_index(output_hashes))

    result = {
        "schema_version": 1,
        "kind": "liveconv-exp028-actual-input-offline-control-result",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "source_sha256": stream.ACTUAL_SOURCE_SHA256,
        "adapter_epochs": [4, 8, 12],
        "compute_ms_by_epoch": {
            str(epoch): value for epoch, value in compute_ms.items()
        },
        "output_hashes_by_epoch": {
            str(epoch): value for epoch, value in output_hashes.items()
        },
        "heldout_target_access_count": 0,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "streaming_cause_decided": False,
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
                        "adapter_epochs": [4, 8, 12],
                        "inference_mode": "offline",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments)
    except (base.ListenNowError, OSError, ValueError) as error:
        print(f"actual-input offline failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
