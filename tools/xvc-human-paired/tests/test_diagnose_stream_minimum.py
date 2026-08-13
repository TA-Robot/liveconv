from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "diagnose_stream_minimum.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_diagnose_stream_minimum", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MINIMUM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MINIMUM
SPEC.loader.exec_module(MINIMUM)


def test_minimum_sweep_bisects_the_100_to_200_boundary() -> None:
    assert MINIMUM.FUTURE_VALUES_MS == (125, 150, 175, 200)
    assert set(MINIMUM.EXPECTED_CONTROL_HASHES) == {200}
    assert [120 + 20 + value for value in MINIMUM.FUTURE_VALUES_MS] == [
        265,
        290,
        315,
        340,
    ]


def test_wrapper_assigns_exp031_before_running() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "diagnostic.EXPERIMENT_NUMBER = 31" in source
    assert "diagnostic.FUTURE_VALUES_MS = FUTURE_VALUES_MS" in source
