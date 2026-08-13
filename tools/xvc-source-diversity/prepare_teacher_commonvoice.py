#!/usr/bin/env python3
"""Materialize EXP-114's training-only, fresh48-disjoint teacher pool."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import prepare_fresh_commonvoice as common

KIND = "liveconv-exp114-commonvoice-teacher48/v1"
GROUP = "commonvoice-teacher-train-disjoint"
ROW_COUNT = 48
FRESH_KIND = common.KIND


def excluded_clients(path: Path) -> set[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    items = value.get("items") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("kind") != FRESH_KIND
        or not isinstance(items, list)
        or len(items) != common.ROW_COUNT
    ):
        raise common.FreshEvaluationError("fresh48 exclusion manifest drifted")
    clients = {
        item.get("client_id_sha256")
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("client_id_sha256"), str)
        and len(item["client_id_sha256"]) == 64
    }
    if len(clients) != common.ROW_COUNT:
        raise common.FreshEvaluationError("fresh48 client identities drifted")
    return clients


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--metadata", type=Path, required=True)
    value.add_argument("--existing-root", type=Path, required=True)
    value.add_argument("--fresh-evaluation", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--output-manifest", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    rows = common.load_metadata(arguments.metadata)
    existing = {
        path.name for path in arguments.existing_root.glob("*.mp3") if path.is_file()
    }
    excluded = excluded_clients(arguments.fresh_evaluation)
    selected = common.select_rows(
        rows,
        existing_filenames=existing,
        excluded_client_hashes=excluded,
        count=ROW_COUNT,
    )
    if arguments.check:
        print(
            json.dumps(
                {
                    "status": "checked-no-download",
                    "selected_rows": len(selected),
                    "selected_speakers": len(
                        {str(row["client_id"]) for row in selected}
                    ),
                    "excluded_fresh_speakers": len(excluded),
                },
                sort_keys=True,
            )
        )
        return 0
    arguments.output_root.mkdir(parents=True, exist_ok=False)
    arguments.output_manifest.parent.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = common.build_manifest(
        selected,
        arguments.output_root,
        kind=KIND,
        group=GROUP,
        selection=(
            "first 48 metadata-order rows with unique clients, excluding all "
            "64 original local clips and the frozen EXP-112 fresh48 speakers; "
            "up_votes>=2, down_votes=0, 10--80 normalized characters"
        ),
    )
    arguments.output_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "materialized",
                "rows": len(manifest["items"]),
                "manifest": str(arguments.output_manifest),
                "manifest_sha256": common.sha256_file(arguments.output_manifest),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
