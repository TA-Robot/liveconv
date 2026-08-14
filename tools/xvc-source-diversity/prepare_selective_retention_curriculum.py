#!/usr/bin/env python3
"""Bind base repair targets only on hard rows and control69 targets elsewhere."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_clean_post_rehearsal import load_json, sha256_file
from prepare_hard_negative_curriculum import (
    EXPECTED_COMPOSITION,
    HARD_POSITIONS,
)
from prepare_hard_negative_curriculum import (
    OUTPUT_KIND as HARD_INPUT_KIND,
)

OUTPUT_KIND = "liveconv-exp150-selective-retention-curriculum-inputs/v1"
CONTROL_PROBE_KIND = "liveconv-exp145-control-hard-negative-probe/v1"
EXPECTED_ROWS = 170
CONTROL_OUTPUT_ROOT = "control-outputs"
REPAIR_TARGET = "base-teacher-repair"
RETENTION_TARGET = "control69-retention"


class SelectiveRetentionError(RuntimeError):
    """The selective repair/retention curriculum cannot be bound safely."""


def control_rows(probe: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    rows = probe.get("rows")
    if probe.get("kind") != CONTROL_PROBE_KIND or not isinstance(rows, list):
        raise SelectiveRetentionError("control probe schema drifted")
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        teacher_id = row.get("teacher_id") if isinstance(row, dict) else None
        target_id = row.get("target_id") if isinstance(row, dict) else None
        digest = row.get("output_sha256") if isinstance(row, dict) else None
        if (
            not isinstance(teacher_id, str)
            or not teacher_id
            or teacher_id in output
            or not isinstance(target_id, str)
            or not target_id
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise SelectiveRetentionError("control probe row drifted")
        output[teacher_id] = {
            "target_id": target_id,
            "output_sha256": digest,
        }
    if len(output) != EXPECTED_ROWS:
        raise SelectiveRetentionError("control probe coverage drifted")
    return output


def control_output_file(target_id: str, teacher_id: str) -> str:
    return str(
        Path(CONTROL_OUTPUT_ROOT)
        / target_id
        / f"teacher-output-{teacher_id}-16k.wav"
    )


def build_curriculum(
    hard_manifest: Mapping[str, Any], probe: Mapping[str, Any]
) -> dict[str, Any]:
    items = hard_manifest.get("items")
    if (
        hard_manifest.get("kind") != HARD_INPUT_KIND
        or hard_manifest.get("composition") != EXPECTED_COMPOSITION
        or not isinstance(items, list)
        or len(items) != EXPECTED_ROWS
    ):
        raise SelectiveRetentionError("hard curriculum schema drifted")
    controls = control_rows(probe)
    output_items: list[dict[str, Any]] = []
    roles: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise SelectiveRetentionError("hard curriculum row drifted")
        teacher_id = item.get("teacher_id")
        target_id = item.get("target_id")
        curriculum_role = item.get("curriculum_role")
        if (
            not isinstance(teacher_id, str)
            or teacher_id not in controls
            or not isinstance(target_id, str)
            or controls[teacher_id]["target_id"] != target_id
            or curriculum_role not in {"hard", "easy"}
        ):
            raise SelectiveRetentionError("curriculum/probe identity drifted")
        row = dict(item)
        row["base_teacher_target_file"] = item["target_file"]
        row["base_teacher_target_sha256"] = item["target_sha256"]
        if curriculum_role == "hard":
            row["learning_target"] = REPAIR_TARGET
            row["target_root"] = "source-work"
        else:
            row["learning_target"] = RETENTION_TARGET
            row["target_root"] = "control-work"
            row["target_file"] = control_output_file(target_id, teacher_id)
            row["target_sha256"] = controls[teacher_id]["output_sha256"]
        roles[str(row["learning_target"])] += 1
        output_items.append(row)
    expected_roles = {REPAIR_TARGET: HARD_POSITIONS, RETENTION_TARGET: HARD_POSITIONS}
    if dict(roles) != expected_roles:
        raise SelectiveRetentionError("learning-target counts drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "hard_curriculum_sha256": None,
            "control_probe_result_sha256": None,
            "selection": (
                "same EXP-146 85-hard/85-easy schedule; hard rows retain the "
                "clean base-X-VC repair target and easy rows use their frozen "
                "control69 output as a retention target"
            ),
            "boundary": (
                "training-only selective distillation; no heldout, JSUT, local "
                "tongue-twister, naturalness, or target-identity selection"
            ),
        },
        "composition": dict(
            Counter(str(item["domain"]) for item in output_items)
        ),
        "curriculum": dict(hard_manifest.get("curriculum", {})),
        "learning_target_counts": expected_roles,
        "items": output_items,
    }


def validate_control_files(manifest: Mapping[str, Any], control_work: Path) -> None:
    checked: set[str] = set()
    for item in manifest["items"]:
        if item["target_root"] != "control-work":
            continue
        filename = str(item["target_file"])
        if filename in checked:
            continue
        path = control_work / filename
        if path.is_symlink() or not path.is_file() or sha256_file(path) != item[
            "target_sha256"
        ]:
            raise SelectiveRetentionError("control retention audio drifted")
        checked.add(filename)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--hard-curriculum", type=Path, required=True)
    value.add_argument("--control-probe-result", type=Path, required=True)
    value.add_argument("--control-work", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest = build_curriculum(
            load_json(arguments.hard_curriculum),
            load_json(arguments.control_probe_result),
        )
        manifest["source"]["hard_curriculum_sha256"] = sha256_file(
            arguments.hard_curriculum
        )
        manifest["source"]["control_probe_result_sha256"] = sha256_file(
            arguments.control_probe_result
        )
        validate_control_files(manifest, arguments.control_work)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "rows": len(manifest["items"]),
                        "learning_target_counts": manifest[
                            "learning_target_counts"
                        ],
                        "composition": manifest["composition"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.output.exists() or arguments.output.is_symlink():
            raise SelectiveRetentionError("curriculum output already exists")
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "bound",
                    "rows": len(manifest["items"]),
                    "output": str(arguments.output),
                    "sha256": sha256_file(arguments.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (SelectiveRetentionError, OSError, ValueError) as error:
        print(f"selective-retention-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
