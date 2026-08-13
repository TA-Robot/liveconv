from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent / "render_runrun_presets.py"
SPEC = importlib.util.spec_from_file_location("rvc_runrun_presets", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_filter_keeps_the_exact_six_profile_set() -> None:
    values = [
        {"profile_id": profile_id, "value": position}
        for position, profile_id in enumerate(MODULE.PROFILE_IDS)
    ]
    values.append({"profile_id": "vc.rvc-v2.unrelated.v1"})

    filtered = MODULE.filter_deployment_document(
        {"schema_version": 1, "variants": values}, "manifest.json"
    )

    assert [item["profile_id"] for item in filtered["variants"]] == list(
        MODULE.PROFILE_IDS
    )


def test_filter_fails_closed_on_a_missing_profile() -> None:
    values = [{"profile_id": profile_id} for profile_id in MODULE.PROFILE_IDS[:-1]]
    with pytest.raises(MODULE.CompareError, match="profile set drifted"):
        MODULE.filter_deployment_document({"profiles": values}, "profiles.json")
