from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_conditioned_retention_targets as render  # noqa: E402


def test_source_pool_preserves_balanced_conditions() -> None:
    kinds = list(render.EXPECTED_CONDITION_COUNTS)
    items = []
    for index in range(85):
        source_index = index if index < 48 else index - 48
        source_id = f"cv{source_index:08d}f"
        kind = kinds[index % 5]
        items.append(
            {
                "id": f"{source_id}-e{1 if index < 48 else 2}",
                "filename": f"row-{index}-{kind}.wav",
                "source_id": source_id,
                "source_sha256": "a" * 64,
                "target_id": f"target-{index % 74}",
                "source_transcript": "評価文",
                "curriculum_position": index * 2 + 1,
                "condition": {"kind": kind},
                "condition_index": index,
                "exposure": 1 if index < 48 else 2,
                "client_id_sha256": f"{source_index:064x}",
            }
        )

    pool = render.source_pool({"kind": render.SOURCE_KIND, "items": items})

    assert len(pool["items"]) == 85
    assert len({row["source_id"] for row in pool["items"]}) == 48
    assert {row["condition"]["kind"] for row in pool["items"]} == set(kinds)
