#!/usr/bin/env python3
"""Materialize EXP-112's fresh, speaker-disjoint Common Voice evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REVISION = "365b7654cd582e20e8000921ef7b0e32caa1906a"
METADATA_SHA256 = "6cb76803047f344a2166b7cdd93c4c6470e551af7e374694675477f1a5dbb49f"
KIND = "liveconv-exp112-commonvoice-fresh48/v1"
ROW_COUNT = 48
MIN_NORMALIZED_CHARACTERS = 10
MAX_NORMALIZED_CHARACTERS = 80
BASE_URL = (
    "https://huggingface.co/datasets/FluidInference/"
    f"cv-corpus-25.0-ja/resolve/{REVISION}/ja_00/clips"
)


class FreshEvaluationError(RuntimeError):
    """EXP-112 inputs cannot be frozen safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    return "".join(character for character in value if character.isalnum())


def load_metadata(path: Path) -> list[dict[str, Any]]:
    if sha256_file(path) != METADATA_SHA256:
        raise FreshEvaluationError("Common Voice metadata identity drifted")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise FreshEvaluationError("metadata row is malformed")
            rows.append(value)
    return rows


def select_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    existing_filenames: set[str],
    count: int = ROW_COUNT,
) -> list[dict[str, Any]]:
    by_filename = {
        str(row.get("file_name")): row
        for row in rows
        if isinstance(row.get("file_name"), str)
    }
    excluded_clients = {
        str(by_filename[name].get("client_id"))
        for name in existing_filenames
        if name in by_filename
    }
    selected: list[dict[str, Any]] = []
    selected_clients: set[str] = set()
    for row in rows:
        filename = row.get("file_name")
        client = row.get("client_id")
        text = row.get("text")
        normalized = normalize_text(text) if isinstance(text, str) else ""
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.endswith(".mp3")
            or filename in existing_filenames
            or not isinstance(client, str)
            or not client
            or client in excluded_clients
            or client in selected_clients
            or row.get("locale") != "ja"
            or not isinstance(row.get("up_votes"), int)
            or int(row["up_votes"]) < 2
            or row.get("down_votes") != 0
            or not MIN_NORMALIZED_CHARACTERS
            <= len(normalized)
            <= MAX_NORMALIZED_CHARACTERS
        ):
            continue
        selected.append(dict(row))
        selected_clients.add(client)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise FreshEvaluationError("not enough fresh disjoint Common Voice rows")
    return selected


def duration_seconds(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = float(completed.stdout.strip())
    if not 0.5 <= value <= 30.0:
        raise FreshEvaluationError(f"audio duration is implausible: {path.name}")
    return round(value, 6)


def download(row: Mapping[str, Any], output_root: Path) -> Path:
    filename = str(row["file_name"])
    destination = output_root / filename
    if destination.is_symlink():
        raise FreshEvaluationError(f"source path is a symlink: {filename}")
    if not destination.exists():
        temporary = output_root / f".{filename}.partial"
        request = urllib.request.Request(
            f"{BASE_URL}/{filename}", headers={"User-Agent": "liveconv-exp112/1"}
        )
        with urllib.request.urlopen(request, timeout=60) as source, temporary.open(
            "wb"
        ) as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        if temporary.stat().st_size < 1_000:
            raise FreshEvaluationError(f"download is unexpectedly small: {filename}")
        os.replace(temporary, destination)
    return destination


def build_manifest(
    selected: Sequence[Mapping[str, Any]], output_root: Path
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in selected:
        path = download(row, output_root)
        stem = Path(str(row["file_name"])).stem.removeprefix("common_voice_ja_")
        items.append(
            {
                "id": f"cv{stem}f",
                "group": "commonvoice-fresh-disjoint",
                "filename": path.name,
                "sha256": sha256_file(path),
                "duration_seconds": duration_seconds(path),
                "window_policy": "first-2.4s-right-pad-if-short",
                "text": row["text"],
                "source_transcript": row["text"],
                "source_normalized_characters": len(
                    normalize_text(str(row["text"]))
                ),
                "client_id_sha256": hashlib.sha256(
                    str(row["client_id"]).encode("utf-8")
                ).hexdigest(),
                "age": row.get("age", ""),
                "gender": row.get("gender", ""),
                "up_votes": row["up_votes"],
                "down_votes": row["down_votes"],
            }
        )
    return {
        "schema_version": 1,
        "kind": KIND,
        "source": {
            "corpus": "Mozilla Common Voice Corpus 25.0 / ja / test-ja00",
            "license": "CC0-1.0",
            "mirror": "FluidInference/cv-corpus-25.0-ja",
            "mirror_revision": REVISION,
            "metadata_sha256": METADATA_SHA256,
            "selection": (
                "first 48 metadata-order rows with unique clients, excluding "
                "all locally materialized clients; up_votes>=2, down_votes=0, "
                "10--80 normalized characters"
            ),
        },
        "items": items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--metadata", type=Path, required=True)
    value.add_argument("--existing-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--output-manifest", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    rows = load_metadata(arguments.metadata)
    existing = {
        path.name for path in arguments.existing_root.glob("*.mp3") if path.is_file()
    }
    selected = select_rows(rows, existing_filenames=existing)
    if arguments.check:
        print(
            json.dumps(
                {
                    "status": "checked-no-download",
                    "metadata_rows": len(rows),
                    "existing_files": len(existing),
                    "selected_rows": len(selected),
                    "selected_speakers": len(
                        {row["client_id"] for row in selected}
                    ),
                },
                sort_keys=True,
            )
        )
        return 0
    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    manifest = build_manifest(selected, arguments.output_root)
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "materialized",
                "rows": len(manifest["items"]),
                "manifest": str(arguments.output_manifest),
                "manifest_sha256": sha256_file(arguments.output_manifest),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
