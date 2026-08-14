#!/usr/bin/env python3
"""Coarse source-relative ASR and repetition screen for X-VC audio.

This tool deliberately compares each converted arm with ASR of its own source.
It can identify content drift or gross loops. It cannot score naturalness,
speaker similarity, target-voice fit, or perceptual quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class ScreenError(RuntimeError):
    """The fixed X-VC screen inputs are incomplete or malformed."""


DECODER_DISAGREEMENT_LIMIT = 0.5


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_japanese(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    output: list[str] = []
    for character in normalized:
        codepoint = ord(character)
        if 0x30A1 <= codepoint <= 0x30F6:
            character = chr(codepoint - 0x60)
        if character.isspace() or unicodedata.category(character)[0] in {"P", "S"}:
            continue
        output.append(character)
    return "".join(output)


def edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def normalized_distance(reference: str, hypothesis: str) -> float:
    reference_normalized = normalize_japanese(reference)
    hypothesis_normalized = normalize_japanese(hypothesis)
    return edit_distance(reference_normalized, hypothesis_normalized) / max(
        len(reference_normalized), 1
    )


def repetition_metrics(value: str) -> dict[str, object]:
    normalized = normalize_japanese(value)
    character_runs = [
        len(match.group(0)) for match in re.finditer(r"(.)\1*", normalized)
    ]
    maximum_run = max(character_runs, default=0)
    maximum_ngram_repeats = 1 if normalized else 0
    for width in range(2, 5):
        for start in range(max(len(normalized) - width + 1, 0)):
            token = normalized[start : start + width]
            repeats = 1
            cursor = start + width
            while normalized[cursor : cursor + width] == token:
                repeats += 1
                cursor += width
            maximum_ngram_repeats = max(maximum_ngram_repeats, repeats)
    return {
        "normalized_characters": len(normalized),
        "maximum_character_run": maximum_run,
        "maximum_repeated_ngram_count": maximum_ngram_repeats,
        "gross_repetition": maximum_run >= 6 or maximum_ngram_repeats >= 4,
    }


def consensus_repetition(greedy: str, beam5: str) -> dict[str, object]:
    """Require two deterministic decoders to agree before calling a gross loop."""

    primary = repetition_metrics(greedy)
    diagnostic = repetition_metrics(beam5)
    return {
        **primary,
        "gross_repetition": bool(primary["gross_repetition"])
        and bool(diagnostic["gross_repetition"]),
        "greedy_gross_repetition": bool(primary["gross_repetition"]),
        "beam5_gross_repetition": bool(diagnostic["gross_repetition"]),
        "beam5_normalized_characters": diagnostic["normalized_characters"],
        "beam5_maximum_character_run": diagnostic["maximum_character_run"],
        "beam5_maximum_repeated_ngram_count": diagnostic[
            "maximum_repeated_ngram_count"
        ],
        "decoder_normalized_distance": normalized_distance(greedy, beam5),
    }


def aggregate_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    def summarize(items: list[Mapping[str, object]]) -> dict[str, object]:
        distances = [float(item["source_relative_distance"]) for item in items]
        stable = [item for item in items if not item.get("decoder_unstable", False)]
        result: dict[str, object] = {
            "rows": len(items),
            "mean_source_relative_distance": sum(distances) / len(distances),
            "maximum_source_relative_distance": max(distances),
            "gross_repetition_rows": sum(
                bool(item["repetition"]["gross_repetition"]) for item in items
            ),
            "decoder_unstable_rows": len(items) - len(stable),
            "decoder_stable_rows": len(stable),
        }
        if stable:
            stable_distances = [
                float(item["source_relative_distance"]) for item in stable
            ]
            result["stable_mean_source_relative_distance"] = sum(
                stable_distances
            ) / len(stable_distances)
            result["stable_maximum_source_relative_distance"] = max(stable_distances)
        known_distances = [
            float(item["known_text_distance"])
            for item in items
            if item.get("known_text_distance") is not None
        ]
        if known_distances:
            result["mean_known_text_distance"] = sum(known_distances) / len(
                known_distances
            )
        stable_known_distances = [
            float(item["known_text_distance"])
            for item in stable
            if item.get("known_text_distance") is not None
        ]
        if stable_known_distances:
            result["stable_mean_known_text_distance"] = sum(
                stable_known_distances
            ) / len(stable_known_distances)
        return result

    buckets: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        buckets[(str(row["group"]), str(row["variant"]))].append(row)
    groups: dict[str, dict[str, object]] = defaultdict(dict)
    for (group, variant), items in sorted(buckets.items()):
        groups[group][variant] = summarize(items)
    macro: dict[str, object] = {}
    variants = sorted({str(row["variant"]) for row in rows})
    for variant in variants:
        items = [row for row in rows if row["variant"] == variant]
        macro[variant] = summarize(items)
    return {"by_group": dict(groups), "macro": macro}


def _load_evaluation(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScreenError("evaluation set is not valid JSON") from error
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ScreenError("evaluation set schema drifted")
    return value


def _load_listener_variants(row_root: Path) -> tuple[str, dict[str, str]]:
    index_path = row_root / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScreenError(f"listener index is invalid: {row_root.name}") from error
    source_file = index.get("source_output_file") if isinstance(index, dict) else None
    rows = index.get("variants") if isinstance(index, dict) else None
    if (
        not isinstance(source_file, str)
        or Path(source_file).name != source_file
        or not isinstance(rows, list)
        or not rows
    ):
        raise ScreenError(f"listener index schema drifted: {row_root.name}")
    variants: dict[str, str] = {}
    for row in rows:
        variant = row.get("variant_id") if isinstance(row, dict) else None
        filename = row.get("output_file") if isinstance(row, dict) else None
        if (
            not isinstance(variant, str)
            or not variant
            or variant in variants
            or not isinstance(filename, str)
            or Path(filename).name != filename
        ):
            raise ScreenError(f"listener variant drifted: {row_root.name}")
        variants[variant] = filename
    return source_file, variants


def _transcribe_pair(model: Any, path: Path) -> tuple[str, str]:
    from faster_whisper.audio import decode_audio

    audio = decode_audio(str(path), sampling_rate=16_000)

    def decode(beam_size: int) -> str:
        segments, _ = model.transcribe(
            audio,
            language="ja",
            task="transcribe",
            beam_size=beam_size,
            temperature=0.0,
            condition_on_previous_text=False,
            log_progress=False,
            word_timestamps=False,
        )
        return "".join(str(segment.text) for segment in segments).strip()

    return decode(1), decode(5)


def run(arguments: argparse.Namespace) -> int:
    evaluation = _load_evaluation(arguments.evaluation_set)
    if arguments.output.exists() or arguments.output.is_symlink():
        raise ScreenError("screen output already exists")
    if arguments.listener_root.is_symlink() or not arguments.listener_root.is_dir():
        raise ScreenError("X-VC listener root is unavailable")
    if arguments.model_root.is_symlink() or not arguments.model_root.is_dir():
        raise ScreenError("STT model root is unavailable")

    from faster_whisper import WhisperModel
    from liveconv_stt.model_artifact import sha256_model_tree

    model_digest = sha256_model_tree(arguments.model_root)
    model = WhisperModel(
        str(arguments.model_root),
        device=arguments.device,
        compute_type=arguments.compute_type,
        cpu_threads=4,
        num_workers=1,
        local_files_only=True,
    )
    rows: list[dict[str, object]] = []
    transcripts: dict[str, str] = {}
    beam5_transcripts: dict[str, str] = {}
    expected_variants: dict[str, str] | None = None
    for index, item in enumerate(evaluation["items"]):
        row_root = arguments.listener_root / f"{index:02d}-{item['id']}"
        source_file, variants = _load_listener_variants(row_root)
        if expected_variants is None:
            expected_variants = variants
        elif variants != expected_variants:
            raise ScreenError("listener variant set changes between rows")
        source_path = row_root / source_file
        expected_files = [source_path, *(row_root / name for name in variants.values())]
        if any(path.is_symlink() or not path.is_file() for path in expected_files):
            raise ScreenError(f"listener row is incomplete: {item['id']}")
        source_transcript, source_beam5_transcript = _transcribe_pair(
            model, source_path
        )
        known_text = item.get("text")
        if known_text is not None and not isinstance(known_text, str):
            raise ScreenError(f"known text is malformed: {item['id']}")
        transcripts[f"{item['id']}/source"] = source_transcript
        beam5_transcripts[f"{item['id']}/source"] = source_beam5_transcript
        for variant, filename in variants.items():
            output_path = row_root / filename
            transcript, beam5_transcript = _transcribe_pair(model, output_path)
            transcripts[f"{item['id']}/{variant}"] = transcript
            beam5_transcripts[f"{item['id']}/{variant}"] = beam5_transcript
            source_normalized = normalize_japanese(source_transcript)
            output_normalized = normalize_japanese(transcript)
            source_repetition = consensus_repetition(
                source_transcript, source_beam5_transcript
            )
            output_repetition = consensus_repetition(transcript, beam5_transcript)
            decoder_unstable = (
                float(source_repetition["decoder_normalized_distance"])
                > DECODER_DISAGREEMENT_LIMIT
                or float(output_repetition["decoder_normalized_distance"])
                > DECODER_DISAGREEMENT_LIMIT
            )
            rows.append(
                {
                    "source_id": item["id"],
                    "group": item["group"],
                    "variant": variant,
                    "source_sha256": sha256_file(source_path),
                    "output_sha256": sha256_file(output_path),
                    "source_transcript": source_transcript,
                    "source_beam5_transcript": source_beam5_transcript,
                    "output_transcript": transcript,
                    "output_beam5_transcript": beam5_transcript,
                    "source_normalized_characters": len(source_normalized),
                    "output_normalized_characters": len(output_normalized),
                    "source_relative_distance": normalized_distance(
                        source_transcript, transcript
                    ),
                    "known_text_distance": (
                        normalized_distance(known_text, transcript)
                        if known_text is not None
                        else None
                    ),
                    "source_known_text_distance": (
                        normalized_distance(known_text, source_transcript)
                        if known_text is not None
                        else None
                    ),
                    "beam5_source_relative_distance": normalized_distance(
                        source_beam5_transcript, beam5_transcript
                    ),
                    "repetition": output_repetition,
                    "source_repetition": source_repetition,
                    "decoder_unstable": decoder_unstable,
                }
            )
    result = {
        "schema_version": 1,
        "kind": "liveconv-xvc-machine-content-screen/v4",
        "boundary": (
            "Auxiliary two-decode ASR only. Gross repetition requires decoder "
            "agreement; content summaries identify rows where greedy and beam5 "
            "differ by more than half the normalized text. This cannot rank "
            "naturalness, target-voice fit, speaker similarity, or a winner."
        ),
        "model": {
            "engine": "faster-whisper==1.2.1",
            "artifact_sha256": model_digest,
            "device": arguments.device,
            "compute_type": arguments.compute_type,
            "decode": {
                "primary_beam_size": 1,
                "diagnostic_beam_size": 5,
                "temperature": 0.0,
                "condition_on_previous_text": False,
                "gross_repetition_policy": ("greedy-and-beam5-must-both-trigger"),
                "decoder_unstable_normalized_distance_above": (
                    DECODER_DISAGREEMENT_LIMIT
                ),
            },
        },
        "evaluation_set_sha256": sha256_file(arguments.evaluation_set),
        "evaluation_kind": evaluation.get("kind"),
        "variants": expected_variants,
        "rows": rows,
        "aggregate": aggregate_rows(rows),
        "transcripts": transcripts,
        "beam5_transcripts": beam5_transcripts,
        "claims": {
            "perceptual_winner": False,
            "promoted": False,
            "route_qualified": False,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["aggregate"], ensure_ascii=False, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-set", type=Path, required=True)
    parser.add_argument("--listener-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="float16")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(_parser().parse_args(argv))
    except (OSError, ValueError, ScreenError) as error:
        print(f"exp033-screen-error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
