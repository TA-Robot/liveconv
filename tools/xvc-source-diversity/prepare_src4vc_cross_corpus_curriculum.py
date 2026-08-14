#!/usr/bin/env python3
"""Replace EXP-213's JSUT85 block with 85 disjoint SRC4VC speakers."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fetch_src4vc_subset import OUTPUT_KIND as SRC4VC_KIND
from prepare_clean_post_rehearsal import load_json, sha256_file
from prepare_cross_corpus_unpaired_curriculum import (
    EXPECTED_ROWS,
    active_window_wav_bytes,
    scheduled_sources,
)
from prepare_cross_corpus_unpaired_curriculum import (
    OUTPUT_KIND as PREDECESSOR_KIND,
)

OUTPUT_KIND = "liveconv-exp244-src4vc-cross-corpus-unpaired-inputs/v1"
EXPECTED_PREDECESSOR_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "hadou-unpaired": 34,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
}
EXPECTED_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "hadou-unpaired": 34,
    "jvs-unpaired": 3,
    "src4vc-smartphone-unpaired": 85,
}
SRC4VC_TRAIN_SPEAKERS = 85
SRC4VC_EVALUATION_SPEAKERS = 15
SRC4VC_EVALUATION_ROWS = 30


class Src4vcCurriculumError(RuntimeError):
    """The one-block source substitution cannot be materialized safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _items(
    manifest: Mapping[str, Any], *, kind: str, count: int, label: str
) -> list[dict[str, Any]]:
    rows = manifest.get("items")
    if manifest.get("kind") != kind or not isinstance(rows, list) or len(rows) != count:
        raise Src4vcCurriculumError(f"{label} manifest identity drifted")
    if not all(isinstance(row, dict) for row in rows):
        raise Src4vcCurriculumError(f"{label} row is malformed")
    return [dict(row) for row in rows]


def source_records(
    *,
    predecessor_manifest: Mapping[str, Any],
    predecessor_root: Path,
    src4vc_manifest: Mapping[str, Any],
    src4vc_root: Path,
) -> list[dict[str, Any]]:
    """Return 85 unchanged predecessor sources plus 85 new speaker sources."""

    predecessor = _items(
        predecessor_manifest,
        kind=PREDECESSOR_KIND,
        count=EXPECTED_ROWS,
        label="EXP-213 predecessor",
    )
    if dict(Counter(str(row.get("domain")) for row in predecessor)) != (
        EXPECTED_PREDECESSOR_COMPOSITION
    ):
        raise Src4vcCurriculumError("predecessor composition drifted")
    src4vc = _items(
        src4vc_manifest,
        kind=SRC4VC_KIND,
        count=SRC4VC_TRAIN_SPEAKERS + SRC4VC_EVALUATION_ROWS,
        label="SRC4VC subset",
    )
    train = [row for row in src4vc if row.get("split") == "train"]
    evaluation = [row for row in src4vc if row.get("split") == "evaluation"]
    train_speakers = {str(row.get("speaker_id")) for row in train}
    evaluation_speakers = {str(row.get("speaker_id")) for row in evaluation}
    if (
        len(train) != SRC4VC_TRAIN_SPEAKERS
        or len(train_speakers) != SRC4VC_TRAIN_SPEAKERS
        or len(evaluation) != SRC4VC_EVALUATION_ROWS
        or len(evaluation_speakers) != SRC4VC_EVALUATION_SPEAKERS
        or train_speakers & evaluation_speakers
    ):
        raise Src4vcCurriculumError("SRC4VC train/evaluation speaker split drifted")

    records: list[dict[str, Any]] = []
    for row in predecessor:
        if row["domain"] == "jsut-unpaired":
            continue
        path = predecessor_root / str(row["source_file"])
        if path.is_symlink() or not path.is_file():
            raise Src4vcCurriculumError(f"predecessor source unavailable: {row['id']}")
        value = path.read_bytes()
        if sha256_bytes(value) != row["source_sha256"]:
            raise Src4vcCurriculumError(f"predecessor source drifted: {row['id']}")
        records.append(
            {
                "domain": str(row["domain"]),
                "teacher_id": str(row["teacher_id"]),
                "source_manifest_id": str(row["source_manifest_id"]),
                "source_text": row.get("source_text"),
                "source_bytes": value,
                "source_speaker_id": row.get("source_speaker_id"),
            }
        )
    for row in train:
        path = src4vc_root / str(row["filename"])
        if path.is_symlink() or not path.is_file():
            raise Src4vcCurriculumError(f"SRC4VC source unavailable: {row['id']}")
        value = path.read_bytes()
        if sha256_bytes(value) != row["sha256"]:
            raise Src4vcCurriculumError(f"SRC4VC source drifted: {row['id']}")
        identifier = str(row["id"])
        records.append(
            {
                "domain": "src4vc-smartphone-unpaired",
                "teacher_id": f"src4vc-smartphone-unpaired-{identifier}",
                "source_manifest_id": f"EXP244:{identifier}",
                "source_text": str(row["text"]),
                "source_bytes": active_window_wav_bytes(value, label=identifier),
                "source_speaker_id": str(row["speaker_id"]),
            }
        )
    composition = dict(Counter(str(row["domain"]) for row in records))
    if composition != EXPECTED_COMPOSITION:
        raise Src4vcCurriculumError("substituted source composition drifted")
    return scheduled_sources(records)


def materialize(
    *,
    predecessor_manifest: Mapping[str, Any],
    predecessor_root: Path,
    src4vc_manifest: Mapping[str, Any],
    src4vc_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    predecessor = _items(
        predecessor_manifest,
        kind=PREDECESSOR_KIND,
        count=EXPECTED_ROWS,
        label="EXP-213 predecessor",
    )
    sources = source_records(
        predecessor_manifest=predecessor_manifest,
        predecessor_root=predecessor_root,
        src4vc_manifest=src4vc_manifest,
        src4vc_root=src4vc_root,
    )
    output_root.mkdir(parents=True)
    (output_root / "sources").mkdir()
    (output_root / "targets").mkdir()
    rows: list[dict[str, Any]] = []
    for position, (source, old_row) in enumerate(
        zip(sources, predecessor, strict=True)
    ):
        target_path = predecessor_root / str(old_row["target_file"])
        if target_path.is_symlink() or not target_path.is_file():
            raise Src4vcCurriculumError(f"target unavailable: {old_row['target_id']}")
        target_bytes = target_path.read_bytes()
        if sha256_bytes(target_bytes) != old_row["target_sha256"]:
            raise Src4vcCurriculumError(f"target drifted: {old_row['target_id']}")
        source_text = source.get("source_text")
        if source_text and source_text == old_row.get("target_text"):
            raise Src4vcCurriculumError("unpaired text separation drifted")
        source_file = Path("sources") / f"{position:03d}-{source['teacher_id']}.wav"
        target_file = Path("targets") / f"{position:03d}-{old_row['target_id']}.wav"
        (output_root / source_file).write_bytes(source["source_bytes"])
        shutil.copyfile(target_path, output_root / target_file)
        row = {
            "id": f"{position:03d}-{source['teacher_id']}--{old_row['target_id']}",
            "source_manifest_id": source["source_manifest_id"],
            "teacher_id": source["teacher_id"],
            "target_id": old_row["target_id"],
            "domain": source["domain"],
            "source_root": "diverse-work",
            "source_file": str(source_file),
            "source_sha256": sha256_bytes(source["source_bytes"]),
            "target_root": "diverse-work",
            "target_file": str(target_file),
            "target_sha256": old_row["target_sha256"],
            "source_relative_distance": 0.0,
            "source_text": source_text,
            "target_text": old_row.get("target_text"),
            "learning_target": "source-content-plus-unpaired-target-identity",
        }
        if source.get("source_speaker_id") is not None:
            row["source_speaker_id"] = source["source_speaker_id"]
        rows.append(row)
    if [row["target_sha256"] for row in rows] != [
        row["target_sha256"] for row in predecessor
    ]:
        raise Src4vcCurriculumError("ordered target assignment drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "one_change": (
                "replace EXP-213 JSUT85 with one RECITATION row from each of 85 "
                "SRC4VC smartphone speakers"
            ),
            "retained": (
                "CV48, JVS3, Hadou34, exact ordered Amitaro targets, active-window "
                "policy, total170, and downstream pseudoparallel method"
            ),
            "speaker_boundary": (
                "85 SRC4VC train speakers; fifteen disjoint evaluation speakers "
                "with two rows each are excluded"
            ),
            "schedule": "ascending sha256(domain:teacher_id) over the fixed 170 rows",
        },
        "composition": dict(Counter(str(row["domain"]) for row in rows)),
        "items": rows,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--predecessor-manifest", type=Path, required=True)
    value.add_argument("--predecessor-root", type=Path, required=True)
    value.add_argument("--src4vc-manifest", type=Path, required=True)
    value.add_argument("--src4vc-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.output_root.exists() or arguments.output_root.is_symlink():
            raise Src4vcCurriculumError("output root already exists")
        result = materialize(
            predecessor_manifest=load_json(arguments.predecessor_manifest),
            predecessor_root=arguments.predecessor_root,
            src4vc_manifest=load_json(arguments.src4vc_manifest),
            src4vc_root=arguments.src4vc_root,
            output_root=arguments.output_root,
        )
        result["source"]["manifest_file_sha256"] = {
            "predecessor": sha256_file(arguments.predecessor_manifest),
            "src4vc_subset": sha256_file(arguments.src4vc_manifest),
        }
        output = arguments.output_root / "curriculum.json"
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "materialized",
                    "rows": len(result["items"]),
                    "composition": result["composition"],
                    "output": str(output),
                    "sha256": sha256_file(output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (KeyError, OSError, Src4vcCurriculumError, ValueError) as error:
        print(f"src4vc-curriculum-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
