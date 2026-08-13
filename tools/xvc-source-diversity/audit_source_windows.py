#!/usr/bin/env python3
"""Audit the exact 2.4-second Hadou windows available to X-VC training."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import screen

SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 38_400
POSITIONS = ("start", "middle", "end")


class SourceWindowAuditError(RuntimeError):
    """The source-window audit cannot continue safely."""


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceWindowAuditError(f"invalid JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise SourceWindowAuditError(f"JSON root is not an object: {path.name}")
    return value


def window_offsets(sample_count: int) -> dict[str, int]:
    if sample_count <= 0:
        raise SourceWindowAuditError("decoded source audio is empty")
    last = max(sample_count - WINDOW_SAMPLES, 0)
    return {"start": 0, "middle": last // 2, "end": last}


def model_window(audio: np.ndarray, offset: int) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if offset < 0 or offset > max(values.size - 1, 0):
        raise SourceWindowAuditError("source-window offset is invalid")
    output = values[offset : offset + WINDOW_SAMPLES]
    if output.size < WINDOW_SAMPLES:
        output = np.pad(output, (0, WINDOW_SAMPLES - output.size))
    if output.shape != (WINDOW_SAMPLES,) or not np.isfinite(output).all():
        raise SourceWindowAuditError("source window is not finite 2.4-second mono")
    return np.ascontiguousarray(output)


def transcribe(model: Any, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(
        audio,
        language="ja",
        task="transcribe",
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        log_progress=False,
        word_timestamps=False,
    )
    return "".join(str(segment.text) for segment in segments).strip()


def text_ngrams(value: str) -> set[str]:
    normalized = screen.normalize_japanese(value)
    return {
        f"{width}:{normalized[start:start + width]}"
        for width in (1, 2, 3)
        for start in range(max(len(normalized) - width + 1, 0))
    }


def eligible_rows(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    excluded_ids: set[str],
) -> list[tuple[Mapping[str, Any], float]]:
    rows = manifest.get("rows")
    audit_rows = audit.get("rows")
    if not isinstance(rows, list) or not isinstance(audit_rows, list):
        raise SourceWindowAuditError("Hadou manifest or pronunciation audit drifted")
    audit_by_id = {
        str(row.get("utterance_id")): row
        for row in audit_rows
        if isinstance(row, dict) and isinstance(row.get("utterance_id"), str)
    }
    output: list[tuple[Mapping[str, Any], float]] = []
    for row in rows:
        identifier = row.get("utterance_id") if isinstance(row, dict) else None
        audit_row = audit_by_id.get(str(identifier))
        comparison = audit_row.get("comparison") if isinstance(audit_row, dict) else None
        best = comparison.get("best") if isinstance(comparison, dict) else None
        cer = best.get("character_error_rate") if isinstance(best, dict) else None
        if (
            not isinstance(row, dict)
            or row.get("split") != "train"
            or not isinstance(identifier, str)
            or identifier in excluded_ids
            or not isinstance(cer, (int, float))
        ):
            continue
        output.append((row, float(cer)))
    if not output:
        raise SourceWindowAuditError("no training-only Hadou source rows remain")
    return output


def aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for position in POSITIONS:
        items = [row for row in rows if row["position"] == position]
        lengths = [int(row["normalized_characters"]) for row in items]
        covered = set().union(*(text_ngrams(str(row["transcript"])) for row in items))
        output[position] = {
            "rows": len(items),
            "empty_rows": sum(not row["normalized_transcript"] for row in items),
            "gross_repetition_rows": sum(
                bool(row["repetition"]["gross_repetition"]) for row in items
            ),
            "mean_normalized_characters": sum(lengths) / len(lengths),
            "median_normalized_characters": statistics.median(lengths),
            "unique_ngrams": dict(
                Counter(token.split(":", 1)[0] for token in covered)
            ),
        }
    return output


def run(arguments: argparse.Namespace) -> int:
    if arguments.output.exists() or arguments.output.is_symlink():
        raise SourceWindowAuditError("source-window audit output already exists")
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise SourceWindowAuditError("Hadou source root is unavailable")
    if arguments.model_root.is_symlink() or not arguments.model_root.is_dir():
        raise SourceWindowAuditError("STT model root is unavailable")

    excluded_ids = {
        path.name
        for path in arguments.target_root.iterdir()
        if path.is_dir() and not path.is_symlink()
    }
    if arguments.excluded_evaluation is not None:
        evaluation = load_json(arguments.excluded_evaluation)
        items = evaluation.get("items")
        if not isinstance(items, list):
            raise SourceWindowAuditError("excluded evaluation schema drifted")
        excluded_ids.update(
            str(item["id"])
            for item in items
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
    selected = eligible_rows(
        load_json(arguments.source_manifest),
        load_json(arguments.pronunciation_audit),
        excluded_ids=excluded_ids,
    )

    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from liveconv_stt.model_artifact import sha256_model_tree

    model = WhisperModel(
        str(arguments.model_root),
        device=arguments.device,
        compute_type=arguments.compute_type,
    )
    rows: list[dict[str, Any]] = []
    for row, full_cer in selected:
        identifier = str(row["utterance_id"])
        source_info = row.get("source_wav")
        if not isinstance(source_info, dict):
            raise SourceWindowAuditError("Hadou source metadata drifted")
        path = arguments.source_root / str(source_info.get("relative_path"))
        if (
            path.is_symlink()
            or not path.is_file()
            or screen.sha256_file(path) != source_info.get("sha256")
        ):
            raise SourceWindowAuditError(f"Hadou source drifted: {identifier}")
        audio = decode_audio(str(path), sampling_rate=SAMPLE_RATE)
        offsets = window_offsets(int(audio.size))
        for position in POSITIONS:
            offset = offsets[position]
            transcript = transcribe(model, model_window(audio, offset))
            normalized = screen.normalize_japanese(transcript)
            rows.append(
                {
                    "utterance_id": identifier,
                    "position": position,
                    "offset_samples_16k": offset,
                    "offset_seconds": offset / SAMPLE_RATE,
                    "source_sha256": source_info["sha256"],
                    "official_display_text": row.get("display_text"),
                    "official_reading_katakana": row.get("reading_katakana"),
                    "full_utterance_audit_cer": full_cer,
                    "transcript": transcript,
                    "normalized_transcript": normalized,
                    "normalized_characters": len(normalized),
                    "repetition": screen.repetition_metrics(transcript),
                }
            )

    result = {
        "schema_version": 1,
        "kind": "liveconv-xvc-hadou-source-window-audit/v1",
        "boundary": (
            "ASR coverage of fixed 2.4-second source windows only; not "
            "naturalness, phoneme truth, target identity, or a quality winner"
        ),
        "window": {
            "sample_rate_hz": SAMPLE_RATE,
            "samples": WINDOW_SAMPLES,
            "positions": list(POSITIONS),
            "policy": "start/middle/end; right-pad only when source is short",
        },
        "model": {
            "tree_sha256": sha256_model_tree(arguments.model_root),
            "compute_type": arguments.compute_type,
        },
        "source_manifest_sha256": screen.sha256_file(arguments.source_manifest),
        "pronunciation_audit_sha256": screen.sha256_file(
            arguments.pronunciation_audit
        ),
        "candidate_utterances": len(selected),
        "aggregate": aggregate(rows),
        "rows": rows,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["aggregate"], ensure_ascii=False, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--pronunciation-audit", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--target-root", type=Path, required=True)
    value.add_argument("--excluded-evaluation", type=Path)
    value.add_argument("--model-root", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--device", choices=("cuda",), default="cuda")
    value.add_argument("--compute-type", choices=("float16",), default="float16")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (SourceWindowAuditError, OSError, ValueError) as error:
        print(f"source-window-audit-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
