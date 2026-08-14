from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_commonvoice_retention_targets as render  # noqa: E402


def manifest() -> dict[str, object]:
    items = []
    for index in range(85):
        source_index = index if index < 48 else index - 48
        exposure = 1 if index < 48 else 2
        source_id = f"cv{source_index:08d}f"
        items.append(
            {
                "id": f"{source_id}-e{exposure}",
                "filename": f"{source_id}.wav",
                "source_id": source_id,
                "source_sha256": "a" * 64,
                "target_id": f"target-{index % 74}",
                "source_transcript": f"評価文{index}",
                "curriculum_position": index * 2 + 1,
                "exposure": exposure,
                "client_id_sha256": f"{source_index:064x}",
            }
        )
    return {"kind": render.SOURCE_KIND, "items": items}


def test_source_pool_preserves_unique_exposure_ids() -> None:
    pool = render.source_pool(manifest())

    assert pool["kind"] == render.POOL_KIND
    assert len(pool["items"]) == 85
    assert len({row["id"] for row in pool["items"]}) == 85
    assert len({row["source_id"] for row in pool["items"]}) == 48


def test_source_pool_rejects_duplicate_exposure_identity() -> None:
    value = manifest()
    value["items"][48]["id"] = value["items"][0]["id"]

    with pytest.raises(render.CommonVoiceTargetError, match="duplicated"):
        render.source_pool(value)
