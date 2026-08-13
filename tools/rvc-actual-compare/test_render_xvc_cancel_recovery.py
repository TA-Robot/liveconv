"""CPU-only tests for the stable X-VC cancellation-recovery runner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parent / "render_xvc_cancel_recovery.py"
SPEC = importlib.util.spec_from_file_location("xvc_cancel_recovery", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_cancel_slice_is_one_stable_profile_and_two_named_sources() -> None:
    assert tuple(run.PROFILE_SPECS) == (run.RVC_PROFILE_ID, run.XVC_PROFILE_ID)
    assert run.CANCELED_SOURCE_ID == "EMOTION100_027"
    assert run.RECOVERY_SOURCE_ID == "RECITATION324_049"
    assert run.CANCEL_AFTER_FRAMES == 100


def test_recovery_control_is_the_exact_fresh_generalization_output() -> None:
    assert run.PROFILE_SPECS[run.RVC_PROFILE_ID]["baseline_file"] == (
        "10-stable-rvc-seed0.wav"
    )
    assert run.PROFILE_SPECS[run.XVC_PROFILE_ID]["baseline_file"] == (
        "20-stable-xvc-q34.wav"
    )
    assert all(
        len(spec["baseline_sha256"]) == 64
        for spec in run.PROFILE_SPECS.values()
    )


def test_runner_closes_the_local_output_gate_before_cancel() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "from liveconv_protocol import GenerationCancel" in source
    assert "renderer.GenerationCancel(" not in source
    assert '"local_output_gate_closed_before_cancel": True' in source
    assert '"stale_output_frames_after_ack"' in source
