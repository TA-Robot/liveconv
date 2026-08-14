#!/usr/bin/env python3
"""Render frozen control69 targets for the disjoint JSUT retention sources."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
from prepare_jsut_retention_sources import (  # noqa: E402
    CATEGORY_COUNTS,
    EXPECTED_ROWS,
    load_json,
)
from prepare_jsut_retention_sources import OUTPUT_KIND as SOURCE_KIND  # noqa: E402

OUTPUT_KIND = "liveconv-exp170-jsut-control69-retention-targets85/v1"
POOL_KIND = "liveconv-exp170-jsut-control69-retention-pool85/v1"


class JsutTargetError(RuntimeError):
    """The frozen JSUT retention target render cannot continue safely."""


def pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def model_window(
    samples: np.ndarray, window_samples: int = base.WINDOW_48K
) -> np.ndarray:
    """Fit one mono source to X-VC's exact 2.4-second window."""

    if samples.ndim != 1 or samples.size == 0:
        raise JsutTargetError("JSUT retention PCM shape drifted")
    if samples.size >= window_samples:
        return np.ascontiguousarray(samples[:window_samples])
    return base._right_pad(samples, window_samples)


def parse_pcm16_at_rate(data: bytes, label: str, sample_rate: int) -> np.ndarray:
    """Read mono PCM16 without forcing the historical 48 kHz source rate."""

    try:
        import io

        with wave.open(io.BytesIO(data), "rb") as reader:
            if (
                reader.getnchannels() != 1
                or reader.getsampwidth() != 2
                or reader.getframerate() != sample_rate
            ):
                raise JsutTargetError(
                    f"{label} must be mono PCM16 at {sample_rate} Hz"
                )
            frames = reader.getnframes()
            payload = reader.readframes(frames)
    except (OSError, EOFError, wave.Error) as error:
        raise JsutTargetError(f"cannot read {label}") from error
    samples = np.frombuffer(payload, dtype="<i2").copy()
    if samples.size != frames or samples.size == 0:
        raise JsutTargetError(f"{label} PCM payload drifted")
    return samples


def source_pool(manifest: Mapping[str, Any]) -> dict[str, Any]:
    items = manifest.get("items")
    if manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise JsutTargetError("JSUT retention source identity drifted")
    rows: list[dict[str, Any]] = []
    teacher_ids: set[str] = set()
    curriculum_positions: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            raise JsutTargetError("JSUT retention source row drifted")
        filename = item.get("filename")
        target_id = item.get("target_id")
        category = item.get("jsut_category")
        transcript = item.get("source_transcript")
        position = item.get("curriculum_position")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or Path(filename).suffix.lower() != ".wav"
            or not isinstance(target_id, str)
            or not target_id
            or category not in CATEGORY_COUNTS
            or not isinstance(transcript, str)
            or not transcript
            or not isinstance(position, int)
        ):
            raise JsutTargetError("JSUT retention source row drifted")
        teacher_id = Path(filename).stem
        if teacher_id in teacher_ids or position in curriculum_positions:
            raise JsutTargetError("JSUT retention source identity is duplicated")
        teacher_ids.add(teacher_id)
        curriculum_positions.add(position)
        rows.append(
            {
                "id": teacher_id,
                "filename": filename,
                "domain": "jsut",
                "jsut_category": category,
                "source_transcript": transcript,
                "source_sha256": item.get("sha256"),
                "target_id": target_id,
                "curriculum_position": position,
            }
        )
    composition = Counter(str(row["jsut_category"]) for row in rows)
    if len(rows) != EXPECTED_ROWS or dict(composition) != dict(CATEGORY_COUNTS):
        raise JsutTargetError("JSUT retention source composition drifted")
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "selection": (
            "all 85 precommitted JSUT retention sources; no model output used"
        ),
        "items": rows,
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    manifest = load_json(arguments.source_manifest)
    pool = source_pool(manifest)
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise JsutTargetError("JSUT retention source root is unavailable")
    for row in pool["items"]:
        path = arguments.source_root / str(row["filename"])
        if path.is_symlink() or not path.is_file():
            raise JsutTargetError("JSUT retention source audio is unavailable")
        digest = row.get("source_sha256")
        if not isinstance(digest, str) or base.sha256_file(path) != digest:
            raise JsutTargetError("JSUT retention source audio drifted")
    targets = method.target_inventory(arguments.pair_root)
    target_ids = {row[0] for row in targets}
    if any(row["target_id"] not in target_ids for row in pool["items"]):
        raise JsutTargetError("JSUT retention target identity drifted")
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise JsutTargetError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-170 work directory",
    )
    return pool, targets


def run(
    arguments: argparse.Namespace,
    pool: Mapping[str, Any],
    target_rows: Sequence[tuple[str, Path, str]],
    *,
    result_kind: str = OUTPUT_KIND,
    question: str = (
        "Can a category-balanced Japanese retention branch preserve normal "
        "behavior under the surviving EXP-163 method?"
    ),
    experiment_id: str = "EXP-170",
    source_sample_rate: int = base.SAMPLE_RATE_48K,
    source_window_samples: int = base.WINDOW_48K,
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise JsutTargetError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise JsutTargetError(f"{experiment_id} requires the explicit gpu0 lease")
    started = time.monotonic()
    arguments.work_dir.mkdir()
    output_root = arguments.work_dir / "control-outputs"
    output_root.mkdir()
    model_source_root = arguments.work_dir / "model-sources"
    model_source_root.mkdir()
    model_sources: dict[str, tuple[Path, str]] = {}
    for item in pool["items"]:
        teacher_id = str(item["id"])
        source_path = arguments.source_root / str(item["filename"])
        samples = parse_pcm16_at_rate(
            source_path.read_bytes(), teacher_id, source_sample_rate
        )
        model_path = model_source_root / f"{teacher_id}.wav"
        base._write_pcm16(
            model_path,
            model_window(samples, source_window_samples),
            rate=source_sample_rate,
        )
        model_sources[teacher_id] = (model_path, base.sha256_file(model_path))

    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise JsutTargetError("CUDA is unavailable")
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
    for index, item in enumerate(pool["items"]):
        teacher_id = str(item["id"])
        target_id = str(item["target_id"])
        source_path, source_digest = model_sources[teacher_id]
        source = base._extract_pair_tensors(
            control,
            pair(teacher_id, source_path, source_digest),
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        if target_id not in target_cache:
            target_path, target_digest = target_by_id[target_id]
            target_cache[target_id] = base._extract_pair_tensors(
                control,
                pair(target_id, target_path, target_digest),
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
        output_row = {
            "target_id": target_id,
            "teacher_id": teacher_id,
            "curriculum_position": item["curriculum_position"],
            "model_source_sha256": source_digest,
            "output_sha256": digest,
        }
        for name in (
            "jsut_category",
            "source_id",
            "exposure",
            "client_id_sha256",
        ):
            if name in item:
                output_row[name] = item[name]
        output_rows.append(output_row)

    method._write_json(arguments.work_dir / "pool.json", pool)
    result = {
        "schema_version": 1,
        "kind": result_kind,
        "status": "completed-training-only-target-render",
        "git_commit": base._git_output(
            ["git", "rev-parse", "HEAD"], "repository commit"
        ),
        "question": question,
        "source_manifest_sha256": base.sha256_file(arguments.source_manifest),
        "control_adapter": str(arguments.control_adapter),
        "rows": output_rows,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "boundary": (
            "training-target preparation only; not evaluation, naturalness, "
            "target identity, a keeper, or promotion"
        ),
    }
    method._write_json(arguments.work_dir / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(output_rows),
                "elapsed_seconds": result["elapsed_seconds"],
                "peak_gpu_bytes": result["peak_gpu_bytes"],
                "output_root": str(output_root),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--pair-root", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    value.add_argument("--work-dir", type=Path, required=True)
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        pool, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "rows": len(pool["items"]),
                        "evaluation_rows": 0,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, pool, targets)
    except (
        JsutTargetError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"jsut-target-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
