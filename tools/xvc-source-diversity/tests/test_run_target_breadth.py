from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_target_breadth.py"
SPEC = importlib.util.spec_from_file_location("xvc_run_target_breadth", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TARGETS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TARGETS
SPEC.loader.exec_module(TARGETS)


def test_target_breadth_schedule_fixes_updates_and_balances_donors() -> None:
    targets = [f"target-{index:03d}" for index in range(TARGETS.TRAIN_TARGET_COUNT)]
    donors = [f"donor-{index:02d}" for index in range(TARGETS.DONOR_COUNT)]

    schedule = TARGETS.training_schedule(targets, donors)

    assert len(schedule) == 1_044
    assert Counter(donor for _, donor in schedule) == {
        donor: 87 for donor in donors
    }
    target_counts = Counter(target for target, _ in schedule)
    assert Counter(target_counts.values()) == {4: 219, 3: 56}
    assert len(set(schedule)) == len(schedule)


def test_listening_index_is_unselected_target_breadth_comparison() -> None:
    item = {
        "age": "twenties",
        "gender": "female_feminine",
        "text": "別の文章を評価します",
    }
    index = TARGETS.listening_index(
        item,
        hashes={
            "base": "a" * 64,
            "cv12-control69": "b" * 64,
            "cv12-target275": "c" * 64,
        },
    )

    assert index["status"] == "completed-listen-now-unselected"
    assert [row["variant_id"] for row in index["variants"]] == [
        "base",
        "cv12-control69",
        "cv12-target275",
    ]
    assert "winner" not in str(index).lower()
