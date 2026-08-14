#!/usr/bin/env python3
"""Materialize a broad, alignment-free human X-VC training curriculum."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import wave
import zipfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from prepare_clean_post_rehearsal import load_json, sha256_file

OUTPUT_KIND = "liveconv-exp203-unpaired-human-factorized-inputs/v1"
SOURCE_MANIFEST_KIND = "liveconv-xvc-human-paired-manifest/v1"
EXPECTED_SOURCE_ROWS = 424
EXPECTED_TRAIN_ROWS = 334
EXPECTED_ROWS = 170
EXPECTED_COMPOSITION = {"human-hadou-unpaired": EXPECTED_ROWS}
TARGET_ROTATION = EXPECTED_TRAIN_ROWS // 2
SAMPLE_RATE = 48_000
WINDOW_SAMPLES = 115_200
FRAME_SAMPLES = 960
ACTIVE_THRESHOLD_DBFS = -45.0


class UnpairedHumanError(RuntimeError):
    """The unpaired human curriculum cannot be materialized safely."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def selected_train_indices(count: int = EXPECTED_TRAIN_ROWS) -> list[int]:
    """Spread 170 source rows deterministically across all 334 train rows."""
    if count != EXPECTED_TRAIN_ROWS:
        raise UnpairedHumanError("train-row count drifted")
    selected = [(index * count) // EXPECTED_ROWS for index in range(EXPECTED_ROWS)]
    if len(selected) != EXPECTED_ROWS or len(set(selected)) != EXPECTED_ROWS:
        raise UnpairedHumanError("source selection drifted")
    return selected


def _decode_pcm16(value: bytes, *, label: str) -> np.ndarray:
    try:
        with wave.open(io.BytesIO(value), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() != SAMPLE_RATE
                or handle.getcomptype() != "NONE"
            ):
                raise UnpairedHumanError(f"unsupported WAV format: {label}")
            samples = np.frombuffer(
                handle.readframes(handle.getnframes()), dtype="<i2"
            ).copy()
    except (EOFError, wave.Error) as error:
        raise UnpairedHumanError(f"invalid WAV: {label}") from error
    if samples.size == 0:
        raise UnpairedHumanError(f"empty WAV: {label}")
    return samples


def speech_active_window(samples: np.ndarray) -> np.ndarray:
    """Choose one guarded active 2.4 s window without time warping."""
    values = np.asarray(samples, dtype=np.int16).reshape(-1)
    complete_frames = values.size // FRAME_SAMPLES
    if complete_frames:
        framed = values[: complete_frames * FRAME_SAMPLES].reshape(
            complete_frames, FRAME_SAMPLES
        )
        rms = np.sqrt(np.mean(framed.astype(np.float64) ** 2, axis=1))
        threshold = 32768.0 * 10.0 ** (ACTIVE_THRESHOLD_DBFS / 20.0)
        active = np.flatnonzero(rms >= threshold)
    else:
        active = np.empty(0, dtype=np.int64)
    if active.size:
        start = max(0, (int(active[0]) - 1) * FRAME_SAMPLES)
        end = min(values.size, (int(active[-1]) + 2) * FRAME_SAMPLES)
        values = values[start:end]
    if values.size > WINDOW_SAMPLES:
        squared = values.astype(np.float64) ** 2
        cumulative = np.concatenate(([0.0], np.cumsum(squared)))
        starts = np.arange(
            0, values.size - WINDOW_SAMPLES + 1, FRAME_SAMPLES, dtype=np.int64
        )
        energies = cumulative[starts + WINDOW_SAMPLES] - cumulative[starts]
        start = int(starts[int(np.argmax(energies))])
        values = values[start : start + WINDOW_SAMPLES]
    if values.size < WINDOW_SAMPLES:
        values = np.pad(values, (0, WINDOW_SAMPLES - values.size))
    output = np.ascontiguousarray(values[:WINDOW_SAMPLES], dtype=np.int16)
    if output.shape != (WINDOW_SAMPLES,):
        raise UnpairedHumanError("active-window shape drifted")
    return output


def _wav_bytes(samples: np.ndarray) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return output.getvalue()


def _validated_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("rows")
    if (
        manifest.get("kind") != SOURCE_MANIFEST_KIND
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_SOURCE_ROWS
        or manifest.get("split_counts")
        != {"heldout": 54, "train": EXPECTED_TRAIN_ROWS, "validation": 36}
    ):
        raise UnpairedHumanError("source manifest identity drifted")
    train = [dict(row) for row in rows if row.get("split") == "train"]
    if len(train) != EXPECTED_TRAIN_ROWS:
        raise UnpairedHumanError("train split drifted")
    return train


def materialize(
    manifest: Mapping[str, Any],
    *,
    source_root: Path,
    target_archive: Path,
    output_root: Path,
) -> dict[str, Any]:
    train = _validated_rows(manifest)
    archive_identity = manifest["sources"]["target_archive"]["sha256"]
    if sha256_file(target_archive) != archive_identity:
        raise UnpairedHumanError("target archive drifted")
    selected = selected_train_indices()
    output_root.mkdir(parents=True)
    sources_root = output_root / "sources"
    targets_root = output_root / "targets"
    sources_root.mkdir()
    targets_root.mkdir()
    items: list[dict[str, Any]] = []
    with zipfile.ZipFile(target_archive) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise UnpairedHumanError("duplicate target archive member")
        for position, source_index in enumerate(selected):
            source_row = train[source_index]
            target_row = train[(source_index + TARGET_ROTATION) % len(train)]
            source_id = str(source_row["utterance_id"])
            target_id = str(target_row["utterance_id"])
            if source_id == target_id or source_row["text_key"] == target_row["text_key"]:
                raise UnpairedHumanError("unpaired text separation drifted")
            source_path = source_root / source_row["source_wav"]["relative_path"]
            if source_path.is_symlink() or not source_path.is_file():
                raise UnpairedHumanError(f"source WAV unavailable: {source_id}")
            source_bytes = source_path.read_bytes()
            if _sha256_bytes(source_bytes) != source_row["source_wav"]["sha256"]:
                raise UnpairedHumanError(f"source WAV drifted: {source_id}")
            member = str(target_row["target_wav"]["archive_member"])
            try:
                target_bytes = archive.read(member)
            except KeyError as error:
                raise UnpairedHumanError(
                    f"target WAV unavailable: {target_id}"
                ) from error
            if _sha256_bytes(target_bytes) != target_row["target_wav"]["sha256"]:
                raise UnpairedHumanError(f"target WAV drifted: {target_id}")
            source_window = _wav_bytes(
                speech_active_window(_decode_pcm16(source_bytes, label=source_id))
            )
            target_window = _wav_bytes(
                speech_active_window(_decode_pcm16(target_bytes, label=target_id))
            )
            source_file = Path("sources") / f"{position:03d}-{source_id}.wav"
            target_file = Path("targets") / f"{position:03d}-{target_id}.wav"
            (output_root / source_file).write_bytes(source_window)
            (output_root / target_file).write_bytes(target_window)
            items.append(
                {
                    "id": f"{position:03d}-{source_id}--{target_id}",
                    "source_manifest_id": source_row["row_id"],
                    "teacher_id": source_id,
                    "target_id": target_id,
                    "domain": "human-hadou-unpaired",
                    "source_root": "diverse-work",
                    "source_file": str(source_file),
                    "source_sha256": _sha256_bytes(source_window),
                    "target_root": "diverse-work",
                    "target_file": str(target_file),
                    "target_sha256": _sha256_bytes(target_window),
                    "source_relative_distance": 0.0,
                    "source_text": source_row["display_text"],
                    "target_text": target_row["display_text"],
                    "learning_target": "source-content-plus-unpaired-target-identity",
                }
            )
    composition = dict(Counter(str(item["domain"]) for item in items))
    if composition != EXPECTED_COMPOSITION:
        raise UnpairedHumanError("curriculum composition drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "human_manifest_sha256": manifest["manifest_sha256"],
            "target_archive_sha256": archive_identity,
            "selection": (
                "170 rows spread across all 334 train IDs; each source is paired "
                "with the target 167 train positions away, so text is different"
            ),
            "window": (
                "one guarded maximum-energy speech-active 2.4 s window per side; "
                "no stretch, DTW, phoneme alignment, or heldout access"
            ),
            "boundary": (
                "source semantic/content supervision and unrelated Amitaro "
                "speaker/adversarial supervision are factorized during training"
            ),
        },
        "composition": composition,
        "items": items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--target-archive", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.output_root.exists() or arguments.output_root.is_symlink():
            raise UnpairedHumanError("output root already exists")
        manifest = load_json(arguments.manifest)
        result = materialize(
            manifest,
            source_root=arguments.source_root,
            target_archive=arguments.target_archive,
            output_root=arguments.output_root,
        )
        result["source"]["manifest_file_sha256"] = sha256_file(arguments.manifest)
        output = arguments.output_root / "curriculum.json"
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "materialized",
                    "rows": len(result["items"]),
                    "output": str(output),
                    "sha256": sha256_file(output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (KeyError, OSError, UnpairedHumanError, ValueError, zipfile.BadZipFile) as error:
        print(f"unpaired-human-error: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
