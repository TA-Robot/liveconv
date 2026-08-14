from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_jsut_retention_targets as render  # noqa: E402


def manifest() -> dict[str, object]:
    items = []
    index = 0
    for category, count in render.CATEGORY_COUNTS.items():
        for category_index in range(count):
            items.append(
                {
                    "filename": f"{category.upper()}_{category_index:04d}.wav",
                    "sha256": "a" * 64,
                    "target_id": f"target-{index % 74}",
                    "jsut_category": category,
                    "source_transcript": f"評価文{index}",
                    "curriculum_position": index * 2 + 1,
                }
            )
            index += 1
    return {"kind": render.SOURCE_KIND, "items": items}


def test_source_pool_binds_all_precommitted_rows() -> None:
    pool = render.source_pool(manifest())

    assert pool["kind"] == render.POOL_KIND
    assert len(pool["items"]) == 85
    assert len({row["id"] for row in pool["items"]}) == 85
    assert {row["domain"] for row in pool["items"]} == {"jsut"}


def test_source_pool_rejects_duplicate_teacher_identity() -> None:
    value = manifest()
    value["items"][1]["filename"] = value["items"][0]["filename"]

    with pytest.raises(render.JsutTargetError, match="duplicated"):
        render.source_pool(value)
