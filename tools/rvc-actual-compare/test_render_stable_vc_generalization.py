"""CPU-only tests for the stable VC public-validation batch."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parent / "render_stable_vc_generalization.py"
SPEC = importlib.util.spec_from_file_location("stable_vc_generalization", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_sources_are_three_distinct_frozen_validation_rows() -> None:
    assert [item["source_id"] for item in run.SOURCES] == [
        "RECITATION324_049",
        "RECITATION324_007",
        "EMOTION100_027",
    ]
    assert len({item["sha256"] for item in run.SOURCES}) == 3
    run.validate_source_manifest()


def test_batch_uses_only_the_two_stable_profiles_in_serial_order() -> None:
    assert [item["profile_id"] for item in run.PROFILE_SPECS] == [
        run.RVC_PROFILE_ID,
        run.XVC_PROFILE_ID,
    ]
    assert [item["output_file"] for item in run.PROFILE_SPECS] == [
        "10-stable-rvc-seed0.wav",
        "20-stable-xvc-q34.wav",
    ]
    source = RUNNER.read_text(encoding="utf-8")
    assert "session.render_profile_turns(" in source
    assert "renderer.render_profile(" not in source


def test_listener_publication_uses_hidden_staging_sibling() -> None:
    destination = Path("/tmp/listening/ms3-stable-vc-generalization-v1")
    assert run.listener_staging_path(destination) == Path(
        "/tmp/listening/.ms3-stable-vc-generalization-v1.staging"
    )
