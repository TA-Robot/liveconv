#!/usr/bin/env python3
"""Freeze a length-balanced symmetric audio-condition X-VC stress matrix."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
for import_root in (TOOL_ROOT, HUMAN_TOOL_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import listen_now as base  # noqa: E402
import render_commonvoice as external  # noqa: E402
import render_new_utterances as render_new  # noqa: E402
import run as method  # noqa: E402

KIND = render_new.EXPANDED_STRESS_KIND
CONDITIONS = tuple(render_new.EXPANDED_STRESS_TRANSFORMS.items())
LENGTH_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("short10to14", 10, 14),
    ("medium15to21", 15, 21),
    ("long22to30", 22, 30),
    ("verylong40plus", 40, None),
)
SOURCES_PER_LENGTH_BIN = 4
EXPECTED_SOURCE_ROWS = len(LENGTH_BINS) * SOURCES_PER_LENGTH_BIN
EXPECTED_ROWS = EXPECTED_SOURCE_ROWS * len(CONDITIONS)


class ExpandedStressError(RuntimeError):
    """The expanded condition matrix cannot be materialized safely."""


def _spread(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) < SOURCES_PER_LENGTH_BIN:
        raise ExpandedStressError("length bin has too few frozen sources")
    last = len(rows) - 1
    indices = [
        (position * last) // (SOURCES_PER_LENGTH_BIN - 1)
        for position in range(SOURCES_PER_LENGTH_BIN)
    ]
    if len(set(indices)) != SOURCES_PER_LENGTH_BIN:
        raise ExpandedStressError("length-bin spread drifted")
    return [dict(rows[index]) for index in indices]


def selected_sources(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Select four metadata-spread speakers from each frozen text-length bin."""

    items = source.get("items")
    if source.get("kind") != render_new.FRESH48_KIND or not isinstance(items, list):
        raise ExpandedStressError("fresh48 source identity drifted")
    selected: list[dict[str, Any]] = []
    for label, lower, upper in LENGTH_BINS:
        candidates = sorted(
            (
                item
                for item in items
                if isinstance(item, dict)
                and isinstance(item.get("source_normalized_characters"), int)
                and int(item["source_normalized_characters"]) >= lower
                and (
                    upper is None or int(item["source_normalized_characters"]) <= upper
                )
            ),
            key=lambda item: (
                int(item["source_normalized_characters"]),
                str(item.get("id")),
            ),
        )
        for item in _spread(candidates):
            selected.append({**item, "length_bin": label})
    if (
        len(selected) != EXPECTED_SOURCE_ROWS
        or len({str(item["id"]) for item in selected}) != EXPECTED_SOURCE_ROWS
        or len({str(item["client_id_sha256"]) for item in selected})
        != EXPECTED_SOURCE_ROWS
    ):
        raise ExpandedStressError("expanded source selection drifted")
    return selected


def planned_rows(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in selected_sources(source):
        for condition_name, transform in CONDITIONS:
            rows.append(
                {
                    **item,
                    "base_id": item["id"],
                    "id": f"{item['id']}-{condition_name}",
                    "filename": (f"{len(rows):03d}-{item['id']}-{condition_name}.wav"),
                    "source_original_duration_seconds": item["duration_seconds"],
                    "duration_seconds": base.MODEL_SAMPLES / 16_000,
                    "group": (f"expanded-stress-{item['length_bin']}-{condition_name}"),
                    "stress_condition": dict(transform),
                    "window_policy": (
                        f"first-2.4s-{condition_name}-right-pad-if-short"
                    ),
                }
            )
    expected_groups = {
        f"expanded-stress-{length}-{condition}": SOURCES_PER_LENGTH_BIN
        for length, _, _ in LENGTH_BINS
        for condition, _ in CONDITIONS
    }
    if (
        len(rows) != EXPECTED_ROWS
        or Counter(row["group"] for row in rows) != expected_groups
    ):
        raise ExpandedStressError("expanded stress composition drifted")
    return rows


def validate_inputs(arguments: argparse.Namespace) -> dict[str, Any]:
    source = render_new.load_evaluation(arguments.source_evaluation)
    if source.get("kind") != render_new.FRESH48_KIND:
        raise ExpandedStressError("fresh48 source kind drifted")
    for item in source["items"]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise ExpandedStressError(f"fresh48 source drifted: {item['id']}")
    planned_rows(source)
    if arguments.output_root.exists() or arguments.output_root.is_symlink():
        raise ExpandedStressError("expanded stress output root already exists")
    if arguments.xvc_source_root.is_symlink() or not arguments.xvc_source_root.is_dir():
        raise ExpandedStressError("X-VC source root is unavailable")
    if arguments.xvc_config.is_symlink() or not arguments.xvc_config.is_file():
        raise ExpandedStressError("X-VC config is unavailable")
    return source


def run(arguments: argparse.Namespace, source: Mapping[str, Any]) -> int:
    planned = planned_rows(source)
    if arguments.check:
        print(
            json.dumps(
                {
                    "status": "checked-no-audio",
                    "source_rows": EXPECTED_SOURCE_ROWS,
                    "evaluation_rows": EXPECTED_ROWS,
                    "groups": dict(Counter(row["group"] for row in planned)),
                },
                sort_keys=True,
            )
        )
        return 0

    xvc_root = str(arguments.xvc_source_root.resolve())
    if xvc_root not in sys.path:
        sys.path.insert(0, xvc_root)
    from models.codec.sac.utils import process_audio
    from utils.file import load_config

    config = load_config(str(arguments.xvc_config))
    if "config" in config:
        config = config["config"]
    arguments.output_root.mkdir()
    normalized_sources: dict[str, Path] = {}
    for item in selected_sources(source):
        source_path = arguments.source_root / str(item["filename"])
        normalized_path = arguments.output_root / f".{item['id']}-source-window.wav"
        values = external.padded_model_audio(source_path, process_audio, config)
        method._write_model_window(normalized_path, values)
        normalized_sources[str(item["id"])] = normalized_path
    materialized: list[dict[str, Any]] = []
    for index, row in enumerate(planned):
        destination = arguments.output_root / str(row["filename"])
        method.transform_window(
            normalized_sources[str(row["base_id"])],
            row["stress_condition"],
            destination=destination,
            process_audio=process_audio,
            config=config,
            seed=base.SEED + index,
        )
        materialized.append({**row, "sha256": base.sha256_file(destination)})
    for path in normalized_sources.values():
        path.unlink()
    manifest = {
        "kind": KIND,
        "source": {
            **source["source"],
            "derived_from_evaluation_sha256": base.sha256_file(
                arguments.source_evaluation
            ),
            "selection": (
                "four metadata-spread disjoint speakers in each of four frozen "
                "normalized-text-length bins"
            ),
            "transform_implementation": "liveconv deterministic 16 kHz window",
        },
        "items": materialized,
    }
    manifest_path = arguments.output_root / "evaluation.json"
    method._write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "status": "materialized",
                "evaluation_rows": len(materialized),
                "evaluation_set": str(manifest_path),
                "evaluation_set_sha256": base.sha256_file(manifest_path),
            },
            sort_keys=True,
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument(
        "--source-evaluation",
        type=Path,
        default=(
            REPO_ROOT
            / "artifacts/xvc-source-diversity/exp112-fresh48-inputs-v1/evaluation.json"
        ),
    )
    value.add_argument(
        "--source-root",
        type=Path,
        default=REPO_ROOT / "artifacts/xvc-method-reset/commonvoice25-ja-fresh48",
    )
    value.add_argument(
        "--xvc-source-root",
        type=Path,
        default=REPO_ROOT / "artifacts/x-vc/source",
    )
    value.add_argument(
        "--xvc-config",
        type=Path,
        default=REPO_ROOT / "artifacts/x-vc/xvc-local.yaml",
    )
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        return run(arguments, validate_inputs(arguments))
    except (
        OSError,
        ValueError,
        method.SourceDiversityError,
        base.ListenNowError,
        external.ExternalEvaluationError,
        ExpandedStressError,
    ) as error:
        print(f"expanded-stress-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
