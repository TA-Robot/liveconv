from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_selective_retention_curriculum as selective  # noqa: E402


def inputs() -> tuple[dict[str, object], dict[str, object]]:
    items = []
    probe_rows = []
    for index in range(selective.EXPECTED_ROWS):
        role = "hard" if index % 2 == 0 else "easy"
        domain = "commonvoice" if index < 56 else "hadou" if index < 167 else "jvs"
        hard_index = (index // 2) % 11
        teacher_id = (
            f"teacher-{hard_index:03d}" if role == "hard" else f"easy-{index:03d}"
        )
        target_id = (
            f"target-{hard_index % 7:03d}"
            if role == "hard"
            else f"target-{index % 7:03d}"
        )
        items.append(
            {
                "id": f"row-{index:03d}",
                "teacher_id": teacher_id,
                "target_id": target_id,
                "domain": domain,
                "curriculum_role": role,
                "source_file": f"source-{teacher_id}.wav",
                "source_sha256": "a" * 64,
                "target_file": f"base-{teacher_id}.wav",
                "target_sha256": "b" * 64,
            }
        )
    identities = {(item["teacher_id"], item["target_id"]) for item in items}
    for teacher_id, target_id in identities:
        probe_rows.append(
            {
                "teacher_id": teacher_id,
                "target_id": target_id,
                "output_sha256": "c" * 64,
            }
        )
    while len(probe_rows) < selective.EXPECTED_ROWS:
        index = len(probe_rows)
        probe_rows.append(
            {
                "teacher_id": f"unused-{index:03d}",
                "target_id": "unused-target",
                "output_sha256": "d" * 64,
            }
        )
    return (
        {
            "kind": selective.HARD_INPUT_KIND,
            "composition": selective.EXPECTED_COMPOSITION,
            "curriculum": {},
            "items": items,
        },
        {"kind": selective.CONTROL_PROBE_KIND, "rows": probe_rows},
    )


def test_selective_curriculum_changes_only_easy_learning_targets() -> None:
    hard, probe = inputs()
    manifest = selective.build_curriculum(hard, probe)

    assert manifest["learning_target_counts"] == {
        selective.REPAIR_TARGET: 85,
        selective.RETENTION_TARGET: 85,
    }
    assert manifest["items"][0]["target_root"] == "source-work"
    assert manifest["items"][0]["target_file"].startswith("base-")
    assert manifest["items"][1]["target_root"] == "control-work"
    assert manifest["items"][1]["base_teacher_target_file"].startswith("base-")


def test_selective_curriculum_rejects_probe_target_mismatch() -> None:
    hard, probe = inputs()
    probe["rows"][0]["target_id"] = "wrong-target"

    with pytest.raises(selective.SelectiveRetentionError, match="identity drifted"):
        selective.build_curriculum(hard, probe)
