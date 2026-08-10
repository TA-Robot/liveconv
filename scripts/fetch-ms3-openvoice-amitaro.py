#!/usr/bin/env python3
"""Fetch exact Amitaro reference clips for the fixed OpenVoice variants."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import stat
import sys
import urllib.error
import zipfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-openvoice-amitaro-intake.json"
COMMON_FETCH_PATH = REPOSITORY_ROOT / "scripts" / "fetch-ms3-rvc-amitaro.py"
MAX_ARCHIVE_MEMBERS = 512
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


def _load_common_fetch() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "liveconv_ms3_common_fetch", COMMON_FETCH_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("common MS-3 fetch module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = _load_common_fetch()


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _member_path(value: object, label: str) -> PurePosixPath:
    text = COMMON._text(value, label).replace("\\", "/")
    path = PurePosixPath(text)
    if text.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} is unsafe")
    return path


def extract_reference(
    archive: Path,
    destination: Path,
    required_members: dict[PurePosixPath, tuple[str, str]],
) -> None:
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if not 1 <= len(members) <= MAX_ARCHIVE_MEMBERS:
            raise ValueError(f"unexpected ZIP member count: {archive.name}")
        if sum(member.file_size for member in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"ZIP expands beyond the allowed size: {archive.name}")
        selected: dict[PurePosixPath, zipfile.ZipInfo] = {}
        seen: set[PurePosixPath] = set()
        for member in members:
            path = COMMON._normalized_member(member)
            if path in seen:
                raise ValueError(f"duplicate ZIP member: {member.filename!r}")
            seen.add(path)
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError(f"unsafe ZIP member: {member.filename!r}")
            if path in required_members:
                selected[path] = member
        missing = set(required_members) - set(selected)
        if missing:
            raise ValueError(
                "reference archive is missing: "
                + ", ".join(str(path) for path in sorted(missing))
            )
        destination.mkdir(mode=0o700)
        for path, (output_name, expected_sha256) in required_members.items():
            output = destination / output_name
            with (
                source.open(selected[path]) as input_stream,
                output.open("xb") as stream,
            ):
                actual = COMMON._copy_bounded(
                    input_stream,
                    stream,
                    MAX_UNCOMPRESSED_BYTES,
                )
            output.chmod(0o600)
            if actual != expected_sha256:
                raise ValueError(f"extracted file digest differs: {output_name}")


def fetch_references(
    intake: object,
    destination: Path,
    *,
    downloader: COMMON.Downloader = COMMON.download_archive,
) -> int:
    document = _object(intake, "intake")
    if document.get("schema_version") != 1 or document.get("provider_id") != "amitaro":
        raise ValueError("unsupported reference intake")
    variants = _array(document.get("variants"), "intake variants")
    if not 1 <= len(variants) <= 4:
        raise ValueError("reference intake must contain between one and four variants")
    destination = destination.resolve()
    if destination == REPOSITORY_ROOT or REPOSITORY_ROOT in destination.parents:
        raise ValueError("reference artifacts must be stored outside the repository")
    if destination.exists():
        raise FileExistsError(f"reference destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    staging.mkdir(mode=0o700)
    try:
        downloads = staging / "downloads"
        extracted = staging / "extracted"
        downloads.mkdir(mode=0o700)
        extracted.mkdir(mode=0o700)
        styles: set[str] = set()
        for variant in variants:
            style_id = COMMON._text(variant.get("style_id"), "style_id")
            if not COMMON.SAFE_ID.fullmatch(style_id) or style_id in styles:
                raise ValueError(f"unsafe or duplicate style_id: {style_id}")
            styles.add(style_id)
            archive_name = COMMON._filename(variant.get("archive_name"), "archive_name")
            archive_sha256 = COMMON._digest(
                variant.get("archive_sha256"), "archive_sha256"
            )
            archive = downloads / archive_name
            downloader(
                COMMON._text(variant.get("download_url"), "download_url"),
                archive,
                archive_sha256,
            )
            if COMMON._sha256_file(archive) != archive_sha256:
                raise ValueError(f"download digest differs: {archive_name}")
            reference_name = COMMON._filename(
                variant.get("reference_name"), "reference_name"
            )
            readme_name = COMMON._filename(variant.get("readme_name"), "readme_name")
            if reference_name == readme_name:
                raise ValueError("reference and readme filenames must differ")
            required = {
                _member_path(variant.get("reference_member"), "reference_member"): (
                    reference_name,
                    COMMON._digest(variant.get("reference_sha256"), "reference_sha256"),
                ),
                _member_path(variant.get("readme_member"), "readme_member"): (
                    readme_name,
                    COMMON._digest(variant.get("readme_sha256"), "readme_sha256"),
                ),
            }
            extract_reference(archive, extracted / style_id, required)
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return len(variants)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        intake = json.loads(arguments.intake.read_text(encoding="utf-8"))
        count = fetch_references(intake, arguments.output)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        urllib.error.URLError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"MS-3 OpenVoice reference fetch failed: {exc}", file=sys.stderr)
        return 2
    print(f"fetched and verified {count} OpenVoice references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
