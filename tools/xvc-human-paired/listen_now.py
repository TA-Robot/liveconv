#!/usr/bin/env python3
"""Train and publish the bounded EXP-025 whole-short listen-now comparison.

This runner deliberately skips the superseded EXP-025 receipt/review pipeline.
It uses only the already named 87 eligible train pairs, never opens a heldout
target, and publishes three explicit base-versus-adapted comparisons on the
fixed MS-3 listener root.  The output is operator screening material, not a
promote result or a 334/36/54 adaptation claim.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import wave
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]

EXPECTED_MANIFEST_SHA256 = (
    "2f35e75f169c7cb5664f9f9cc201ff7e79c4d5ba2e700f5c769c6ba1f22f351a"
)
EXPECTED_XVC_REVISION = "49df8c591eafc48b096e466d96f9839f9c0dd739"
EXPECTED_XVC_CONFIG_SHA256 = (
    "5f9aae0487ffcf1b69f5833317d068bfe62c6de1a12b0921abebe742b39c3be7"
)
EXPECTED_CHECKPOINT_BYTES = 5_007_756_915
EXPECTED_TARGET_ARCHIVE_SHA256 = (
    "1fc131f18554625038aaa9876bab0d75660f266ff5e9e18d74cdbb3e6e0df000"
)
EXPECTED_INVENTORY_SHA256 = (
    "078aac5cf583693bf2882a4aadb04b93b78ebca8959fce4586c1544f9025f727"
)
EXPECTED_INVENTORY_FILE_SHA256 = (
    "7a5d532817a63a8cf5520018d88a554f9e4ccccf3d436262b4c8e9440d957ccd"
)
EXPECTED_TARGET_NAME_LIST_SHA256 = (
    "b139638594dcde82f8e026bcca96c6d86d75a7b7144c3274052c87c7b37d3dfa"
)
EXPECTED_TARGET_COUNT = 79
EXPECTED_TRAINABLE_PARAMETERS = 1_031_680
EXPECTED_TRAIN_PAIRS = 87
EXPECTED_TRAIN_ROW_IDS_SHA256 = (
    "b2a447066896ccc1816259bbb5f59a450345fbc719a2b9d336e34c910cf5f2d7"
)
SAMPLE_RATE_48K = 48_000
FRAME_SAMPLES = 960
WINDOW_48K = 115_200
MIN_TARGET_SPEECH_SAMPLES = 86_400
MIN_STRETCH_FACTOR = 0.5
MAX_STRETCH_FACTOR = 2.0
RMS_THRESHOLD = 10.0 ** (-45.0 / 20.0)
MODEL_SAMPLES = 38_400
SEMANTIC_FRAMES = 30
TARGET_HIDDEN_FRAMES = 120
EPOCHS = 4
TOTAL_UPDATES = EXPECTED_TRAIN_PAIRS * EPOCHS
LEARNING_RATE = 1e-4
GRADIENT_CLIP_NORM = 5.0
SEED = 20_260_813
RENDER_COUNT = 3
PINNED_FFMPEG = Path("/usr/bin/ffmpeg")
PINNED_FFMPEG_SHA256 = (
    "ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41"
)
PINNED_LIBRUBBERBAND = Path("/lib/x86_64-linux-gnu/librubberband.so.2")
PINNED_LIBRUBBERBAND_SHA256 = (
    "97c10ec8328a9d5dab1b2e4c562f0a43402a30dacf9bdb20287691331e751670"
)
OFFICIAL_ITA_ROW_IDS = frozenset(
    [f"ITA:EMOTION100_{number:03d}" for number in range(1, 101)]
    + [f"ITA:RECITATION324_{number:03d}" for number in range(1, 325)]
)


class ListenNowError(RuntimeError):
    """The bounded listen-now run cannot safely continue."""


class CandidateIneligible(ListenNowError):
    """One exact row falls outside the fixed listen-now duration boundary."""


@dataclass(frozen=True, slots=True)
class MaterializedPair:
    pair_id: str
    source_path: Path
    target_path: Path
    source_sha256: str
    target_sha256: str


@dataclass(frozen=True, slots=True)
class RenderSource:
    pair_id: str
    display_text: str
    source_path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _regular_file_bytes(path: Path, label: str) -> bytes:
    if path.is_symlink():
        raise ListenNowError(f"{label} must not be a symlink")
    try:
        details = path.stat()
    except OSError as error:
        raise ListenNowError(f"{label} is unreadable") from error
    if not path.is_file() or not stat.S_ISREG(details.st_mode):
        raise ListenNowError(f"{label} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ListenNowError(f"{label} is unreadable") from error


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_regular_file_bytes(path, label))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ListenNowError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ListenNowError(f"{label} must be a JSON object")
    return value


def _safe_pair_id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ListenNowError(f"{label} is not a safe pair ID")
    return value


def _pair_id_from_value(value: Mapping[str, object], label: str) -> str:
    pair_id = _safe_pair_id(
        value.get("pair_id", value.get("utterance_id")), label
    )
    utterance_id = value.get("utterance_id")
    if utterance_id is not None and _safe_pair_id(utterance_id, label) != pair_id:
        raise ListenNowError(f"{label} pair and utterance IDs disagree")
    row_id = value.get("row_id")
    if row_id is not None and row_id != f"ITA:{pair_id}":
        raise ListenNowError(f"{label} row ID drifted")
    return pair_id


def _safe_locator(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ListenNowError(f"{label} is not a safe relative locator")
    parts = value.split("/")
    if value.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ListenNowError(f"{label} is not a safe relative locator")
    return value


def _wav_locator(
    row: Mapping[str, object], side: str, pair_id: str
) -> tuple[str, str]:
    descriptor = row.get(side)
    if not isinstance(descriptor, Mapping):
        raise ListenNowError(f"{side} descriptor is missing for {pair_id}")
    locator_field = "relative_path" if side == "source_wav" else "archive_member"
    locator = _safe_locator(
        descriptor.get(locator_field, descriptor.get("relative_path")),
        f"{side} locator for {pair_id}",
    )
    digest = descriptor.get("sha256")
    if not _is_sha256(digest):
        raise ListenNowError(f"{side} digest is invalid for {pair_id}")
    return locator, str(digest)


def _row_id_from_row(row: Mapping[str, object], label: str) -> str:
    pair_id = _pair_id_from_value(row, label)
    row_id = row.get("row_id", f"ITA:{pair_id}")
    if row_id != f"ITA:{pair_id}":
        raise ListenNowError(f"{label} row ID drifted")
    return str(row_id)


def _candidate_id_digest(values: Sequence[str]) -> str:
    payload = "".join(f"{value}\n" for value in values).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _manifest_rows(
    manifest: Mapping[str, object],
) -> tuple[str, list[dict[str, Any]]]:
    declared = manifest.get("manifest_sha256")
    if (
        manifest.get("kind") != "liveconv-xvc-human-paired-manifest/v1"
        or manifest.get("schema_version") != 1
        or not _is_sha256(declared)
    ):
        raise ListenNowError("EXP-025 manifest header is invalid")
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    if hashlib.sha256(_canonical_bytes(body)).hexdigest() != declared:
        raise ListenNowError("EXP-025 manifest self-hash drifted")
    raw_rows = manifest.get("rows")
    if not isinstance(raw_rows, list):
        raise ListenNowError("EXP-025 manifest rows are missing")
    rows: list[dict[str, Any]] = []
    row_ids: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ListenNowError("EXP-025 manifest row is malformed")
        pair_id = _pair_id_from_value(raw, "EXP-025 manifest row")
        row_id = _row_id_from_row(raw, "EXP-025 manifest row")
        if row_id in row_ids or raw.get("split") not in {
            "train",
            "validation",
            "heldout",
        }:
            raise ListenNowError(f"EXP-025 manifest row drifted: {pair_id}")
        _wav_locator(raw, "source_wav", pair_id)
        _wav_locator(raw, "target_wav", pair_id)
        row_ids.add(row_id)
        rows.append(raw)
    if (
        str(declared) != EXPECTED_MANIFEST_SHA256
        or row_ids != OFFICIAL_ITA_ROW_IDS
        or len(rows) != len(OFFICIAL_ITA_ROW_IDS)
        or manifest.get("style") != "runrun"
    ):
        raise ListenNowError("EXP-025 manifest is not the exact ITA 424 input")
    return str(declared), rows


def _pcm16_array(value: np.ndarray | bytes) -> np.ndarray:
    if isinstance(value, bytes):
        if len(value) % 2:
            raise ListenNowError("PCM16 payload has an odd byte length")
        result = np.frombuffer(value, dtype="<i2")
    else:
        result = np.asarray(value)
        if result.ndim != 1:
            raise ListenNowError("PCM must be one-dimensional mono")
        if result.dtype != np.int16:
            if not np.issubdtype(result.dtype, np.integer):
                raise ListenNowError("PCM must be signed PCM16")
            result = result.astype(np.int16)
    if result.ndim != 1 or not result.size:
        raise ListenNowError("PCM must be non-empty mono PCM16")
    return np.ascontiguousarray(result, dtype=np.int16)


def _parse_pcm16_wav(data: bytes, label: str) -> np.ndarray:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ListenNowError(f"{label} is not a RIFF/WAVE file")
    if struct.unpack_from("<I", data, 4)[0] + 8 != len(data):
        raise ListenNowError(f"{label} has a truncated or trailing RIFF payload")
    try:
        with wave.open(io.BytesIO(data), "rb") as input_file:
            if (
                input_file.getcomptype() != "NONE"
                or input_file.getnchannels() != 1
                or input_file.getsampwidth() != 2
                or input_file.getframerate() != SAMPLE_RATE_48K
            ):
                raise ListenNowError(f"{label} must be mono PCM16 at 48000 Hz")
            frames = input_file.getnframes()
            payload = input_file.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise ListenNowError(f"{label} WAV parse failed") from error
    if len(payload) != frames * 2:
        raise ListenNowError(f"{label} WAV payload is truncated")
    result = _pcm16_array(payload)
    if np.any((result == np.int16(-32768)) | (result == np.int16(32767))):
        raise ListenNowError(f"{label} contains PCM16 full-scale clipping")
    return result


def endpoint_complete_speech(pcm: np.ndarray, rate: int) -> tuple[int, int]:
    if rate != SAMPLE_RATE_48K:
        raise ListenNowError("endpoint detection requires 48000 Hz")
    samples = _pcm16_array(pcm)
    complete_frames, partial_samples = divmod(len(samples), FRAME_SAMPLES)
    if complete_frames == 0:
        raise ListenNowError("PCM is shorter than one 20 ms frame")
    if partial_samples:
        tail = samples[-partial_samples:].astype(np.float64) / 32768.0
        if float(np.sqrt(np.mean(np.square(tail)))) >= RMS_THRESHOLD:
            raise ListenNowError("speech has an active partial tail")
    frames = samples[: complete_frames * FRAME_SAMPLES].astype(np.float64)
    frames = frames.reshape(complete_frames, FRAME_SAMPLES) / 32768.0
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    active = np.flatnonzero(rms >= RMS_THRESHOLD)
    if not len(active):
        raise ListenNowError("speech is empty at the -45 dBFS threshold")
    if active[0] == 0 or active[-1] >= complete_frames - 1:
        raise ListenNowError("speech lacks one complete 20 ms endpoint guard")
    return (int(active[0]) - 1) * FRAME_SAMPLES, (int(active[-1]) + 2) * FRAME_SAMPLES


def _candidate_geometry(
    source_pcm: np.ndarray, target_pcm: np.ndarray
) -> dict[str, object]:
    source_start, source_stop = endpoint_complete_speech(source_pcm, SAMPLE_RATE_48K)
    target_start, target_stop = endpoint_complete_speech(target_pcm, SAMPLE_RATE_48K)
    source_length = source_stop - source_start
    target_length = target_stop - target_start
    if not MIN_TARGET_SPEECH_SAMPLES <= target_length <= WINDOW_48K:
        raise CandidateIneligible("target speech duration must be 1.8..2.4 seconds")
    factor = target_length / source_length
    if not MIN_STRETCH_FACTOR <= factor <= MAX_STRETCH_FACTOR:
        raise CandidateIneligible("source stretch factor must be within 0.5..2")
    return {
        "source_speech_interval_samples": {"start": source_start, "stop": source_stop},
        "target_speech_interval_samples": {"start": target_start, "stop": target_stop},
        "stretch_factor": factor,
    }


def _root_wav_bytes(root: Path, locator: str, label: str) -> bytes:
    if root.is_symlink() or not root.is_dir():
        raise ListenNowError(f"{label} root is unavailable")
    candidate = root
    for part in locator.split("/"):
        candidate /= part
        if candidate.is_symlink():
            raise ListenNowError(f"{label} path traverses a symlink")
    return _regular_file_bytes(candidate, label)


def _assert_wav_hash(data: bytes, expected: str, label: str) -> None:
    if hashlib.sha256(data).hexdigest() != expected:
        raise ListenNowError(f"{label} SHA-256 drifted")


def _right_pad(pcm: np.ndarray, required_samples: int) -> np.ndarray:
    samples = _pcm16_array(pcm)
    if len(samples) > required_samples:
        raise ListenNowError("complete speech interval exceeds the fixed window")
    return np.pad(samples, (0, required_samples - len(samples)), mode="constant")


def _fit_length(pcm: np.ndarray, required_samples: int) -> np.ndarray:
    """Apply only the sub-frame length correction needed after rubberband."""

    samples = _pcm16_array(pcm)
    if len(samples) >= required_samples:
        return samples[:required_samples].copy()
    return np.pad(samples, (0, required_samples - len(samples)), mode="constant")


def ffmpeg_rubberband_identity() -> None:
    if sha256_file(PINNED_FFMPEG) != PINNED_FFMPEG_SHA256:
        raise ListenNowError("pinned ffmpeg identity drifted")
    try:
        resolved = PINNED_LIBRUBBERBAND.resolve(strict=True)
    except OSError as error:
        raise ListenNowError("pinned librubberband is unavailable") from error
    if (
        not PINNED_LIBRUBBERBAND.is_symlink()
        or sha256_file(resolved) != PINNED_LIBRUBBERBAND_SHA256
    ):
        raise ListenNowError("pinned librubberband identity drifted")
    try:
        filters = subprocess.run(
            [str(PINNED_FFMPEG), "-hide_banner", "-filters"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ListenNowError("cannot inspect ffmpeg filters") from error
    if filters.returncode or "rubberband" not in filters.stdout:
        raise ListenNowError("pinned ffmpeg lacks the rubberband filter")


def ffmpeg_rubberband_stretch(pcm: np.ndarray, *, factor: float) -> np.ndarray:
    if not MIN_STRETCH_FACTOR <= factor <= MAX_STRETCH_FACTOR:
        raise ListenNowError("rubberband factor is outside 0.5..2")
    ffmpeg_rubberband_identity()
    with tempfile.TemporaryDirectory(prefix="exp025-listen-now-") as temporary:
        root = Path(temporary)
        source_path = root / "source.wav"
        output_path = root / "stretched.wav"
        _write_pcm16(source_path, _pcm16_array(pcm))
        command = [
            str(PINNED_FFMPEG),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-af",
            f"rubberband=tempo={1.0 / factor:.12f}",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE_48K),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError) as error:
            raise ListenNowError("ffmpeg rubberband stretch failed") from error
        return _parse_pcm16_wav(output_path.read_bytes(), "rubberband output")


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def expanded79_scope(inventory_path: Path) -> dict[str, object]:
    if sha256_file(inventory_path) != EXPECTED_INVENTORY_FILE_SHA256:
        raise ListenNowError("X-VC module inventory file identity drifted")
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ListenNowError("X-VC module inventory is unreadable") from error
    modules = inventory.get("modules") if isinstance(inventory, dict) else None
    acoustic = modules.get("acoustic_converter") if isinstance(modules, dict) else None
    linears = acoustic.get("linear_modules") if isinstance(acoustic, dict) else None
    if (
        inventory.get("inventory_sha256") != EXPECTED_INVENTORY_SHA256
        or not isinstance(linears, list)
    ):
        raise ListenNowError("X-VC module inventory identity drifted")
    targets = [
        item.get("name")
        for item in linears
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    units = [
        item.get("lora_rank_unit_count")
        for item in linears
        if isinstance(item, dict)
    ]
    if (
        len(targets) != EXPECTED_TARGET_COUNT
        or len(set(targets)) != EXPECTED_TARGET_COUNT
        or _canonical_sha256(targets) != EXPECTED_TARGET_NAME_LIST_SHA256
        or len(units) != EXPECTED_TARGET_COUNT
        or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in units
        )
        or 8 * sum(units) != EXPECTED_TRAINABLE_PARAMETERS
    ):
        raise ListenNowError("expanded79 LoRA scope drifted")
    return {
        "target_modules": targets,
        "trainable_parameter_count": EXPECTED_TRAINABLE_PARAMETERS,
    }


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _require_new_output(path: Path, root: Path, label: str) -> None:
    if not _inside(path, root):
        raise ListenNowError(f"{label} must stay below {root}")
    if path.exists() or path.is_symlink():
        raise ListenNowError(f"{label} must not already exist")
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ListenNowError(f"{label} parent must be a real directory")


def _git_output(arguments: Sequence[str], label: str) -> str:
    try:
        return subprocess.run(
            list(arguments),
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise ListenNowError(f"cannot inspect {label}") from error


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _load_json(arguments.manifest, "EXP-025 manifest")
    manifest_sha256, rows = _manifest_rows(manifest)
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise ListenNowError("EXP-025 manifest identity drifted")

    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise ListenNowError("Hadou source root is unavailable")
    if arguments.target_archive.is_symlink() or not arguments.target_archive.is_file():
        raise ListenNowError("Amitaro target archive is unavailable")
    if sha256_file(arguments.target_archive) != EXPECTED_TARGET_ARCHIVE_SHA256:
        raise ListenNowError("Amitaro target archive identity drifted")
    if arguments.xvc_source_root.is_symlink() or not arguments.xvc_source_root.is_dir():
        raise ListenNowError("X-VC source root is unavailable")
    revision = _git_output(
        ["git", "-C", str(arguments.xvc_source_root), "rev-parse", "HEAD"],
        "X-VC revision",
    )
    dirty = _git_output(
        [
            "git",
            "-C",
            str(arguments.xvc_source_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        "X-VC worktree",
    )
    if revision != EXPECTED_XVC_REVISION or dirty:
        raise ListenNowError("X-VC source is not the pinned clean revision")
    if sha256_file(arguments.xvc_config) != EXPECTED_XVC_CONFIG_SHA256:
        raise ListenNowError("X-VC configuration identity drifted")
    if (
        arguments.checkpoint.is_symlink()
        or not arguments.checkpoint.is_file()
        or arguments.checkpoint.stat().st_size != EXPECTED_CHECKPOINT_BYTES
    ):
        raise ListenNowError("X-VC checkpoint is unavailable or has the wrong size")
    ffmpeg_rubberband_identity()
    expanded79_scope(arguments.inventory)

    _require_new_output(
        arguments.work_dir,
        REPO_ROOT / "artifacts" / "xvc-human-paired" / "listen-now",
        "private listen-now work directory",
    )
    _require_new_output(
        arguments.listener_dir,
        REPO_ROOT / "artifacts" / "ms3" / "listening",
        "listener collection directory",
    )
    return manifest, rows


def _archive_wav(archive: zipfile.ZipFile, member: str, label: str) -> bytes:
    try:
        info = archive.getinfo(member)
        if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ListenNowError(f"{label} is not a regular archive member")
        return archive.read(info)
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise ListenNowError(f"cannot read {label}") from error


def _write_pcm16(path: Path, samples: np.ndarray, rate: int = SAMPLE_RATE_48K) -> None:
    values = np.ascontiguousarray(samples, dtype="<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(values.tobytes())


def _materialize_training_pairs(
    rows: Sequence[Mapping[str, object]],
    *,
    source_root: Path,
    target_archive: Path,
    output_root: Path,
) -> list[MaterializedPair]:
    output_root.mkdir(parents=True)
    pairs: list[MaterializedPair] = []
    row_ids: list[str] = []
    with zipfile.ZipFile(target_archive) as archive:
        for row in rows:
            if row.get("split") != "train":
                continue
            pair_id = _pair_id_from_value(row, "EXP-025 train row")
            source_locator, source_hash = _wav_locator(row, "source_wav", pair_id)
            target_locator, target_hash = _wav_locator(row, "target_wav", pair_id)
            source_bytes = _root_wav_bytes(
                source_root, source_locator, f"Hadou source {pair_id}"
            )
            target_bytes = _archive_wav(
                archive, target_locator, f"Amitaro target {pair_id}"
            )
            _assert_wav_hash(source_bytes, source_hash, "Hadou source")
            _assert_wav_hash(target_bytes, target_hash, "Amitaro target")
            source_pcm = _parse_pcm16_wav(source_bytes, f"Hadou source {pair_id}")
            target_pcm = _parse_pcm16_wav(target_bytes, f"Amitaro target {pair_id}")
            try:
                geometry = _candidate_geometry(source_pcm, target_pcm)
            except CandidateIneligible:
                continue
            source_interval = geometry["source_speech_interval_samples"]
            target_interval = geometry["target_speech_interval_samples"]
            assert isinstance(source_interval, Mapping)
            assert isinstance(target_interval, Mapping)
            stretched = ffmpeg_rubberband_stretch(
                source_pcm[
                    int(source_interval["start"]) : int(source_interval["stop"])
                ],
                factor=float(geometry["stretch_factor"]),
            )
            target_length = int(target_interval["stop"]) - int(
                target_interval["start"]
            )
            source_window = _right_pad(
                _fit_length(stretched, target_length), WINDOW_48K
            )
            target_window = _right_pad(
                target_pcm[
                    int(target_interval["start"]) : int(target_interval["stop"])
                ],
                WINDOW_48K,
            )
            pair_dir = output_root / pair_id
            pair_dir.mkdir()
            source_path = pair_dir / "source-48k.wav"
            target_path = pair_dir / "target-48k.wav"
            _write_pcm16(source_path, source_window)
            _write_pcm16(target_path, target_window)
            pairs.append(
                MaterializedPair(
                    pair_id=pair_id,
                    source_path=source_path,
                    target_path=target_path,
                    source_sha256=sha256_file(source_path),
                    target_sha256=sha256_file(target_path),
                )
            )
            row_ids.append(_row_id_from_row(row, "EXP-025 train row"))
    if len(pairs) != EXPECTED_TRAIN_PAIRS:
        raise ListenNowError(
            "eligible EXP-025 train count drifted: "
            f"{len(pairs)} != {EXPECTED_TRAIN_PAIRS}"
        )
    if _candidate_id_digest(row_ids) != EXPECTED_TRAIN_ROW_IDS_SHA256:
        raise ListenNowError("eligible EXP-025 train row IDs drifted")
    return pairs


def select_source_only_render_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    read_source: Callable[[Mapping[str, object]], np.ndarray],
    count: int = RENDER_COUNT,
) -> list[tuple[Mapping[str, object], np.ndarray]]:
    """Choose public heldout sources without resolving any heldout target."""

    selected: list[tuple[Mapping[str, object], np.ndarray]] = []
    for row in rows:
        if row.get("split") != "heldout":
            continue
        pcm = read_source(row)
        start, stop = endpoint_complete_speech(pcm, SAMPLE_RATE_48K)
        if stop - start > WINDOW_48K:
            continue
        selected.append((row, _right_pad(pcm[start:stop], WINDOW_48K)))
        if len(selected) == count:
            return selected
    raise ListenNowError(f"fewer than {count} source-only render rows fit 2.4 seconds")


def _materialize_render_sources(
    rows: Sequence[Mapping[str, object]], *, source_root: Path, output_root: Path
) -> list[RenderSource]:
    output_root.mkdir()

    def read_source(row: Mapping[str, object]) -> np.ndarray:
        pair_id = _pair_id_from_value(row, "render source row")
        locator, expected = _wav_locator(row, "source_wav", pair_id)
        payload = _root_wav_bytes(
            source_root, locator, f"render source {pair_id}"
        )
        _assert_wav_hash(payload, expected, f"render source {pair_id}")
        return _parse_pcm16_wav(payload, f"render source {pair_id}")

    selected = select_source_only_render_rows(rows, read_source=read_source)
    result: list[RenderSource] = []
    for row, samples in selected:
        pair_id = _pair_id_from_value(row, "render source row")
        path = output_root / f"{pair_id}.wav"
        _write_pcm16(path, samples)
        result.append(
            RenderSource(
                pair_id=pair_id,
                display_text=str(row.get("display_text", pair_id)),
                source_path=path,
            )
        )
    return result


def _model_audio(
    path: Path, process_audio: Any, config: Mapping[str, object]
) -> np.ndarray:
    values = process_audio(str(path), config, int(config["latent_hop_length"]))
    array = np.asarray(values, dtype=np.float32).reshape(-1)
    if array.size < MODEL_SAMPLES or not np.isfinite(array).all():
        raise ListenNowError(f"X-VC preprocessing failed for {path.name}")
    return np.ascontiguousarray(array[:MODEL_SAMPLES])


def _extract_pair_tensors(
    model: Any,
    pair: MaterializedPair,
    *,
    process_audio: Any,
    config: Mapping[str, object],
    torch: Any,
    device: Any,
) -> dict[str, Any]:
    source = torch.from_numpy(_model_audio(pair.source_path, process_audio, config))
    target = torch.from_numpy(_model_audio(pair.target_path, process_audio, config))
    source = source.reshape(1, 1, -1).to(device=device, dtype=torch.float32)
    target = target.reshape(1, 1, -1).to(device=device, dtype=torch.float32)
    with torch.inference_mode():
        source_features = model.semantic_encoder.extract_and_encode(source.squeeze(1))
        target_features = model.semantic_encoder.extract_and_encode(target.squeeze(1))
    tokens = source_features.get("speech_tokens")
    hidden = target_features.get("whisper_hidden_states_50hz")
    if tokens is None or hidden is None:
        raise ListenNowError(f"semantic features are incomplete: {pair.pair_id}")
    tokens = tokens[:, :SEMANTIC_FRAMES].to(torch.int64)
    hidden = hidden[..., :TARGET_HIDDEN_FRAMES].to(torch.float32)
    if tokens.shape != (1, SEMANTIC_FRAMES) or hidden.shape[-1] != TARGET_HIDDEN_FRAMES:
        raise ListenNowError(f"semantic feature shape drifted: {pair.pair_id}")
    if not all(bool(torch.isfinite(value).all()) for value in (source, target, hidden)):
        raise ListenNowError(f"non-finite cached tensor: {pair.pair_id}")
    return {
        "source_wav": source.cpu().contiguous(),
        "target_wav": target.cpu().contiguous(),
        "semantic_tokens": tokens.cpu().contiguous(),
        "ssl_feat": hidden.cpu().contiguous(),
    }


def _extract_render_source(
    model: Any,
    source: RenderSource,
    *,
    process_audio: Any,
    config: Mapping[str, object],
    torch: Any,
    device: Any,
) -> dict[str, Any]:
    waveform = torch.from_numpy(_model_audio(source.source_path, process_audio, config))
    waveform = waveform.reshape(1, 1, -1).to(device=device, dtype=torch.float32)
    with torch.inference_mode():
        features = model.semantic_encoder.extract_and_encode(waveform.squeeze(1))
    tokens = features.get("speech_tokens")
    if tokens is None or tokens[:, :SEMANTIC_FRAMES].shape != (1, SEMANTIC_FRAMES):
        raise ListenNowError(f"render semantic tokens are incomplete: {source.pair_id}")
    return {
        "source_wav": waveform.cpu().contiguous(),
        "semantic_tokens": tokens[:, :SEMANTIC_FRAMES]
        .to(torch.int64)
        .cpu()
        .contiguous(),
    }


def _configure_deterministic_cuda(torch: Any, device: Any) -> None:
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.cuda.set_device(device)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_cudnn_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)


def _initialize_loss(model: Any, config_path: Path) -> None:
    from utils.file import load_config

    config = load_config(str(config_path))
    if "config" in config:
        config = config["config"]
    loss_config = config["model"]["generator"]["loss_config"]
    model.loss_config = loss_config
    model.init_loss_function(loss_config)


def _set_adapter_training_only(model: Any) -> list[Any]:
    model.eval()
    active = 0
    for name, module in model.named_modules():
        if ".lora_A" in name or ".lora_B" in name:
            module.train(True)
            active += 1
    trainable = []
    for name, parameter in model.named_parameters():
        is_adapter = ".lora_A." in name or ".lora_B." in name
        if parameter.requires_grad != is_adapter:
            raise ListenNowError(f"unexpected trainability state: {name}")
        if parameter.requires_grad:
            trainable.append(parameter)
    if active == 0 or not trainable:
        raise ListenNowError("PEFT did not expose trainable LoRA tensors")
    return trainable


def _composite_loss(
    model: Any, batch: Mapping[str, Any], torch: Any
) -> tuple[Any, float]:
    outputs = model(dict(batch))
    if not isinstance(outputs, dict) or outputs.get("recons") is None:
        raise ListenNowError("X-VC training output is malformed")
    reconstruction = outputs["recons"]
    if not bool(torch.isfinite(reconstruction).all()):
        raise ListenNowError("X-VC training reconstruction is non-finite")
    outputs["audios"] = batch["target_wav"][..., : reconstruction.shape[-1]]
    losses = model.generative_loss(outputs)
    loss = losses.get("loss") if isinstance(losses, dict) else None
    if loss is None or not bool(torch.isfinite(loss)):
        raise ListenNowError("X-VC generative loss is non-finite")
    return loss, float(loss.detach().cpu())


def _gpu_batch(
    tensors: Mapping[str, Any], *, torch: Any, device: Any
) -> dict[str, Any]:
    source = tensors["source_wav"].to(device=device, dtype=torch.float32)
    target = tensors["target_wav"].to(device=device, dtype=torch.float32)
    return {
        "source_wav": source,
        "target_wav": target,
        "target_wav_cond": torch.zeros_like(target),
        "semantic_tokens": tensors["semantic_tokens"].to(
            device=device, dtype=torch.int64
        ),
        "ssl_feat": tensors["ssl_feat"].to(device=device, dtype=torch.float32),
    }


def _inference(
    model: Any,
    source: Mapping[str, Any],
    reference: Mapping[str, Any],
    *,
    seed: int,
    torch: Any,
    device: Any,
) -> Any:
    index = device.index
    if index is None:
        raise ListenNowError("render requires numbered cuda:0")
    batch = {
        "source_wav": source["source_wav"].to(device=device, dtype=torch.float32),
        "target_wav": reference["target_wav"].to(
            device=device, dtype=torch.float32
        ),
        "semantic_tokens": source["semantic_tokens"].to(
            device=device, dtype=torch.int64
        ),
        "ssl_feat": reference["ssl_feat"].to(device=device, dtype=torch.float32),
    }
    batch["target_wav_cond"] = torch.zeros_like(batch["target_wav"])
    model.eval()
    with torch.random.fork_rng(devices=[index], enabled=True), torch.no_grad():
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        rendered = model.inference(batch).get("recons")
    if (
        rendered is None
        or rendered.shape != (1, 1, MODEL_SAMPLES)
        or not bool(torch.isfinite(rendered).all())
    ):
        raise ListenNowError("X-VC listen-now render is not finite 2.4-second mono")
    return rendered


def _write_float_wav(path: Path, rendered: Any, sample_rate: int) -> str:
    values = rendered.detach().to("cpu", dtype=rendered.dtype).reshape(-1).numpy()
    if values.size != MODEL_SAMPLES or not np.isfinite(values).all():
        raise ListenNowError("rendered waveform is malformed")
    pcm = (np.clip(values, -1.0, 1.0) * 32767.0).round().astype("<i2")
    _write_pcm16(path, pcm, sample_rate)
    return sha256_file(path)


def listening_index(
    source: RenderSource,
    *,
    target_reference_id: str,
    base_sha256: str,
    adapted_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_kind": "EXP-025 whole-short human X-VC listen-now",
        "status": "completed-listen-now-unselected",
        "source_file": (
            f"Hadou public source-only / {source.pair_id} / {source.display_text}"
        ),
        "source_output_file": "00-source-reference.wav",
        "target_reference_output_file": "01-target-reference.wav",
        "reference_audio": [
            {
                "kind": "source",
                "label": f"Hadou source / {source.pair_id}",
                "output_file": "00-source-reference.wav",
                "excluded_from_preference": True,
            },
            {
                "kind": "target",
                "label": f"Amitaro runrun train-role reference / {target_reference_id}",
                "output_file": "01-target-reference.wav",
                "excluded_from_preference": True,
            },
        ],
        "variants": [
            {
                "variant_id": "xvc-base",
                "display_name": "X-VC base / human input / adapterなし",
                "display_order": 1,
                "output_file": "10-xvc-base.wav",
                "status": "passed",
                "profile_id": "xvc.base.human-listen-now",
                "family_id": "x-vc",
                "output_sha256": base_sha256,
            },
            {
                "variant_id": "xvc-whole-short-87-adapted",
                "display_name": "X-VC / 人間whole-short 87ペア / 348 updates",
                "display_order": 2,
                "output_file": "20-xvc-whole-short-87.wav",
                "status": "passed",
                "profile_id": "xvc.exp025.whole-short-87.listen-now",
                "family_id": "x-vc",
                "output_sha256": adapted_sha256,
            },
        ],
    }


def run(
    arguments: argparse.Namespace,
    manifest: Mapping[str, Any],
    rows: list[dict[str, Any]],
) -> int:
    for name in ("HF_DATASETS_OFFLINE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(name) != "1":
            raise ListenNowError(f"{name}=1 is required before model import")
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda:0":
        raise ListenNowError("listen-now training requires the explicit gpu0 lease")

    started = time.monotonic()
    arguments.work_dir.mkdir()
    materialized = _materialize_training_pairs(
        rows,
        source_root=arguments.source_root,
        target_archive=arguments.target_archive,
        output_root=arguments.work_dir / "train-pairs",
    )
    render_sources = _materialize_render_sources(
        rows,
        source_root=arguments.source_root,
        output_root=arguments.work_dir / "render-sources",
    )

    import torch
    from peft import LoraConfig, get_peft_model

    if not torch.cuda.is_available():
        raise ListenNowError("CUDA is unavailable")
    device = torch.device(arguments.device)
    _configure_deterministic_cuda(torch, device)
    torch.cuda.reset_peak_memory_stats(device)
    source_root = str(arguments.xvc_source_root.resolve())
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from models.codec.sac.model import XVC
    from utils.audio import process_audio
    from utils.file import load_config

    config = load_config(str(arguments.xvc_config))
    if "config" in config:
        config = config["config"]
    sample_rate = int(config["sample_rate"])
    base = XVC.load_from_checkpoint(
        str(arguments.xvc_config), str(arguments.checkpoint), device, ema_load=False
    )
    _initialize_loss(base, arguments.xvc_config)
    train_tensors = [
        _extract_pair_tensors(
            base,
            pair,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for pair in materialized
    ]
    render_tensors = [
        _extract_render_source(
            base,
            source,
            process_audio=process_audio,
            config=config,
            torch=torch,
            device=device,
        )
        for source in render_sources
    ]
    target_reference = train_tensors[0]
    target_reference_pair = materialized[0]

    base_outputs = [
        _inference(
            base,
            source,
            target_reference,
            seed=SEED + index,
            torch=torch,
            device=device,
        )
        for index, source in enumerate(render_tensors)
    ]

    scope = expanded79_scope(arguments.inventory)
    targets = list(scope["target_modules"])
    model = get_peft_model(
        base,
        LoraConfig(
            r=8,
            lora_alpha=8,
            lora_dropout=0.0,
            bias="none",
            use_dora=False,
            use_rslora=False,
            target_modules=targets,
        ),
    )
    observed = getattr(model, "targeted_module_names", None)
    if not isinstance(observed, (list, tuple)) or set(observed) != set(targets):
        raise ListenNowError("PEFT target module set drifted")
    trainable = _set_adapter_training_only(model)
    if sum(parameter.numel() for parameter in trainable) != int(
        scope["trainable_parameter_count"]
    ):
        raise ListenNowError("LoRA trainable parameter count drifted")
    optimizer = torch.optim.AdamW(trainable, lr=LEARNING_RATE)
    losses: list[float] = []
    for _epoch in range(EPOCHS):
        for tensors in train_tensors:
            _set_adapter_training_only(model)
            optimizer.zero_grad(set_to_none=True)
            batch = _gpu_batch(tensors, torch=torch, device=device)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss, numeric = _composite_loss(model, batch, torch)
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                trainable, GRADIENT_CLIP_NORM
            )
            if not math.isfinite(float(gradient_norm.detach().cpu())):
                raise ListenNowError("X-VC gradient norm is non-finite")
            optimizer.step()
            losses.append(numeric)
    if len(losses) != TOTAL_UPDATES:
        raise ListenNowError("X-VC update count drifted")

    adapter_dir = arguments.work_dir / "adapter-0348"
    model.save_pretrained(adapter_dir, safe_serialization=True)
    adapted_outputs = [
        _inference(
            model,
            source,
            target_reference,
            seed=SEED + index,
            torch=torch,
            device=device,
        )
        for index, source in enumerate(render_tensors)
    ]

    arguments.listener_dir.mkdir()
    listener_rows: list[dict[str, object]] = []
    for index, (source, base_render, adapted_render) in enumerate(
        zip(render_sources, base_outputs, adapted_outputs, strict=True), start=1
    ):
        row_dir = arguments.listener_dir / f"{index:02d}-{source.pair_id}"
        row_dir.mkdir()
        shutil.copyfile(source.source_path, row_dir / "00-source-reference.wav")
        shutil.copyfile(
            target_reference_pair.target_path, row_dir / "01-target-reference.wav"
        )
        base_sha = _write_float_wav(
            row_dir / "10-xvc-base.wav", base_render, sample_rate
        )
        adapted_sha = _write_float_wav(
            row_dir / "20-xvc-whole-short-87.wav", adapted_render, sample_rate
        )
        _write_json(
            row_dir / "index.json",
            listening_index(
                source,
                target_reference_id=target_reference_pair.pair_id,
                base_sha256=base_sha,
                adapted_sha256=adapted_sha,
            ),
        )
        listener_rows.append(
            {
                "source_id": source.pair_id,
                "base_sha256": base_sha,
                "adapted_sha256": adapted_sha,
            }
        )

    receipt = {
        "schema_version": 1,
        "kind": "liveconv-exp025-whole-short-listen-now-result",
        "status": "completed-listen-now-unselected",
        "git_commit": _git_output(["git", "rev-parse", "HEAD"], "repository commit"),
        "question": (
            "Does 87-pair whole-short human adaptation sound worth a promote pass?"
        ),
        "train_pair_count": len(materialized),
        "epochs": EPOCHS,
        "updates": len(losses),
        "learning_rate": LEARNING_RATE,
        "gradient_clip_norm": GRADIENT_CLIP_NORM,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "render_sources": listener_rows,
        "target_reference_id": target_reference_pair.pair_id,
        "heldout_target_access_count": 0,
        "elapsed_seconds": time.monotonic() - started,
        "peak_gpu_bytes": int(torch.cuda.max_memory_allocated(device)),
        "claims": {
            "promoted": False,
            "route_qualified": False,
            "product_selected": False,
            "serious_334_36_54_adaptation": False,
        },
    }
    _write_json(arguments.work_dir / "listen-now-result.json", receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "listener_dir": str(arguments.listener_dir),
                "updates": len(losses),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-archive", type=Path, required=True)
    parser.add_argument("--xvc-source-root", type=Path, required=True)
    parser.add_argument("--xvc-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts"
            / "exp007"
            / "phase0-inputs-v1"
            / "inventory.json"
        ),
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--listener-dir", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease", choices=("gpu0",))
    parser.add_argument("--device", choices=("cuda:0",), default="cuda:0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        manifest, rows = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "checked-no-cuda",
                        "manifest_sha256": manifest["manifest_sha256"],
                        "row_count": len(rows),
                        "expected_train_pair_count": EXPECTED_TRAIN_PAIRS,
                    },
                    sort_keys=True,
                )
            )
            return 0
        return run(arguments, manifest, rows)
    except (
        ListenNowError,
        OSError,
        ValueError,
    ) as error:
        print(f"listen-now-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
