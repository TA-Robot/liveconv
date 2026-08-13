from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "diagnose_stream_threshold.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_diagnose_stream_threshold", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
THRESHOLD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = THRESHOLD
SPEC.loader.exec_module(THRESHOLD)


def test_threshold_sweep_brackets_the_repetition_boundary() -> None:
    assert THRESHOLD.FUTURE_VALUES_MS == (100, 200, 250, 300)
    assert set(THRESHOLD.EXPECTED_CONTROL_HASHES) == {100, 300}
    assert 120 + 20 + 250 == 390
    assert 120 + 20 + 300 == 440


def test_wrapper_relabels_the_shared_fail_closed_runner() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "diagnostic.EXPERIMENT_NUMBER = 30" in source
    assert "diagnostic.EXPECTED_CONTROL_HASHES = EXPECTED_CONTROL_HASHES" in source
