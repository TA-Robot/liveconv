#!/usr/bin/env python3
"""Bind the active Common Voice CV26 matched EXP-318/319 pair without CUDA.

The six zero-active clips are intentionally not silently padded into the new
source pool.  The remaining 26 clips are decoded from the raw Common Voice
MP3s and windowed with the exact EXP-186 signal-only policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_commonvoice_active_windows import (
    SAMPLE_RATE,
    SELECTION_POLICY,
    WINDOW_SAMPLES,
    decode_mp3,
    select_speech_active_window,
    wav_bytes,
)

EXP238_KIND = "liveconv-exp238-cross-corpus-control69-pseudoparallel-inputs/v1"
EXP306_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-inputs/v1"
EXP306_POOL_KIND = "liveconv-exp306-xvc-pseudoparallel-cv32-pool/v1"
EXP317_KIND = "liveconv-exp317-xvc-pseudoparallel-cv32-replacement-inputs/v1"
EXP318_KIND = "liveconv-exp318-xvc-pseudoparallel-cv26-current-window-control-inputs/v1"
EXP319_KIND = "liveconv-exp319-xvc-cv26-active-window-pool/v1"
RECEIPT_KIND = "liveconv-exp318-exp319-xvc-cv26-receipt/v1"

EXPECTED_ROWS = 170
EXPECTED_CV32 = 32
EXPECTED_CV26 = 26
EXPECTED_BASE_COMPOSITION = {
    "commonvoice-unpaired": 48,
    "jsut-unpaired": 85,
    "jvs-unpaired": 3,
    "hadou-unpaired": 34,
}
RETAINED_POSITIONS = [
    4,
    5,
    6,
    11,
    13,
    16,
    19,
    25,
    27,
    30,
    35,
    36,
    39,
    43,
    48,
    54,
    55,
    57,
    58,
    59,
    63,
    71,
    75,
    86,
    101,
    103,
]
EXCLUDED_POSITIONS = [14, 31, 52, 78, 80, 91]
ZERO_ACTIVE_IDS = [
    "cv22959165u",
    "cv38987912u",
    "cv39076307u",
    "cv41934139u",
    "cv42263615u",
    "cv45113065u",
]
EXP055_EXCLUDED_ID = "cv27706775u"


class Cv26Error(RuntimeError):
    """The deterministic EXP-318/319 binding cannot be admitted."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Cv26Error(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise Cv26Error(f"JSON object required: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise Cv26Error(f"{label} path is malformed")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise Cv26Error(f"{label} path is unsafe")
    return value


def rows(value: Mapping[str, Any], *, kind: str, count: int, label: str) -> list[dict[str, Any]]:
    items = value.get("items")
    if value.get("kind") != kind or not isinstance(items, list) or len(items) != count:
        raise Cv26Error(f"{label} manifest identity drifted")
    if not all(isinstance(item, dict) for item in items):
        raise Cv26Error(f"{label} row is malformed")
    return [dict(item) for item in items]


def validate_row_shape(row: Mapping[str, Any], label: str) -> None:
    if not isinstance(row.get("id"), str) or not row["id"]:
        raise Cv26Error(f"{label} id is malformed")
    if not isinstance(row.get("teacher_id"), str) or not row["teacher_id"]:
        raise Cv26Error(f"{label} teacher_id is malformed")
    for key in ("source_file", "target_file", "real_target_file"):
        safe_relative(row.get(key), f"{label} {key}")
    for key in ("source_sha256", "target_sha256", "real_target_sha256"):
        if not is_sha256(row.get(key)):
            raise Cv26Error(f"{label} {key} is malformed")
    if (
        row.get("source_root") != "source-work"
        or row.get("target_root") != "diverse-work"
        or row.get("real_target_root") != "source-work"
    ):
        raise Cv26Error(f"{label} root binding drifted")


def validate_exp238(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = rows(value, kind=EXP238_KIND, count=EXPECTED_ROWS, label="EXP-238")
    if value.get("composition") != EXPECTED_BASE_COMPOSITION:
        raise Cv26Error("EXP-238 composition drifted")
    for index, row in enumerate(output):
        validate_row_shape(row, f"EXP-238 row {index}")
    return output


def validate_exp317(
    value: Mapping[str, Any], exp238_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    output = rows(value, kind=EXP317_KIND, count=EXPECTED_ROWS, label="EXP-317")
    if value.get("composition") != EXPECTED_BASE_COMPOSITION:
        raise Cv26Error("EXP-317 composition drifted")
    for index, row in enumerate(output):
        validate_row_shape(row, f"EXP-317 row {index}")
    if any(output[index] == exp238_rows[index] for index in RETAINED_POSITIONS):
        raise Cv26Error("EXP-317 retained replacement was not applied")
    for index in range(EXPECTED_ROWS):
        if index not in RETAINED_POSITIONS and index not in EXCLUDED_POSITIONS:
            if output[index] != exp238_rows[index]:
                raise Cv26Error(f"EXP-317 unexpected non-CV row change: {index}")
    return output


def validate_exp306_pool(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = rows(value, kind=EXP306_POOL_KIND, count=EXPECTED_CV32, label="EXP-306 pool")
    if value.get("composition") != {"commonvoice-unpaired": EXPECTED_CV32}:
        raise Cv26Error("EXP-306 pool composition drifted")
    seen: set[str] = set()
    for index, row in enumerate(output):
        if row.get("position") != index:
            raise Cv26Error("EXP-306 pool order drifted")
        for key in ("source_file", "real_target_file"):
            safe_relative(row.get(key), f"EXP-306 pool row {index} {key}")
        for key in ("source_sha256", "real_target_sha256"):
            if not is_sha256(row.get(key)):
                raise Cv26Error(f"EXP-306 pool row {index} {key} is malformed")
        if (
            row.get("source_root") != "source-work"
            or row.get("real_target_root") != "source-work"
            or row.get("target_root") != "diverse-work"
            or not isinstance(row.get("target_id"), str)
            or row.get("domain") != "commonvoice-unpaired"
            or row["id"] in seen
        ):
            raise Cv26Error("EXP-306 pool identity drifted")
        seen.add(str(row["id"]))
    return output


def _mp3_identity(metadata: Mapping[str, Any], mp3_root: Path) -> dict[str, Any]:
    identifier = metadata.get("id")
    filename = metadata.get("filename")
    if (
        not isinstance(identifier, str)
        or not isinstance(filename, str)
        or Path(filename).name != filename
        or Path(filename).suffix.lower() != ".mp3"
        or not is_sha256(metadata.get("sha256"))
        or not is_sha256(metadata.get("client_id_sha256"))
        or not isinstance(metadata.get("text"), str)
    ):
        raise Cv26Error("EXP-055 Common Voice identity drifted")
    path = mp3_root / filename
    if path.is_symlink() or not path.is_file() or sha256_file(path) != metadata["sha256"]:
        raise Cv26Error(f"Common Voice MP3 identity drifted: {identifier}")
    selected, metrics = select_speech_active_window(decode_mp3(path))
    payload = wav_bytes(selected)
    return {
        "id": identifier,
        "filename": filename,
        "client_id_sha256": metadata["client_id_sha256"],
        "source_text": str(metadata["text"]),
        "source_original_sha256": metadata["sha256"],
        "source_wav": payload,
        "source_sha256": sha256_bytes(payload),
        "window": metrics,
    }


def active_commonvoice(expanded: Mapping[str, Any], mp3_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_items = expanded.get("items")
    if (
        expanded.get("kind") != "liveconv-exp055-commonvoice-local-unused/v1"
        or not isinstance(source_items, list)
        or len(source_items) != EXPECTED_CV32 + 1
    ):
        raise Cv26Error("EXP-055 expanded evaluation coverage drifted")
    identities: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            raise Cv26Error("EXP-055 expanded row is malformed")
        identity = _mp3_identity(item, mp3_root)
        if identity["id"] != EXP055_EXCLUDED_ID:
            identities.append(identity)
    identities_by_id = {str(item["id"]): item for item in identities}
    if len(identities_by_id) != EXPECTED_CV32:
        raise Cv26Error("EXP-055 expanded IDs are not unique")
    zero = sorted(
        str(item["id"])
        for item in identities
        if float(item["window"]["active_sample_fraction"]) == 0.0
    )
    expected_zero = sorted(ZERO_ACTIVE_IDS)
    if zero != expected_zero:
        raise Cv26Error(f"zero-active Common Voice IDs drifted: {zero}")
    active = [
        item
        for item in identities
        if float(item["window"]["active_sample_fraction"]) > 0.0
    ]
    if len(active) != EXPECTED_CV26:
        raise Cv26Error("active Common Voice count drifted")
    return active, identities


def _copy_verified(source: Path, destination: Path, digest: str, label: str) -> None:
    if source.is_symlink() or not source.is_file() or sha256_file(source) != digest:
        raise Cv26Error(f"{label} audio identity drifted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise Cv26Error(f"treatment source path already exists: {destination}")
    shutil.copyfile(source, destination)
    if sha256_file(destination) != digest:
        raise Cv26Error(f"{label} copied audio hash drifted")


def build_pair(
    exp238: Sequence[Mapping[str, Any]],
    exp317: Sequence[Mapping[str, Any]],
    exp306_pool: Sequence[Mapping[str, Any]],
    active: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    cv_positions = [
        index
        for index, row in enumerate(exp238)
        if row.get("domain") == "commonvoice-unpaired"
    ]
    if len(cv_positions) != 48:
        raise Cv26Error("EXP-238 Common Voice positions drifted")
    expected_cv32_positions = sorted(RETAINED_POSITIONS + EXCLUDED_POSITIONS)
    if cv_positions[:EXPECTED_CV32] != expected_cv32_positions:
        raise Cv26Error("Common Voice position mapping drifted")
    active_by_id = {str(row["id"]): row for row in active}
    if len(active_by_id) != EXPECTED_CV26:
        raise Cv26Error("active source identity is not unique")
    retained = set(RETAINED_POSITIONS)
    excluded = set(EXCLUDED_POSITIONS)
    if retained & excluded or len(retained) != EXPECTED_CV26 or len(excluded) != 6:
        raise Cv26Error("frozen retained/excluded position contract drifted")
    output_items = [dict(row) for row in exp238]
    pool_items: list[dict[str, Any]] = []
    active_order = 0
    for cv_index, position in enumerate(cv_positions[:EXPECTED_CV32]):
        current = dict(exp317[position])
        base = exp238[position]
        pool_row = exp306_pool[cv_index]
        if (
            current.get("id") != pool_row.get("id")
            or current.get("teacher_id") != pool_row.get("teacher_id")
            or current.get("target_id") != pool_row.get("target_id")
            or current.get("real_target_file") != pool_row.get("real_target_file")
            or current.get("real_target_sha256") != pool_row.get("real_target_sha256")
        ):
            raise Cv26Error(f"EXP-317/306 position identity drifted: {position}")
        identifier = str(pool_row.get("source_manifest_id", "")).split(":")[-1]
        if identifier not in active_by_id and position in retained:
            raise Cv26Error(f"retained source is not active Common Voice: {position}")
        if position in excluded:
            if current.get("target_id") != base.get("target_id"):
                raise Cv26Error(f"excluded position target drifted: {position}")
            continue
        if position not in retained:
            raise Cv26Error(f"unclassified CV position: {position}")
        source = active_by_id[identifier]
        if (
            pool_row.get("source_client_id_sha256") != source["client_id_sha256"]
            or pool_row.get("source_text") != source["source_text"]
            or pool_row.get("source_original_sha256") != source["source_original_sha256"]
        ):
            raise Cv26Error(f"active source metadata drifted: {identifier}")
        source_file = f"active-sources/{active_order:02d}-{identifier}.wav"
        # EXP-318 is the current-window control: retain EXP-317's current
        # source/teacher row exactly.  EXP-319 is the separate active-window
        # treatment source pool and receives the new source bytes.
        output_items[position] = dict(current)
        active_row = dict(current)
        active_row.update(
            {
                "source_file": source_file,
                "source_sha256": source["source_sha256"],
                "source_text": source["source_text"],
                "source_client_id_sha256": source["client_id_sha256"],
                "source_original_sha256": source["source_original_sha256"],
                "source_window": source["window"],
                "source_window_policy": SELECTION_POLICY,
                "source_window_sample_rate": SAMPLE_RATE,
                "source_window_samples": WINDOW_SAMPLES,
                "curriculum_position": position,
            }
        )
        pool_items.append(active_row)
        active_order += 1
    if len(pool_items) != EXPECTED_CV26:
        raise Cv26Error("EXP-319 active pool count drifted")
    for position in EXCLUDED_POSITIONS:
        if output_items[position] != exp238[position]:
            raise Cv26Error(f"excluded position was not restored: {position}")
    for position in range(EXPECTED_ROWS):
        if position not in RETAINED_POSITIONS and position not in EXCLUDED_POSITIONS:
            if output_items[position] != exp238[position]:
                raise Cv26Error(f"non-CV row unexpectedly changed: {position}")
    composition = {}
    for row in output_items:
        domain = str(row.get("domain"))
        composition[domain] = composition.get(domain, 0) + 1
    if composition != EXPECTED_BASE_COMPOSITION:
        raise Cv26Error("EXP-318 composition drifted")
    curriculum = {
        "schema_version": 1,
        "kind": EXP318_KIND,
        "source": {
            "selection": "EXP-238 with the 26 active Common Voice windows from EXP-055/EXP-306 retained",
            "excluded_zero_active_ids": sorted(ZERO_ACTIVE_IDS),
            "retained_positions": RETAINED_POSITIONS,
            "restored_positions": EXCLUDED_POSITIONS,
            "boundary": "matched 170-update current-window control; no GPU, naturalness, or winner claim",
        },
        "composition": composition,
        "items": output_items,
    }
    pool = {
        "schema_version": 1,
        "kind": EXP319_KIND,
        "source": {
            "selection": "the 26 retained EXP-317 positions, decoded from raw EXP-055 Common Voice MP3s",
            "window_policy": SELECTION_POLICY,
            "excluded_zero_active_ids": sorted(ZERO_ACTIVE_IDS),
            "retained_positions": RETAINED_POSITIONS,
            "boundary": "active source pool only; current EXP-306 teacher targets are reused",
        },
        "composition": {"commonvoice-unpaired": EXPECTED_CV26},
        "items": pool_items,
    }
    return curriculum, pool, RETAINED_POSITIONS


def materialize(
    *,
    exp238_rows: Sequence[Mapping[str, Any]],
    curriculum: Mapping[str, Any],
    pool: Mapping[str, Any],
    active: Sequence[Mapping[str, Any]],
    exp238_source_work: Path,
    current_source_work: Path,
    output_root: Path,
) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise Cv26Error("EXP-318/319 output root already exists")
    source_output = output_root / "source-work"
    source_output.mkdir(parents=True)
    active_by_id = {str(item["id"]): item for item in active}
    for row in exp238_rows:
        _copy_verified(
            exp238_source_work / str(row["source_file"]),
            source_output / str(row["source_file"]),
            str(row["source_sha256"]),
            f"EXP-238 source {row['id']}",
        )
        _copy_verified(
            exp238_source_work / str(row["real_target_file"]),
            source_output / str(row["real_target_file"]),
            str(row["real_target_sha256"]),
            f"EXP-238 real target {row['id']}",
        )
    for row in pool["items"]:
        identifier = str(row["source_manifest_id"]).split(":")[-1]
        source = active_by_id[identifier]
        target = source_output / str(row["source_file"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source["source_wav"])
        if sha256_file(target) != row["source_sha256"]:
            raise Cv26Error(f"active source copy drifted: {identifier}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--exp238-curriculum", type=Path, required=True)
    value.add_argument("--exp238-source-work", type=Path, required=True)
    value.add_argument("--exp317-curriculum", type=Path, required=True)
    value.add_argument("--exp306-pool", type=Path, required=True)
    value.add_argument("--current-source-work", type=Path, required=True)
    value.add_argument("--current-diverse-work", type=Path, required=True)
    value.add_argument("--exp055-expanded-evaluation", type=Path, required=True)
    value.add_argument("--commonvoice-mp3-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        exp238_manifest = load_json(arguments.exp238_curriculum)
        exp317_manifest = load_json(arguments.exp317_curriculum)
        exp306_pool_manifest = load_json(arguments.exp306_pool)
        expanded = load_json(arguments.exp055_expanded_evaluation)
        exp238_rows = validate_exp238(exp238_manifest)
        exp317_rows = validate_exp317(exp317_manifest, exp238_rows)
        exp306_pool = validate_exp306_pool(exp306_pool_manifest)
        active, all_identities = active_commonvoice(expanded, arguments.commonvoice_mp3_root)
        curriculum, pool, positions = build_pair(
            exp238_rows, exp317_rows, exp306_pool, active
        )
        # Current roots are admission inputs for the teacher/real-target rows;
        # treatment source-work is a separate output root.
        for row in curriculum["items"]:
            for root, key, digest_key in (
                (arguments.current_source_work, "source_file", "source_sha256"),
                (arguments.current_diverse_work, "target_file", "target_sha256"),
                (arguments.current_source_work, "real_target_file", "real_target_sha256"),
            ):
                path = root / str(row[key])
                if path.is_symlink() or not path.is_file() or sha256_file(path) != row[digest_key]:
                    # Active source bytes are new and are materialized below;
                    # all base/teacher/real-target rows must already exist.
                    if key == "source_file" and str(row["source_file"]).startswith("active-sources/"):
                        continue
                    raise Cv26Error(f"current audio identity drifted: {row['id']}")
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-write",
                        "exp318_rows": len(curriculum["items"]),
                        "exp319_rows": len(pool["items"]),
                        "retained_positions": positions,
                        "zero_active_ids": sorted(ZERO_ACTIVE_IDS),
                        "decoded_rows": len(all_identities),
                    },
                    sort_keys=True,
                )
            )
            return 0
        materialize(
            exp238_rows=exp238_rows,
            curriculum=curriculum,
            pool=pool,
            active=active,
            exp238_source_work=arguments.exp238_source_work,
            current_source_work=arguments.current_source_work,
            output_root=arguments.output_root,
        )
        output_root = arguments.output_root
        curriculum["source"].update(
            {
                "exp238_curriculum_sha256": sha256_file(arguments.exp238_curriculum),
                "exp317_curriculum_sha256": sha256_file(arguments.exp317_curriculum),
                "exp306_pool_sha256": sha256_file(arguments.exp306_pool),
                "expanded_evaluation_sha256": sha256_file(
                    arguments.exp055_expanded_evaluation
                ),
            }
        )
        pool["source"].update(curriculum["source"])
        curriculum_path = output_root / "exp318-curriculum.json"
        pool_path = output_root / "exp319-pool.json"
        curriculum_path.write_text(
            json.dumps(curriculum, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pool_path.write_text(
            json.dumps(pool, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipt = {
            "schema_version": 1,
            "kind": RECEIPT_KIND,
            "status": "materialized-no-cuda",
            "exp318_kind": EXP318_KIND,
            "exp319_kind": EXP319_KIND,
            "exp318_sha256": sha256_file(curriculum_path),
            "exp319_sha256": sha256_file(pool_path),
            "rows": EXPECTED_ROWS,
            "active_rows": EXPECTED_CV26,
            "retained_positions": RETAINED_POSITIONS,
            "excluded_positions": EXCLUDED_POSITIONS,
            "zero_active_ids": sorted(ZERO_ACTIVE_IDS),
            "window_policy": SELECTION_POLICY,
            "source_work": str(output_root / "source-work"),
            "current_diverse_work": str(arguments.current_diverse_work),
            "boundary": "CPU source-window preparation only; no teacher rendering or GPU claim",
        }
        receipt_path = output_root / "receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "exp318": str(curriculum_path),
                    "exp319": str(pool_path),
                    "receipt": str(receipt_path),
                    "active_rows": EXPECTED_CV26,
                },
                sort_keys=True,
            )
        )
        return 0
    except (Cv26Error, OSError, ValueError, KeyError) as error:
        print(f"exp318-exp319-cv26-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
