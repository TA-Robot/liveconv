from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_window_breadth_teacher.py"
SPEC = importlib.util.spec_from_file_location("xvc_window_breadth", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREPARE
SPEC.loader.exec_module(PREPARE)


def test_selection_uses_every_quality_utterance_once_and_balances_positions() -> None:
    rows = []
    for index in range(150):
        for position_index, position in enumerate(PREPARE.POSITIONS):
            rows.append(
                {
                    "utterance_id": f"ROW-{index:03d}",
                    "position": position,
                    "normalized_transcript": f"アイウエオ{position_index}{index}",
                    "transcript": f"アイウエオ{position_index}{index}",
                    "full_utterance_audit_cer": 0.1,
                    "repetition": {"gross_repetition": False},
                }
            )

    selected = PREPARE.select_hadou_windows(rows)

    assert len(selected) == 150
    assert len({row["utterance_id"] for row in selected}) == 150
    assert Counter(row["position"] for row in selected) == {
        "start": 50,
        "middle": 50,
        "end": 50,
    }
