"""CPU-only tests for the stable two-family heldout shortlist."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parent / "render_stable_vc_shortlist.py"
SPEC = importlib.util.spec_from_file_location("stable_vc_shortlist", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_stable_shortlist_generates_only_missing_public_rows() -> None:
    assert run.PROFILE_ID.endswith("clean-bright-seed0.v1")
    assert run.GENERATED_SOURCE_IDS == ("EMOTION100_002", "EMOTION100_004")
    assert run.REUSED_SOURCE_ID == "EMOTION100_017"


def test_stable_shortlist_reuses_one_surviving_xvc_arm() -> None:
    compose = run._load_module("stable_shortlist_test_compose", run.COMPOSE_RUNNER)
    xvc = run._xvc_arm(compose)
    assert xvc["profile_id"] == "vc.x-vc.amitaro-yofukashi-q34.v1"
