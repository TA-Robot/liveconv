from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_control_hard_negatives as probe  # noqa: E402


def manifest() -> dict[str, object]:
    return {
        "items": [
            {
                "teacher_id": f"teacher-{index:03d}",
                "domain": "commonvoice",
                "source_transcript": f"評価文{index}",
            }
            for index in range(probe.post.EXPECTED_ROWS)
        ]
    }


def test_probe_pool_binds_every_clean_source_once() -> None:
    pool = probe.probe_pool(manifest())

    assert pool["kind"] == probe.POOL_KIND
    assert len(pool["items"]) == probe.post.EXPECTED_ROWS
    assert len({item["id"] for item in pool["items"]}) == probe.post.EXPECTED_ROWS


def test_probe_pool_rejects_duplicate_teacher() -> None:
    value = manifest()
    value["items"][1]["teacher_id"] = value["items"][0]["teacher_id"]

    with pytest.raises(probe.HardNegativeProbeError, match="identity drifted"):
        probe.probe_pool(value)


def test_probe_pool_allows_empty_prior_asr_transcript() -> None:
    value = manifest()
    value["items"][0]["source_transcript"] = ""

    pool = probe.probe_pool(value)

    assert pool["items"][0]["source_transcript"] == ""
