from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "run_filtered_pairs.py"
SPEC = importlib.util.spec_from_file_location("run_filtered_pairs", MODULE_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_load_real_audit_passes_frozen_admission():
    audit = RUNNER.load_audit(
        Path("artifacts/xvc-source-diversity/exp059-pseudo-content-audit-v1.json")
    )

    assert audit["aggregate"]["selected_mean_distance"] < 0.75 * audit["aggregate"][
        "all_mean_distance"
    ]
    assert len(audit["aggregate"]["selected_donor_update_counts"]) == 12


def test_load_audit_rejects_tampered_result(tmp_path):
    source = Path(
        "artifacts/xvc-source-diversity/exp059-pseudo-content-audit-v1.json"
    )
    value = json.loads(source.read_text(encoding="utf-8"))
    value["aggregate"]["selected_mean_distance"] = 99.0
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(RUNNER.FilteredPairError, match="did not pass admission"):
        RUNNER.load_audit(path)
