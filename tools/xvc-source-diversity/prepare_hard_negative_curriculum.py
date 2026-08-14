#!/usr/bin/env python3
"""Bind a fixed 50/50 hard/easy curriculum from training-only control outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_clean_post_rehearsal import load_json, sha256_file

CLEAN_KIND = "liveconv-exp141-clean-post-rehearsal-inputs/v1"
SCREEN_KIND = "liveconv-xvc-pseudo-teacher-output-screen/v1"
OUTPUT_KIND = "liveconv-exp146-hard-negative-curriculum-inputs/v1"
EXPECTED_ROWS = 170
EXPECTED_HARD_ROWS = 11
EXPECTED_GROSS_ROWS = 1
HARD_POSITIONS = 85
EASY_DOMAIN_COUNTS = {"commonvoice": 16, "hadou": 66, "jvs": 3}
EXPECTED_COMPOSITION = {"commonvoice": 56, "hadou": 111, "jvs": 3}


class HardCurriculumError(RuntimeError):
    """The hard-negative curriculum cannot be reproduced safely."""


def stratified_positions(row_count: int, selection_count: int) -> list[int]:
    if selection_count <= 0 or row_count < selection_count:
        raise HardCurriculumError("invalid easy-row selection size")
    positions = [
        ((2 * index + 1) * row_count) // (2 * selection_count)
        for index in range(selection_count)
    ]
    if len(set(positions)) != selection_count or positions[-1] >= row_count:
        raise HardCurriculumError("easy-row positions drifted")
    return positions


def screen_by_teacher(screen: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = screen.get("rows")
    if screen.get("kind") != SCREEN_KIND or not isinstance(rows, list):
        raise HardCurriculumError("control screen schema drifted")
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        teacher_id = row.get("teacher_id") if isinstance(row, dict) else None
        repetition = row.get("repetition") if isinstance(row, dict) else None
        distance = (
            row.get("source_relative_distance") if isinstance(row, dict) else None
        )
        if (
            not isinstance(teacher_id, str)
            or not teacher_id
            or teacher_id in output
            or not isinstance(repetition, dict)
            or not isinstance(repetition.get("gross_repetition"), bool)
            or not isinstance(distance, (int, float))
        ):
            raise HardCurriculumError("control screen row drifted")
        output[teacher_id] = dict(row)
    if len(output) != EXPECTED_ROWS:
        raise HardCurriculumError("control screen coverage drifted")
    return output


def build_curriculum(
    clean: Mapping[str, Any], screen: Mapping[str, Any]
) -> dict[str, Any]:
    clean_items = clean.get("items")
    if (
        clean.get("kind") != CLEAN_KIND
        or not isinstance(clean_items, list)
        or len(clean_items) != EXPECTED_ROWS
    ):
        raise HardCurriculumError("clean manifest schema drifted")
    screen_rows = screen_by_teacher(screen)
    clean_ids = {
        item.get("teacher_id") for item in clean_items if isinstance(item, dict)
    }
    if clean_ids != set(screen_rows):
        raise HardCurriculumError("control screen identity binding drifted")

    hard: list[dict[str, Any]] = []
    easy_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in clean_items:
        if not isinstance(item, dict):
            raise HardCurriculumError("clean manifest row drifted")
        screen_row = screen_rows[str(item["teacher_id"])]
        is_hard = bool(screen_row["repetition"]["gross_repetition"]) or float(
            screen_row["source_relative_distance"]
        ) >= 0.5
        enriched = dict(item)
        enriched["control_source_relative_distance"] = screen_row[
            "source_relative_distance"
        ]
        enriched["control_gross_repetition"] = screen_row["repetition"][
            "gross_repetition"
        ]
        if is_hard:
            hard.append(enriched)
        else:
            easy_by_domain[str(item["domain"])].append(enriched)
    if (
        len(hard) != EXPECTED_HARD_ROWS
        or sum(bool(item["control_gross_repetition"]) for item in hard)
        != EXPECTED_GROSS_ROWS
    ):
        raise HardCurriculumError("hard-negative frontier drifted")

    easy: list[dict[str, Any]] = []
    for domain, count in EASY_DOMAIN_COUNTS.items():
        rows = easy_by_domain.get(domain, [])
        easy.extend(rows[index] for index in stratified_positions(len(rows), count))
    if len(easy) != EXPECTED_ROWS - HARD_POSITIONS:
        raise HardCurriculumError("easy-row curriculum count drifted")

    items: list[dict[str, Any]] = []
    for index in range(HARD_POSITIONS):
        for role, source in (
            ("hard", hard[index % len(hard)]),
            ("easy", easy[index]),
        ):
            row = dict(source)
            row["source_manifest_id"] = source["id"]
            row["id"] = f"{2 * index:03d}-{role}-{source['id']}"
            if role == "easy":
                row["id"] = f"{2 * index + 1:03d}-{role}-{source['id']}"
            row["curriculum_role"] = role
            items.append(row)
    composition = dict(Counter(str(item["domain"]) for item in items))
    if len(items) != EXPECTED_ROWS or composition != EXPECTED_COMPOSITION:
        raise HardCurriculumError("curriculum composition drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "clean_manifest_sha256": clean.get("source", {}).get(
                "teacher_manifest_sha256"
            ),
            "control_screen_sha256": None,
            "selection": (
                "170 fixed updates alternating 85 control-hard positions and "
                "85 domain-stratified clean positions; hard means gross "
                "repetition or source-relative distance >= 0.5"
            ),
            "boundary": (
                "training-only failure sampling; no heldout, JSUT, local "
                "tongue-twister, naturalness, or target-identity selection"
            ),
        },
        "composition": composition,
        "curriculum": {
            "hard_positions": HARD_POSITIONS,
            "unique_hard_rows": len(hard),
            "gross_hard_rows": EXPECTED_GROSS_ROWS,
            "easy_positions": len(easy),
            "easy_domain_counts": EASY_DOMAIN_COUNTS,
        },
        "items": items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--clean-manifest", type=Path, required=True)
    value.add_argument("--control-screen", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        clean = load_json(arguments.clean_manifest)
        screen = load_json(arguments.control_screen)
        manifest = build_curriculum(clean, screen)
        manifest["source"]["clean_manifest_sha256"] = sha256_file(
            arguments.clean_manifest
        )
        manifest["source"]["control_screen_sha256"] = sha256_file(
            arguments.control_screen
        )
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "rows": len(manifest["items"]),
                        "curriculum": manifest["curriculum"],
                        "composition": manifest["composition"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.output.exists() or arguments.output.is_symlink():
            raise HardCurriculumError("curriculum output already exists")
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
    except (HardCurriculumError, OSError, ValueError) as error:
        print(f"hard-curriculum-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
