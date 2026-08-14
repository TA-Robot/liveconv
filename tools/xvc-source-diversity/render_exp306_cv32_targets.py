#!/usr/bin/env python3
"""Render EXP-306's 32 frozen-control69 Common Voice teacher targets.

The CPU preparation step intentionally owns all source identity and disjointness
checks.  This script has one CUDA job: run the frozen control69 converter on the
32 new source WAVs, copy the unchanged EXP-238 teacher outputs, and emit the
complete EXP-306 treatment curriculum.  ``--check`` performs no model import
and no CUDA work.
"""

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

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
from prepare_clean_post_rehearsal import load_json, sha256_file  # noqa: E402
from prepare_exp305_exp306_cv32 import (  # noqa: E402
    BASE_COMPOSITION,
    BREADTH_OUTPUT_KIND,
    BREADTH_POOL_KIND,
    EXP238_KIND,
    EXPECTED_NEW_ROWS,
    EXPECTED_ROWS,
    Cv32PreparationError,
)

RESULT_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-target-render/v1"
LEARNING_TARGET = "source-aligned-control69-plus-real-target-adversarial"


class Cv32RenderError(RuntimeError):
    """The bounded EXP-306 target render cannot continue safely."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise Cv32RenderError(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Cv32RenderError(f"{label} path escapes its root")
    return value


def source_pool(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("kind") != BREADTH_POOL_KIND or value.get("composition") != {
        "commonvoice-unpaired": EXPECTED_NEW_ROWS
    }:
        raise Cv32RenderError("EXP-306 pool identity drifted")
    rows = value.get("items")
    if not isinstance(rows, list) or len(rows) != EXPECTED_NEW_ROWS:
        raise Cv32RenderError("EXP-306 pool row count drifted")
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    targets: list[str] = []
    for position, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("position") != position:
            raise Cv32RenderError("EXP-306 pool order drifted")
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in ids:
            raise Cv32RenderError("EXP-306 pool IDs drifted")
        ids.add(identifier)
        for key in ("source_file", "real_target_file"):
            _relative(row.get(key), f"EXP-306 {key}")
        for key in ("source_sha256", "real_target_sha256"):
            if not _is_sha256(row.get(key)):
                raise Cv32RenderError(f"EXP-306 {key} drifted")
        if (
            row.get("source_root") != "source-work"
            or row.get("real_target_root") != "source-work"
            or row.get("domain") != "commonvoice-unpaired"
            or row.get("learning_target") != LEARNING_TARGET
            or not isinstance(row.get("teacher_id"), str)
            or not isinstance(row.get("target_id"), str)
        ):
            raise Cv32RenderError("EXP-306 pool row contract drifted")
        targets.append(str(row["target_id"]))
        output.append(dict(row))
    if len(targets) != EXPECTED_NEW_ROWS:
        raise Cv32RenderError("EXP-306 target assignment count drifted")
    return {
        "schema_version": 1,
        "kind": BREADTH_POOL_KIND,
        "composition": {"commonvoice-unpaired": EXPECTED_NEW_ROWS},
        "items": output,
    }


def _copy_verified(source: Path, destination: Path, digest: str, label: str) -> None:
    if source.is_symlink() or not source.is_file() or sha256_file(source) != digest:
        raise Cv32RenderError(f"{label} audio drifted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise Cv32RenderError(f"render output already exists: {destination}")
    shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise Cv32RenderError(f"{label} copied hash drifted")


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pool = source_pool(load_json(arguments.pool))
    if arguments.source_work.is_symlink() or not arguments.source_work.is_dir():
        raise Cv32RenderError("EXP-306 source-work is unavailable")
    for row in pool["items"]:
        source = arguments.source_work / str(row["source_file"])
        target = arguments.source_work / str(row["real_target_file"])
        for path, digest, label in (
            (source, row["source_sha256"], "source"),
            (target, row["real_target_sha256"], "real target"),
        ):
            if path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
                raise Cv32RenderError(f"EXP-306 {label} audio drifted: {row['id']}")
    if (
        arguments.control_adapter.is_symlink()
        or not (arguments.control_adapter / "adapter_model.safetensors").is_file()
    ):
        raise Cv32RenderError("frozen control69 adapter is unavailable")
    if (
        arguments.base_diverse_work.is_symlink()
        or not arguments.base_diverse_work.is_dir()
    ):
        raise Cv32RenderError("EXP-238 diverse-work is unavailable")
    base_manifest = load_json(arguments.exp238_curriculum)
    rows = base_manifest.get("items")
    if (
        base_manifest.get("kind") != EXP238_KIND
        or base_manifest.get("composition") != BASE_COMPOSITION
        or not isinstance(rows, list)
        or len(rows) != 170
    ):
        raise Cv32RenderError("EXP-238 curriculum identity drifted")
    for row in rows:
        if not isinstance(row, dict):
            raise Cv32RenderError("EXP-238 curriculum row malformed")
        path = arguments.base_diverse_work / str(row.get("target_file"))
        digest = row.get("target_sha256")
        if (
            path.is_symlink()
            or not path.is_file()
            or not _is_sha256(digest)
            or sha256_file(path) != digest
        ):
            raise Cv32RenderError(f"EXP-238 teacher output drifted: {row.get('id')}")
    if (
        arguments.output_diverse_work.exists()
        or arguments.output_diverse_work.is_symlink()
    ):
        raise Cv32RenderError("EXP-306 diverse-work output already exists")
    return pool, base_manifest


def _pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def _build_curriculum(
    base_manifest: Mapping[str, Any],
    pool: Mapping[str, Any],
    rendered: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    base_rows = base_manifest["items"]
    if (
        not isinstance(base_rows, list)
        or len(base_rows) != 170
        or len(rendered) != EXPECTED_NEW_ROWS
    ):
        raise Cv32RenderError("EXP-306 curriculum row count drifted")
    by_position: dict[int, Mapping[str, Any]] = {}
    for row in rendered:
        if not isinstance(row, Mapping) or not isinstance(row.get("position"), int):
            raise Cv32RenderError("EXP-306 rendered row malformed")
        position = int(row["position"])
        if position in by_position or position < 0 or position >= EXPECTED_NEW_ROWS:
            raise Cv32RenderError("EXP-306 rendered order drifted")
        by_position[position] = row
    if set(by_position) != set(range(EXPECTED_NEW_ROWS)):
        raise Cv32RenderError("EXP-306 rendered coverage drifted")
    output_rows = [dict(row) for row in base_rows]
    for source in pool["items"]:
        position = int(source["position"])
        row = by_position[position]
        if (
            row.get("teacher_id") != source["teacher_id"]
            or row.get("target_id") != source["target_id"]
            or not _is_sha256(row.get("output_sha256"))
        ):
            raise Cv32RenderError("EXP-306 source/target identity drifted")
        target_file = _relative(row.get("target_file"), "EXP-306 target")
        if not target_file.startswith("control-outputs/"):
            raise Cv32RenderError("EXP-306 target output path drifted")
        item = dict(source)
        item.update(
            {
                "target_file": target_file,
                "target_sha256": row["output_sha256"],
                "target_root": "diverse-work",
                "target_text": item["source_text"],
                "real_target_text": item.get("target_text"),
                "output_position": position,
            }
        )
        output_rows.append(item)
    if len(output_rows) != EXPECTED_ROWS:
        raise Cv32RenderError("EXP-306 complete curriculum count drifted")
    counts = {}
    for row in output_rows:
        domain = str(row.get("domain"))
        counts[domain] = counts.get(domain, 0) + 1
    if counts != {
        "commonvoice-unpaired": 80,
        "jsut-unpaired": 85,
        "jvs-unpaired": 3,
        "hadou-unpaired": 34,
    }:
        raise Cv32RenderError("EXP-306 composition drifted")
    return {
        "schema_version": 1,
        "kind": BREADTH_OUTPUT_KIND,
        "source": {
            "selection": (
                "exact EXP-238 170 rows plus 32 genuinely unused Common Voice clients"
            ),
            "target": (
                "frozen control69 same-content conversion under the EXP-305 target "
                "assignment"
            ),
            "boundary": (
                "training-only data breadth; ASR/corruption screens cannot establish "
                "naturalness or a winner"
            ),
        },
        "composition": counts,
        "learning_target_counts": {LEARNING_TARGET: EXPECTED_ROWS},
        "items": output_rows,
    }


def run(
    arguments: argparse.Namespace,
    pool: Mapping[str, Any],
    base_manifest: Mapping[str, Any],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise Cv32RenderError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise Cv32RenderError("EXP-306 requires the explicit gpu0 lease")
    started = time.monotonic()
    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise Cv32RenderError("CUDA is unavailable")
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
    target_cache: dict[str, dict[str, Any]] = {}
    arguments.output_diverse_work.mkdir(parents=True)
    output_rows: list[dict[str, Any]] = []
    for position, item in enumerate(pool["items"]):
        source_path = arguments.source_work / str(item["source_file"])
        source = base._extract_pair_tensors(
            control,
            _pair(str(item["teacher_id"]), source_path, str(item["source_sha256"])),
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        target_id = str(item["target_id"])
        if target_id not in target_cache:
            target_path = arguments.source_work / str(item["real_target_file"])
            target_cache[target_id] = base._extract_pair_tensors(
                control,
                _pair(target_id, target_path, str(item["real_target_sha256"])),
                process_audio=process_audio,
                config=config,
                torch=torch,
                device=device,
            )
        waveform = (
            base._inference(
                control,
                source,
                target_cache[target_id],
                seed=base.SEED + position,
                torch=torch,
                device=device,
            )
            .detach()
            .cpu()
        )
        output_path = (
            arguments.output_diverse_work
            / f"control-outputs/cv32-{position:02d}-{item['id']}-16k.wav"
        )
        output_rows.append(
            {
                "position": position,
                "teacher_id": item["teacher_id"],
                "target_id": target_id,
                "target_file": output_path.relative_to(
                    arguments.output_diverse_work
                ).as_posix(),
                "output_sha256": base._write_float_wav(
                    output_path, waveform, sample_rate
                ),
            }
        )
    for row in base_manifest["items"]:
        source = arguments.base_diverse_work / str(row["target_file"])
        destination = arguments.output_diverse_work / str(row["target_file"])
        _copy_verified(
            source,
            destination,
            str(row["target_sha256"]),
            f"EXP-238 teacher {row['id']}",
        )
    curriculum = _build_curriculum(base_manifest, pool, output_rows)
    curriculum_path = arguments.output_diverse_work / "curriculum.json"
    curriculum_path.write_text(
        json.dumps(curriculum, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = {
        "schema_version": 1,
        "kind": RESULT_KIND,
        "status": "completed-training-only-target-render",
        "rows": output_rows,
        "source_pool_sha256": sha256_file(arguments.pool),
        "base_curriculum_sha256": sha256_file(arguments.exp238_curriculum),
        "curriculum_sha256": sha256_file(curriculum_path),
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "boundary": (
            "new training-target preparation only; no listener, winner, or "
            "promotion claim"
        ),
    }
    (arguments.output_diverse_work / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": len(output_rows),
                "elapsed_seconds": result["elapsed_seconds"],
                "peak_gpu_bytes": result["peak_gpu_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--pool", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--exp238-curriculum", type=Path, required=True)
    value.add_argument("--base-diverse-work", type=Path, required=True)
    value.add_argument("--output-diverse-work", type=Path, required=True)
    value.add_argument("--control-adapter", type=Path, required=True)
    value.add_argument("--xvc-source-root", type=Path, required=True)
    value.add_argument("--xvc-config", type=Path, required=True)
    value.add_argument("--checkpoint", type=Path, required=True)
    value.add_argument(
        "--inventory",
        type=Path,
        default=REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json",
    )
    value.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    value.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        pool, base_manifest = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "rows": EXPECTED_NEW_ROWS,
                        "complete_rows": EXPECTED_ROWS,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, pool, base_manifest)
    except (
        Cv32RenderError,
        Cv32PreparationError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        print(f"exp306-cv32-render-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
