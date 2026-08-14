#!/usr/bin/env python3
"""Render control69 targets for EXP-186's speaker-balanced retention rows."""

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
import run as method  # noqa: E402
import render_jsut_retention_targets as shared  # noqa: E402
from prepare_commonvoice_retention_sources import (  # noqa: E402
    EXPECTED_ROWS,
    EXPECTED_SOURCES,
    CommonVoiceRetentionError,
    load_json,
)
from prepare_commonvoice_retention_sources import OUTPUT_KIND as SOURCE_KIND  # noqa: E402

OUTPUT_KIND = "liveconv-exp186-commonvoice48-control69-targets85/v1"
POOL_KIND = "liveconv-exp186-commonvoice48-control69-pool85/v1"


class CommonVoiceTargetError(RuntimeError):
    """The speaker-balanced retention target render cannot continue safely."""


def source_pool(manifest: Mapping[str, Any]) -> dict[str, Any]:
    items = manifest.get("items")
    if manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise CommonVoiceTargetError("Common Voice retention source identity drifted")
    rows: list[dict[str, Any]] = []
    teacher_ids: set[str] = set()
    curriculum_positions: set[int] = set()
    speakers: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise CommonVoiceTargetError("Common Voice retention source row drifted")
        teacher_id = item.get("id")
        filename = item.get("filename")
        source_id = item.get("source_id")
        target_id = item.get("target_id")
        transcript = item.get("source_transcript")
        position = item.get("curriculum_position")
        exposure = item.get("exposure")
        client_id = item.get("client_id_sha256")
        if (
            not isinstance(teacher_id, str)
            or not teacher_id
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or Path(filename).suffix.lower() != ".wav"
            or not isinstance(source_id, str)
            or filename != f"{source_id}.wav"
            or not isinstance(target_id, str)
            or not target_id
            or not isinstance(transcript, str)
            or not transcript
            or not isinstance(position, int)
            or exposure not in {1, 2}
            or not isinstance(client_id, str)
            or len(client_id) != 64
        ):
            raise CommonVoiceTargetError("Common Voice retention source row drifted")
        if teacher_id in teacher_ids or position in curriculum_positions:
            raise CommonVoiceTargetError("Common Voice retention identity duplicated")
        teacher_ids.add(teacher_id)
        curriculum_positions.add(position)
        speakers[source_id] += 1
        rows.append(
            {
                "id": teacher_id,
                "filename": filename,
                "domain": "commonvoice",
                "source_id": source_id,
                "exposure": exposure,
                "client_id_sha256": client_id,
                "source_transcript": transcript,
                "source_sha256": item.get("source_sha256"),
                "target_id": target_id,
                "curriculum_position": position,
            }
        )
    if (
        len(rows) != EXPECTED_ROWS
        or len(speakers) != EXPECTED_SOURCES
        or min(speakers.values(), default=0) != 1
        or max(speakers.values(), default=0) != 2
    ):
        raise CommonVoiceTargetError("Common Voice retention coverage drifted")
    return {
        "schema_version": 1,
        "kind": POOL_KIND,
        "selection": (
            "all 85 precommitted Common Voice speaker exposures; no model "
            "output used"
        ),
        "items": rows,
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[tuple[str, Path, str]]]:
    pool = source_pool(load_json(arguments.source_manifest))
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise CommonVoiceTargetError("Common Voice source root is unavailable")
    checked_sources: set[str] = set()
    for row in pool["items"]:
        source_id = str(row["source_id"])
        if source_id in checked_sources:
            continue
        path = arguments.source_root / str(row["filename"])
        digest = row.get("source_sha256")
        if (
            path.is_symlink()
            or not path.is_file()
            or not isinstance(digest, str)
            or base.sha256_file(path) != digest
        ):
            raise CommonVoiceTargetError("Common Voice source audio drifted")
        checked_sources.add(source_id)
    targets = method.target_inventory(arguments.pair_root)
    target_ids = {row[0] for row in targets}
    if any(row["target_id"] not in target_ids for row in pool["items"]):
        raise CommonVoiceTargetError("Common Voice target identity drifted")
    if arguments.control_adapter.is_symlink() or not (
        arguments.control_adapter / "adapter_model.safetensors"
    ).is_file():
        raise CommonVoiceTargetError("control69 adapter is unavailable")
    method._validate_xvc(arguments)
    base._require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-source-diversity",
        "EXP-186 target work directory",
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
        default=(
            REPO_ROOT / "artifacts" / "exp007" / "phase0-inputs-v1" / "inventory.json"
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
                    {"status": "checked-no-cuda", "rows": len(pool["items"])},
                    sort_keys=True,
                )
            )
            return 0
        return shared.run(
            arguments,
            pool,
            targets,
            result_kind=OUTPUT_KIND,
            question=(
                "Can speaker-balanced Common Voice retention data preserve "
                "ordinary behavior under the surviving EXP-163 method?"
            ),
            experiment_id="EXP-186",
        )
    except (
        CommonVoiceRetentionError,
        CommonVoiceTargetError,
        shared.JsutTargetError,
        base.ListenNowError,
        method.SourceDiversityError,
        OSError,
        ValueError,
    ) as error:
        print(f"commonvoice-target-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
