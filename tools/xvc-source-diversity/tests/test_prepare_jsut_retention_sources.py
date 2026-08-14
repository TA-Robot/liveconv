from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_jsut_retention_sources as jsut  # noqa: E402


def test_selection_excludes_frozen_ids_before_equal_bin_centers() -> None:
    transcript = [(f"BASIC5000_{index:04d}", f"text {index}") for index in range(100)]
    excluded = {"BASIC5000_0010", "BASIC5000_0050", "BASIC5000_0090"}

    selected = jsut.select_training_rows(transcript, excluded, 10)

    assert len(selected) == 10
    assert not ({identifier for _, identifier, _ in selected} & excluded)
    assert [row[0] for row in selected] == sorted(row[0] for row in selected)


def test_easy_slots_bind_exactly_85_curriculum_positions() -> None:
    items = []
    for position in range(170):
        role = "hard" if position % 2 == 0 else "easy"
        items.append(
            {
                "curriculum_role": role,
                "source_manifest_id": f"source-{position}",
                "target_id": f"target-{position % 74}",
            }
        )
    selective = {"kind": jsut.SELECTIVE_KIND, "items": items}

    slots = jsut.easy_slots(selective)

    assert len(slots) == 85
    assert [slot["curriculum_position"] for slot in slots[:3]] == [1, 3, 5]
    assert slots[-1]["curriculum_position"] == 169
