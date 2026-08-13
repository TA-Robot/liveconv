#!/usr/bin/env python3
"""Bind clean, unique EXP-138 teacher outputs for post-adaptation rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCREEN_KIND = "liveconv-xvc-pseudo-teacher-output-screen/v1"
RESULT_KIND = "liveconv-exp138-xvc-real-teacher-window201/v1"
TEACHER_MANIFEST_SHA256 = (
    "a8ac653b59fa3566bd9d5a0e51bb0e20f5a7de79ad4ee4ce2ac7d14324f18dda"
)
SOURCE_COMMIT = "a6f8727a043312e730560b453b62abb9f55952c3"
DISTANCE_LIMIT = 0.5
EXPECTED_ROWS = 170
EXPECTED_DOMAINS = {"commonvoice": 35, "hadou": 132, "jvs": 3}
OUTPUT_KIND = "liveconv-exp141-clean-post-rehearsal-inputs/v1"


class CleanTeacherError(RuntimeError):
    """The clean teacher binding cannot be reproduced safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CleanTeacherError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise CleanTeacherError(f"malformed JSON object: {path.name}")
    return value


def admitted_rows(screen: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = screen.get("rows")
    if (
        screen.get("kind") != SCREEN_KIND
        or screen.get("teacher_manifest_sha256") != TEACHER_MANIFEST_SHA256
        or not isinstance(rows, list)
        or len(rows) != 209
    ):
        raise CleanTeacherError("EXP-138 pseudo-teacher screen drifted")
    admitted: list[dict[str, Any]] = []
    seen_teachers: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise CleanTeacherError("pseudo-teacher screen row is malformed")
        repetition = row.get("repetition")
        teacher_id = row.get("teacher_id")
        distance = row.get("source_relative_distance")
        if (
            not isinstance(repetition, dict)
            or not isinstance(teacher_id, str)
            or not teacher_id
            or not isinstance(row.get("target_id"), str)
            or not isinstance(row.get("domain"), str)
            or not isinstance(distance, (int, float))
        ):
            raise CleanTeacherError("pseudo-teacher identity is malformed")
        if (
            repetition.get("gross_repetition") is True
            or float(distance) >= DISTANCE_LIMIT
            or teacher_id in seen_teachers
        ):
            continue
        seen_teachers.add(teacher_id)
        admitted.append(dict(row))
    if (
        len(admitted) != EXPECTED_ROWS
        or dict(Counter(str(row["domain"]) for row in admitted))
        != EXPECTED_DOMAINS
    ):
        raise CleanTeacherError("clean teacher admission count drifted")
    return admitted


def build_manifest(
    rows: Sequence[Mapping[str, Any]], source_work: Path
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in rows:
        teacher_id = str(row["teacher_id"])
        target_id = str(row["target_id"])
        if Path(teacher_id).name != teacher_id or Path(target_id).name != target_id:
            raise CleanTeacherError("teacher path component is unsafe")
        source_relative = Path("teacher-references") / f"{teacher_id}.wav"
        target_relative = (
            Path("verified-generated-source-pairs")
            / target_id
            / f"teacher-output-{teacher_id}-16k.wav"
        )
        source_path = source_work / source_relative
        target_path = source_work / target_relative
        if (
            source_path.is_symlink()
            or target_path.is_symlink()
            or not source_path.is_file()
            or not target_path.is_file()
            or sha256_file(source_path) != row.get("source_sha256")
            or sha256_file(target_path) != row.get("output_sha256")
        ):
            raise CleanTeacherError(f"teacher audio drifted: {teacher_id}")
        items.append(
            {
                "id": f"{target_id}--{teacher_id}",
                "domain": row["domain"],
                "teacher_id": teacher_id,
                "target_id": target_id,
                "source_file": source_relative.as_posix(),
                "source_sha256": row["source_sha256"],
                "target_file": target_relative.as_posix(),
                "target_sha256": row["output_sha256"],
                "source_transcript": row.get("source_transcript", ""),
                "teacher_transcript": row.get("output_transcript", ""),
                "source_relative_distance": row["source_relative_distance"],
            }
        )
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "experiment": "EXP-138",
            "git_commit": SOURCE_COMMIT,
            "teacher_manifest_sha256": TEACHER_MANIFEST_SHA256,
            "admission": (
                "first occurrence of each real teacher id; no gross repetition; "
                "source-relative auxiliary ASR distance < 0.5"
            ),
            "boundary": (
                "Machine content/corruption admission only; not naturalness, "
                "speaker similarity, or a quality winner"
            ),
        },
        "composition": EXPECTED_DOMAINS,
        "items": items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = load_json(arguments.source_work / "result.json")
        if (
            result.get("kind") != RESULT_KIND
            or result.get("git_commit") != SOURCE_COMMIT
            or result.get("fixed", {}).get("real_teacher_manifest_sha256")
            != TEACHER_MANIFEST_SHA256
        ):
            raise CleanTeacherError("EXP-138 result identity drifted")
        screen_path = arguments.source_work / "pseudo-teacher-screen.json"
        rows = admitted_rows(load_json(screen_path))
        manifest = build_manifest(rows, arguments.source_work)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "rows": len(rows),
                        "composition": EXPECTED_DOMAINS,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.output.exists() or arguments.output.is_symlink():
            raise CleanTeacherError("output already exists")
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "bound",
                    "rows": len(rows),
                    "output": str(arguments.output),
                    "sha256": sha256_file(arguments.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (CleanTeacherError, OSError, ValueError) as error:
        print(f"exp141-clean-teacher-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
