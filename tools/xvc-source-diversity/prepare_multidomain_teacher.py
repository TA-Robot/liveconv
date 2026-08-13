#!/usr/bin/env python3
"""Materialize EXP-124's fixed CV24 + Hadou21 + JVS3 teacher pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

KIND = "liveconv-exp124-multidomain-teacher48/v1"
GROUP = "multidomain-teacher-train-disjoint"
DOMAIN_COUNTS = {"commonvoice": 24, "hadou": 21, "jvs": 3}


class MultidomainTeacherError(RuntimeError):
    """The fixed cross-corpus pool cannot be materialized safely."""


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
        raise MultidomainTeacherError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise MultidomainTeacherError(f"JSON root is not an object: {path.name}")
    return value


def select_sources(arguments: argparse.Namespace) -> list[dict[str, Any]]:
    cv = load_json(arguments.commonvoice_manifest)
    cv_items = cv.get("items")
    if not isinstance(cv_items, list) or len(cv_items) != 48:
        raise MultidomainTeacherError("Common Voice teacher48 manifest drifted")
    selected: list[dict[str, Any]] = []
    for item in cv_items[: DOMAIN_COUNTS["commonvoice"]]:
        source = arguments.commonvoice_root / str(item["filename"])
        if not source.is_file() or sha256_file(source) != item.get("sha256"):
            raise MultidomainTeacherError("Common Voice source drifted")
        selected.append(
            {
                "id": f"cv-{item['id']}",
                "domain": "commonvoice",
                "source": source,
                "filename": f"cv-{item['filename']}",
                "client_id_sha256": item["client_id_sha256"],
                "source_transcript": item["source_transcript"],
                "source_id": item["id"],
            }
        )

    hadou = load_json(arguments.hadou_manifest)
    hadou_rows = hadou.get("rows")
    evaluation = load_json(arguments.hadou_evaluation)
    evaluation_items = evaluation.get("items")
    if not isinstance(hadou_rows, list) or not isinstance(evaluation_items, list):
        raise MultidomainTeacherError("Hadou manifest drifted")
    evaluation_ids = {
        str(item["id"]) for item in evaluation_items if isinstance(item, dict)
    }
    target_ids = {
        path.name
        for path in arguments.target_root.iterdir()
        if path.is_dir() and not path.is_symlink()
    }
    eligible = [
        row
        for row in hadou_rows
        if isinstance(row, dict)
        and row.get("split") == "train"
        and row.get("utterance_id") not in evaluation_ids
        and row.get("utterance_id") not in target_ids
    ]
    if len(eligible) < DOMAIN_COUNTS["hadou"]:
        raise MultidomainTeacherError("insufficient disjoint Hadou training rows")
    hadou_client = sha256_text("Hadou-Voice-Dataset@4f68840833d01d825b6ec4c24da55858dabf96bb")
    for row in eligible[: DOMAIN_COUNTS["hadou"]]:
        source_info = row.get("source_wav")
        if not isinstance(source_info, dict):
            raise MultidomainTeacherError("Hadou source metadata drifted")
        source = arguments.hadou_root / str(source_info.get("relative_path"))
        if not source.is_file() or sha256_file(source) != source_info.get("sha256"):
            raise MultidomainTeacherError("Hadou source drifted")
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
            }
        )

    jvs = load_json(arguments.jvs_manifest)
    jvs_items = jvs.get("items")
    clean_jvs = [
        item
        for item in jvs_items if isinstance(item, dict)
        and item.get("source_set") == "jvs"
        and item.get("transform") == {"kind": "clean"}
    ] if isinstance(jvs_items, list) else []
    if len(clean_jvs) != DOMAIN_COUNTS["jvs"]:
        raise MultidomainTeacherError("official JVS sample set drifted")
    for item in clean_jvs:
        source = arguments.jvs_root / str(item["filename"])
        if not source.is_file() or sha256_file(source) != item.get("sha256"):
            raise MultidomainTeacherError("JVS source drifted")
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
            }
        )

    if Counter(item["domain"] for item in selected) != DOMAIN_COUNTS:
        raise MultidomainTeacherError("multi-domain composition drifted")
    if len({item["id"] for item in selected}) != 48:
        raise MultidomainTeacherError("multi-domain source identity drifted")
    return selected


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--commonvoice-manifest", type=Path, required=True)
    value.add_argument("--commonvoice-root", type=Path, required=True)
    value.add_argument("--hadou-manifest", type=Path, required=True)
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
    if arguments.check:
        print(json.dumps({"status": "checked-no-write", "domains": DOMAIN_COUNTS}, sort_keys=True))
        return 0
    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    for item in selected:
        destination = arguments.output_root / item["filename"]
        shutil.copyfile(item["source"], destination)
        items.append(
            {
                "id": item["id"],
                "domain": item["domain"],
                "group": GROUP,
                "filename": item["filename"],
                "sha256": sha256_file(destination),
                "client_id_sha256": item["client_id_sha256"],
                "source_transcript": item["source_transcript"],
                "source_id": item["source_id"],
            }
        )
    manifest = {
        "schema_version": 1,
        "kind": KIND,
        "composition": DOMAIN_COUNTS,
        "selection": (
            "CV teacher48 first 24; first 21 Hadou train rows excluding all "
            "Amitaro target IDs and frozen Hadou31 evaluation IDs; three exact "
            "official clean JVS samples"
        ),
        "items": items,
    }
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "materialized",
                "domains": DOMAIN_COUNTS,
                "manifest_sha256": sha256_file(arguments.output_manifest),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
