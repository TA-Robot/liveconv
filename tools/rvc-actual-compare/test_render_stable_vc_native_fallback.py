"""CPU-only tests for the stable-VC native-fallback listening render."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).parent / "render_stable_vc_native_fallback.py"
SPEC = importlib.util.spec_from_file_location("stable_vc_native_fallback", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_fallback_is_one_fixed_exclusive_switch_on_two_stable_profiles() -> None:
    assert run.SWITCH_SECONDS == 2.0
    assert run.SWITCH_FRAME == 96_000
    assert len(run.PROFILES) == 2
    assert [item["slug"] for item in run.PROFILES] == ["rvc-seed0", "xvc-q34"]


def test_splice_changes_routes_at_the_exact_pcm24_frame() -> None:
    remote = bytes(range(30))
    native = bytes(range(30, 60))
    assert run.splice_pcm24(remote, native, 4) == remote[:12] + native[12:]


def test_splice_rejects_a_switch_outside_retained_audio() -> None:
    with pytest.raises(run.NativeFallbackError):
        run.splice_pcm24(b"\x00" * 12, b"\x00" * 12, 4)


def test_inputs_are_exact_retained_actual_shortlist_audio() -> None:
    assert run.SOURCE_FILE == "00-source.wav"
    assert len(run.SOURCE_SHA256) == 64
    assert all(len(item["remote_sha256"]) == 64 for item in run.PROFILES)
