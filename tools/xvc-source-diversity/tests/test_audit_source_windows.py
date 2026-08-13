from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "audit_source_windows.py"
SPEC = importlib.util.spec_from_file_location("xvc_source_window_audit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def test_window_offsets_cover_start_middle_and_end() -> None:
    assert AUDIT.window_offsets(60_000) == {
        "start": 0,
        "middle": 10_800,
        "end": 21_600,
    }
    assert AUDIT.window_offsets(20_000) == {
        "start": 0,
        "middle": 0,
        "end": 0,
    }


def test_model_window_crops_and_right_pads() -> None:
    audio = np.arange(40_000, dtype=np.float32)
    cropped = AUDIT.model_window(audio, 1_600)
    assert cropped.shape == (38_400,)
    assert cropped[0] == 1_600
    assert cropped[-1] == 39_999

    padded = AUDIT.model_window(np.ones(1_000, dtype=np.float32), 0)
    assert padded.shape == (38_400,)
    assert padded[:1_000].all()
    assert not padded[1_000:].any()


def test_empty_audio_is_rejected() -> None:
    with pytest.raises(AUDIT.SourceWindowAuditError):
        AUDIT.window_offsets(0)
