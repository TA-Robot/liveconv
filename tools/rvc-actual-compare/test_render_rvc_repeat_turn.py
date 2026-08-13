"""CPU-only tests for the same-input RVC repeat diagnostic."""

from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np

RUNNER = Path(__file__).parent / "render_rvc_repeat_turn.py"
SPEC = importlib.util.spec_from_file_location("rvc_repeat_turn", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_repeat_scope_is_one_profile_one_source_three_turns() -> None:
    assert run.PROFILE_ID == "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1"
    assert run.SOURCE_ID == "EMOTION100_017"
    assert run.REPEAT_COUNT == 3
    assert run.SEEDED_PROFILE_ID.endswith("clean-bright-seed0.v1")


def test_signal_comparison_reports_exact_and_changed_pcm() -> None:
    anchor = np.asarray([0.0, 0.5, -0.5], dtype="<f4").tobytes()
    exact = run.signal_comparison(anchor, anchor)
    assert exact["correlation_to_generation_1"] == 1.0
    assert exact["rms_difference"] == 0.0

    changed = np.asarray([0.0, 0.25, -0.25], dtype="<f4").tobytes()
    comparison = run.signal_comparison(anchor, changed)
    assert comparison["correlation_to_generation_1"] == 1.0
    assert comparison["rms_difference"] > 0.0


def test_actual_mode_is_one_frozen_seeded_profile() -> None:
    arguments = Namespace(
        actual_source_wav=Path("source.wav"),
        actual_unseeded_control_wav=Path("control.wav"),
        profile_id=run.SEEDED_PROFILE_ID,
    )
    assert run.actual_input_mode(arguments)

    arguments.profile_id = run.PROFILE_ID
    try:
        run.actual_input_mode(arguments)
    except run.RepeatTurnError as error:
        assert "seed-0" in str(error)
    else:
        raise AssertionError("unseeded actual-input rerender was admitted")
