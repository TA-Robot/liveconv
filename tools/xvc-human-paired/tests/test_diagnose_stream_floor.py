from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "diagnose_stream_floor.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_diagnose_stream_floor", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
FLOOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FLOOR
SPEC.loader.exec_module(FLOOR)


def test_floor_sweep_is_the_final_100_to_125_bracket() -> None:
    assert FLOOR.FUTURE_VALUES_MS == (100, 110, 120, 125)
    assert set(FLOOR.EXPECTED_CONTROL_HASHES) == {100, 125}
    assert [120 + 20 + value for value in FLOOR.FUTURE_VALUES_MS] == [
        240,
        250,
        260,
        265,
    ]


def test_wrapper_assigns_exp032() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "diagnostic.EXPERIMENT_NUMBER = 32" in source
