#!/usr/bin/env python3
"""Render control69 targets from EXP-191 conditioned retention sources."""

from __future__ import annotations

import argparse
import json
import sys
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
import render_jsut_retention_targets as shared  # noqa: E402
import run as method  # noqa: E402
from prepare_conditioned_retention_sources import (  # noqa: E402
    EXPECTED_CONDITION_COUNTS,
    EXPECTED_ROWS,
    EXPECTED_SOURCES,
    ConditionedRetentionError,
    load_json,
)
from prepare_conditioned_retention_sources import OUTPUT_KIND as SOURCE_KIND  # noqa: E402

OUTPUT_KIND = "liveconv-exp191-conditioned-control69-targets85/v1"
POOL_KIND = "liveconv-exp191-conditioned-control69-pool85/v1"


class ConditionedTargetError(RuntimeError):
    """Conditioned control69 target rendering cannot continue safely."""


def source_pool(manifest: Mapping[str, Any]) -> dict[str, Any]:
    items = manifest.get("items")
    if manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise ConditionedTargetError("conditioned source identity drifted")
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    filenames: set[str] = set()
    positions: set[int] = set()
    speakers: set[str] = set()
    conditions: Counter[str] = Counter()
    for item in items:
        teacher_id = item.get("id") if isinstance(item, dict) else None
        filename = item.get("filename") if isinstance(item, dict) else None
        source_id = item.get("source_id") if isinstance(item, dict) else None
        target_id = item.get("target_id") if isinstance(item, dict) else None
        transcript = item.get("source_transcript") if isinstance(item, dict) else None
        position = item.get("curriculum_position") if isinstance(item, dict) else None
        condition = item.get("condition") if isinstance(item, dict) else None
        condition_index = item.get("condition_index") if isinstance(item, dict) else None
        kind = condition.get("kind") if isinstance(condition, dict) else None
        if (
            not isinstance(teacher_id, str)
            or teacher_id in ids
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or filename in filenames
            or not isinstance(source_id, str)
            or not isinstance(target_id, str)
            or not target_id
            or not isinstance(transcript, str)
            or not transcript
            or not isinstance(position, int)
            or position in positions
            or not isinstance(condition_index, int)
            or not isinstance(kind, str)
        ):
            raise ConditionedTargetError("conditioned source row drifted")
        ids.add(teacher_id)
        filenames.add(filename)
        positions.add(position)
        speakers.add(source_id)
        conditions[kind] += 1
        rows.append(
            {
                "id": teacher_id,
                "filename": filename,
                "domain": "commonvoice",
                "source_id": source_id,
                "exposure": item.get("exposure"),
                "client_id_sha256": item.get("client_id_sha256"),
                "source_transcript": transcript,
                "source_sha256": item.get("source_sha256"),
                "target_id": target_id,
                "curriculum_position": position,
                "condition": condition,
                "condition_index": condition_index,
            }
        )
    if (
        len(rows) != EXPECTED_ROWS
        or len(speakers) != EXPECTED_SOURCES
        or dict(conditions) != EXPECTED_CONDITION_COUNTS
    ):
        raise ConditionedTargetError("conditioned source coverage drifted")
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "selection": "all 85 precommitted conditioned exposures",
        "items": rows,
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    pool = source_pool(load_json(arguments.source_manifest))
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise ConditionedTargetError("conditioned source root is unavailable")
    for row in pool["items"]:
        path = arguments.source_root / str(row["filename"])
        digest = row.get("source_sha256")
        if (
            path.is_symlink()
            or not path.is_file()
            or not isinstance(digest, str)
            or base.sha256_file(path) != digest
        ):
            raise ConditionedTargetError("conditioned source audio drifted")
    targets = method.target_inventory(arguments.pair_root)
    target_ids = {row[0] for row in targets}
    if any(row["target_id"] not in target_ids for row in pool["items"]):
        raise ConditionedTargetError("conditioned target identity drifted")
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise ConditionedTargetError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-191 target work directory",
    )
    return pool, targets


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
        default=REPO_ROOT / "artifacts" / "exp007" / "phase0-inputs-v1" / "inventory.json",
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
            print(json.dumps({"status": "checked-no-cuda", "rows": len(pool["items"])}, sort_keys=True))
            return 0
        return shared.run(
            arguments,
            pool,
            targets,
            result_kind=OUTPUT_KIND,
            question=(
                "Can control69 retention targets generated from conditioned real "
                "sources preserve route limitations under selective repair?"
            ),
            experiment_id="EXP-191",
            source_sample_rate=16_000,
            source_window_samples=38_400,
        )
    except (
        ConditionedRetentionError,
        ConditionedTargetError,
        shared.JsutTargetError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"conditioned-target-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
