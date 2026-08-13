#!/usr/bin/env python3
"""Materialize EXP-138's near-one-pass 201-source X-VC teacher pool."""

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

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_window_teacher as window

KIND = "liveconv-exp138-window-breadth201/v1"
GROUP = "window-breadth201-train-disjoint"
CV_KIND = "liveconv-exp114-commonvoice-teacher48/v1"
WINDOW_AUDIT_KIND = "liveconv-xvc-hadou-source-window-audit/v1"
COMPOSITION = {"commonvoice": 48, "hadou": 150, "jvs": 3}
POSITIONS = ("start", "end", "middle")
ROWS_PER_POSITION = 50


class WindowBreadthError(RuntimeError):
    """The large real-window pool cannot be materialized safely."""


def valid_window(row: Mapping[str, Any], position: str) -> bool:
    repetition = row.get("repetition")
    normalized = row.get("normalized_transcript")
    return bool(
        row.get("position") == position
        and isinstance(row.get("utterance_id"), str)
        and isinstance(normalized, str)
        and len(normalized) >= 4
        and isinstance(row.get("full_utterance_audit_cer"), (int, float))
        and float(row["full_utterance_audit_cer"]) <= window.MAX_FULL_CER
        and isinstance(repetition, dict)
        and repetition.get("gross_repetition") is False
    )


def select_hadou_windows(
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    candidates = {
        position: [row for row in rows if valid_window(row, position)]
        for position in POSITIONS
    }
    eligible_ids = {
        str(row["utterance_id"])
        for row in rows
        if any(valid_window(row, position) for position in POSITIONS)
    }
    if len(eligible_ids) != COMPOSITION["hadou"]:
        raise WindowBreadthError("quality-admitted Hadou utterance count drifted")

    selected: list[Mapping[str, Any]] = []
    used_ids: set[str] = set()
    covered: set[str] = set()
    for position in POSITIONS:
        for _ in range(ROWS_PER_POSITION):
            available = [
                row
                for row in candidates[position]
                if str(row["utterance_id"]) not in used_ids
            ]
            if not available:
                raise WindowBreadthError("balanced unique window assignment exhausted")
            winner = min(
                available,
                key=lambda row: (
                    -sum(
                        3 if token.startswith("3:") else 2 if token.startswith("2:") else 1
                        for token in window.ngrams(str(row["normalized_transcript"])) - covered
                    ),
                    float(row["full_utterance_audit_cer"]),
                    str(row["utterance_id"]),
                ),
            )
            selected.append(winner)
            used_ids.add(str(winner["utterance_id"]))
            covered.update(window.ngrams(str(winner["normalized_transcript"])))
    if (
        used_ids != eligible_ids
        or Counter(row["position"] for row in selected)
        != {position: ROWS_PER_POSITION for position in POSITIONS}
    ):
        raise WindowBreadthError("Hadou one-window-per-utterance balance drifted")
    return selected


def materialize(arguments: argparse.Namespace) -> dict[str, Any]:
    cv = window.load_json(arguments.commonvoice_manifest)
    prior = window.load_json(arguments.prior_window_manifest)
    audit = window.load_json(arguments.window_audit)
    source = window.load_json(arguments.source_manifest)
    cv_items = cv.get("items")
    prior_items = prior.get("items")
    audit_rows = audit.get("rows")
    source_rows = source.get("rows")
    if (
        cv.get("kind") != CV_KIND
        or not isinstance(cv_items, list)
        or len(cv_items) != COMPOSITION["commonvoice"]
        or not isinstance(prior_items, list)
        or not isinstance(audit_rows, list)
        or not isinstance(source_rows, list)
        or audit.get("kind") != WINDOW_AUDIT_KIND
        or audit.get("source_manifest_sha256")
        != window.sha256_file(arguments.source_manifest)
    ):
        raise WindowBreadthError("input schema or audit binding drifted")
    jvs_items = [item for item in prior_items if item.get("domain") == "jvs"]
    if len(jvs_items) != COMPOSITION["jvs"]:
        raise WindowBreadthError("fixed JVS source set drifted")
    selected = select_hadou_windows(audit_rows)
    source_by_id = {
        str(row.get("utterance_id")): row
        for row in source_rows
        if isinstance(row, dict) and isinstance(row.get("utterance_id"), str)
    }

    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    for item in cv_items:
        path = arguments.commonvoice_root / str(item["filename"])
        if path.is_symlink() or not path.is_file() or window.sha256_file(path) != item.get("sha256"):
            raise WindowBreadthError("Common Voice teacher source drifted")
        filename = f"cv-{item['filename']}"
        destination = arguments.output_root / filename
        shutil.copyfile(path, destination)
        items.append(
            {
                "id": f"cv-{item['id']}",
                "domain": "commonvoice",
                "filename": filename,
                "client_id_sha256": item["client_id_sha256"],
                "source_transcript": item["source_transcript"],
                "source_id": item["id"],
                "selection_bin": None,
                "group": GROUP,
                "sha256": window.sha256_file(destination),
            }
        )
    for item in jvs_items:
        path = arguments.prior_window_root / str(item["filename"])
        if path.is_symlink() or not path.is_file() or window.sha256_file(path) != item.get("sha256"):
            raise WindowBreadthError("JVS teacher source drifted")
        destination = arguments.output_root / str(item["filename"])
        shutil.copyfile(path, destination)
        items.append(dict(item) | {"group": GROUP, "sha256": window.sha256_file(destination)})
    for audited in selected:
        identifier = str(audited["utterance_id"])
        position = str(audited["position"])
        row = source_by_id.get(identifier)
        source_info = row.get("source_wav") if isinstance(row, dict) else None
        if not isinstance(source_info, dict):
            raise WindowBreadthError("selected Hadou metadata drifted")
        path = arguments.source_root / str(source_info.get("relative_path"))
        if path.is_symlink() or not path.is_file() or window.sha256_file(path) != source_info.get("sha256"):
            raise WindowBreadthError(f"selected Hadou source drifted: {identifier}")
        filename = f"hadou-{identifier}-{position}.wav"
        destination = arguments.output_root / filename
        window.crop_pcm16_window(
            path, destination, int(audited["offset_samples_16k"])
        )
        items.append(
            {
                "id": f"hadou-{identifier}-{position}",
                "domain": "hadou",
                "filename": filename,
                "client_id_sha256": hashlib.sha256(
                    b"Hadou-Voice-Dataset@4f68840833d01d825b6ec4c24da55858dabf96bb"
                ).hexdigest(),
                "source_transcript": audited["transcript"],
                "source_id": identifier,
                "selection_bin": position,
                "audit_cer": audited["full_utterance_audit_cer"],
                "reading_katakana": row.get("reading_katakana"),
                "window_position": position,
                "window_offset_seconds": audited["offset_seconds"],
                "window_policy": "audited-start-middle-end-2.4s",
                "group": GROUP,
                "sha256": window.sha256_file(destination),
            }
        )
    if Counter(item["domain"] for item in items) != COMPOSITION:
        raise WindowBreadthError("large teacher composition drifted")
    manifest = {
        "schema_version": 1,
        "kind": KIND,
        "composition": COMPOSITION,
        "selection": (
            "Common Voice 48 and JVS3 fixed; all 150 quality-admitted, target-"
            "and Hadou31-disjoint training utterances contribute exactly one "
            "audited 2.4-second source window, balanced 50 start/50 middle/50 "
            "end; position assignment greedily maximizes source-window ASR "
            "1/2/3-gram coverage without using evaluation outputs"
        ),
        "window_audit_sha256": window.sha256_file(arguments.window_audit),
        "items": items,
    }
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "domains": COMPOSITION,
        "positions": dict(Counter(row["position"] for row in selected)),
        "manifest_sha256": window.sha256_file(arguments.output_manifest),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--commonvoice-manifest", type=Path, required=True)
    value.add_argument("--commonvoice-root", type=Path, required=True)
    value.add_argument("--prior-window-manifest", type=Path, required=True)
    value.add_argument("--prior-window-root", type=Path, required=True)
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
    except (WindowBreadthError, window.WindowTeacherError, OSError, ValueError) as error:
        print(f"window-breadth-error: {error}")
        return 2
    print(json.dumps({"status": "materialized", **summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
