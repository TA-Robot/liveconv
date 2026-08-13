from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).with_name("render_rvc_seed_repeat.py")
SPEC = importlib.util.spec_from_file_location("render_rvc_seed_repeat", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def test_seed_repeat_scope_is_bounded() -> None:
    assert RUN.PROFILE_ID == "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1"
    assert RUN.SOURCE_ID == "EMOTION100_017"
    assert RUN.REPEAT_COUNT == 3


def test_signal_comparison_reports_exact_and_changed_pcm() -> None:
    anchor = np.asarray([0.0, 0.25, -0.25, 0.5], dtype="<f4").tobytes()
    changed = np.asarray([0.0, 0.25, -0.20, 0.5], dtype="<f4").tobytes()

    exact = RUN.signal_comparison(anchor, anchor)
    different = RUN.signal_comparison(anchor, changed)

    assert exact["exact"] is True
    assert exact["max_abs_difference"] == 0.0
    assert different["exact"] is False
    assert different["max_abs_difference"] > 0.0
