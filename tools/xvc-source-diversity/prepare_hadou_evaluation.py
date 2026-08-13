#!/usr/bin/env python3
"""Materialize the frozen clean Hadou heldout evaluation windows."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
HUMAN_TOOL_ROOT = REPO_ROOT / "tools" / "xvc-human-paired"
if str(HUMAN_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(HUMAN_TOOL_ROOT))

import listen_now as base  # noqa: E402

SELECTION_KIND = "liveconv-exp060-hadou-clean-heldout/v1"
SOURCE_MANIFEST_SHA256 = (
    "12e334fb3649fa57a90713a8fe3d036a59bbc7d5aa8971f4cdc4f785941b772b"
)
AUDIT_SHA256 = "73d749f6e087b83c1f30c0650f5c67225715f3848ddd9e38c8e446873fe524ee"
ID_LIST_SHA256 = "4c02ea64a71da74cd5a92eb868017945172c5310695f51ac3b7612364379a35f"
ROW_COUNT = 31
HADOU_CLIENT_SHA256 = hashlib.sha256(b"Hadou Voice Dataset speaker").hexdigest()


class HadouPreparationError(RuntimeError):
    """The frozen Hadou evaluation cannot be materialized safely."""


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HadouPreparationError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise HadouPreparationError(f"{label} schema drifted")
    return value


def select_rows(
    selection: Mapping[str, Any],
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    ids = selection.get("ids")
    rows = manifest.get("rows")
    audit_rows = audit.get("rows")
    if (
        selection.get("kind") != SELECTION_KIND
        or not isinstance(ids, list)
        or len(ids) != ROW_COUNT
        or not isinstance(rows, list)
        or not isinstance(audit_rows, list)
    ):
        raise HadouPreparationError("Hadou selection schema drifted")
    observed_id_digest = hashlib.sha256(
        ("\n".join(ids) + "\n").encode("ascii")
    ).hexdigest()
    if observed_id_digest != ID_LIST_SHA256:
        raise HadouPreparationError("Hadou selection ID digest drifted")
    manifest_by_id = {
        str(row.get("utterance_id")): row for row in rows if isinstance(row, dict)
    }
    audit_by_id = {
        str(row.get("utterance_id")): row
        for row in audit_rows
        if isinstance(row, dict)
    }
    eligible = sorted(
        identifier
        for identifier, row in manifest_by_id.items()
        if row.get("split") == "heldout"
        and identifier in audit_by_id
        and float(
            audit_by_id[identifier]["comparison"]["best"][
                "character_error_rate"
            ]
        )
        <= 0.15
    )
    if list(ids) != eligible:
        raise HadouPreparationError("Hadou frozen selection no longer derives")
    return [(manifest_by_id[identifier], audit_by_id[identifier]) for identifier in ids]


def validate(
    arguments: argparse.Namespace,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if base.sha256_file(arguments.source_manifest) != SOURCE_MANIFEST_SHA256:
        raise HadouPreparationError("Hadou source manifest identity drifted")
    if base.sha256_file(arguments.pronunciation_audit) != AUDIT_SHA256:
        raise HadouPreparationError("Hadou pronunciation audit identity drifted")
    selection = load_json(arguments.selection, "Hadou selection")
    manifest = load_json(arguments.source_manifest, "Hadou source manifest")
    audit = load_json(arguments.pronunciation_audit, "Hadou pronunciation audit")
    selected = select_rows(selection, manifest, audit)
    if arguments.source_root.is_symlink() or not arguments.source_root.is_dir():
        raise HadouPreparationError("Hadou source root is unavailable")
    if arguments.output_root.exists() or arguments.output_root.is_symlink():
        raise HadouPreparationError("Hadou evaluation output already exists")
    for row, _ in selected:
        source = arguments.source_root / str(row["source_wav"]["relative_path"])
        if (
            source.is_symlink()
            or not source.is_file()
            or base.sha256_file(source) != row["source_wav"]["sha256"]
        ):
            raise HadouPreparationError("Hadou source WAV identity drifted")
    return selected


def execute(
    arguments: argparse.Namespace,
    selected: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> int:
    arguments.output_root.mkdir()
    items: list[dict[str, object]] = []
    for row, audit in selected:
        identifier = str(row["utterance_id"])
        source = arguments.source_root / str(row["source_wav"]["relative_path"])
        pcm = base._parse_pcm16_wav(source.read_bytes(), f"Hadou {identifier}")
        start, stop = base.endpoint_complete_speech(pcm, base.SAMPLE_RATE_48K)
        active = pcm[start : min(stop, start + base.WINDOW_48K)]
        window = base._right_pad(active, base.WINDOW_48K)
        filename = f"{identifier}.wav"
        output = arguments.output_root / filename
        base._write_pcm16(output, window)
        items.append(
            {
                "id": identifier,
                "filename": filename,
                "sha256": base.sha256_file(output),
                "client_id_sha256": HADOU_CLIENT_SHA256,
                "text": row["display_text"],
                "duration_seconds": 2.4,
                "group": "hadou-clean-heldout",
                "window_policy": (
                    "first-endpoint-complete-2.4s-right-pad-if-short"
                ),
                "full_utterance_audit_cer": audit["comparison"]["best"][
                    "character_error_rate"
                ],
            }
        )
    evaluation = {
        "schema_version": 1,
        "kind": SELECTION_KIND,
        "source": {"name": "Hadou Voice Dataset / ITA", "license": "CC-BY-4.0"},
        "items": items,
    }
    output = arguments.output_root / "evaluation.json"
    output.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": "materialized", "rows": len(items), "output": str(output)}
        )
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--check", action="store_true")
    value.add_argument("--selection", type=Path, required=True)
    value.add_argument("--source-manifest", type=Path, required=True)
    value.add_argument("--pronunciation-audit", type=Path, required=True)
    value.add_argument("--source-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        selected = validate(arguments)
        if arguments.check:
            print(json.dumps({"status": "ready", "rows": len(selected)}))
            return 0
        return execute(arguments, selected)
    except HadouPreparationError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
