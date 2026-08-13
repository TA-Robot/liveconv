from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_window_teacher.py"
SPEC = importlib.util.spec_from_file_location("xvc_window_teacher", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREPARE
SPEC.loader.exec_module(PREPARE)


def test_selection_is_position_balanced_unique_and_quality_filtered() -> None:
    rows = []
    for position_index, position in enumerate(PREPARE.POSITIONS):
        for index in range(12):
            rows.append(
                {
                    "utterance_id": f"{position}-{index}",
                    "position": position,
                    "normalized_transcript": f"アイウエオ{position_index}{index}",
                    "transcript": f"アイウエオ{position_index}{index}",
                    "full_utterance_audit_cer": 0.2 if index == 0 else 0.1,
                    "repetition": {"gross_repetition": index == 1},
                }
            )
    selected = PREPARE.select_windows(rows)
    assert len(selected) == 21
    assert len({row["utterance_id"] for row in selected}) == 21
    assert Counter(row["position"] for row in selected) == {
        "start": 7,
        "middle": 7,
        "end": 7,
    }
    assert max(row["full_utterance_audit_cer"] for row in selected) <= 0.15
    assert not any(row["repetition"]["gross_repetition"] for row in selected)
