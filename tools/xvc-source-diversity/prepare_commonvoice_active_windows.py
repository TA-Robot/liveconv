#!/usr/bin/env python3
"""Materialize signal-only speech-active windows for 48 frozen CV speakers."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import wave
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from prepare_clean_post_rehearsal import sha256_file
OUTPUT_KIND = "liveconv-exp186-commonvoice48-speech-active-windows/v1"
SOURCE_KIND = "liveconv-exp114-commonvoice-teacher48/v1"
EXPECTED_SOURCES = 48
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 38_400
HOP_SAMPLES = 1_600
ACTIVE_THRESHOLD = 0.01
SELECTION_POLICY = (
    "decode the complete frozen MP3 at mono 16 kHz PCM16, score every 2.4-second "
    "window at 100 ms hops by samples above absolute amplitude 0.01, break ties "
    "by squared energy then earliest start; no text, ASR, model output, or "
    "evaluation score is read"
)


class ActiveWindowError(RuntimeError):
    """The speech-active Common Voice windows cannot be frozen safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ActiveWindowError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise ActiveWindowError("Common Voice manifest root is not an object")
    return value


def select_speech_active_window(samples: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    if samples.ndim != 1 or samples.size == 0 or samples.dtype != np.int16:
        raise ActiveWindowError("decoded Common Voice PCM identity drifted")
    if samples.size <= WINDOW_SAMPLES:
        starts = [0]
    else:
        final = samples.size - WINDOW_SAMPLES
        starts = list(range(0, final + 1, HOP_SAMPLES))
        if starts[-1] != final:
            starts.append(final)
    threshold = int(round(ACTIVE_THRESHOLD * 32768.0))
    best: tuple[int, int, int] | None = None
    best_start = 0
    for start in starts:
        window = samples[start : start + WINDOW_SAMPLES].astype(np.int32)
        active = int(np.count_nonzero(np.abs(window) > threshold))
        energy = int(np.square(window, dtype=np.int64).sum())
        score = (active, energy, -start)
        if best is None or score > best:
            best = score
            best_start = start
    selected = np.zeros(WINDOW_SAMPLES, dtype=np.int16)
    available = samples[best_start : best_start + WINDOW_SAMPLES]
    selected[: available.size] = available
    values = selected.astype(np.float64) / 32768.0
    return selected, {
        "window_start_sample": best_start,
        "window_start_seconds": best_start / SAMPLE_RATE,
        "active_sample_fraction": float(
            np.mean(np.abs(selected.astype(np.int32)) > threshold)
        ),
        "rms": float(np.sqrt(np.mean(np.square(values)))),
        "candidate_windows": len(starts),
    }


def decode_mp3(path: Path) -> np.ndarray:
    if path.is_symlink() or not path.is_file():
        raise ActiveWindowError("Common Voice MP3 is unavailable")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map_metadata",
        "-1",
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "s16le",
        "-",
    ]
    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ActiveWindowError("ffmpeg Common Voice decode failed") from error
    if process.returncode != 0 or not process.stdout:
        raise ActiveWindowError("ffmpeg Common Voice decode failed")
    samples = np.frombuffer(process.stdout, dtype="<i2").copy()
    if samples.size == 0:
        raise ActiveWindowError("decoded Common Voice MP3 is empty")
    return samples


def wav_bytes(samples: np.ndarray) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(np.ascontiguousarray(samples, dtype="<i2").tobytes())
    return output.getvalue()


def build(
    source_manifest: Mapping[str, Any],
    source_manifest_path: Path,
    audio_root: Path,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    items = source_manifest.get("items")
    if source_manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise ActiveWindowError("EXP-114 Common Voice identity drifted")
    if len(items) != EXPECTED_SOURCES:
        raise ActiveWindowError("EXP-114 Common Voice coverage drifted")
    output_rows: list[dict[str, Any]] = []
    audio: dict[str, bytes] = {}
    source_ids: set[str] = set()
    client_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ActiveWindowError("EXP-114 Common Voice row drifted")
        identifier = item.get("id")
        filename = item.get("filename")
        source_sha256 = item.get("sha256")
        client_id = item.get("client_id_sha256")
        transcript = item.get("source_transcript")
        if (
            not isinstance(identifier, str)
            or identifier in source_ids
            or not isinstance(filename, str)
            or Path(filename).name != filename
            or Path(filename).suffix.lower() != ".mp3"
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or not isinstance(client_id, str)
            or client_id in client_ids
            or not isinstance(transcript, str)
            or not transcript
        ):
            raise ActiveWindowError("EXP-114 Common Voice row identity drifted")
        source_path = audio_root / filename
        if sha256_file(source_path) != source_sha256:
            raise ActiveWindowError("Common Voice MP3 hash drifted")
        selected, metrics = select_speech_active_window(decode_mp3(source_path))
        payload = wav_bytes(selected)
        output_filename = f"{identifier}.wav"
        audio[output_filename] = payload
        output_rows.append(
            {
                "id": identifier,
                "filename": output_filename,
                "source_filename": filename,
                "source_sha256": source_sha256,
                "window_sha256": __import__("hashlib").sha256(payload).hexdigest(),
                "client_id_sha256": client_id,
                "source_transcript": transcript,
                **metrics,
            }
        )
        source_ids.add(identifier)
        client_ids.add(client_id)
    if len(output_rows) != EXPECTED_SOURCES or len(audio) != EXPECTED_SOURCES:
        raise ActiveWindowError("speech-active Common Voice coverage drifted")
    return (
        {
            "schema_version": 1,
            "kind": OUTPUT_KIND,
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "selection": {
                "policy": SELECTION_POLICY,
                "sample_rate": SAMPLE_RATE,
                "window_samples": WINDOW_SAMPLES,
                "hop_samples": HOP_SAMPLES,
                "active_threshold": ACTIVE_THRESHOLD,
            },
            "items": output_rows,
        },
        audio,
    )


def materialize(
    output_root: Path, manifest: Mapping[str, Any], audio: Mapping[str, bytes]
) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise ActiveWindowError("speech-active output already exists")
    output_root.mkdir(parents=True)
    source_root = output_root / "source-wav"
    source_root.mkdir()
    for filename, payload in audio.items():
        (source_root / filename).write_bytes(payload)
    (output_root / "windows.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--audio-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest, audio = build(
            load_json(arguments.source_manifest),
            arguments.source_manifest,
            arguments.audio_root,
        )
        if not arguments.check:
            materialize(arguments.output_root, manifest, audio)
        print(
            json.dumps(
                {
                    "status": "checked" if arguments.check else "materialized",
                    "rows": len(manifest["items"]),
                    "minimum_active_sample_fraction": min(
                        row["active_sample_fraction"] for row in manifest["items"]
                    ),
                    "output_root": str(arguments.output_root),
                },
                sort_keys=True,
            )
        )
        return 0
    except (ActiveWindowError, OSError, ValueError) as error:
        print(f"commonvoice-active-window-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
