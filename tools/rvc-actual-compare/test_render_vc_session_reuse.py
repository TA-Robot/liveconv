"""CPU-only tests for the persistent Gateway session comparison."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parent / "render_vc_session_reuse.py"
SPEC = importlib.util.spec_from_file_location("vc_session_reuse", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_comparison_is_bounded_to_two_surviving_live_profiles() -> None:
    assert run.PROFILE_IDS == (
        "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1",
        "vc.x-vc.amitaro-yofukashi-q34.v1",
    )
    assert all(
        len(run.FRESH[profile_id]["hashes"]) == 3 for profile_id in run.PROFILE_IDS
    )


def test_turn_must_fit_advertised_credit() -> None:
    assert run.validate_turn_capacity(120, 400, 8_000) == 400
    try:
        run.validate_turn_capacity(120, 50, 1_000)
    except run.SessionReuseError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("oversized turn was accepted")


def test_hash_comparison_is_exact_only_for_identical_audio() -> None:
    assert run.comparison_status("a", "a") == "exact"
    assert run.comparison_status("a", "b") == "different"
