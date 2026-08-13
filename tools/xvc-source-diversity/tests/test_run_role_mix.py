from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_role_mix.py"
SPEC = importlib.util.spec_from_file_location("xvc_run_role_mix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ROLE_MIX = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ROLE_MIX
SPEC.loader.exec_module(ROLE_MIX)


def test_role_schedule_is_interleaved_exact_official_ratio() -> None:
    schedule = ROLE_MIX.role_schedule()

    assert schedule[:10] == list(ROLE_MIX.ROLE_CYCLE) * 2
    assert len(schedule) == 1_044
    assert Counter(schedule) == ROLE_MIX.ROLE_COUNTS


def test_role_schedule_rejects_another_update_count() -> None:
    with pytest.raises(ROLE_MIX.RoleMixError, match="update count"):
        ROLE_MIX.role_schedule(1_043)


def test_assigned_tensors_follow_waveform_roles() -> None:
    target = {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    generated = {
        "source_wav": "donor-wave",
        "semantic_tokens": "donor-token",
        "target_wav": "donor-wave",
        "ssl_feat": "donor-ssl",
    }

    assert ROLE_MIX.assigned_tensors(target, generated, "standard") == {
        "source_wav": "donor-wave",
        "semantic_tokens": "donor-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    assert ROLE_MIX.assigned_tensors(target, generated, "reconstruction") == {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    assert ROLE_MIX.assigned_tensors(target, generated, "reversed") == {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "donor-wave",
        "ssl_feat": "donor-ssl",
    }


def test_predecessor_receipt_rejects_drift(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"kind": "wrong"}), encoding="utf-8")

    with pytest.raises(ROLE_MIX.RoleMixError, match="identity"):
        ROLE_MIX._load_predecessor(path)
