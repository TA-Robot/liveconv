#!/usr/bin/env python3
"""Render control69 on clean training-only sources to mine collapse triggers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
import run_post_rehearsal as post  # noqa: E402

OUTPUT_KIND = "liveconv-exp145-control-hard-negative-probe/v1"
POOL_KIND = "liveconv-exp145-control-hard-negative-pool/v1"


class HardNegativeProbeError(RuntimeError):
    """The bounded training-only control probe cannot continue safely."""


def probe_pool(manifest: Mapping[str, Any]) -> dict[str, Any]:
    items = manifest.get("items")
    if not isinstance(items, list) or len(items) != post.EXPECTED_ROWS:
        raise HardNegativeProbeError("clean rehearsal rows drifted")
    rows: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for item in items:
        teacher_id = item.get("teacher_id") if isinstance(item, dict) else None
        domain = item.get("domain") if isinstance(item, dict) else None
        transcript = item.get("source_transcript") if isinstance(item, dict) else None
        if (
            not isinstance(teacher_id, str)
            or not teacher_id
            or teacher_id in identifiers
            or not isinstance(domain, str)
            or not domain
            or not isinstance(transcript, str)
        ):
            raise HardNegativeProbeError("control probe identity drifted")
        identifiers.add(teacher_id)
        rows.append(
            {
                "id": teacher_id,
                "domain": domain,
                "source_transcript": transcript,
            }
        )
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "selection": (
            "all 170 pre-admitted unique training-only sources; no heldout or "
            "evaluation output used"
        ),
        "items": rows,
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    manifest = post.load_manifest(arguments.training_manifest, arguments.source_work)
    probe_pool(manifest)
    targets = method.target_inventory(arguments.pair_root)
    target_ids = {row[0] for row in targets}
    if any(item.get("target_id") not in target_ids for item in manifest["items"]):
        raise HardNegativeProbeError("control probe target identity drifted")
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise HardNegativeProbeError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-145 work directory",
    )
    return manifest, targets


def run(
    arguments: argparse.Namespace,
    manifest: Mapping[str, Any],
    target_rows: Sequence[tuple[str, Path, str]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise HardNegativeProbeError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise HardNegativeProbeError("EXP-145 requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    output_root = arguments.work_dir / "control-outputs"
    output_root.mkdir()

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise HardNegativeProbeError("CUDA is unavailable")
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
    plain = method._load_xvc(arguments, XVC, device)
    control = PeftModel.from_pretrained(
        plain, str(arguments.control_adapter), is_trainable=False
    )
    target_by_id = {
        identifier: (path, digest) for identifier, path, digest in target_rows
    }
    target_cache: dict[str, dict[str, Any]] = {}
    output_rows: list[dict[str, Any]] = []
    for index, item in enumerate(manifest["items"]):
        teacher_id = str(item["teacher_id"])
        target_id = str(item["target_id"])
        source_path = arguments.source_work / str(item["source_file"])
        source = base._extract_pair_tensors(
            control,
            post._pair(teacher_id, source_path, str(item["source_sha256"])),
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        if target_id not in target_cache:
            target_path, target_digest = target_by_id[target_id]
            target_cache[target_id] = base._extract_pair_tensors(
                control,
                post._pair(target_id, target_path, target_digest),
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
        waveform = base._inference(
            control,
            source,
            target_cache[target_id],
            seed=base.SEED + index,
            torch=torch,
            device=device,
        ).detach().cpu()
        row_root = output_root / target_id
        row_root.mkdir(exist_ok=True)
        output_path = row_root / f"teacher-output-{teacher_id}-16k.wav"
        digest = base._write_float_wav(output_path, waveform, sample_rate)
        output_rows.append(
            {
                "target_id": target_id,
                "teacher_id": teacher_id,
                "output_sha256": digest,
            }
        )

    pool = probe_pool(manifest)
    method._write_json(arguments.work_dir / "pool.json", pool)
    result = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "status": "completed-training-only-diagnostic",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": (
            "Which clean training-only real sources make control69 collapse "
            "when their frozen base-X-VC teachers did not?"
        ),
        "training_manifest_sha256": post.sha256_file(arguments.training_manifest),
        "control_adapter": str(arguments.control_adapter),
        "rows": output_rows,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "boundary": (
            "hard-negative discovery only; not evaluation, naturalness, target "
            "identity, a keeper, or promotion"
        ),
    }
    method._write_json(arguments.work_dir / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(output_rows),
                "output_root": str(output_root),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--training-manifest", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--pair-root", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json",
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "rows": len(manifest["items"]),
                        "evaluation_rows": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, manifest, targets)
    except (
        HardNegativeProbeError,
        post.PostRehearsalError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"control-hard-negative-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
