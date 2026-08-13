from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).with_name("render_stable_rvc_input_gain.py")
SPEC = importlib.util.spec_from_file_location(
    "render_stable_rvc_input_gain", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def frame(value: float) -> bytes:
    return np.full(960, value, dtype="<f4").tobytes()


def test_apply_gain_preserves_frames_and_applies_sqrt_two() -> None:
    result = MODULE.apply_gain([frame(0.125), frame(-0.25)])

    assert len(result) == 2
    assert all(len(item) == 960 * 4 for item in result)
    samples = np.frombuffer(b"".join(result), dtype="<f4")
    assert samples[0] == pytest.approx(0.125 * math.sqrt(2.0))
    assert samples[-1] == pytest.approx(-0.25 * math.sqrt(2.0))


def test_apply_gain_rejects_clipping() -> None:
    with pytest.raises(MODULE.StableInputGainError, match="clip"):
        MODULE.apply_gain([frame(0.8)])


def test_frame_levels_reports_peak_and_rms() -> None:
    levels = MODULE.frame_levels([frame(0.25), frame(-0.25)])

    assert levels == {"absolute_peak": 0.25, "rms": 0.25}


def test_listener_staging_is_sibling() -> None:
    listener = Path("/listener/comparison")

    assert MODULE.listener_staging_path(listener) == Path(
        "/listener/.comparison.staging"
    )
