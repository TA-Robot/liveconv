#!/usr/bin/env python3
"""Audit EXP-035 pseudo sources before quality-filtered X-VC retraining.

ASR is used only to reject empty, repeated, or content-drifting training input.
It is not a naturalness, speaker-similarity, or voice-quality evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import screen  # noqa: E402

PAIR_COUNT = 87
DONOR_COUNT = 12
KEEP_PER_TARGET = 6
TOTAL_UPDATES = 1044
EXPECTED_GENERATED_INVENTORY_SHA256 = (
    "e909e465ae5b49fb2be67dded797acf13895acd7f2ddd77c570cea8acdba9cd0"
)


class TrainingPairAuditError(RuntimeError):
    """The fixed pseudo-source audit cannot safely continue."""


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_donor_ids(path: Path, *, expected_count: int = DONOR_COUNT) -> list[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrainingPairAuditError("donor manifest is not valid JSON") from error
    items = value.get("items") if isinstance(value, dict) else None
    if not isinstance(items, list) or len(items) != expected_count:
        raise TrainingPairAuditError("donor manifest count drifted")
    donor_ids = [item.get("id") if isinstance(item, dict) else None for item in items]
    if any(not isinstance(item, str) or not item for item in donor_ids):
        raise TrainingPairAuditError("donor ID is malformed")
    if len(set(donor_ids)) != expected_count:
        raise TrainingPairAuditError("donor IDs are not unique")
    return list(donor_ids)


def source_inventory(
    pair_root: Path,
    pseudo_root: Path,
    donor_ids: Sequence[str],
    *,
    expected_pairs: int = PAIR_COUNT,
) -> tuple[list[dict[str, object]], dict[str, Path]]:
    if pair_root.is_symlink() or not pair_root.is_dir():
        raise TrainingPairAuditError("target pair root is unavailable")
    if pseudo_root.is_symlink() or not pseudo_root.is_dir():
        raise TrainingPairAuditError("pseudo-source root is unavailable")
    pair_dirs = sorted(
        (
            path
            for path in pair_root.iterdir()
            if path.is_dir() and not path.is_symlink()
        ),
        key=lambda path: path.name,
    )
    if len(pair_dirs) != expected_pairs:
        raise TrainingPairAuditError("target pair count drifted")
    if {path.name for path in pair_dirs} != {
        path.name
        for path in pseudo_root.iterdir()
        if path.is_dir() and not path.is_symlink()
    }:
        raise TrainingPairAuditError("pseudo-source target inventory drifted")
    rows: list[dict[str, object]] = []
    targets: dict[str, Path] = {}
    for pair_dir in pair_dirs:
        target = pair_dir / "target-48k.wav"
        pseudo_dir = pseudo_root / pair_dir.name
        if target.is_symlink() or not target.is_file():
            raise TrainingPairAuditError(f"target WAV is missing: {pair_dir.name}")
        if pseudo_dir.is_symlink() or not pseudo_dir.is_dir():
            raise TrainingPairAuditError(
                f"pseudo-source directory is missing: {pair_dir.name}"
            )
        targets[pair_dir.name] = target
        expected_names = {f"source-{donor_id}-16k.wav" for donor_id in donor_ids}
        observed_names = {
            path.name
            for path in pseudo_dir.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        if observed_names != expected_names:
            raise TrainingPairAuditError(
                f"pseudo-source donor inventory drifted: {pair_dir.name}"
            )
        for donor_id in donor_ids:
            source = pseudo_dir / f"source-{donor_id}-16k.wav"
            rows.append(
                {
                    "pair_id": pair_dir.name,
                    "donor_id": donor_id,
                    "source_sha256": screen.sha256_file(source),
                    "source_path": source,
                }
            )
    return rows, targets


def rank_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    keep_per_target: int = KEEP_PER_TARGET,
    expected_targets: int = PAIR_COUNT,
) -> tuple[list[dict[str, object]], list[tuple[str, str]]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["pair_id"])].append(row)
    if len(grouped) != expected_targets:
        raise TrainingPairAuditError("scored target count drifted")
    ranked: list[dict[str, object]] = []
    selected_pairs: list[tuple[str, str]] = []
    for pair_id in sorted(grouped):
        items = grouped[pair_id]
        eligible = [
            row
            for row in items
            if bool(row.get("output_normalized_characters"))
            and not bool(row["repetition"]["gross_repetition"])
        ]
        if len(eligible) < keep_per_target:
            raise TrainingPairAuditError(
                f"fewer than {keep_per_target} eligible pseudo sources: {pair_id}"
            )
        ordered = sorted(
            eligible,
            key=lambda row: (
                float(row["target_relative_distance"]),
                abs(
                    int(row["output_normalized_characters"])
                    - int(row["target_normalized_characters"])
                ),
                str(row["donor_id"]),
            ),
        )
        selected = {
            (pair_id, str(row["donor_id"])): rank
            for rank, row in enumerate(ordered[:keep_per_target], start=1)
        }
        for row in items:
            value = dict(row)
            key = (pair_id, str(row["donor_id"]))
            value["selected"] = key in selected
            value["selection_rank"] = selected.get(key)
            ranked.append(value)
        selected_pairs.extend(
            (pair_id, str(row["donor_id"])) for row in ordered[:keep_per_target]
        )
    schedule = selected_pairs * 2
    if len(schedule) != TOTAL_UPDATES:
        raise TrainingPairAuditError("quality-filtered update schedule drifted")
    return ranked, schedule


def aggregate_rows(
    rows: Sequence[Mapping[str, object]], schedule: Sequence[tuple[str, str]]
) -> dict[str, object]:
    selected = [row for row in rows if row["selected"]]
    all_distances = [float(row["target_relative_distance"]) for row in rows]
    selected_distances = [
        float(row["target_relative_distance"]) for row in selected
    ]
    donor_counts = Counter(donor_id for _, donor_id in schedule)
    return {
        "scored_pairs": len(rows),
        "selected_unique_pairs": len(selected),
        "optimizer_updates": len(schedule),
        "empty_rows": sum(
            int(row["output_normalized_characters"]) == 0 for row in rows
        ),
        "gross_repetition_rows": sum(
            bool(row["repetition"]["gross_repetition"]) for row in rows
        ),
        "all_mean_distance": sum(all_distances) / len(all_distances),
        "all_median_distance": statistics.median(all_distances),
        "selected_mean_distance": sum(selected_distances) / len(selected_distances),
        "selected_median_distance": statistics.median(selected_distances),
        "selected_maximum_distance": max(selected_distances),
        "selected_donor_update_counts": dict(sorted(donor_counts.items())),
    }


def validate_inputs(
    arguments: argparse.Namespace,
) -> tuple[list[dict[str, object]], dict[str, Path]]:
    donor_ids = load_donor_ids(arguments.donors)
    inventory, targets = source_inventory(
        arguments.pair_root, arguments.pseudo_root, donor_ids
    )
    identity_rows = [
        {
            "target_id": row["pair_id"],
            "donor_id": row["donor_id"],
            "source_sha256": row["source_sha256"],
        }
        for row in inventory
    ]
    if canonical_sha256(identity_rows) != EXPECTED_GENERATED_INVENTORY_SHA256:
        raise TrainingPairAuditError("EXP-035 generated inventory identity drifted")
    if arguments.model_root.is_symlink() or not arguments.model_root.is_dir():
        raise TrainingPairAuditError("STT model root is unavailable")
    if arguments.output.exists() or arguments.output.is_symlink():
        raise TrainingPairAuditError("audit output already exists")
    return inventory, targets


def execute(
    arguments: argparse.Namespace,
    inventory: list[dict[str, object]],
    targets: Mapping[str, Path],
) -> int:
    if arguments.confirm_gpu_lease != "gpu0" or arguments.device != "cuda":
        raise TrainingPairAuditError("execution requires the explicit gpu0 lease")
    started = time.monotonic()
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
    by_pair: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in inventory:
        by_pair[str(row["pair_id"])].append(row)
    scored: list[dict[str, object]] = []
    for pair_index, pair_id in enumerate(sorted(by_pair), start=1):
        target = targets[pair_id]
        target_transcript = screen._transcribe(model, target)
        target_characters = len(screen.normalize_japanese(target_transcript))
        if target_characters == 0:
            raise TrainingPairAuditError(f"target ASR is empty: {pair_id}")
        for identity in by_pair[pair_id]:
            source_path = identity["source_path"]
            transcript = screen._transcribe(model, source_path)
            output_characters = len(screen.normalize_japanese(transcript))
            scored.append(
                {
                    "pair_id": pair_id,
                    "donor_id": identity["donor_id"],
                    "target_sha256": screen.sha256_file(target),
                    "source_sha256": identity["source_sha256"],
                    "target_transcript": target_transcript,
                    "output_transcript": transcript,
                    "target_normalized_characters": target_characters,
                    "output_normalized_characters": output_characters,
                    "target_relative_distance": screen.normalized_distance(
                        target_transcript, transcript
                    ),
                    "repetition": screen.repetition_metrics(transcript),
                }
            )
        if pair_index % 10 == 0 or pair_index == len(by_pair):
            print(
                json.dumps(
                    {"audited_targets": pair_index, "total_targets": len(by_pair)}
                ),
                flush=True,
            )
    ranked, schedule = rank_rows(scored)
    aggregate = aggregate_rows(ranked, schedule)
    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": "liveconv-xvc-pseudo-source-content-audit/v1",
        "status": "completed-training-input-audit",
        "boundary": (
            "ASR rejects training-content corruption only; it does not measure "
            "naturalness, speaker identity, or voice quality."
        ),
        "source": {
            "experiment_id": "EXP-035",
            "generated_inventory_sha256": EXPECTED_GENERATED_INVENTORY_SHA256,
        },
        "selection": {
            "policy": "best six nonempty non-gross rows per target, two passes",
            "keep_per_target": KEEP_PER_TARGET,
            "passes": 2,
            "schedule": [
                {"pair_id": pair_id, "donor_id": donor_id}
                for pair_id, donor_id in schedule
            ],
        },
        "aggregate": aggregate,
        "rows": ranked,
        "model": {
            "tree_sha256": sha256_model_tree(arguments.model_root),
            "device": arguments.device,
            "compute_type": arguments.compute_type,
        },
        "elapsed_seconds": time.monotonic() - started,
    }
    result["audit_sha256"] = canonical_sha256(result)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    partial = arguments.output.with_suffix(arguments.output.suffix + ".partial")
    if partial.exists() or partial.is_symlink():
        raise TrainingPairAuditError("partial audit output already exists")
    partial.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(partial, arguments.output)
    print(json.dumps({"status": result["status"], **aggregate}), flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--donors", type=Path, required=True)
    parser.add_argument("--pair-root", type=Path, required=True)
    parser.add_argument("--pseudo-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-gpu-lease")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        inventory, targets = validate_inputs(arguments)
        if arguments.check:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "targets": len(targets),
                        "pseudo_sources": len(inventory),
                        "generated_inventory_sha256": canonical_sha256(
                            [
                                {
                                    "target_id": row["pair_id"],
                                    "donor_id": row["donor_id"],
                                    "source_sha256": row["source_sha256"],
                                }
                                for row in inventory
                            ]
                        ),
                    }
                )
            )
            return 0
        return execute(arguments, inventory, targets)
    except TrainingPairAuditError as error:
        print(str(error), file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
