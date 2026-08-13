#!/usr/bin/env python3
"""Materialize EXP-134's model-window-aware cross-corpus teacher pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

KIND = "liveconv-exp134-window-teacher48/v1"
GROUP = "window-teacher-train-disjoint"
BASE_KIND = "liveconv-exp130-phonetic-teacher48/v1"
AUDIT_KIND = "liveconv-xvc-hadou-source-window-audit/v1"
DOMAIN_COUNTS = {"commonvoice": 24, "hadou": 21, "jvs": 3}
POSITIONS = ("start", "middle", "end")
ROWS_PER_POSITION = 7
MAX_FULL_CER = 0.15
SAMPLE_RATE = 48_000
WINDOW_FRAMES = 115_200


class WindowTeacherError(RuntimeError):
    """The model-window-aware pool cannot be materialized safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WindowTeacherError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise WindowTeacherError(f"JSON root is not an object: {path.name}")
    return value


def ngrams(value: str) -> set[str]:
    return {
        f"{width}:{value[start:start + width]}"
        for width in (1, 2, 3)
        for start in range(max(len(value) - width + 1, 0))
    }


def select_windows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    candidates: dict[str, list[Mapping[str, Any]]] = {
        position: [] for position in POSITIONS
    }
    for row in rows:
        position = row.get("position") if isinstance(row, dict) else None
        normalized = row.get("normalized_transcript") if isinstance(row, dict) else None
        repetition = row.get("repetition") if isinstance(row, dict) else None
        if (
            position not in candidates
            or not isinstance(row.get("utterance_id"), str)
            or not isinstance(normalized, str)
            or len(normalized) < 4
            or not isinstance(row.get("full_utterance_audit_cer"), (int, float))
            or float(row["full_utterance_audit_cer"]) > MAX_FULL_CER
            or not isinstance(repetition, dict)
            or repetition.get("gross_repetition") is not False
        ):
            continue
        candidates[str(position)].append(row)
    if any(len(values) < ROWS_PER_POSITION for values in candidates.values()):
        raise WindowTeacherError("insufficient audited source windows")

    selected: list[Mapping[str, Any]] = []
    used_ids: set[str] = set()
    covered: set[str] = set()
    for _ in range(ROWS_PER_POSITION):
        for position in POSITIONS:
            available = [
                row
                for row in candidates[position]
                if str(row["utterance_id"]) not in used_ids
            ]
            if not available:
                raise WindowTeacherError("unique source-window coverage exhausted")
            winner = min(
                available,
                key=lambda row: (
                    -sum(
                        3 if token.startswith("3:") else 2 if token.startswith("2:") else 1
                        for token in ngrams(str(row["normalized_transcript"])) - covered
                    ),
                    float(row["full_utterance_audit_cer"]),
                    str(row["utterance_id"]),
                ),
            )
            selected.append(winner)
            used_ids.add(str(winner["utterance_id"]))
            covered.update(ngrams(str(winner["normalized_transcript"])))
    if Counter(row["position"] for row in selected) != {
        position: ROWS_PER_POSITION for position in POSITIONS
    }:
        raise WindowTeacherError("source-window position balance drifted")
    return selected


def crop_pcm16_window(source: Path, destination: Path, offset_16k: int) -> None:
    with wave.open(str(source), "rb") as reader:
        if (
            reader.getnchannels() != 1
            or reader.getsampwidth() != 2
            or reader.getframerate() != SAMPLE_RATE
            or reader.getcomptype() != "NONE"
        ):
            raise WindowTeacherError(f"Hadou WAV format drifted: {source.name}")
        frame_count = reader.getnframes()
        reader.setpos(min(offset_16k * 3, max(frame_count - 1, 0)))
        payload = reader.readframes(WINDOW_FRAMES)
    payload += b"\x00" * max(WINDOW_FRAMES * 2 - len(payload), 0)
    if len(payload) != WINDOW_FRAMES * 2:
        raise WindowTeacherError("Hadou model window length drifted")
    with wave.open(str(destination), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(payload)


def materialize(arguments: argparse.Namespace) -> dict[str, Any]:
    base = load_json(arguments.base_manifest)
    audit = load_json(arguments.window_audit)
    source = load_json(arguments.source_manifest)
    base_items = base.get("items")
    audit_rows = audit.get("rows")
    source_rows = source.get("rows")
    if (
        base.get("kind") != BASE_KIND
        or audit.get("kind") != AUDIT_KIND
        or not isinstance(base_items, list)
        or not isinstance(audit_rows, list)
        or not isinstance(source_rows, list)
    ):
        raise WindowTeacherError("input schema drifted")
    if audit.get("source_manifest_sha256") != sha256_file(arguments.source_manifest):
        raise WindowTeacherError("source-window audit manifest binding drifted")
    fixed = [item for item in base_items if item.get("domain") != "hadou"]
    if Counter(item.get("domain") for item in fixed) != {"commonvoice": 24, "jvs": 3}:
        raise WindowTeacherError("fixed CV/JVS composition drifted")
    selected = select_windows(audit_rows)
    source_by_id = {
        str(row.get("utterance_id")): row
        for row in source_rows
        if isinstance(row, dict) and isinstance(row.get("utterance_id"), str)
    }

    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    for item in fixed:
        path = arguments.base_root / str(item["filename"])
        if path.is_symlink() or not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise WindowTeacherError("fixed CV/JVS source drifted")
        destination = arguments.output_root / str(item["filename"])
        shutil.copyfile(path, destination)
        items.append(dict(item) | {"group": GROUP, "sha256": sha256_file(destination)})

    for window in selected:
        identifier = str(window["utterance_id"])
        position = str(window["position"])
        row = source_by_id.get(identifier)
        source_info = row.get("source_wav") if isinstance(row, dict) else None
        if not isinstance(source_info, dict):
            raise WindowTeacherError("selected Hadou source metadata drifted")
        path = arguments.source_root / str(source_info.get("relative_path"))
        if path.is_symlink() or not path.is_file() or sha256_file(path) != source_info.get("sha256"):
            raise WindowTeacherError(f"selected Hadou source drifted: {identifier}")
        filename = f"hadou-{identifier}-{position}.wav"
        destination = arguments.output_root / filename
        crop_pcm16_window(path, destination, int(window["offset_samples_16k"]))
        items.append(
            {
                "id": f"hadou-{identifier}-{position}",
                "domain": "hadou",
                "filename": filename,
                "client_id_sha256": hashlib.sha256(
                    b"Hadou-Voice-Dataset@4f68840833d01d825b6ec4c24da55858dabf96bb"
                ).hexdigest(),
                "source_transcript": window["transcript"],
                "source_id": identifier,
                "selection_bin": position,
                "audit_cer": window["full_utterance_audit_cer"],
                "reading_katakana": row.get("reading_katakana"),
                "window_position": position,
                "window_offset_seconds": window["offset_seconds"],
                "window_policy": "audited-start-middle-end-2.4s",
                "group": GROUP,
                "sha256": sha256_file(destination),
            }
        )
    if Counter(item["domain"] for item in items) != DOMAIN_COUNTS:
        raise WindowTeacherError("materialized domain composition drifted")
    manifest = {
        "schema_version": 1,
        "kind": KIND,
        "composition": DOMAIN_COUNTS,
        "selection": (
            "EXP-130 CV24/JVS3 fixed; Hadou21 is seven unique training-only "
            "utterances per audited start/middle/end 2.4-second position, full-"
            "utterance CER <= 0.15, nonempty and nonrepeating, greedily maximizing "
            "new source-window ASR 1/2/3-grams; target and Hadou31 IDs were "
            "excluded by the bound EXP-133 audit"
        ),
        "window_audit_sha256": sha256_file(arguments.window_audit),
        "items": items,
    }
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "domains": DOMAIN_COUNTS,
        "positions": dict(Counter(row["position"] for row in selected)),
        "manifest_sha256": sha256_file(arguments.output_manifest),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--base-manifest", type=Path, required=True)
    value.add_argument("--base-root", type=Path, required=True)
    value.add_argument("--window-audit", type=Path, required=True)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--output-manifest", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        summary = materialize(arguments)
    except (WindowTeacherError, OSError, ValueError, wave.Error) as error:
        print(f"window-teacher-error: {error}")
        return 2
    print(json.dumps({"status": "materialized", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
