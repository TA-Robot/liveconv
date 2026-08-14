#!/usr/bin/env python3
"""Bind 48 disjoint Common Voice speakers to EXP-150's 85 easy slots."""

from __future__ import annotations

import argparse
import json
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prepare_clean_post_rehearsal import sha256_file
from prepare_commonvoice_active_windows import OUTPUT_KIND as ACTIVE_WINDOW_KIND
from prepare_jsut_evaluation import stratified_positions
from prepare_jsut_retention_sources import easy_slots

OUTPUT_KIND = "liveconv-exp186-commonvoice48-retention-sources85/v2"
SOURCE_KIND = "liveconv-exp114-commonvoice-teacher48/v1"
EXPECTED_SOURCES = 48
EXPECTED_ROWS = 85
EXTRA_EXPOSURES = EXPECTED_ROWS - EXPECTED_SOURCES
SELECTION_POLICY = (
    "all 48 frozen EXP-114 training-only Common Voice speakers once, plus "
    "37 equal-width manifest-order bin centers once more; no text, audio, "
    "model output, or evaluation score selects duplicate exposure"
)


class CommonVoiceRetentionError(RuntimeError):
    """The speaker-balanced retention source binding cannot continue safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommonVoiceRetentionError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise CommonVoiceRetentionError(f"JSON root is not an object: {path.name}")
    return value


def exposure_schedule(source_items: Sequence[Mapping[str, Any]]) -> list[int]:
    if len(source_items) != EXPECTED_SOURCES:
        raise CommonVoiceRetentionError("Common Voice source count drifted")
    extras = stratified_positions(EXPECTED_SOURCES, EXTRA_EXPOSURES)
    if len(extras) != EXTRA_EXPOSURES or len(set(extras)) != EXTRA_EXPOSURES:
        raise CommonVoiceRetentionError("duplicate exposure schedule drifted")
    schedule = list(range(EXPECTED_SOURCES)) + extras
    counts = Counter(schedule)
    if (
        len(schedule) != EXPECTED_ROWS
        or set(counts.values()) != {1, 2}
        or sum(value == 2 for value in counts.values()) != EXTRA_EXPOSURES
    ):
        raise CommonVoiceRetentionError("speaker exposure balance drifted")
    return schedule


def wav_identity(path: Path) -> tuple[int, int, int]:
    if path.is_symlink() or not path.is_file():
        raise CommonVoiceRetentionError("Common Voice source window is unavailable")
    try:
        with wave.open(str(path), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frames = reader.getnframes()
    except (wave.Error, OSError) as error:
        raise CommonVoiceRetentionError("invalid Common Voice source window") from error
    if channels != 1 or sample_width != 2 or sample_rate != 16_000 or frames <= 0:
        raise CommonVoiceRetentionError("Common Voice source PCM identity drifted")
    return sample_rate, frames, sample_width * 8


def build(
    source_manifest: Mapping[str, Any],
    source_manifest_path: Path,
    window_manifest: Mapping[str, Any],
    window_manifest_path: Path,
    source_root: Path,
    selective: Mapping[str, Any],
    selective_path: Path,
) -> dict[str, Any]:
    items = source_manifest.get("items")
    if source_manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise CommonVoiceRetentionError("EXP-114 source identity drifted")
    if len(items) != EXPECTED_SOURCES:
        raise CommonVoiceRetentionError("EXP-114 source coverage drifted")
    window_items = window_manifest.get("items")
    if (
        window_manifest.get("kind") != ACTIVE_WINDOW_KIND
        or not isinstance(window_items, list)
        or len(window_items) != EXPECTED_SOURCES
    ):
        raise CommonVoiceRetentionError("speech-active window identity drifted")
    windows = {
        str(item.get("id")): item
        for item in window_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(windows) != EXPECTED_SOURCES:
        raise CommonVoiceRetentionError("speech-active window coverage drifted")
    slots = easy_slots(selective)
    schedule = exposure_schedule(items)
    client_ids: set[str] = set()
    source_ids: set[str] = set()
    source_rows: list[dict[str, Any]] = []
    for source_index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CommonVoiceRetentionError("EXP-114 source row drifted")
        identifier = item.get("id")
        client_id = item.get("client_id_sha256")
        transcript = item.get("source_transcript")
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in source_ids
            or not isinstance(client_id, str)
            or len(client_id) != 64
            or client_id in client_ids
            or not isinstance(transcript, str)
            or not transcript
        ):
            raise CommonVoiceRetentionError("EXP-114 speaker identity drifted")
        window = windows.get(identifier)
        if (
            not isinstance(window, dict)
            or window.get("client_id_sha256") != client_id
            or window.get("source_sha256") != item.get("sha256")
            or not isinstance(window.get("window_sha256"), str)
            or not isinstance(window.get("window_start_sample"), int)
            or not isinstance(window.get("active_sample_fraction"), (int, float))
        ):
            raise CommonVoiceRetentionError("speech-active source binding drifted")
        path = source_root / f"{identifier}.wav"
        sample_rate, frames, bit_depth = wav_identity(path)
        if sha256_file(path) != window["window_sha256"]:
            raise CommonVoiceRetentionError("speech-active source audio drifted")
        source_ids.add(identifier)
        client_ids.add(client_id)
        source_rows.append(
            {
                "source_index": source_index,
                "source_id": identifier,
                "filename": path.name,
                "source_sha256": sha256_file(path),
                "source_transcript": transcript,
                "client_id_sha256": client_id,
                "sample_rate": sample_rate,
                "frames": frames,
                "bit_depth": bit_depth,
                "window_start_sample": window["window_start_sample"],
                "window_start_seconds": window["window_start_seconds"],
                "active_sample_fraction": window["active_sample_fraction"],
                "window_selection_policy": window_manifest["selection"]["policy"],
            }
        )
    exposure_counts: Counter[str] = Counter()
    output_items: list[dict[str, Any]] = []
    for source_index, slot in zip(schedule, slots, strict=True):
        source = source_rows[source_index]
        source_id = str(source["source_id"])
        exposure_counts[source_id] += 1
        exposure = exposure_counts[source_id]
        output_items.append(
            {
                **source,
                **slot,
                "id": f"{source_id}-e{exposure}",
                "exposure": exposure,
                "domain": "commonvoice",
                "selection_policy": SELECTION_POLICY,
            }
        )
    counts = Counter(str(item["source_id"]) for item in output_items)
    if (
        len(output_items) != EXPECTED_ROWS
        or len(counts) != EXPECTED_SOURCES
        or min(counts.values()) != 1
        or max(counts.values()) != 2
    ):
        raise CommonVoiceRetentionError("Common Voice retention binding drifted")
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "name": "Mozilla Common Voice Corpus 25.0 Japanese",
            "role": "training-only retention sources",
            "redistribution": "audio excluded from git and result bundles",
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "window_manifest_sha256": sha256_file(window_manifest_path),
            "selective_curriculum_sha256": sha256_file(selective_path),
        },
        "selection": {
            "policy": SELECTION_POLICY,
            "unique_speakers": EXPECTED_SOURCES,
            "total_exposures": EXPECTED_ROWS,
            "exposure_counts": dict(sorted(counts.items())),
        },
        "composition": {"commonvoice": EXPECTED_ROWS},
        "items": output_items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--window-manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--selective-curriculum", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        manifest = build(
            load_json(arguments.source_manifest),
            arguments.source_manifest,
            load_json(arguments.window_manifest),
            arguments.window_manifest,
            arguments.source_root,
            load_json(arguments.selective_curriculum),
            arguments.selective_curriculum,
        )
        if not arguments.check:
            if arguments.output.exists() or arguments.output.is_symlink():
                raise CommonVoiceRetentionError("retention source output exists")
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "status": "checked" if arguments.check else "materialized",
                    "rows": len(manifest["items"]),
                    "unique_speakers": manifest["selection"]["unique_speakers"],
                    "output": str(arguments.output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (CommonVoiceRetentionError, OSError, ValueError) as error:
        print(f"commonvoice-retention-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
