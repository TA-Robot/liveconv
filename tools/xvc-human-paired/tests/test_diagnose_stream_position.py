from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
MODULE_PATH = TOOL_ROOT / "diagnose_stream_position.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_human_paired_diagnose_stream_position", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
POSITION = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = POSITION
SPEC.loader.exec_module(POSITION)


def test_future_sweep_moves_only_current_position() -> None:
    assert POSITION.FUTURE_VALUES_MS == (0, 100, 300, 500)
    assert POSITION.stream.CHUNK_MS == 2400
    assert POSITION.stream.CURRENT_MS == 120
    assert POSITION.stream.SMOOTH_MS == 20

    document = POSITION.listening_index(
        {0: "a" * 64, 100: "b" * 64, 300: "c" * 64, 500: "d" * 64}
    )
    assert [item["parameters"]["history_ms"] for item in document["variants"]] == [
        2260,
        2160,
        1960,
        1760,
    ]


def test_future100_is_an_exact_fail_closed_control() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "output_hashes[100] != EXPECTED_FUTURE100_SHA256" in source
    assert "stream._measured_stream(" in source
    assert '"position_hypothesis_confirmed": False' in source
