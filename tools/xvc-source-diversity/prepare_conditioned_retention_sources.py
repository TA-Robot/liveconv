#!/usr/bin/env python3
"""Apply one balanced output-blind condition cycle to EXP-186 easy sources."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import run as method  # noqa: E402
from prepare_clean_post_rehearsal import sha256_file  # noqa: E402
from prepare_commonvoice_retention_sources import (  # noqa: E402
    EXPECTED_ROWS,
    EXPECTED_SOURCES,
)
from prepare_commonvoice_retention_sources import OUTPUT_KIND as SOURCE_KIND  # noqa: E402

OUTPUT_KIND = "liveconv-exp191-conditioned-retention-sources85/v1"
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 38_400
NOISE_SEED = 191_000
CONDITION_CYCLE: tuple[Mapping[str, Any], ...] = (
    {"kind": "clean"},
    {"kind": "noise", "snr_db": 15.0},
    {"kind": "tempo", "factor": 1.1},
    {"kind": "pitch", "factor": 2.0 ** (2.0 / 12.0)},
    {"kind": "leading-silence", "milliseconds": 150},
)
EXPECTED_CONDITION_COUNTS = {
    "clean": 17,
    "noise": 17,
    "tempo": 17,
    "pitch": 17,
    "leading-silence": 17,
}
SELECTION_POLICY = (
    "cycle clean/noise15/tempo1.1/pitch+2/leading150ms in frozen EXP-186 "
    "manifest order; no text, ASR, model output, evaluation, or prior result "
    "selects a condition"
)


class ConditionedRetentionError(RuntimeError):
    """Condition-balanced retention sources cannot be frozen safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConditionedRetentionError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise ConditionedRetentionError("conditioned source root is not an object")
    return value


def condition_schedule(count: int = EXPECTED_ROWS) -> list[dict[str, Any]]:
    schedule = [dict(CONDITION_CYCLE[index % len(CONDITION_CYCLE)]) for index in range(count)]
    observed = Counter(str(item["kind"]) for item in schedule)
    if count != EXPECTED_ROWS or dict(observed) != EXPECTED_CONDITION_COUNTS:
        raise ConditionedRetentionError("condition schedule drifted")
    return schedule


def read_window(path: Path) -> np.ndarray:
    if path.is_symlink() or not path.is_file():
        raise ConditionedRetentionError("retention source window is unavailable")
    try:
        with wave.open(str(path), "rb") as reader:
            if (
                reader.getnchannels() != 1
                or reader.getsampwidth() != 2
                or reader.getframerate() != SAMPLE_RATE
                or reader.getnframes() != WINDOW_SAMPLES
            ):
                raise ConditionedRetentionError("retention PCM identity drifted")
            payload = reader.readframes(WINDOW_SAMPLES)
    except (OSError, wave.Error) as error:
        raise ConditionedRetentionError("cannot read retention source window") from error
    values = np.frombuffer(payload, dtype="<i2").copy()
    if values.size != WINDOW_SAMPLES:
        raise ConditionedRetentionError("retention PCM payload drifted")
    return values


def fit_window(values: np.ndarray) -> np.ndarray:
    output = np.zeros(WINDOW_SAMPLES, dtype=np.int16)
    available = np.ascontiguousarray(values[:WINDOW_SAMPLES], dtype=np.int16)
    output[: available.size] = available
    return output


def transform_samples(
    values: np.ndarray,
    condition: Mapping[str, Any],
    *,
    seed: int,
) -> np.ndarray:
    kind = condition.get("kind")
    if kind == "clean":
        return fit_window(values)
    floating = values.astype(np.float32) / 32768.0
    if kind == "noise":
        rms = float(np.sqrt(np.mean(np.square(floating), dtype=np.float64)))
        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(floating.shape).astype(np.float32)
        noise_rms = float(np.sqrt(np.mean(np.square(noise), dtype=np.float64)))
        if rms <= 0.0 or noise_rms <= 0.0:
            raise ConditionedRetentionError("cannot condition a silent source")
        snr_db = float(condition["snr_db"])
        floating = floating + noise * np.float32(
            rms / (10.0 ** (snr_db / 20.0)) / noise_rms
        )
    elif kind == "leading-silence":
        samples = int(round(float(condition["milliseconds"]) * 16.0))
        if samples <= 0 or samples >= WINDOW_SAMPLES:
            raise ConditionedRetentionError("leading silence condition drifted")
        floating = np.concatenate((np.zeros(samples, dtype=np.float32), floating))[
            :WINDOW_SAMPLES
        ]
    else:
        raise ConditionedRetentionError(f"unsupported in-memory condition: {kind}")
    return np.rint(np.clip(floating, -1.0, 1.0) * 32767.0).astype(np.int16)


def transform_file(
    source: Path,
    destination: Path,
    condition: Mapping[str, Any],
    *,
    seed: int,
) -> None:
    kind = str(condition["kind"])
    if kind in {"tempo", "pitch"}:
        temporary = destination.with_suffix(".transform.wav")
        try:
            subprocess.run(
                [
                    str(base.PINNED_FFMPEG),
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
                    "-af",
                    method._rubberband_filter(kind, float(condition["factor"])),
                    "-ac",
                    "1",
                    "-ar",
                    str(SAMPLE_RATE),
                    str(temporary),
                ],
                check=True,
                timeout=60,
            )
            values = read_window_or_variable(temporary)
        except (OSError, subprocess.SubprocessError) as error:
            raise ConditionedRetentionError(f"failed to apply {kind}") from error
        finally:
            if temporary.exists():
                temporary.unlink()
        output = fit_window(values)
    else:
        output = transform_samples(read_window(source), condition, seed=seed)
    base._write_pcm16(destination, output, rate=SAMPLE_RATE)


def read_window_or_variable(path: Path) -> np.ndarray:
    try:
        with wave.open(str(path), "rb") as reader:
            if (
                reader.getnchannels() != 1
                or reader.getsampwidth() != 2
                or reader.getframerate() != SAMPLE_RATE
            ):
                raise ConditionedRetentionError("transformed PCM identity drifted")
            payload = reader.readframes(reader.getnframes())
    except (OSError, wave.Error) as error:
        raise ConditionedRetentionError("cannot read transformed source") from error
    values = np.frombuffer(payload, dtype="<i2").copy()
    if values.size == 0:
        raise ConditionedRetentionError("transformed source is empty")
    return values


def validate_inputs(
    manifest: Mapping[str, Any], source_root: Path
) -> list[dict[str, Any]]:
    items = manifest.get("items")
    if manifest.get("kind") != SOURCE_KIND or not isinstance(items, list):
        raise ConditionedRetentionError("EXP-186 source identity drifted")
    if len(items) != EXPECTED_ROWS:
        raise ConditionedRetentionError("EXP-186 source coverage drifted")
    speakers: set[str] = set()
    ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in items:
        identifier = item.get("id") if isinstance(item, dict) else None
        source_id = item.get("source_id") if isinstance(item, dict) else None
        filename = item.get("filename") if isinstance(item, dict) else None
        digest = item.get("source_sha256") if isinstance(item, dict) else None
        if (
            not isinstance(identifier, str)
            or identifier in ids
            or not isinstance(source_id, str)
            or not isinstance(filename, str)
            or filename != f"{source_id}.wav"
            or not isinstance(digest, str)
        ):
            raise ConditionedRetentionError("EXP-186 source row drifted")
        path = source_root / filename
        read_window(path)
        if sha256_file(path) != digest:
            raise ConditionedRetentionError("EXP-186 source audio drifted")
        rows.append(dict(item))
        ids.add(identifier)
        speakers.add(source_id)
    if len(speakers) != EXPECTED_SOURCES:
        raise ConditionedRetentionError("EXP-186 speaker coverage drifted")
    return rows


def materialize(
    output_root: Path,
    source_manifest: Path,
    source_root: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if output_root.exists() or output_root.is_symlink():
        raise ConditionedRetentionError("conditioned source output exists")
    output_root.mkdir(parents=True)
    audio_root = output_root / "source-wav"
    audio_root.mkdir()
    schedule = condition_schedule()
    output_rows: list[dict[str, Any]] = []
    for index, (item, condition) in enumerate(zip(rows, schedule, strict=True)):
        identifier = str(item["id"])
        kind = str(condition["kind"])
        filename = f"{identifier}-{kind}.wav"
        destination = audio_root / filename
        transform_file(
            source_root / str(item["filename"]),
            destination,
            condition,
            seed=NOISE_SEED + index,
        )
        output_rows.append(
            {
                **dict(item),
                "filename": filename,
                "input_window_filename": item["filename"],
                "input_window_sha256": item["source_sha256"],
                "source_sha256": sha256_file(destination),
                "condition": condition,
                "condition_index": index,
            }
        )
    result = {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source_manifest_sha256": sha256_file(source_manifest),
        "selection": {
            "policy": SELECTION_POLICY,
            "condition_counts": EXPECTED_CONDITION_COUNTS,
            "noise_seed_base": NOISE_SEED,
        },
        "composition": {"commonvoice": EXPECTED_ROWS},
        "items": output_rows,
    }
    (output_root / "sources.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--check", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        rows = validate_inputs(load_json(arguments.source_manifest), arguments.source_root)
        if arguments.check:
            result = {
                "status": "checked-no-write",
                "rows": len(rows),
                "condition_counts": EXPECTED_CONDITION_COUNTS,
            }
        else:
            manifest = materialize(
                arguments.output_root,
                arguments.source_manifest,
                arguments.source_root,
                rows,
            )
            result = {
                "status": "materialized",
                "rows": len(manifest["items"]),
                "condition_counts": manifest["selection"]["condition_counts"],
                "output_root": str(arguments.output_root),
            }
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ConditionedRetentionError, OSError, ValueError) as error:
        print(f"conditioned-retention-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
