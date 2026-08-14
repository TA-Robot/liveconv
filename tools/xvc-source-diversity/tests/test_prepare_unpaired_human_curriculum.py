from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_unpaired_human_curriculum as unpaired  # noqa: E402


def test_selection_spreads_unique_rows_across_complete_train_split() -> None:
    selected = unpaired.selected_train_indices()

    assert len(selected) == unpaired.EXPECTED_ROWS
    assert len(set(selected)) == unpaired.EXPECTED_ROWS
    assert selected[0] == 0
    assert selected[-1] >= unpaired.EXPECTED_TRAIN_ROWS - 2


def test_active_window_chooses_speech_and_keeps_exact_shape() -> None:
    silence = np.zeros(unpaired.WINDOW_SAMPLES, dtype=np.int16)
    speech = np.full(unpaired.WINDOW_SAMPLES, 2_000, dtype=np.int16)
    source = np.concatenate((silence, speech, silence))

    selected = unpaired.speech_active_window(source)

    assert selected.shape == (unpaired.WINDOW_SAMPLES,)
    assert selected.dtype == np.int16
    assert np.mean(np.abs(selected)) == 2_000


def test_short_active_window_is_right_padded_without_stretch() -> None:
    source = np.full(unpaired.FRAME_SAMPLES * 3, 1_000, dtype=np.int16)

    selected = unpaired.speech_active_window(source)

    assert np.array_equal(selected[: source.size], source)
    assert not np.any(selected[source.size :])
