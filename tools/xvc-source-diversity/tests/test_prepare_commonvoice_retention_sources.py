from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_commonvoice_retention_sources as commonvoice  # noqa: E402


def test_exposure_schedule_uses_every_speaker_and_balances_duplicates() -> None:
    items = [{"id": f"speaker-{index}"} for index in range(48)]

    schedule = commonvoice.exposure_schedule(items)
    counts = Counter(schedule)

    assert len(schedule) == 85
    assert len(counts) == 48
    assert Counter(counts.values()) == {1: 11, 2: 37}
    assert schedule[:48] == list(range(48))


def test_exposure_schedule_is_manifest_order_only() -> None:
    left = [{"id": f"speaker-{index}", "text": "x"} for index in range(48)]
    right = [{"id": f"other-{index}", "text": "different"} for index in range(48)]

    assert commonvoice.exposure_schedule(left) == commonvoice.exposure_schedule(right)
