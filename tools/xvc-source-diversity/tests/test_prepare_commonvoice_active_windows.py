from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_commonvoice_active_windows as active  # noqa: E402


def test_selects_later_speech_active_window_without_text_or_asr() -> None:
    samples = np.zeros(active.WINDOW_SAMPLES * 2, dtype=np.int16)
    samples[: active.WINDOW_SAMPLES] = 400
    samples[active.WINDOW_SAMPLES :] = 4_000

    selected, metrics = active.select_speech_active_window(samples)

    assert metrics["window_start_sample"] == active.WINDOW_SAMPLES
    assert np.all(selected == 4_000)


def test_equal_windows_choose_earliest_start() -> None:
    samples = np.full(active.WINDOW_SAMPLES + active.HOP_SAMPLES, 4_000, dtype=np.int16)

    selected, metrics = active.select_speech_active_window(samples)

    assert metrics["window_start_sample"] == 0
    assert selected.shape == (active.WINDOW_SAMPLES,)
