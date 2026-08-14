#!/usr/bin/env python3
"""Screen frozen X-VC pseudo-teacher outputs against their own source audio."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import screen


class TeacherScreenError(RuntimeError):
    """Pseudo-teacher screen inputs are incomplete or ambiguous."""


def load_pool(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TeacherScreenError("teacher pool is not valid JSON") from error
    items = value.get("items") if isinstance(value, dict) else None
    if not isinstance(items, list) or not items:
        raise TeacherScreenError("teacher pool schema drifted")
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        identifier = item.get("id") if isinstance(item, dict) else None
        domain = item.get("domain", "commonvoice") if isinstance(item, dict) else None
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in output
            or not isinstance(domain, str)
            or not domain
        ):
            raise TeacherScreenError("teacher pool row drifted")
        output[identifier] = dict(item)
    return output


def discover_outputs(
    root: Path, pool: Mapping[str, Mapping[str, Any]]
) -> list[tuple[str, str, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise TeacherScreenError("teacher output root is unavailable")
    rows: list[tuple[str, str, Path]] = []
    counts: Counter[str] = Counter()
    prefix = "teacher-output-"
    suffix = "-16k.wav"
    for path in sorted(root.glob("*/teacher-output-*-16k.wav")):
        filename = path.name
        teacher_id = filename[len(prefix) : -len(suffix)]
        target_id = path.parent.name
        if (
            path.is_symlink()
            or teacher_id not in pool
            or not target_id
            or any(existing[0] == target_id and existing[1] == teacher_id for existing in rows)
        ):
            raise TeacherScreenError("teacher output identity drifted")
        rows.append((target_id, teacher_id, path))
        counts[teacher_id] += 1
    if not rows or set(counts) != set(pool):
        raise TeacherScreenError("teacher output coverage drifted")
    if max(counts.values()) - min(counts.values()) > 1:
        raise TeacherScreenError("teacher output exposure balance drifted")
    return rows


def aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row["domain"])].append(row)
    output: dict[str, Any] = {}
    for domain, items in sorted(buckets.items()):
        distances = [float(item["source_relative_distance"]) for item in items]
        output[domain] = {
            "rows": len(items),
            "mean_source_relative_distance": sum(distances) / len(distances),
            "median_source_relative_distance": statistics.median(distances),
            "distance_at_least_half_rows": sum(value >= 0.5 for value in distances),
            "gross_repetition_rows": sum(
                bool(item["repetition"]["gross_repetition"]) for item in items
            ),
            "decoder_unstable_rows": sum(
                bool(item.get("decoder_unstable", False)) for item in items
            ),
        }
    distances = [float(item["source_relative_distance"]) for item in rows]
    output["macro"] = {
        "rows": len(rows),
        "mean_source_relative_distance": sum(distances) / len(distances),
        "median_source_relative_distance": statistics.median(distances),
        "distance_at_least_half_rows": sum(value >= 0.5 for value in distances),
        "gross_repetition_rows": sum(
            bool(item["repetition"]["gross_repetition"]) for item in rows
        ),
        "decoder_unstable_rows": sum(
            bool(item.get("decoder_unstable", False)) for item in rows
        ),
    }
    return output


def run(arguments: argparse.Namespace) -> int:
    pool = load_pool(arguments.teacher_manifest)
    outputs = discover_outputs(arguments.teacher_output_root, pool)
    if arguments.output.exists() or arguments.output.is_symlink():
        raise TeacherScreenError("teacher screen output already exists")
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise TeacherScreenError("teacher source root is unavailable")
    if arguments.model_root.is_symlink() or not arguments.model_root.is_dir():
        raise TeacherScreenError("STT model root is unavailable")

    from faster_whisper import WhisperModel
    from liveconv_stt.model_artifact import sha256_model_tree

    model = WhisperModel(
        str(arguments.model_root),
        device=arguments.device,
        compute_type=arguments.compute_type,
        cpu_threads=4,
        num_workers=1,
        local_files_only=True,
    )
    source_transcripts: dict[str, tuple[str, str]] = {}
    source_hashes: dict[str, str] = {}
    for teacher_id in sorted(pool):
        path = arguments.source_root / f"{teacher_id}.wav"
        if path.is_symlink() or not path.is_file():
            raise TeacherScreenError(f"teacher source is unavailable: {teacher_id}")
        source_transcripts[teacher_id] = screen._transcribe_pair(model, path)
        source_hashes[teacher_id] = screen.sha256_file(path)

    rows: list[dict[str, Any]] = []
    for target_id, teacher_id, path in outputs:
        transcript, beam5_transcript = screen._transcribe_pair(model, path)
        source_transcript, source_beam5_transcript = source_transcripts[teacher_id]
        source_repetition = screen.consensus_repetition(
            source_transcript, source_beam5_transcript
        )
        output_repetition = screen.consensus_repetition(
            transcript, beam5_transcript
        )
        decoder_unstable = (
            float(source_repetition["decoder_normalized_distance"])
            > screen.DECODER_DISAGREEMENT_LIMIT
            or float(output_repetition["decoder_normalized_distance"])
            > screen.DECODER_DISAGREEMENT_LIMIT
        )
        row: dict[str, Any] = {
            "target_id": target_id,
            "teacher_id": teacher_id,
            "domain": pool[teacher_id].get("domain", "commonvoice"),
            "source_sha256": source_hashes[teacher_id],
            "output_sha256": screen.sha256_file(path),
            "source_transcript": source_transcript,
            "source_beam5_transcript": source_beam5_transcript,
            "output_transcript": transcript,
            "output_beam5_transcript": beam5_transcript,
            "source_relative_distance": screen.normalized_distance(
                source_transcript, transcript
            ),
            "beam5_source_relative_distance": screen.normalized_distance(
                source_beam5_transcript, beam5_transcript
            ),
            "repetition": output_repetition,
            "source_repetition": source_repetition,
            "decoder_unstable": decoder_unstable,
        }
        known = pool[teacher_id].get("source_transcript")
        if isinstance(known, str) and known:
            row["known_text_distance"] = screen.normalized_distance(known, transcript)
            row["source_known_text_distance"] = screen.normalized_distance(
                known, source_transcript
            )
        rows.append(row)

    result = {
        "schema_version": 1,
        "kind": "liveconv-xvc-pseudo-teacher-output-screen/v1",
        "boundary": (
            "auxiliary two-decode source-relative ASR only; gross repetition "
            "requires greedy and beam5 agreement. This is not naturalness, "
            "speaker similarity, target-voice quality, or a winner"
        ),
        "teacher_manifest_sha256": screen.sha256_file(arguments.teacher_manifest),
        "model": {
            "tree_sha256": sha256_model_tree(arguments.model_root),
            "compute_type": arguments.compute_type,
            "decode": {
                "primary_beam_size": 1,
                "diagnostic_beam_size": 5,
                "gross_repetition_policy": "greedy-and-beam5-must-both-trigger",
                "decoder_unstable_normalized_distance_above": (
                    screen.DECODER_DISAGREEMENT_LIMIT
                ),
            },
        },
        "aggregate": aggregate(rows),
        "rows": rows,
    }
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["aggregate"], ensure_ascii=False, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--teacher-manifest", type=Path, required=True)
    value.add_argument("--teacher-output-root", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--model-root", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--device", choices=("cuda",), default="cuda")
    value.add_argument("--compute-type", choices=("float16",), default="float16")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except (TeacherScreenError, OSError, ValueError) as error:
        print(f"teacher-screen-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
