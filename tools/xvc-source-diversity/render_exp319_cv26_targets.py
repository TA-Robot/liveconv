#!/usr/bin/env python3
"""Render EXP-319's 26 frozen-control69 active-window teacher targets.

The source/window materializer owns Common Voice decoding and source identity.
This bounded CUDA step validates that pool, renders only the 26 replacement
teachers, copies the verified EXP-238 teachers, and emits the complete 170-row
curriculum.  ``--check`` performs no model import and no CUDA work.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
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

EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
POOL_KIND = "liveconv-exp319-xvc-cv26-active-window-pool/v1"
OUTPUT_KIND = "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-inputs/v1"
RESULT_KIND = "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-target-render/v1"
LEARNING_TARGET = "source-aligned-control69-plus-real-target-adversarial"

EXPECTED_ROWS = 170
EXPECTED_NEW_ROWS = 26
BASE_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}
REPLACEMENT_POSITIONS = [
    4,
    5,
    6,
    11,
    13,
    16,
    19,
    25,
    27,
    30,
    35,
    36,
    39,
    43,
    48,
    54,
    55,
    57,
    58,
    59,
    63,
    71,
    75,
    86,
    101,
    103,
]


class Cv26RenderError(RuntimeError):
    """The bounded EXP-319 target render cannot continue safely."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise Cv26RenderError(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Cv26RenderError(f"{label} path escapes its root")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise Cv26RenderError(f"{label} identity is malformed")
    return value


def _validate_audio(path: Path, digest: object, label: str) -> None:
    if path.is_symlink() or not path.is_file() or not _is_sha256(digest):
        raise Cv26RenderError(f"{label} audio is unavailable")
    if sha256_file(path) != digest:
        raise Cv26RenderError(f"{label} audio hash drifted")


def base_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = value.get("items")
    if (
        value.get("kind") != EXP238_KIND
        or value.get("composition") != BASE_COMPOSITION
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
        or not all(isinstance(item, dict) for item in items)
    ):
        raise Cv26RenderError("EXP-238 curriculum identity drifted")
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    teachers: set[str] = set()
    for index, item in enumerate(items):
        identifier = _identifier(item.get("id"), f"EXP-238 row {index}")
        teacher_id = _identifier(item.get("teacher_id"), f"EXP-238 row {index}")
        if identifier in ids or teacher_id in teachers:
            raise Cv26RenderError("EXP-238 row identities are not unique")
        for key in ("source_file", "target_file", "real_target_file"):
            _relative(item.get(key), f"EXP-238 {key}")
        for key in ("source_sha256", "target_sha256", "real_target_sha256"):
            if not _is_sha256(item.get(key)):
                raise Cv26RenderError(f"EXP-238 {key} drifted")
        if (
            item.get("source_root") != "source-work"
            or item.get("target_root") != "diverse-work"
            or item.get("real_target_root") != "source-work"
            or item.get("learning_target") != LEARNING_TARGET
        ):
            raise Cv26RenderError("EXP-238 source/target root contract drifted")
        ids.add(identifier)
        teachers.add(teacher_id)
        output.append(dict(item))
    return output


def source_pool(value: Mapping[str, Any]) -> dict[str, Any]:
    items = value.get("items")
    if (
        value.get("kind") != POOL_KIND
        or value.get("composition") != {"commonvoice-unpaired": EXPECTED_NEW_ROWS}
        or not isinstance(items, list)
        or len(items) != EXPECTED_NEW_ROWS
        or not all(isinstance(item, dict) for item in items)
    ):
        raise Cv26RenderError("EXP-319 pool identity drifted")
    output: list[dict[str, Any]] = []
    ids: set[str] = set()
    teachers: set[str] = set()
    sources: set[str] = set()
    pool_positions: set[int] = set()
    for expected_position, item in zip(REPLACEMENT_POSITIONS, items, strict=True):
        position = item.get("curriculum_position")
        if position != expected_position:
            raise Cv26RenderError("EXP-319 absolute position order drifted")
        if "position" in item:
            local_position = item.get("position")
            if (
                not isinstance(local_position, int)
                or local_position < 0
                or local_position in pool_positions
            ):
                raise Cv26RenderError("EXP-319 pool position identity drifted")
            pool_positions.add(local_position)
        identifier = _identifier(item.get("id"), "EXP-319 row")
        teacher_id = _identifier(item.get("teacher_id"), "EXP-319 row")
        if identifier in ids or teacher_id in teachers:
            raise Cv26RenderError("EXP-319 row identities are not unique")
        for key in ("source_file", "real_target_file"):
            _relative(item.get(key), f"EXP-319 {key}")
        for key in ("source_sha256", "real_target_sha256"):
            if not _is_sha256(item.get(key)):
                raise Cv26RenderError(f"EXP-319 {key} drifted")
        source_file = str(item["source_file"])
        if source_file in sources:
            raise Cv26RenderError("EXP-319 source files are not unique")
        if (
            item.get("domain") != "commonvoice-unpaired"
            or item.get("source_root") != "source-work"
            or item.get("real_target_root") != "source-work"
            or item.get("target_root") != "diverse-work"
            or item.get("learning_target") != LEARNING_TARGET
            or not _identifier(item.get("target_id"), "EXP-319 target")
            or not isinstance(item.get("source_text"), str)
            or not item["source_text"]
        ):
            raise Cv26RenderError("EXP-319 pool row contract drifted")
        ids.add(identifier)
        teachers.add(teacher_id)
        sources.add(source_file)
        output.append(dict(item))
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "composition": {"commonvoice-unpaired": EXPECTED_NEW_ROWS},
        "items": output,
    }


def _copy_verified(source: Path, destination: Path, digest: str, label: str) -> None:
    _validate_audio(source, digest, label)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise Cv26RenderError(f"render output already exists: {destination}")
    shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise Cv26RenderError(f"{label} copied hash drifted")


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pool = source_pool(load_json(arguments.pool))
    manifest = load_json(arguments.exp238_curriculum)
    rows = base_rows(manifest)
    if arguments.source_work.is_symlink() or not arguments.source_work.is_dir():
        raise Cv26RenderError("EXP-319 source-work is unavailable")
    for row in rows:
        _validate_audio(
            arguments.source_work / str(row["source_file"]),
            row["source_sha256"],
            f"EXP-238 source {row['id']}",
        )
        _validate_audio(
            arguments.source_work / str(row["real_target_file"]),
            row["real_target_sha256"],
            f"EXP-238 real target {row['id']}",
        )
    for row in pool["items"]:
        _validate_audio(
            arguments.source_work / str(row["source_file"]),
            row["source_sha256"],
            f"EXP-319 source {row['id']}",
        )
        _validate_audio(
            arguments.source_work / str(row["real_target_file"]),
            row["real_target_sha256"],
            f"EXP-319 real target {row['id']}",
        )
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise Cv26RenderError("frozen control69 adapter is unavailable")
    if arguments.base_diverse_work.is_symlink() or not arguments.base_diverse_work.is_dir():
        raise Cv26RenderError("EXP-238 diverse-work is unavailable")
    for row in rows:
        _validate_audio(
            arguments.base_diverse_work / str(row["target_file"]),
            row["target_sha256"],
            f"EXP-238 teacher {row['id']}",
        )
    if arguments.output_diverse_work.exists() or arguments.output_diverse_work.is_symlink():
        raise Cv26RenderError("EXP-319 diverse-work output already exists")
    return pool, manifest


def _pair(identifier: str, path: Path, digest: str) -> base.MaterializedPair:
    return base.MaterializedPair(identifier, path, path, digest, digest)


def _build_curriculum(
    manifest: Mapping[str, Any],
    pool: Mapping[str, Any],
    rendered: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    original = base_rows(manifest)
    if len(rendered) != EXPECTED_NEW_ROWS:
        raise Cv26RenderError("EXP-319 rendered row count drifted")
    by_position: dict[int, Mapping[str, Any]] = {}
    for row in rendered:
        position = row.get("position")
        if not isinstance(position, int) or position in by_position:
            raise Cv26RenderError("EXP-319 rendered position is malformed")
        if position not in REPLACEMENT_POSITIONS:
            raise Cv26RenderError("EXP-319 rendered coverage drifted")
        by_position[position] = row
    if set(by_position) != set(REPLACEMENT_POSITIONS):
        raise Cv26RenderError("EXP-319 rendered coverage drifted")
    output_rows = [dict(row) for row in original]
    for pool_row in pool["items"]:
        position = int(pool_row["curriculum_position"])
        base_row = original[position]
        for key in (
            "target_id",
            "real_target_root",
            "real_target_file",
            "real_target_sha256",
        ):
            if pool_row.get(key) != base_row.get(key):
                raise Cv26RenderError(
                    f"EXP-319 position-specific target drifted: {position}"
                )
        if "real_target_text" in pool_row and pool_row.get("real_target_text") != base_row.get(
            "real_target_text"
        ):
            raise Cv26RenderError(
                f"EXP-319 position-specific target text drifted: {position}"
            )
        rendered_row = by_position[position]
        if (
            rendered_row.get("teacher_id") != pool_row.get("teacher_id")
            or rendered_row.get("target_id") != pool_row.get("target_id")
            or not _is_sha256(rendered_row.get("output_sha256"))
        ):
            raise Cv26RenderError(f"EXP-319 rendered source/target identity drifted: {position}")
        target_file = _relative(rendered_row.get("target_file"), "EXP-319 target")
        if not target_file.startswith("control-outputs/"):
            raise Cv26RenderError("EXP-319 target output path drifted")
        item = dict(pool_row)
        item.update(
            {
                "target_file": target_file,
                "target_sha256": rendered_row["output_sha256"],
                "target_root": "diverse-work",
                "target_text": item["source_text"],
                "real_target_text": base_row.get("real_target_text"),
                "output_position": position,
            }
        )
        output_rows[position] = item
    for position, (before, after) in enumerate(zip(original, output_rows, strict=True)):
        if position not in REPLACEMENT_POSITIONS and after != before:
            raise Cv26RenderError(f"EXP-319 unchanged EXP-238 row drifted: {position}")
    composition = dict(Counter(str(row.get("domain")) for row in output_rows))
    if composition != BASE_COMPOSITION:
        raise Cv26RenderError("EXP-319 composition drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "selection": (
                "exact EXP-238 170 rows with the 26 EXP-319 active-window sources "
                "at their absolute schedule positions"
            ),
            "replacement_positions": REPLACEMENT_POSITIONS,
            "target": "fresh frozen control69 teachers with EXP-238 position-specific real Amitaro targets",
            "boundary": "training-only target preparation; no naturalness, keeper, or winner claim",
        },
        "composition": composition,
        "learning_target_counts": dict(
            Counter(str(row.get("learning_target")) for row in output_rows)
        ),
        "items": output_rows,
    }


def _create_output_root(path: Path) -> Path:
    path.mkdir(parents=True)
    control_outputs = path / "control-outputs"
    control_outputs.mkdir()
    return control_outputs


def run(
    arguments: argparse.Namespace,
    pool: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise Cv26RenderError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise Cv26RenderError("EXP-319 requires the explicit gpu0 lease")
    started = time.monotonic()
    import torch
    from peft import PeftModel

    if not torch.cuda.is_available():
        raise Cv26RenderError("CUDA is unavailable")
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
    output_root = _create_output_root(arguments.output_diverse_work)
    output_rows: list[dict[str, Any]] = []
    for item in pool["items"]:
        position = int(item["curriculum_position"])
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
        output_path = output_root / f"cv26-{position:03d}-{item['id']}-16k.wav"
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
    for row in base_rows(manifest):
        _copy_verified(
            arguments.base_diverse_work / str(row["target_file"]),
            arguments.output_diverse_work / str(row["target_file"]),
            str(row["target_sha256"]),
            f"EXP-238 teacher {row['id']}",
        )
    curriculum = _build_curriculum(manifest, pool, output_rows)
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
        "boundary": "new training-target preparation only; no listener, winner, or promotion claim",
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
        pool, manifest = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "rows": EXPECTED_NEW_ROWS,
                        "complete_rows": EXPECTED_ROWS,
                        "replacement_positions": REPLACEMENT_POSITIONS,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, pool, manifest)
    except (
        Cv26RenderError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
        KeyError,
    ) as error:
        print(f"exp319-cv26-render-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
