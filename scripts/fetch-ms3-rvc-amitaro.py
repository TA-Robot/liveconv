#!/usr/bin/env python3
"""Fetch and safely unpack the exact public Amitaro RVC candidate archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import urlparse

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTAKE = REPOSITORY_ROOT / "config" / "ms3-rvc-amitaro-intake.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 16
MAX_UNCOMPRESSED_BYTES = 768 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024

Downloader = Callable[[str, Path, str], None]


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _array(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be non-empty text")
    return value


def _digest(value: object, label: str) -> str:
    digest = _text(value, label)
    if not SHA256.fullmatch(digest):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _filename(value: object, label: str) -> str:
    name = _text(value, label)
    if name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError(f"{label} must be a plain filename")
    return name


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(COPY_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_bounded(source: BinaryIO, destination: BinaryIO, limit: int) -> str:
    digest = hashlib.sha256()
    total = 0
    while chunk := source.read(COPY_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise ValueError("download or extracted member exceeds its size limit")
        destination.write(chunk)
        digest.update(chunk)
    return digest.hexdigest()


def download_archive(url: str, destination: Path, expected_sha256: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "amitaro.net"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("candidate URL must be exact HTTPS on amitaro.net")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "liveconv-ms3-candidate-fetch/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != "amitaro.net":
            raise ValueError("candidate download redirected outside amitaro.net HTTPS")
        with destination.open("xb") as stream:
            actual = _copy_bounded(response, stream, MAX_ARCHIVE_BYTES)
    destination.chmod(0o600)
    if actual != expected_sha256:
        raise ValueError(f"download digest differs: {destination.name}")


def _normalized_member(info: zipfile.ZipInfo) -> PurePosixPath:
    normalized = info.filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
        or (info.external_attr >> 16) & stat.S_IFMT(stat.S_IFLNK)
        or info.flag_bits & 0x1
    ):
        raise ValueError(f"unsafe ZIP member: {info.filename!r}")
    return path


def extract_candidate(
    archive: Path,
    destination: Path,
    expected_files: dict[str, str],
) -> None:
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if not 1 <= len(members) <= MAX_ARCHIVE_MEMBERS:
            raise ValueError(f"unexpected ZIP member count: {archive.name}")
        if sum(member.file_size for member in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"ZIP expands beyond the allowed size: {archive.name}")
        selected: dict[str, zipfile.ZipInfo] = {}
        seen_paths: set[PurePosixPath] = set()
        for member in members:
            path = _normalized_member(member)
            if path in seen_paths:
                raise ValueError(f"duplicate ZIP member: {member.filename!r}")
            seen_paths.add(path)
            if member.is_dir():
                continue
            if path.name in expected_files:
                if path.name in selected:
                    raise ValueError(f"duplicate candidate file: {path.name}")
                selected[path.name] = member
        missing = set(expected_files) - set(selected)
        if missing:
            raise ValueError(
                f"candidate archive is missing: {', '.join(sorted(missing))}"
            )

        destination.mkdir(mode=0o700)
        for name, expected_sha256 in expected_files.items():
            output = destination / name
            with (
                source.open(selected[name]) as input_stream,
                output.open("xb") as stream,
            ):
                actual = _copy_bounded(input_stream, stream, MAX_UNCOMPRESSED_BYTES)
            output.chmod(0o600)
            if actual != expected_sha256:
                raise ValueError(f"extracted file digest differs: {name}")


def fetch_candidates(
    intake: object,
    destination: Path,
    *,
    downloader: Downloader = download_archive,
) -> int:
    document = _object(intake, "intake")
    if document.get("schema_version") != 1 or document.get("provider_id") != "amitaro":
        raise ValueError("unsupported candidate intake")
    variants = _array(document.get("variants"), "intake variants")
    if not 1 <= len(variants) <= 12:
        raise ValueError("intake must contain between one and twelve variants")

    destination = destination.resolve()
    if destination == REPOSITORY_ROOT or REPOSITORY_ROOT in destination.parents:
        raise ValueError("candidate artifacts must be stored outside the repository")
    if destination.exists():
        raise FileExistsError(f"candidate destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    staging.mkdir(mode=0o700)
    try:
        downloads = staging / "downloads"
        extracted = staging / "extracted"
        downloads.mkdir(mode=0o700)
        extracted.mkdir(mode=0o700)
        seen_styles: set[str] = set()
        seen_archives: set[str] = set()
        for candidate in variants:
            style_id = _text(candidate.get("style_id"), "style_id")
            if not SAFE_ID.fullmatch(style_id) or style_id in seen_styles:
                raise ValueError(f"unsafe or duplicate style_id: {style_id}")
            seen_styles.add(style_id)
            archive_name = _filename(candidate.get("archive_name"), "archive_name")
            if archive_name in seen_archives:
                raise ValueError(f"duplicate archive_name: {archive_name}")
            seen_archives.add(archive_name)
            url = _text(candidate.get("download_url"), "download_url")
            archive_sha256 = _digest(candidate.get("archive_sha256"), "archive_sha256")
            archive = downloads / archive_name
            downloader(url, archive, archive_sha256)
            if archive.is_symlink() or not archive.is_file():
                raise ValueError(
                    f"downloader did not create a regular file: {archive_name}"
                )
            if archive.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError(f"download exceeds size limit: {archive_name}")
            if _sha256_file(archive) != archive_sha256:
                raise ValueError(f"download digest differs: {archive_name}")
            expected_files = {
                _filename(candidate.get("checkpoint_name"), "checkpoint_name"): _digest(
                    candidate.get("checkpoint_sha256"), "checkpoint_sha256"
                ),
                _filename(candidate.get("index_name"), "index_name"): _digest(
                    candidate.get("index_sha256"), "index_sha256"
                ),
                _filename(candidate.get("readme_name"), "readme_name"): _digest(
                    candidate.get("readme_sha256"), "readme_sha256"
                ),
            }
            if len(expected_files) != 3:
                raise ValueError(f"candidate filenames must be distinct: {style_id}")
            extract_candidate(archive, extracted / style_id, expected_files)
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
        count = fetch_candidates(intake, arguments.output)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        urllib.error.URLError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"MS-3 RVC fetch failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"fetched and verified {count} RVC variants into {arguments.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
