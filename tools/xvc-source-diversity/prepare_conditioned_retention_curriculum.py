#!/usr/bin/env python3
"""Bind EXP-191 conditioned retention targets into the selective curriculum."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_clean_post_rehearsal import load_json, sha256_file
from prepare_commonvoice_retention_curriculum import (
    EXPECTED_COMPOSITION,
    EXPECTED_ROWS,
    EXPECTED_TARGET_COUNTS,
    CommonVoiceCurriculumError,
    build_curriculum as build_commonvoice_curriculum,
    validate_files,
)
from prepare_conditioned_retention_sources import OUTPUT_KIND as SOURCE_KIND
from render_conditioned_retention_targets import OUTPUT_KIND as TARGET_KIND

OUTPUT_KIND = "liveconv-exp191-conditioned-selective-retention-inputs/v1"


def build_curriculum(
    selective: Mapping[str, Any],
    sources: Mapping[str, Any],
    target_result: Mapping[str, Any],
    teacher_screen: Mapping[str, Any],
) -> dict[str, Any]:
    result = build_commonvoice_curriculum(
        selective,
        sources,
        target_result,
        teacher_screen,
        source_kind=SOURCE_KIND,
        target_kind=TARGET_KIND,
        output_kind=OUTPUT_KIND,
    )
    condition_counts: dict[str, int] = {}
    for item in result["items"]:
        condition = item.get("source_condition")
        if not isinstance(condition, dict):
            continue
        kind = str(condition["kind"])
        condition_counts[kind] = condition_counts.get(kind, 0) + 1
    if condition_counts != {
        "clean": 17,
        "noise": 17,
        "tempo": 17,
        "pitch": 17,
        "leading-silence": 17,
    }:
        raise CommonVoiceCurriculumError("conditioned curriculum balance drifted")
    result["curriculum"]["easy_condition_counts"] = condition_counts
    result["source"]["selection"] = (
        "EXP-186 hard85 unchanged; easy85 replaced position-for-position by "
        "balanced conditioned sources and their frozen non-gross control69 outputs"
    )
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--selective-curriculum", type=Path, required=True)
    value.add_argument("--retention-sources", type=Path, required=True)
    value.add_argument("--target-result", type=Path, required=True)
    value.add_argument("--teacher-screen", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--diverse-work", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        paths = (
            arguments.selective_curriculum,
            arguments.retention_sources,
            arguments.target_result,
            arguments.teacher_screen,
        )
        manifest = build_curriculum(*(load_json(path) for path in paths))
        manifest["source"].update(
            {
                "selective_curriculum_sha256": sha256_file(paths[0]),
                "retention_sources_sha256": sha256_file(paths[1]),
                "target_result_sha256": sha256_file(paths[2]),
                "teacher_screen_sha256": sha256_file(paths[3]),
            }
        )
        validate_files(manifest, arguments.source_work, arguments.diverse_work)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "rows": len(manifest["items"]),
                        "composition": manifest["composition"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.output.exists() or arguments.output.is_symlink():
            raise CommonVoiceCurriculumError("conditioned curriculum output exists")
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
                    "sha256": sha256_file(arguments.output),
                    "output": str(arguments.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (CommonVoiceCurriculumError, OSError, ValueError) as error:
        print(f"conditioned-curriculum-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
