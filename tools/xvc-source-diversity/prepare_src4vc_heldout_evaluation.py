#!/usr/bin/env python3
"""Materialize the frozen disjoint SRC4VC30 listen-now evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fetch_src4vc_subset import OUTPUT_KIND as SUBSET_KIND
from prepare_clean_post_rehearsal import load_json, sha256_file

OUTPUT_KIND = "liveconv-exp250-src4vc-heldout30/v1"
SOURCE_LICENSE = "SRC4VC research-use; redistribution prohibited"
EXPECTED_ROWS = 30
EXPECTED_SPEAKERS = 15


class Src4vcHeldoutError(RuntimeError):
    """The disjoint heldout surface cannot be materialized safely."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def selected_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = manifest.get("items")
    if manifest.get("kind") != SUBSET_KIND or not isinstance(items, list):
        raise Src4vcHeldoutError("SRC4VC subset identity drifted")
    if len(items) != 115 or not all(isinstance(item, dict) for item in items):
        raise Src4vcHeldoutError("SRC4VC subset row count drifted")
    train = [dict(item) for item in items if item.get("split") == "train"]
    evaluation = [
        dict(item) for item in items if item.get("split") == "evaluation"
    ]
    train_speakers = {str(item.get("speaker_id")) for item in train}
    evaluation_counts = Counter(str(item.get("speaker_id")) for item in evaluation)
    if (
        len(train) != 85
        or len(train_speakers) != 85
        or len(evaluation) != EXPECTED_ROWS
        or len(evaluation_counts) != EXPECTED_SPEAKERS
        or set(evaluation_counts.values()) != {2}
        or train_speakers & set(evaluation_counts)
    ):
        raise Src4vcHeldoutError("SRC4VC heldout speaker boundary drifted")
    return sorted(evaluation, key=lambda item: str(item["id"]))


def materialize(
    *, manifest: Mapping[str, Any], subset_root: Path, output_root: Path
) -> dict[str, Any]:
    items = selected_rows(manifest)
    output_root.mkdir(parents=True)
    output_items: list[dict[str, Any]] = []
    for item in items:
        source = subset_root / str(item["filename"])
        if source.is_symlink() or not source.is_file():
            raise Src4vcHeldoutError(f"SRC4VC heldout WAV unavailable: {item['id']}")
        if sha256_file(source) != item.get("sha256"):
            raise Src4vcHeldoutError(f"SRC4VC heldout WAV drifted: {item['id']}")
        filename = f"{item['id']}.wav"
        shutil.copyfile(source, output_root / filename)
        speaker = str(item["speaker_id"])
        output_items.append(
            {
                "id": str(item["id"]),
                "group": "src4vc-disjoint-heldout",
                "filename": filename,
                "sha256": str(item["sha256"]),
                "client_id_sha256": sha256_text(speaker),
                "src4vc_speaker_id": speaker,
                "text": str(item["text"]),
                "source_transcript": str(item["text"]),
                "duration_seconds": float(item["duration_seconds"]),
                "sample_rate": int(item["sample_rate"]),
                "window_policy": "first-2.4s-right-pad-if-short",
                "selection_policy": (
                    "first two RECITATION rows from each of fifteen frozen "
                    "speakers disjoint from SRC4VC85 training"
                ),
            }
        )
    return {
        "schema_version": 1,
        "kind": OUTPUT_KIND,
        "source": {
            "corpus": "SRC4VC version 1",
            "license": SOURCE_LICENSE,
            "boundary": (
                "private research artifact; raw audio and manifest are not "
                "committed or redistributed"
            ),
        },
        "items": output_items,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--subset-manifest", type=Path, required=True)
    value.add_argument("--subset-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.output_root.exists() or arguments.output_root.is_symlink():
            raise Src4vcHeldoutError("output root already exists")
        result = materialize(
            manifest=load_json(arguments.subset_manifest),
            subset_root=arguments.subset_root,
            output_root=arguments.output_root,
        )
        result["source"]["subset_manifest_sha256"] = sha256_file(
            arguments.subset_manifest
        )
        output = arguments.output_root / "evaluation.json"
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "materialized-private-heldout",
                    "rows": len(result["items"]),
                    "speakers": len(
                        {item["src4vc_speaker_id"] for item in result["items"]}
                    ),
                    "output": str(output),
                    "sha256": sha256_file(output),
                },
                sort_keys=True,
            )
        )
        return 0
    except (KeyError, OSError, Src4vcHeldoutError, ValueError) as error:
        print(f"src4vc-heldout-error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
