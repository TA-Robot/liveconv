#!/usr/bin/env python3
"""Bind the EXP-317 Common Voice replacement curriculum without CUDA.

EXP-317 keeps the EXP-238 170-row schedule and real Amitaro assignments.  The
first 32 Common Voice positions are replaced by the 32 genuinely new source
rows appended by EXP-306; every other position stays byte-for-byte equal to
EXP-238.  The existing source/diverse roots are only validated and referenced,
never copied or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
EXP306_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-inputs/v1"
OUTPUT_KIND = "liveconv-exp317-xvc-pseudoparallel-cv32-replacement-inputs/v1"
RECEIPT_KIND = "liveconv-exp317-xvc-pseudoparallel-cv32-replacement-receipt/v1"

EXPECTED_ROWS = 170
EXPECTED_NEW_ROWS = 32
EXPECTED_RETAINED_ROWS = EXPECTED_ROWS - EXPECTED_NEW_ROWS
EXPECTED_EXP306_ROWS = EXPECTED_ROWS + EXPECTED_NEW_ROWS
BASE_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}
EXP306_COMPOSITION = {**BASE_COMPOSITION, "commonvoice-unpaired": 80}


class Exp317Error(RuntimeError):
    """The deterministic EXP-317 binding cannot be admitted."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Exp317Error(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise Exp317Error(f"JSON object required: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise Exp317Error(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Exp317Error(f"{label} path is unsafe")
    return value


def manifest_items(
    manifest: Mapping[str, Any], *, kind: str, count: int, label: str
) -> list[dict[str, Any]]:
    rows = manifest.get("items")
    if manifest.get("kind") != kind or not isinstance(rows, list) or len(rows) != count:
        raise Exp317Error(f"{label} manifest identity drifted")
    if not all(isinstance(row, dict) for row in rows):
        raise Exp317Error(f"{label} row is malformed")
    return [dict(row) for row in rows]


def _validate_row_shape(row: Mapping[str, Any], label: str) -> None:
    if not isinstance(row.get("id"), str) or not row["id"]:
        raise Exp317Error(f"{label} row ID is malformed")
    if not isinstance(row.get("teacher_id"), str) or not row["teacher_id"]:
        raise Exp317Error(f"{label} teacher ID is malformed")
    for key in ("source_file", "target_file", "real_target_file"):
        safe_relative(row.get(key), f"{label} {key}")
    for key in ("source_sha256", "target_sha256", "real_target_sha256"):
        if not is_sha256(row.get(key)):
            raise Exp317Error(f"{label} {key} is malformed")
    if (
        row.get("source_root") != "source-work"
        or row.get("target_root") != "diverse-work"
        or row.get("real_target_root") != "source-work"
        or row.get("learning_target")
        != "source-aligned-control69-plus-real-target-adversarial"
    ):
        raise Exp317Error(f"{label} source/target root contract drifted")


def validate_exp238(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = manifest_items(
        manifest, kind=EXP238_KIND, count=EXPECTED_ROWS, label="EXP-238"
    )
    if manifest.get("composition") != BASE_COMPOSITION:
        raise Exp317Error("EXP-238 composition drifted")
    ids: set[str] = set()
    teachers: set[str] = set()
    domains: Counter[str] = Counter()
    for row in rows:
        _validate_row_shape(row, "EXP-238")
        if row["id"] in ids or row["teacher_id"] in teachers:
            raise Exp317Error("EXP-238 row identity is not unique")
        ids.add(str(row["id"]))
        teachers.add(str(row["teacher_id"]))
        domains[str(row.get("domain"))] += 1
    if dict(domains) != BASE_COMPOSITION:
        raise Exp317Error("EXP-238 domain composition drifted")
    return rows


def validate_exp306(
    manifest: Mapping[str, Any], exp238_rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[int]]:
    rows = manifest_items(
        manifest, kind=EXP306_KIND, count=EXPECTED_EXP306_ROWS, label="EXP-306"
    )
    if manifest.get("composition") != EXP306_COMPOSITION:
        raise Exp317Error("EXP-306 composition drifted")
    if list(rows[:EXPECTED_ROWS]) != [dict(row) for row in exp238_rows]:
        raise Exp317Error("EXP-306 first 170 rows are not exact EXP-238 rows")

    appended = rows[EXPECTED_ROWS:]
    ids: set[str] = set()
    teachers: set[str] = set()
    source_ids: set[str] = set()
    source_files: set[str] = set()
    source_hashes: set[str] = set()
    client_hashes: set[str] = set()
    old_ids = {str(row["id"]) for row in exp238_rows}
    old_teachers = {str(row["teacher_id"]) for row in exp238_rows}
    old_sources = {str(row["source_file"]) for row in exp238_rows}
    old_hashes = {str(row["source_sha256"]) for row in exp238_rows}
    for index, row in enumerate(appended):
        label = f"EXP-306 appended row {index}"
        _validate_row_shape(row, label)
        if row.get("domain") != "commonvoice-unpaired":
            raise Exp317Error("EXP-306 appended row is not Common Voice")
        if row["id"] in ids or row["id"] in old_ids:
            raise Exp317Error("EXP-306 appended IDs are not unique/new")
        if row["teacher_id"] in teachers or row["teacher_id"] in old_teachers:
            raise Exp317Error("EXP-306 appended teachers are not unique/new")
        if row["source_manifest_id"] in source_ids:
            raise Exp317Error("EXP-306 appended source manifests are not unique")
        if row["source_file"] in source_files or row["source_file"] in old_sources:
            raise Exp317Error("EXP-306 appended source files are not unique/new")
        if row["source_sha256"] in source_hashes or row["source_sha256"] in old_hashes:
            raise Exp317Error("EXP-306 appended source hashes are not unique/new")
        client = row.get("source_client_id_sha256")
        if client is not None:
            if not is_sha256(client) or client in client_hashes:
                raise Exp317Error("EXP-306 appended source clients are not unique")
            client_hashes.add(str(client))
        ids.add(str(row["id"]))
        teachers.add(str(row["teacher_id"]))
        source_ids.add(str(row["source_manifest_id"]))
        source_files.add(str(row["source_file"]))
        source_hashes.add(str(row["source_sha256"]))
    positions = [
        index
        for index, row in enumerate(exp238_rows)
        if row.get("domain") == "commonvoice-unpaired"
    ]
    if len(positions) != BASE_COMPOSITION["commonvoice-unpaired"]:
        raise Exp317Error("EXP-238 Common Voice positions drifted")
    return appended, positions[:EXPECTED_NEW_ROWS]


def validate_audio(
    manifest: Sequence[Mapping[str, Any]], source_work: Path, diverse_work: Path
) -> None:
    if source_work.is_symlink() or not source_work.is_dir():
        raise Exp317Error("source-work is unavailable")
    if diverse_work.is_symlink() or not diverse_work.is_dir():
        raise Exp317Error("diverse-work is unavailable")
    for row in manifest:
        for root_name, root, key, digest_key in (
            ("source-work", source_work, "source_file", "source_sha256"),
            ("diverse-work", diverse_work, "target_file", "target_sha256"),
            ("source-work", source_work, "real_target_file", "real_target_sha256"),
        ):
            root_key = (
                "source_root"
                if key == "source_file"
                else "target_root"
                if key == "target_file"
                else "real_target_root"
            )
            if row.get(root_key) != root_name:
                raise Exp317Error(f"root binding drifted: {row.get('id')}")
            path = root / str(row[key])
            if (
                path.is_symlink()
                or not path.is_file()
                or sha256_file(path) != row[digest_key]
            ):
                raise Exp317Error(f"audio identity drifted: {row.get('id')} {key}")


def build_curriculum(
    exp238: Mapping[str, Any], exp306: Mapping[str, Any]
) -> tuple[dict[str, Any], list[int]]:
    old_rows = validate_exp238(exp238)
    appended, positions = validate_exp306(exp306, old_rows)
    output_rows = [dict(row) for row in old_rows]
    for position, new_row, old_row in zip(
        positions, appended, (old_rows[index] for index in positions), strict=True
    ):
        for key in (
            "target_id",
            "real_target_file",
            "real_target_sha256",
            "real_target_root",
        ):
            if new_row.get(key) != old_row.get(key):
                raise Exp317Error(f"position-specific real target drifted: {position}")
        if new_row.get("source_file") == old_row.get("source_file") or new_row.get(
            "source_sha256"
        ) == old_row.get("source_sha256"):
            raise Exp317Error(f"replacement source is not new: {position}")
        replacement = dict(new_row)
        replacement["real_target_text"] = old_row.get("real_target_text")
        output_rows[position] = replacement
    for index, (old_row, output_row) in enumerate(
        zip(old_rows, output_rows, strict=True)
    ):
        if index not in positions and output_row != old_row:
            raise Exp317Error(f"unchanged EXP-238 row drifted: {index}")
    composition = dict(Counter(str(row.get("domain")) for row in output_rows))
    if composition != BASE_COMPOSITION:
        raise Exp317Error("EXP-317 composition drifted")
    manifest = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "selection": (
                "exact EXP-238 170 rows; replace first 32 Common Voice positions "
                "with EXP-306 appended CV32 rows"
            ),
            "fixed": (
                "position-specific target_id and real Amitaro target WAV assignment "
                "remain identical to EXP-238"
            ),
            "boundary": (
                "training-only source replacement; no naturalness, keeper, or "
                "winner claim"
            ),
        },
        "composition": composition,
        "learning_target_counts": dict(
            Counter(str(row.get("learning_target")) for row in output_rows)
        ),
        "replacement_positions": positions,
        "items": output_rows,
    }
    return manifest, positions


def receipt(
    manifest: Mapping[str, Any],
    *,
    exp238_path: Path,
    exp306_path: Path,
    output_path: Path,
    positions: Sequence[int],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "status": "bound-no-cuda",
        "output_kind": OUTPUT_KIND,
        "rows": len(manifest["items"]),
        "unchanged_rows": EXPECTED_RETAINED_ROWS,
        "replacement_rows": len(positions),
        "replacement_positions": list(positions),
        "composition": manifest["composition"],
        "input_sha256": {
            "exp238_curriculum": sha256_file(exp238_path),
            "exp306_curriculum": sha256_file(exp306_path),
        },
        "output_sha256": sha256_file(output_path),
        "boundary": (
            "CPU manifest binding only; existing source-work/diverse-work reused "
            "and not modified"
        ),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--exp238-curriculum", type=Path, required=True)
    value.add_argument("--exp306-curriculum", type=Path, required=True)
    value.add_argument("--source-work", type=Path, required=True)
    value.add_argument("--diverse-work", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--receipt", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        exp238 = load_json(arguments.exp238_curriculum)
        exp306 = load_json(arguments.exp306_curriculum)
        manifest, positions = build_curriculum(exp238, exp306)
        validate_audio(manifest["items"], arguments.source_work, arguments.diverse_work)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "rows": len(manifest["items"]),
                        "replacement_rows": len(positions),
                        "replacement_positions": positions,
                        "composition": manifest["composition"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.output.exists() or arguments.output.is_symlink():
            raise Exp317Error("curriculum output already exists")
        if arguments.receipt.exists() or arguments.receipt.is_symlink():
            raise Exp317Error("receipt output already exists")
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.receipt.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        result = receipt(
            manifest,
            exp238_path=arguments.exp238_curriculum,
            exp306_path=arguments.exp306_curriculum,
            output_path=arguments.output,
            positions=positions,
        )
        arguments.receipt.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "rows": result["rows"],
                    "replacement_rows": result["replacement_rows"],
                    "output": str(arguments.output),
                    "receipt": str(arguments.receipt),
                    "sha256": sha256_file(arguments.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (Exp317Error, OSError, ValueError, KeyError) as error:
        print(f"exp317-cv32-replacement-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
