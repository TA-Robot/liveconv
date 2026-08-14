#!/usr/bin/env python3
"""Freeze disjoint category-balanced JSUT sources for retention training."""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_jsut_evaluation import (
    OFFICIAL_ARCHIVE_SHA256,
    JsutEvaluationError,
    _read_member,
    parse_transcript,
    sha256_bytes,
    sha256_file,
    stratified_positions,
    wav_metadata,
)
from prepare_jsut_evaluation import OUTPUT_KIND as EVALUATION_KIND
from prepare_selective_retention_curriculum import OUTPUT_KIND as SELECTIVE_KIND

OUTPUT_KIND = "liveconv-exp169-jsut-retention-sources85/v1"
CATEGORY_COUNTS: Mapping[str, int] = {
    "basic5000": 29,
    "onomatopee300": 14,
    "countersuffix26": 14,
    "loanword128": 14,
    "travel1000": 14,
}
EXPECTED_ROWS = sum(CATEGORY_COUNTS.values())
SELECTION_POLICY = (
    "exclude frozen JSUT24 IDs, then take equal-width transcript-order bin "
    "centers without reading text, audio, or model output"
)


class JsutRetentionError(RuntimeError):
    """The disjoint JSUT retention source set cannot be frozen safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JsutRetentionError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise JsutRetentionError(f"JSON root is not an object: {path.name}")
    return value


def select_training_rows(
    transcript: Sequence[tuple[str, str]],
    excluded_identifiers: set[str],
    count: int,
) -> list[tuple[int, str, str]]:
    available = [
        (position, identifier, text)
        for position, (identifier, text) in enumerate(transcript, start=1)
        if identifier not in excluded_identifiers
    ]
    positions = stratified_positions(len(available), count)
    selected = [available[position] for position in positions]
    if (
        len(selected) != count
        or len({identifier for _, identifier, _ in selected}) != count
        or any(identifier in excluded_identifiers for _, identifier, _ in selected)
    ):
        raise JsutRetentionError("JSUT retention selection drifted")
    return selected


def easy_slots(selective: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = selective.get("items")
    if selective.get("kind") != SELECTIVE_KIND or not isinstance(items, list):
        raise JsutRetentionError("selective curriculum identity drifted")
    slots = [
        {
            "curriculum_position": position,
            "source_manifest_id": str(item["source_manifest_id"]),
            "target_id": str(item["target_id"]),
        }
        for position, item in enumerate(items)
        if isinstance(item, dict) and item.get("curriculum_role") == "easy"
    ]
    positions = {row["curriculum_position"] for row in slots}
    if len(slots) != EXPECTED_ROWS or len(positions) != EXPECTED_ROWS:
        raise JsutRetentionError("selective easy-slot count drifted")
    return slots


def build(
    archive_path: Path,
    evaluation_path: Path,
    selective_path: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise JsutRetentionError("JSUT archive is unavailable")
    archive_sha256 = sha256_file(archive_path)
    if archive_sha256 != OFFICIAL_ARCHIVE_SHA256:
        raise JsutRetentionError("JSUT archive identity drifted")
    evaluation = load_json(evaluation_path)
    evaluation_items = evaluation.get("items")
    if evaluation.get("kind") != EVALUATION_KIND or not isinstance(
        evaluation_items, list
    ):
        raise JsutRetentionError("frozen JSUT evaluation identity drifted")
    excluded_by_category: dict[str, set[str]] = {
        category: set() for category in CATEGORY_COUNTS
    }
    for item in evaluation_items:
        category = item.get("jsut_category") if isinstance(item, dict) else None
        filename = item.get("filename") if isinstance(item, dict) else None
        if category not in excluded_by_category or not isinstance(filename, str):
            raise JsutRetentionError("frozen JSUT evaluation row drifted")
        excluded_by_category[category].add(Path(filename).stem)
    selective = load_json(selective_path)
    slots = easy_slots(selective)

    selected_rows: list[dict[str, Any]] = []
    audio: dict[str, bytes] = {}
    with zipfile.ZipFile(archive_path) as archive:
        for category, count in CATEGORY_COUNTS.items():
            transcript_name = f"jsut_ver1.1/{category}/transcript_utf8.txt"
            transcript = parse_transcript(
                _read_member(archive, transcript_name), category
            )
            for transcript_position, identifier, text in select_training_rows(
                transcript, excluded_by_category[category], count
            ):
                filename = f"{identifier}.wav"
                member = f"jsut_ver1.1/{category}/wav/{filename}"
                value = _read_member(archive, member)
                sample_rate, duration = wav_metadata(value, identifier)
                if filename in audio:
                    raise JsutRetentionError("duplicate JSUT retention filename")
                audio[filename] = value
                selected_rows.append(
                    {
                        "id": f"jsut-retention-{identifier.lower()}",
                        "filename": filename,
                        "sha256": sha256_bytes(value),
                        "source_transcript": text,
                        "duration_seconds": duration,
                        "sample_rate": sample_rate,
                        "domain": "jsut",
                        "jsut_category": category,
                        "transcript_position": transcript_position,
                        "selection_policy": SELECTION_POLICY,
                    }
                )
    if len(selected_rows) != EXPECTED_ROWS or len(audio) != EXPECTED_ROWS:
        raise JsutRetentionError("JSUT retention row count drifted")
    items = [
        {
            **row,
            **slot,
        }
        for row, slot in zip(selected_rows, slots, strict=True)
    ]
    composition = dict(Counter(str(item["jsut_category"]) for item in items))
    if composition != dict(CATEGORY_COUNTS):
        raise JsutRetentionError("JSUT retention composition drifted")
    manifest = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "name": "JSUT corpus version 1.1",
            "archive_sha256": archive_sha256,
            "license": "JSUT-LICENCE.txt (category-specific CC BY/CC BY-SA)",
            "redistribution": "audio excluded from git and result bundles",
        },
        "selection": {
            "policy": SELECTION_POLICY,
            "category_counts": dict(CATEGORY_COUNTS),
            "excluded_evaluation_rows": len(evaluation_items),
        },
        "evaluation_manifest_sha256": sha256_file(evaluation_path),
        "selective_curriculum_sha256": sha256_file(selective_path),
        "composition": composition,
        "items": items,
    }
    return manifest, audio


def materialize(
    output_root: Path,
    manifest: Mapping[str, Any],
    audio: Mapping[str, bytes],
) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise JsutRetentionError("JSUT retention output already exists")
    output_root.mkdir(parents=True)
    source_root = output_root / "source-wav"
    source_root.mkdir()
    for filename, value in audio.items():
        (source_root / filename).write_bytes(value)
    (output_root / "sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--archive", type=Path, required=True)
    value.add_argument("--evaluation", type=Path, required=True)
    value.add_argument("--selective-curriculum", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, audio = build(
            arguments.archive,
            arguments.evaluation,
            arguments.selective_curriculum,
        )
        if not arguments.check:
            materialize(arguments.output_root, manifest, audio)
        print(
            json.dumps(
                {
                    "status": "checked" if arguments.check else "materialized",
                    "rows": len(manifest["items"]),
                    "composition": manifest["composition"],
                    "output_root": str(arguments.output_root),
                },
                sort_keys=True,
            )
        )
        return 0
    except (
        JsutEvaluationError,
        JsutRetentionError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        print(f"jsut-retention-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
