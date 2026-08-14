#!/usr/bin/env python3
"""Replace only EXP-150 easy rows with EXP-186 Common Voice retention rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_clean_post_rehearsal import load_json, sha256_file
from prepare_commonvoice_retention_sources import EXPECTED_ROWS as RETENTION_ROWS
from prepare_commonvoice_retention_sources import OUTPUT_KIND as SOURCE_KIND
from prepare_selective_retention_curriculum import OUTPUT_KIND as SELECTIVE_KIND
from prepare_selective_retention_curriculum import REPAIR_TARGET, RETENTION_TARGET
from render_commonvoice_retention_targets import OUTPUT_KIND as TARGET_KIND
from screen_teacher_outputs import aggregate

OUTPUT_KIND = "liveconv-exp186-commonvoice48-selective-retention-inputs/v1"
SCREEN_KIND = "liveconv-xvc-pseudo-teacher-output-screen/v1"
EXPECTED_ROWS = 170
EXPECTED_COMPOSITION = {"commonvoice": 125, "hadou": 45}
EXPECTED_TARGET_COUNTS = {REPAIR_TARGET: 85, RETENTION_TARGET: 85}


class CommonVoiceCurriculumError(RuntimeError):
    """The speaker-balanced retention curriculum cannot be bound safely."""


def keyed_rows(
    value: Mapping[str, Any],
    *,
    kind: str,
    key: str,
    expected: int,
    field: str = "items",
) -> dict[Any, dict[str, Any]]:
    items = value.get(field)
    if value.get("kind") != kind or not isinstance(items, list):
        raise CommonVoiceCurriculumError("Common Voice curriculum schema drifted")
    output: dict[Any, dict[str, Any]] = {}
    for item in items:
        identifier = item.get(key) if isinstance(item, dict) else None
        if identifier is None or identifier in output:
            raise CommonVoiceCurriculumError("Common Voice curriculum identity drifted")
        output[identifier] = dict(item)
    if len(output) != expected:
        raise CommonVoiceCurriculumError("Common Voice curriculum coverage drifted")
    return output


def build_curriculum(
    selective: Mapping[str, Any],
    retention_sources: Mapping[str, Any],
    target_result: Mapping[str, Any],
    teacher_screen: Mapping[str, Any],
) -> dict[str, Any]:
    selective_items = selective.get("items")
    if (
        selective.get("kind") != SELECTIVE_KIND
        or not isinstance(selective_items, list)
        or len(selective_items) != EXPECTED_ROWS
    ):
        raise CommonVoiceCurriculumError("selective curriculum identity drifted")
    sources = keyed_rows(
        retention_sources,
        kind=SOURCE_KIND,
        key="curriculum_position",
        expected=RETENTION_ROWS,
    )
    targets = keyed_rows(
        target_result,
        kind=TARGET_KIND,
        key="curriculum_position",
        expected=RETENTION_ROWS,
        field="rows",
    )
    screens = keyed_rows(
        teacher_screen,
        kind=SCREEN_KIND,
        key="teacher_id",
        expected=RETENTION_ROWS,
        field="rows",
    )
    output_items: list[dict[str, Any]] = []
    for position, item in enumerate(selective_items):
        if not isinstance(item, dict) or item.get("curriculum_role") not in {
            "hard",
            "easy",
        }:
            raise CommonVoiceCurriculumError("selective curriculum row drifted")
        if item["curriculum_role"] == "hard":
            row = dict(item)
            row["source_root"] = "source-work"
            output_items.append(row)
            continue
        source = sources.get(position)
        target = targets.get(position)
        if source is None or target is None:
            raise CommonVoiceCurriculumError("easy-position binding drifted")
        teacher_id = str(source.get("id"))
        screen = screens.get(teacher_id)
        target_id = str(item.get("target_id"))
        if (
            target.get("teacher_id") != teacher_id
            or target.get("source_id") != source.get("source_id")
            or target.get("target_id") != target_id
            or screen is None
            or screen.get("target_id") != target_id
            or bool(screen.get("repetition", {}).get("gross_repetition"))
            or not isinstance(target.get("model_source_sha256"), str)
            or not isinstance(target.get("output_sha256"), str)
        ):
            raise CommonVoiceCurriculumError("source/target/screen binding drifted")
        output_items.append(
            {
                "id": f"{position:03d}-easy-{target_id}--{teacher_id}",
                "curriculum_role": "easy",
                "learning_target": RETENTION_TARGET,
                "domain": "commonvoice",
                "source_manifest_id": source["id"],
                "source_root": "diverse-work",
                "source_file": str(Path("model-sources") / f"{teacher_id}.wav"),
                "source_sha256": target["model_source_sha256"],
                "source_transcript": source["source_transcript"],
                "teacher_id": teacher_id,
                "teacher_transcript": screen["output_transcript"],
                "source_relative_distance": screen["source_relative_distance"],
                "control_gross_repetition": False,
                "control_source_relative_distance": screen[
                    "source_relative_distance"
                ],
                "source_speaker_id_sha256": source["client_id_sha256"],
                "source_id": source["source_id"],
                "source_exposure": source["exposure"],
                "target_id": target_id,
                "target_root": "diverse-work",
                "target_file": str(
                    Path("control-outputs")
                    / target_id
                    / f"teacher-output-{teacher_id}-16k.wav"
                ),
                "target_sha256": target["output_sha256"],
            }
        )
    composition = dict(Counter(str(item["domain"]) for item in output_items))
    targets_by_role = dict(
        Counter(str(item["learning_target"]) for item in output_items)
    )
    if composition != EXPECTED_COMPOSITION or targets_by_role != EXPECTED_TARGET_COUNTS:
        raise CommonVoiceCurriculumError("Common Voice curriculum composition drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "selection": (
                "EXP-150 hard85 unchanged; easy85 replaced position-for-position "
                "with 48-speaker Common Voice exposures and frozen non-gross "
                "control69 outputs"
            ),
            "boundary": (
                "training-only data-method comparison; ASR is a gross content "
                "or corruption diagnostic, not quality or a winner"
            ),
        },
        "composition": composition,
        "curriculum": {
            **dict(selective.get("curriculum", {})),
            "easy_unique_speakers": 48,
            "easy_max_speaker_exposures": 2,
        },
        "learning_target_counts": targets_by_role,
        "teacher_screen_aggregate": aggregate(list(screens.values())),
        "items": output_items,
    }


def validate_files(
    manifest: Mapping[str, Any], source_work: Path, diverse_work: Path
) -> None:
    for item in manifest["items"]:
        source_root = (
            diverse_work
            if item.get("source_root") == "diverse-work"
            else source_work
        )
        target_root = (
            diverse_work
            if item.get("target_root") == "diverse-work"
            else source_work
        )
        for path, digest in (
            (source_root / str(item["source_file"]), item["source_sha256"]),
            (target_root / str(item["target_file"]), item["target_sha256"]),
        ):
            if path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
                raise CommonVoiceCurriculumError("curriculum audio drifted")


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
            raise CommonVoiceCurriculumError("curriculum output already exists")
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
        print(f"commonvoice-curriculum-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
