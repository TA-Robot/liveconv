from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_hard_negative_curriculum as curriculum  # noqa: E402


def inputs() -> tuple[dict[str, object], dict[str, object]]:
    items = []
    rows = []
    for index in range(curriculum.EXPECTED_ROWS):
        domain = "commonvoice" if index < 35 else "hadou" if index < 167 else "jvs"
        teacher_id = f"teacher-{index:03d}"
        items.append(
            {
                "id": f"target-{index:03d}--{teacher_id}",
                "teacher_id": teacher_id,
                "target_id": f"target-{index:03d}",
                "domain": domain,
            }
        )
        hard = index in {0, 1, 2, 3, 4, 35, 36, 37, 38, 39, 40}
        rows.append(
            {
                "teacher_id": teacher_id,
                "source_relative_distance": (
                    20.0 if index == 35 else 0.5 if hard else 0.1
                ),
                "repetition": {"gross_repetition": index == 35},
            }
        )
    return (
        {"kind": curriculum.CLEAN_KIND, "source": {}, "items": items},
        {"kind": curriculum.SCREEN_KIND, "rows": rows},
    )


def test_curriculum_alternates_hard_and_stratified_easy_rows() -> None:
    clean, screen = inputs()
    manifest = curriculum.build_curriculum(clean, screen)

    assert len(manifest["items"]) == 170
    assert manifest["composition"] == curriculum.EXPECTED_COMPOSITION
    assert manifest["curriculum"]["unique_hard_rows"] == 11
    assert [item["curriculum_role"] for item in manifest["items"][:4]] == [
        "hard",
        "easy",
        "hard",
        "easy",
    ]
    hard_ids = {
        item["source_manifest_id"]
        for item in manifest["items"]
        if item["curriculum_role"] == "hard"
    }
    assert len(hard_ids) == 11


def test_curriculum_rejects_changed_hard_frontier() -> None:
    clean, screen = inputs()
    screen["rows"][0]["source_relative_distance"] = 0.1

    with pytest.raises(curriculum.HardCurriculumError, match="frontier drifted"):
        curriculum.build_curriculum(clean, screen)
