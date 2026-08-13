from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validate_semantic_gate.py"
SPEC = importlib.util.spec_from_file_location("xvc_semantic_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


def test_precommitted_rule_reports_true_and_false_predictions() -> None:
    rows = [
        {"source_id": "loop", "tokens": {"unique_tokens": 4}},
        {"source_id": "false-positive", "tokens": {"unique_tokens": 5}},
        {"source_id": "clear", "tokens": {"unique_tokens": 12}},
    ]

    result = GATE.evaluate_rule(rows, {"loop"})

    assert result["true_positive_rows"] == 1
    assert result["false_negative_rows"] == 0
    assert result["false_positive_rows"] == 1
    assert result["false_positive_ids"] == ["false-positive"]


def test_precommitted_rule_reports_a_missed_loop() -> None:
    rows = [{"source_id": "loop", "tokens": {"unique_tokens": 6}}]

    result = GATE.evaluate_rule(rows, {"loop"})

    assert result["false_negative_ids"] == ["loop"]
