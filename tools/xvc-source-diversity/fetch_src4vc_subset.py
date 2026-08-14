#!/usr/bin/env python3
"""Fetch a bounded train/heldout SRC4VC subset with HTTP ZIP ranges."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import io
import json
import struct
import sys
import urllib.error
import urllib.request
import wave
import zlib
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ARCHIVE_URL = "https://sython.org/Corpus/SRC4VC/SRC4VC_ver1.zip"
ARCHIVE_BYTES = 3_417_630_585
ARCHIVE_ETAG = '"cbb4e779-612341409c634"'
CENTRAL_DIRECTORY_OFFSET = 3_415_175_402
CENTRAL_DIRECTORY_BYTES = 2_455_161
CENTRAL_DIRECTORY_SHA256 = (
    "aaacb5d30f3d1e36e539f04210f647e223b98df1a70efcf54aa7a5ea9d20c048"
)
OUTPUT_KIND = "liveconv-exp244-src4vc-smartphone-subset/v1"
ROOT_PREFIX = "SRC4VC_ver1"
SPEAKERS = 100
HELDOUT_SPEAKERS = 15
TRAIN_ROWS = 85
HELDOUT_ROWS = 30
USER_AGENT = "liveconv-src4vc-research-fetch/1"


class Src4vcFetchError(RuntimeError):
    """The bounded SRC4VC acquisition cannot continue safely."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def heldout_speakers() -> set[str]:
    """Return fifteen evenly spread speaker IDs without reading audio."""

    indices = {
        (position * SPEAKERS + SPEAKERS // 2) // HELDOUT_SPEAKERS + 1
        for position in range(HELDOUT_SPEAKERS)
    }
    if len(indices) != HELDOUT_SPEAKERS or min(indices) < 1 or max(indices) > 100:
        raise Src4vcFetchError("heldout speaker spread drifted")
    return {f"SRC4VC{index:03d}" for index in indices}


def parse_central_directory(value: bytes) -> dict[str, dict[str, int | str]]:
    """Parse the pinned non-Zip64 central directory without extracting audio."""

    entries: dict[str, dict[str, int | str]] = {}
    position = 0
    while position < len(value):
        if position + 46 > len(value):
            raise Src4vcFetchError("central directory is truncated")
        fields = struct.unpack_from("<4s6H3L5H2L", value, position)
        if fields[0] != b"PK\x01\x02":
            raise Src4vcFetchError("central directory signature drifted")
        filename_bytes, extra_bytes, comment_bytes = fields[10:13]
        stop = position + 46 + filename_bytes + extra_bytes + comment_bytes
        if stop > len(value):
            raise Src4vcFetchError("central directory entry is truncated")
        try:
            filename = value[position + 46 : position + 46 + filename_bytes].decode(
                "utf-8"
            )
        except UnicodeDecodeError as error:
            raise Src4vcFetchError("central directory filename is not UTF-8") from error
        if (
            filename in entries
            or filename.startswith("/")
            or ".." in Path(filename).parts
        ):
            raise Src4vcFetchError("unsafe or duplicate archive filename")
        entries[filename] = {
            "filename": filename,
            "method": fields[4],
            "crc32": fields[7],
            "compressed_bytes": fields[8],
            "uncompressed_bytes": fields[9],
            "local_offset": fields[16],
        }
        position = stop
    if position != len(value):
        raise Src4vcFetchError("central directory length drifted")
    return entries


def selected_rows(
    entries: Mapping[str, Mapping[str, int | str]],
    *,
    train_utterance_index: int = 0,
) -> list[dict[str, str]]:
    """Select one row for 85 train speakers and two for 15 heldout speakers.

    ``train_utterance_index`` deliberately changes only the train row chosen
    for each speaker.  The heldout rows remain the first two lexicographic
    RECITATION entries so that a source-breadth lane cannot accidentally move
    its evaluation boundary.
    """

    if (
        isinstance(train_utterance_index, bool)
        or not isinstance(train_utterance_index, int)
        or train_utterance_index < 0
        or train_utterance_index >= 10
    ):
        raise Src4vcFetchError("train utterance index must be an integer from 0 to 9")

    by_speaker: dict[str, list[str]] = {}
    heldout = heldout_speakers()
    for speaker_index in range(1, SPEAKERS + 1):
        speaker = f"SRC4VC{speaker_index:03d}"
        prefix = f"{ROOT_PREFIX}/{speaker}/wav/RECITATION_"
        names = sorted(
            name
            for name in entries
            if name.startswith(prefix) and name.endswith(".wav")
        )
        if len(names) != 10:
            raise Src4vcFetchError(f"{speaker}: RECITATION inventory drifted")
        by_speaker[speaker] = names
    rows: list[dict[str, str]] = []
    for speaker, names in sorted(by_speaker.items()):
        split = "evaluation" if speaker in heldout else "train"
        selected = (
            names[:2]
            if split == "evaluation"
            else [names[train_utterance_index]]
        )
        for wav_name in selected:
            basename = Path(wav_name).stem
            txt_name = wav_name.replace("/wav/", "/txt/").removesuffix(".wav") + ".txt"
            metadata_name = f"{ROOT_PREFIX}/{speaker}/speaker_metadata.yml"
            for required in (txt_name, metadata_name):
                if required not in entries:
                    raise Src4vcFetchError(f"archive member is missing: {required}")
            rows.append(
                {
                    "id": f"{speaker.lower()}-{basename.lower()}",
                    "speaker_id": speaker,
                    "split": split,
                    "wav_entry": wav_name,
                    "text_entry": txt_name,
                    "metadata_entry": metadata_name,
                }
            )
    counts = Counter(row["split"] for row in rows)
    if counts != {"train": TRAIN_ROWS, "evaluation": HELDOUT_ROWS}:
        raise Src4vcFetchError("SRC4VC split composition drifted")
    return rows


def extract_local_payload(blob: bytes, entry: Mapping[str, int | str]) -> bytes:
    """Validate and inflate one local ZIP member fetched from its pinned offset."""

    if len(blob) < 30:
        raise Src4vcFetchError("local ZIP record is truncated")
    fields = struct.unpack_from("<4s5H3L2H", blob, 0)
    if fields[0] != b"PK\x03\x04":
        raise Src4vcFetchError("local ZIP signature drifted")
    filename_bytes, extra_bytes = fields[9:11]
    start = 30 + filename_bytes + extra_bytes
    compressed_bytes = int(entry["compressed_bytes"])
    stop = start + compressed_bytes
    if stop > len(blob):
        raise Src4vcFetchError("local ZIP payload is truncated")
    method = int(entry["method"])
    compressed = blob[start:stop]
    try:
        if method == 0:
            output = compressed
        elif method == 8:
            output = zlib.decompress(compressed, -15)
        else:
            raise Src4vcFetchError(f"unsupported ZIP compression method: {method}")
    except zlib.error as error:
        raise Src4vcFetchError("ZIP deflate payload is corrupt") from error
    if len(output) != int(entry["uncompressed_bytes"]) or binascii.crc32(
        output
    ) & 0xFFFFFFFF != int(entry["crc32"]):
        raise Src4vcFetchError("ZIP member size or CRC drifted")
    return output


def parse_metadata(value: bytes) -> dict[str, str | float]:
    """Read SRC4VC's flat YAML subset without accepting executable YAML tags."""

    required = {
        "device_raw_name",
        "device_normalized_name",
        "gender",
        "age",
        "locale",
        "dialect",
        "acting_experience",
    }
    try:
        lines = value.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise Src4vcFetchError("speaker metadata is not UTF-8") from error
    raw_values: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in lines:
        if not line.strip():
            continue
        key, separator, raw = line.partition(":")
        if separator and key in required:
            if key in raw_values:
                raise Src4vcFetchError("speaker metadata shape drifted")
            current_key = key
            raw_values[key] = [raw.strip()]
        elif current_key is not None and line[:1].isspace():
            # Three published rows contain quoted YAML scalars continued on an
            # indented line. Join only that known flat shape; reject tags and
            # arbitrary nested YAML rather than invoking a general loader.
            raw_values[current_key].append(line.strip())
        else:
            raise Src4vcFetchError("speaker metadata shape drifted")
    if set(raw_values) != required:
        raise Src4vcFetchError("speaker metadata fields drifted")
    result: dict[str, str | float] = {}
    for key, parts in raw_values.items():
        text = " ".join(parts).strip().strip("'").strip('"')
        if key == "age":
            try:
                result[key] = float(text)
            except ValueError as error:
                raise Src4vcFetchError("speaker age is malformed") from error
        else:
            result[key] = text
    return result


def parse_mos(value: bytes) -> dict[str, float]:
    try:
        lines = value.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise Src4vcFetchError("speaker MOS table is not UTF-8") from error
    result: dict[str, float] = {}
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 3 or not fields[0].startswith("SRC4VC"):
            raise Src4vcFetchError("speaker MOS table shape drifted")
        result[fields[0]] = float(fields[1])
    if len(result) != SPEAKERS:
        raise Src4vcFetchError("speaker MOS count drifted")
    return result


def validate_wav(value: bytes, *, label: str) -> tuple[float, int]:
    try:
        with wave.open(io.BytesIO(value), "rb") as handle:
            sample_rate = handle.getframerate()
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or sample_rate not in {24_000, 44_100, 48_000}
                or handle.getcomptype() != "NONE"
                or handle.getnframes() <= 0
            ):
                raise Src4vcFetchError(f"{label}: WAV format drifted")
            return handle.getnframes() / sample_rate, sample_rate
    except (EOFError, wave.Error) as error:
        raise Src4vcFetchError(f"{label}: WAV is invalid") from error


def fetch_range(url: str, start: int, stop: int) -> tuple[bytes, Mapping[str, str]]:
    request = urllib.request.Request(
        url,
        headers={"Range": f"bytes={start}-{stop}", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 206:
            raise Src4vcFetchError("server did not honor the ZIP byte range")
        return response.read(), response.headers


def fetch_member(
    url: str,
    entry: Mapping[str, int | str],
    *,
    getter: Callable[[str, int, int], tuple[bytes, Mapping[str, str]]] = fetch_range,
) -> bytes:
    offset = int(entry["local_offset"])
    # All pinned filenames/extras are small. Fetching 4 KiB beyond the compressed
    # body avoids a second request while the parser still validates exact bounds.
    stop = (
        offset
        + 30
        + len(str(entry["filename"]).encode("utf-8"))
        + 4096
        + int(entry["compressed_bytes"])
    )
    blob, _ = getter(url, offset, min(stop, ARCHIVE_BYTES - 1))
    return extract_local_payload(blob, entry)


def run(arguments: argparse.Namespace) -> int:
    central, headers = fetch_range(
        arguments.archive_url,
        CENTRAL_DIRECTORY_OFFSET,
        CENTRAL_DIRECTORY_OFFSET + CENTRAL_DIRECTORY_BYTES - 1,
    )
    if (
        sha256_bytes(central) != CENTRAL_DIRECTORY_SHA256
        or headers.get("ETag") != ARCHIVE_ETAG
    ):
        raise Src4vcFetchError("SRC4VC archive identity drifted")
    entries = parse_central_directory(central)
    rows = selected_rows(
        entries, train_utterance_index=arguments.train_utterance_index
    )
    if arguments.check:
        print(
            json.dumps(
                {
                    "status": "checked-network-no-audio",
                    "archive_entries": len(entries),
                    "train_rows": TRAIN_ROWS,
                    "evaluation_rows": HELDOUT_ROWS,
                    "train_utterance_index": arguments.train_utterance_index,
                    "heldout_speakers": sorted(heldout_speakers()),
                },
                sort_keys=True,
            )
        )
        return 0
    if arguments.output_root.exists() or arguments.output_root.is_symlink():
        raise Src4vcFetchError("SRC4VC subset output root already exists")

    mos_name = f"{ROOT_PREFIX}/speaker_wise_mos.txt"
    required_names = {mos_name}
    for row in rows:
        required_names.update(
            (row["wav_entry"], row["text_entry"], row["metadata_entry"])
        )
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        payloads = dict(
            zip(
                sorted(required_names),
                pool.map(
                    lambda name: fetch_member(arguments.archive_url, entries[name]),
                    sorted(required_names),
                ),
                strict=True,
            )
        )
    mos = parse_mos(payloads[mos_name])
    materialized: list[dict[str, Any]] = []
    arguments.output_root.mkdir(parents=True)
    for row in rows:
        audio = payloads[row["wav_entry"]]
        duration, sample_rate = validate_wav(audio, label=row["id"])
        try:
            transcript = payloads[row["text_entry"]].decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise Src4vcFetchError(f"{row['id']}: transcript is not UTF-8") from error
        if not transcript:
            raise Src4vcFetchError(f"{row['id']}: transcript is empty")
        relative = Path("audio") / row["speaker_id"] / (Path(row["wav_entry"]).name)
        destination = arguments.output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(audio)
        materialized.append(
            {
                **row,
                "filename": relative.as_posix(),
                "sha256": sha256_bytes(audio),
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "text": transcript,
                "text_sha256": sha256_bytes(payloads[row["text_entry"]]),
                "speaker_mos": mos[row["speaker_id"]],
                "speaker_metadata": parse_metadata(payloads[row["metadata_entry"]]),
                "speaker_metadata_sha256": sha256_bytes(
                    payloads[row["metadata_entry"]]
                ),
            }
        )
    manifest = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "corpus": "SRC4VC version 1",
            "official_page": (
                "https://y-saito.sakura.ne.jp/sython/Corpus/SRC4VC/index.html"
            ),
            "archive_url": ARCHIVE_URL,
            "archive_bytes": ARCHIVE_BYTES,
            "archive_etag": ARCHIVE_ETAG,
            "central_directory_sha256": CENTRAL_DIRECTORY_SHA256,
            "terms": (
                "free for research use; redistribution prohibited; raw audio "
                "remains ignored under artifacts/"
            ),
            "selection": (
                "one lexicographically first RECITATION row for 85 speakers; "
                "two for fifteen evenly spread disjoint heldout speakers"
            ),
        },
        "train_utterance_index": arguments.train_utterance_index,
        "split_counts": {"train": TRAIN_ROWS, "evaluation": HELDOUT_ROWS},
        "items": materialized,
    }
    output = arguments.output_root / "subset.json"
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "materialized-private-research-subset",
                "items": len(materialized),
                "manifest": str(output),
                "manifest_sha256": sha256_bytes(output.read_bytes()),
                "train_utterance_index": arguments.train_utterance_index,
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--archive-url", default=ARCHIVE_URL)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--train-utterance-index", type=int, default=0)
    value.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (
        Src4vcFetchError,
        OSError,
        ValueError,
        urllib.error.URLError,
    ) as error:
        print(f"src4vc-fetch-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
