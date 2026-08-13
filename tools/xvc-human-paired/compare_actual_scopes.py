#!/usr/bin/env python3
"""Compare base, expanded79-e12, and control69-e12 on actual input offline."""

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
import render_actual_offline_horizons as offline
import stream_actual_horizons as stream

EXPANDED_ADAPTER_SHA256 = (
    "221817b6842b43ec79bb569fd6a33a6c181d5340245753e00cdbb4b0399044de"
)
EXPANDED_CONFIG_SHA256 = (
    "7b9df8ad7832d589ae4129c9da7fa052610379b7d4a4168ce381eb83fd08f12d"
)
CONTROL69_RESULT_SHA256 = (
    "c0da08550dc9e5edffd649a5b25a2dec72792ccb591365ea7b840b2fd79f83f0"
)
CONTROL69_ADAPTER_SHA256 = (
    "efa63bdec33bcfd2816bd267c9bfa7dfd42d6a39b5c872b720db74cff01fbffe"
)
CONTROL69_CONFIG_SHA256 = (
    "74611b93bbbe556b328aec6ec8ecc6cc1a029ee8307d98e35165523e4f24af07"
)


def listening_index(hashes: Mapping[str, str]) -> dict[str, object]:
    variants = [
        {
            "variant_id": "xvc-base-offline",
            "display_name": "X-VC base / actual input / offline",
            "display_order": 1,
            "output_file": "10-xvc-base-offline.wav",
            "status": "passed",
            "profile_id": "xvc.base.actual.offline.listen-now",
            "family_id": "x-vc",
            "output_sha256": hashes["base"],
        },
        {
            "variant_id": "xvc-expanded79-e12-offline",
            "display_name": (
                "X-VC human87 / expanded79 / LR 1e-4 / epoch 12 / offline"
            ),
            "display_order": 2,
            "output_file": "20-xvc-expanded79-e12-offline.wav",
            "status": "passed",
            "profile_id": "xvc.exp026.expanded79.e12.actual.offline",
            "family_id": "x-vc",
            "output_sha256": hashes["expanded79-e12"],
        },
        {
            "variant_id": "xvc-control69-e12-offline",
            "display_name": (
                "X-VC human87 / control69 / LR 1e-4 / epoch 12 / offline"
            ),
            "display_order": 3,
            "output_file": "30-xvc-control69-e12-offline.wav",
            "status": "passed",
            "profile_id": "xvc.exp026.control69.e12.actual.offline",
            "family_id": "x-vc",
            "output_sha256": hashes["control69-e12"],
        },
    ]
    return {
        "schema_version": 1,
        "run_kind": "EXP-026 actual-input X-VC LoRA-scope offline comparison",
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


def _adapter(directory: Path, model_sha: str, config_sha: str, label: str) -> Path:
    model = directory / "adapter_model.safetensors"
    config = directory / "adapter_config.json"
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or base.sha256_file(model) != model_sha
        or base.sha256_file(config) != config_sha
    ):
        raise base.ListenNowError(f"{label} adapter identity drifted")
    return directory


def validate_inputs(arguments: argparse.Namespace) -> tuple[Path, Path, Path]:
    base.validate_inputs(arguments)
    if (
        arguments.actual_source.is_symlink()
        or base.sha256_file(arguments.actual_source) != stream.ACTUAL_SOURCE_SHA256
    ):
        raise base.ListenNowError("actual ChatGPT source identity drifted")
    target = (
        arguments.expanded_work_dir
        / "train-pairs"
        / "EMOTION100_003"
        / "target-48k.wav"
    )
    if (
        target.is_symlink()
        or base.sha256_file(target) != stream.TARGET_REFERENCE_SHA256
    ):
        raise base.ListenNowError("target reference identity drifted")
    expanded = _adapter(
        arguments.expanded_work_dir / "adapter-1044",
        EXPANDED_ADAPTER_SHA256,
        EXPANDED_CONFIG_SHA256,
        "expanded79 epoch-12",
    )
    result = arguments.control69_work_dir / "listen-now-result.json"
    if base.sha256_file(result) != CONTROL69_RESULT_SHA256:
        raise base.ListenNowError("control69 result identity drifted")
    control = _adapter(
        arguments.control69_work_dir / "adapter-1044",
        CONTROL69_ADAPTER_SHA256,
        CONTROL69_CONFIG_SHA256,
        "control69 epoch-12",
    )
    if arguments.work_dir.exists() or arguments.listener_dir.exists():
        raise base.ListenNowError("work and listener outputs must be new")
    return target, expanded, control


def run(arguments: argparse.Namespace) -> int:
    target_path, expanded_adapter, control_adapter = validate_inputs(arguments)
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise base.ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise base.ListenNowError("the explicit gpu0/cuda:0 lease is required")

    started = time.monotonic()
    arguments.work_dir.mkdir()
    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise base.ListenNowError("CUDA is unavailable")
    device = torch.device(arguments.device)
    base._configure_deterministic_cuda(torch, device)
    torch.cuda.reset_peak_memory_stats(device)
    root = str(arguments.xvc_source_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
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
        raise base.ListenNowError("model audio drifted")
    source = torch.from_numpy(source_array).reshape(1, 1, -1).to(device)
    target = torch.from_numpy(target_array).reshape(1, 1, -1).to(device)

    model = XVC.load_from_checkpoint(
        str(arguments.xvc_config), str(arguments.checkpoint), device, ema_load=False
    )
    rendered: dict[str, Any] = {}
    compute_ms: dict[str, float] = {}
    value, elapsed = offline._offline(model, source, target, torch=torch, device=device)
    rendered["base"] = value.detach().cpu()
    compute_ms["base"] = elapsed
    model = PeftModel.from_pretrained(
        model, expanded_adapter, adapter_name="expanded79-e12", is_trainable=False
    )
    model.load_adapter(
        control_adapter, adapter_name="control69-e12", is_trainable=False
    )
    for key in ("expanded79-e12", "control69-e12"):
        model.set_adapter(key)
        value, elapsed = offline._offline(
            model, source, target, torch=torch, device=device
        )
        rendered[key] = value.detach().cpu()
        compute_ms[key] = elapsed

    staging = arguments.work_dir / "listener-staging"
    staging.mkdir()
    shutil.copyfile(arguments.actual_source, staging / "00-native-source.wav")
    shutil.copyfile(target_path, staging / "01-target-reference.wav")
    filenames = {
        "base": "10-xvc-base-offline.wav",
        "expanded79-e12": "20-xvc-expanded79-e12-offline.wav",
        "control69-e12": "30-xvc-control69-e12-offline.wav",
    }
    hashes = {
        key: stream._write_output(staging / filenames[key], value, sample_rate)
        for key, value in rendered.items()
    }
    base._write_json(staging / "index.json", listening_index(hashes))
    result = {
        "schema_version": 1,
        "kind": "liveconv-exp026-actual-input-scope-offline-result",
        "status": "completed-listen-now-unselected",
        "git_commit": base._git_output(["git", "rev-parse", "HEAD"], "commit"),
        "source_sha256": stream.ACTUAL_SOURCE_SHA256,
        "compute_ms": compute_ms,
        "output_sha256": hashes,
        "heldout_target_access_count": 0,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "realtime_qualified": False,
        },
    }
    base._write_json(arguments.work_dir / "listen-now-result.json", result)
    staging.rename(arguments.listener_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--target-archive", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=(
            base.REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json"
        ),
    )
    value.add_argument("--expanded-work-dir", type=Path, required=True)
    value.add_argument("--control69-work-dir", type=Path, required=True)
    value.add_argument("--actual-source", type=Path, required=True)
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--listener-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease")
    value.add_argument("--device", default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        target, expanded, control = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "target": target.name,
                        "expanded_adapter": expanded.name,
                        "control69_adapter": control.name,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments)
    except (base.ListenNowError, OSError, ValueError) as error:
        print(f"compare_actual_scopes: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
