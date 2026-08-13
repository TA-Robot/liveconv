from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).with_name("render_stable_actual_shortlist.py")
SPEC = importlib.util.spec_from_file_location("stable_actual_shortlist", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_shortlist_binds_stable_profile_ids() -> None:
    assert run.RVC_PROFILE_ID.endswith("clean-bright-seed0.v1")
    assert run.XVC_PROFILE_ID == "vc.x-vc.amitaro-yofukashi-q34.v1"


def test_checked_file_rejects_identity_drift(tmp_path: Path) -> None:
    path = tmp_path / "source.f32le"
    path.write_bytes(b"source")

    with pytest.raises(run.StableActualError, match="identity drifted"):
        run.checked_file(path, "0" * 64, "source")


def test_listener_staging_is_atomic_sibling() -> None:
    final = Path("/listener/ms3-stable-vc-actual-shortlist-v1")
    assert run.listener_staging_path(final) == Path(
        "/listener/.ms3-stable-vc-actual-shortlist-v1.staging"
    )
