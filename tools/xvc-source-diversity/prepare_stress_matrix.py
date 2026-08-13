#!/usr/bin/env python3
"""Freeze a multi-speaker Common Voice audio-condition stress matrix."""

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

KIND = "liveconv-exp086-commonvoice-condition-matrix/v1"
CONDITIONS: tuple[tuple[str, dict[str, object]], ...] = (
    ("clean", {"kind": "clean"}),
    ("noise20", {"kind": "noise", "snr_db": 20.0}),
    ("silence300", {"kind": "leading-silence", "milliseconds": 300}),
    ("tempo120", {"kind": "tempo", "factor": 1.2}),
    ("pitchp3", {"kind": "pitch", "factor": 1.189207115}),
)
EXPECTED_SOURCE_ROWS = 12
EXPECTED_ROWS = EXPECTED_SOURCE_ROWS * len(CONDITIONS)


class StressMatrixError(RuntimeError):
    """The fixed multi-speaker stress matrix cannot be materialized safely."""


def planned_rows(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = source.get("items")
    if not isinstance(items, list) or len(items) != EXPECTED_SOURCE_ROWS:
        raise StressMatrixError("source evaluation row count drifted")
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise StressMatrixError("source evaluation row is malformed")
        for condition_name, transform in CONDITIONS:
            rows.append(
                {
                    **item,
                    "base_id": item["id"],
                    "id": f"{item['id']}-{condition_name}",
                    "filename": f"{len(rows):02d}-{item['id']}-{condition_name}.wav",
                    "duration_seconds": base.MODEL_SAMPLES / 16_000,
                    "group": f"stress-{condition_name}",
                    "stress_condition": dict(transform),
                    "window_policy": (
                        f"first-2.4s-{condition_name}-right-pad-if-short"
                    ),
                }
            )
    if len(rows) != EXPECTED_ROWS:
        raise StressMatrixError("stress matrix size drifted")
    if Counter(row["group"] for row in rows) != {
        f"stress-{name}": EXPECTED_SOURCE_ROWS for name, _ in CONDITIONS
    }:
        raise StressMatrixError("stress matrix balance drifted")
    return rows


def validate_inputs(arguments: argparse.Namespace) -> dict[str, Any]:
    source = render_new.load_evaluation(arguments.source_evaluation)
    if source.get("kind") != render_new.KIND:
        raise StressMatrixError("source evaluation kind drifted")
    for item in source["items"]:
        path = arguments.source_root / item["filename"]
        if (
            path.is_symlink()
            or not path.is_file()
            or base.sha256_file(path) != item["sha256"]
        ):
            raise StressMatrixError(f"source audio drifted: {item['id']}")
    planned_rows(source)
    if arguments.output_root.exists() or arguments.output_root.is_symlink():
        raise StressMatrixError("stress output root already exists")
    if arguments.xvc_source_root.is_symlink() or not arguments.xvc_source_root.is_dir():
        raise StressMatrixError("X-VC source root is unavailable")
    if arguments.xvc_config.is_symlink() or not arguments.xvc_config.is_file():
        raise StressMatrixError("X-VC config is unavailable")
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
    for item in source["items"]:
        source_path = arguments.source_root / item["filename"]
        normalized_path = arguments.output_root / f".{item['id']}-source-window.wav"
        values = external.padded_model_audio(source_path, process_audio, config)
        method._write_model_window(normalized_path, values)
        normalized_sources[str(item["id"])] = normalized_path
    materialized: list[dict[str, Any]] = []
    for index, row in enumerate(planned):
        source_path = normalized_sources[str(row["base_id"])]
        destination = arguments.output_root / row["filename"]
        method.transform_window(
            source_path,
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--source-evaluation",
        type=Path,
        default=(
            REPO_ROOT
            / "experiments"
            / "EXP-039-xvc-new-utterances"
            / "inputs.json"
        ),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=REPO_ROOT / "artifacts" / "xvc-method-reset" / "commonvoice25-ja",
    )
    parser.add_argument(
        "--xvc-source-root",
        type=Path,
        default=REPO_ROOT / "artifacts" / "x-vc" / "source",
    )
    parser.add_argument(
        "--xvc-config",
        type=Path,
        default=REPO_ROOT / "artifacts" / "x-vc" / "xvc-local.yaml",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return run(arguments, validate_inputs(arguments))
    except (
        OSError,
        ValueError,
        method.SourceDiversityError,
        base.ListenNowError,
        external.ExternalEvaluationError,
        StressMatrixError,
    ) as error:
        print(f"exp086-stress-matrix-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
