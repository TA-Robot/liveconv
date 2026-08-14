from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_conditioned_retention_sources as conditioned  # noqa: E402


def test_condition_schedule_is_balanced_and_manifest_order_only() -> None:
    schedule = conditioned.condition_schedule()

    assert len(schedule) == 85
    assert Counter(item["kind"] for item in schedule) == {
        "clean": 17,
        "noise": 17,
        "tempo": 17,
        "pitch": 17,
        "leading-silence": 17,
    }
    assert [item["kind"] for item in schedule[:5]] == [
        "clean",
        "noise",
        "tempo",
        "pitch",
        "leading-silence",
    ]


def test_leading_silence_preserves_fixed_window_length() -> None:
    values = np.full(conditioned.WINDOW_SAMPLES, 1_000, dtype=np.int16)

    transformed = conditioned.transform_samples(
        values,
        {"kind": "leading-silence", "milliseconds": 150},
        seed=1,
    )

    assert transformed.shape == values.shape
    assert np.count_nonzero(transformed[:2_400]) == 0
    assert np.all(transformed[2_400:] == 1_000)


def test_noise_is_deterministic_and_changes_the_window() -> None:
    values = np.full(conditioned.WINDOW_SAMPLES, 1_000, dtype=np.int16)
    condition = {"kind": "noise", "snr_db": 15.0}

    left = conditioned.transform_samples(values, condition, seed=191)
    right = conditioned.transform_samples(values, condition, seed=191)

    assert np.array_equal(left, right)
    assert not np.array_equal(left, values)
