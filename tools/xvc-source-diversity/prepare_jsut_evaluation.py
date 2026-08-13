#!/usr/bin/env python3
"""Freeze a category-balanced, output-independent JSUT evaluation set."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import stat
import wave
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

OFFICIAL_ARCHIVE_SHA256 = (
    "081da547f63fd2868184d3a5b488ff325b7ea88464fec2168222b8aeacb20faf"
)
OUTPUT_KIND = "liveconv-jsut-category-heldout24/v1"
WINDOW_POLICY = "first-2.4s-right-pad-if-short"
SPEAKER_SHA256 = hashlib.sha256(b"JSUT official speaker 1").hexdigest()
CATEGORY_COUNTS: Mapping[str, int] = {
    "basic5000": 8,
    "onomatopee300": 4,
    "countersuffix26": 4,
    "loanword128": 4,
    "travel1000": 4,
}


class JsutEvaluationError(RuntimeError):
    """The bounded JSUT evaluation set cannot be prepared safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as opened:
        while chunk := opened.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise JsutEvaluationError(f"JSUT archive member is missing: {name}") from error
    if info.is_dir() or _is_symlink(info) or info.filename != name:
        raise JsutEvaluationError(f"unsafe JSUT archive member: {name}")
    return archive.read(info)


def parse_transcript(value: bytes, category: str) -> list[tuple[str, str]]:
    try:
        lines = value.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as error:
        raise JsutEvaluationError(f"{category} transcript is not UTF-8") from error
    rows: list[tuple[str, str]] = []
    identifiers: set[str] = set()
    for line in lines:
        identifier, separator, text = line.partition(":")
        if (
            separator != ":"
            or not identifier
            or Path(identifier).name != identifier
            or identifier in identifiers
            or not text.strip()
        ):
            raise JsutEvaluationError(f"{category} transcript row is malformed")
        identifiers.add(identifier)
        rows.append((identifier, text.strip()))
    if len(rows) < CATEGORY_COUNTS[category]:
        raise JsutEvaluationError(f"{category} has too few transcript rows")
    return rows


def stratified_positions(row_count: int, selection_count: int) -> list[int]:
    """Select fixed bin centers without inspecting text, audio, or model output."""

    if selection_count <= 0 or row_count < selection_count:
        raise JsutEvaluationError("invalid JSUT stratified selection size")
    positions = [
        ((2 * index + 1) * row_count) // (2 * selection_count)
        for index in range(selection_count)
    ]
    if len(set(positions)) != selection_count or positions[-1] >= row_count:
        raise JsutEvaluationError("JSUT stratified positions drifted")
    return positions


def wav_metadata(value: bytes, identifier: str) -> tuple[int, float]:
    try:
        with wave.open(io.BytesIO(value), "rb") as opened:
            channels = opened.getnchannels()
            sample_width = opened.getsampwidth()
            sample_rate = opened.getframerate()
            frames = opened.getnframes()
    except (EOFError, wave.Error) as error:
        raise JsutEvaluationError(f"invalid JSUT WAV: {identifier}") from error
    if channels != 1 or sample_width != 2 or sample_rate != 48_000 or frames <= 0:
        raise JsutEvaluationError(f"unexpected JSUT WAV format: {identifier}")
    return sample_rate, frames / sample_rate


def build(
    archive_path: Path,
    *,
    expected_archive_sha256: str = OFFICIAL_ARCHIVE_SHA256,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise JsutEvaluationError("JSUT archive is unavailable")
    archive_sha256 = sha256_file(archive_path)
    if archive_sha256 != expected_archive_sha256:
        raise JsutEvaluationError("JSUT archive identity drifted")
    items: list[dict[str, Any]] = []
    audio: dict[str, bytes] = {}
    with zipfile.ZipFile(archive_path) as archive:
        for category, count in CATEGORY_COUNTS.items():
            transcript_name = f"jsut_ver1.1/{category}/transcript_utf8.txt"
            transcript = parse_transcript(
                _read_member(archive, transcript_name), category
            )
            for position in stratified_positions(len(transcript), count):
                identifier, text = transcript[position]
                filename = f"{identifier}.wav"
                member = f"jsut_ver1.1/{category}/wav/{filename}"
                value = _read_member(archive, member)
                sample_rate, duration = wav_metadata(value, identifier)
                if filename in audio:
                    raise JsutEvaluationError("duplicate JSUT output filename")
                audio[filename] = value
                items.append(
                    {
                        "id": f"jsut-{identifier.lower()}",
                        "filename": filename,
                        "sha256": sha256_bytes(value),
                        "client_id_sha256": SPEAKER_SHA256,
                        "source_transcript": text,
                        "text": text,
                        "duration_seconds": duration,
                        "sample_rate": sample_rate,
                        "group": f"jsut-heldout-{category}",
                        "jsut_category": category,
                        "selection_policy": "transcript-order-equal-bin-center",
                        "transcript_position": position + 1,
                        "window_policy": WINDOW_POLICY,
                    }
                )
    if len(items) != sum(CATEGORY_COUNTS.values()):
        raise JsutEvaluationError("JSUT evaluation row count drifted")
    manifest = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "name": "JSUT corpus version 1.1",
            "url": (
                "https://sites.google.com/site/shinnosuketakamichi/publication/jsut"
            ),
            "archive_sha256": archive_sha256,
            "license": "JSUT-LICENCE.txt (category-specific CC BY/CC BY-SA)",
            "redistribution": "audio excluded from git and result bundles",
        },
        "selection": {
            "policy": (
                "equal-width transcript-order bins; take each bin center without "
                "reading model outputs"
            ),
            "category_counts": dict(CATEGORY_COUNTS),
            "speaker_count": 1,
        },
        "items": items,
    }
    return manifest, audio


def materialize(
    output_root: Path,
    manifest: Mapping[str, Any],
    audio: Mapping[str, bytes],
) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise JsutEvaluationError("JSUT evaluation output already exists")
    output_root.mkdir(parents=True)
    source_root = output_root / "source-wav"
    source_root.mkdir()
    for filename, value in audio.items():
        (source_root / filename).write_bytes(value)
    (output_root / "evaluation.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--archive", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, audio = build(arguments.archive)
        if not arguments.check:
            materialize(arguments.output_root, manifest, audio)
        print(
            json.dumps(
                {
                    "status": "checked" if arguments.check else "materialized",
                    "rows": len(manifest["items"]),
                    "category_counts": dict(CATEGORY_COUNTS),
                    "output_root": str(arguments.output_root),
                },
                sort_keys=True,
            )
        )
        return 0
    except (JsutEvaluationError, OSError, zipfile.BadZipFile) as error:
        print(f"jsut-evaluation-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
