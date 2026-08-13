#!/usr/bin/env python3
"""Materialize EXP-130's quality-filtered, kana-coverage teacher pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

KIND = "liveconv-exp130-phonetic-teacher48/v1"
GROUP = "phonetic-teacher-train-disjoint"
DOMAIN_COUNTS = {"commonvoice": 24, "hadou": 21, "jvs": 3}
MAX_HADOU_CER = 0.15


class PhoneticTeacherError(RuntimeError):
    """The quality-filtered coverage pool cannot be materialized safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PhoneticTeacherError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise PhoneticTeacherError(f"JSON root is not an object: {path.name}")
    return value


def normalize_reading(value: str) -> str:
    return "".join(character for character in value if character.isalnum())


def ngrams(value: str) -> set[str]:
    return {
        f"{width}:{value[start:start + width]}"
        for width in (1, 2, 3)
        for start in range(max(len(value) - width + 1, 0))
    }


def select_hadou(
    rows: Sequence[Mapping[str, Any]],
    audit_rows: Sequence[Mapping[str, Any]],
    *,
    excluded_ids: set[str],
) -> list[Mapping[str, Any]]:
    audit = {
        str(row.get("utterance_id")): row
        for row in audit_rows
        if isinstance(row, dict) and isinstance(row.get("utterance_id"), str)
    }
    eligible: list[tuple[int, Mapping[str, Any], float, str]] = []
    for order, row in enumerate(rows):
        identifier = row.get("utterance_id")
        reading = row.get("reading_katakana")
        audit_row = audit.get(str(identifier))
        comparison = audit_row.get("comparison") if isinstance(audit_row, dict) else None
        best = comparison.get("best") if isinstance(comparison, dict) else None
        cer = best.get("character_error_rate") if isinstance(best, dict) else None
        normalized = normalize_reading(reading) if isinstance(reading, str) else ""
        if (
            row.get("split") != "train"
            or not isinstance(identifier, str)
            or identifier in excluded_ids
            or not isinstance(cer, (int, float))
            or float(cer) > MAX_HADOU_CER
            or len(normalized) < 4
        ):
            continue
        eligible.append((order, row, float(cer), normalized))
    if len(eligible) < DOMAIN_COUNTS["hadou"]:
        raise PhoneticTeacherError("insufficient quality-filtered Hadou rows")

    lengths = sorted(len(value[3]) for value in eligible)
    low = lengths[len(lengths) // 3]
    high = lengths[(2 * len(lengths)) // 3]
    bins: dict[str, list[tuple[int, Mapping[str, Any], float, str]]] = {
        "short": [],
        "medium": [],
        "long": [],
    }
    for value in eligible:
        length = len(value[3])
        name = "short" if length <= low else "medium" if length <= high else "long"
        bins[name].append(value)
    if any(len(values) < 7 for values in bins.values()):
        raise PhoneticTeacherError("Hadou length-bin coverage drifted")

    covered: set[str] = set()
    selected: list[Mapping[str, Any]] = []
    used: set[str] = set()
    for _ in range(7):
        for name in ("short", "medium", "long"):
            candidates = [
                value
                for value in bins[name]
                if str(value[1]["utterance_id"]) not in used
            ]
            winner = min(
                candidates,
                key=lambda value: (
                    -sum(
                        (3 if token.startswith("3:") else 2 if token.startswith("2:") else 1)
                        for token in ngrams(value[3]) - covered
                    ),
                    value[2],
                    value[0],
                ),
            )
            identifier = str(winner[1]["utterance_id"])
            selected.append(
                dict(winner[1])
                | {"_selection_bin": name, "_audit_cer": winner[2]}
            )
            used.add(identifier)
            covered.update(ngrams(winner[3]))
    if len(selected) != DOMAIN_COUNTS["hadou"]:
        raise PhoneticTeacherError("Hadou selection count drifted")
    return selected


def select_sources(arguments: argparse.Namespace) -> list[dict[str, Any]]:
    cv = load_json(arguments.commonvoice_manifest)
    cv_items = cv.get("items")
    if not isinstance(cv_items, list) or len(cv_items) != 48:
        raise PhoneticTeacherError("Common Voice teacher48 manifest drifted")
    selected: list[dict[str, Any]] = []
    for item in cv_items[: DOMAIN_COUNTS["commonvoice"]]:
        source = arguments.commonvoice_root / str(item["filename"])
        if not source.is_file() or sha256_file(source) != item.get("sha256"):
            raise PhoneticTeacherError("Common Voice source drifted")
        selected.append(
            {
                "id": f"cv-{item['id']}",
                "domain": "commonvoice",
                "source": source,
                "filename": f"cv-{item['filename']}",
                "client_id_sha256": item["client_id_sha256"],
                "source_transcript": item["source_transcript"],
                "source_id": item["id"],
                "selection_bin": None,
            }
        )

    hadou = load_json(arguments.hadou_manifest)
    audit = load_json(arguments.hadou_audit)
    evaluation = load_json(arguments.hadou_evaluation)
    hadou_rows = hadou.get("rows")
    audit_rows = audit.get("rows")
    evaluation_items = evaluation.get("items")
    if not all(isinstance(value, list) for value in (hadou_rows, audit_rows, evaluation_items)):
        raise PhoneticTeacherError("Hadou input schema drifted")
    excluded_ids = {
        str(item["id"]) for item in evaluation_items if isinstance(item, dict)
    } | {
        path.name
        for path in arguments.target_root.iterdir()
        if path.is_dir() and not path.is_symlink()
    }
    hadou_selected = select_hadou(hadou_rows, audit_rows, excluded_ids=excluded_ids)
    hadou_client = sha256_text("Hadou-Voice-Dataset@4f68840833d01d825b6ec4c24da55858dabf96bb")
    for row in hadou_selected:
        source_info = row.get("source_wav")
        if not isinstance(source_info, dict):
            raise PhoneticTeacherError("Hadou source metadata drifted")
        source = arguments.hadou_root / str(source_info.get("relative_path"))
        if not source.is_file() or sha256_file(source) != source_info.get("sha256"):
            raise PhoneticTeacherError("Hadou source drifted")
        identifier = str(row["utterance_id"])
        selected.append(
            {
                "id": f"hadou-{identifier}",
                "domain": "hadou",
                "source": source,
                "filename": f"hadou-{identifier}.wav",
                "client_id_sha256": hadou_client,
                "source_transcript": row["display_text"],
                "source_id": identifier,
                "selection_bin": row["_selection_bin"],
                "audit_cer": row["_audit_cer"],
                "reading_katakana": row["reading_katakana"],
            }
        )

    jvs = load_json(arguments.jvs_manifest)
    jvs_items = jvs.get("items")
    clean_jvs = [
        item
        for item in jvs_items
        if isinstance(item, dict)
        and item.get("source_set") == "jvs"
        and item.get("transform") == {"kind": "clean"}
    ] if isinstance(jvs_items, list) else []
    if len(clean_jvs) != DOMAIN_COUNTS["jvs"]:
        raise PhoneticTeacherError("official JVS sample set drifted")
    for item in clean_jvs:
        source = arguments.jvs_root / str(item["filename"])
        if not source.is_file() or sha256_file(source) != item.get("sha256"):
            raise PhoneticTeacherError("JVS source drifted")
        identifier = str(item["id"]).removesuffix("-clean")
        selected.append(
            {
                "id": f"jvs-{identifier}",
                "domain": "jvs",
                "source": source,
                "filename": f"jvs-{identifier}.wav",
                "client_id_sha256": sha256_text(f"official-JVS-sample:{identifier}"),
                "source_transcript": None,
                "source_id": identifier,
                "selection_bin": None,
            }
        )
    if Counter(item["domain"] for item in selected) != DOMAIN_COUNTS:
        raise PhoneticTeacherError("teacher composition drifted")
    return selected


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--commonvoice-manifest", type=Path, required=True)
    value.add_argument("--commonvoice-root", type=Path, required=True)
    value.add_argument("--hadou-manifest", type=Path, required=True)
    value.add_argument("--hadou-audit", type=Path, required=True)
    value.add_argument("--hadou-root", type=Path, required=True)
    value.add_argument("--hadou-evaluation", type=Path, required=True)
    value.add_argument("--target-root", type=Path, required=True)
    value.add_argument("--jvs-manifest", type=Path, required=True)
    value.add_argument("--jvs-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--output-manifest", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    selected = select_sources(arguments)
    hadou = [item for item in selected if item["domain"] == "hadou"]
    summary = {
        "domains": DOMAIN_COUNTS,
        "hadou_bins": dict(Counter(item["selection_bin"] for item in hadou)),
        "hadou_max_audit_cer": max(float(item["audit_cer"]) for item in hadou),
    }
    if arguments.check:
        print(json.dumps({"status": "checked-no-write", **summary}, sort_keys=True))
        return 0
    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    for item in selected:
        destination = arguments.output_root / item["filename"]
        shutil.copyfile(item["source"], destination)
        items.append(
            {
                key: item.get(key)
                for key in (
                    "id", "domain", "filename", "client_id_sha256",
                    "source_transcript", "source_id", "selection_bin",
                    "audit_cer", "reading_katakana",
                )
            }
            | {"group": GROUP, "sha256": sha256_file(destination)}
        )
    manifest = {
        "schema_version": 1,
        "kind": KIND,
        "composition": DOMAIN_COUNTS,
        "selection": (
            "CV24 and JVS3 fixed from EXP-124; Hadou21 selected as seven rows "
            "from each deterministic reading-length tertile, ASR audit CER <= "
            "0.15, greedily maximizing new official-katakana 1/2/3-grams; all "
            "Amitaro target and frozen Hadou31 IDs excluded"
        ),
        "items": items,
    }
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "materialized", **summary, "manifest_sha256": sha256_file(arguments.output_manifest)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
