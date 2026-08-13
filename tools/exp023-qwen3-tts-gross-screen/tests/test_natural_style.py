"""CPU-only tests for the bounded EXP-023 natural-style comparison."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).parents[1] / "run_natural_style.py"
SPEC = importlib.util.spec_from_file_location("exp023_natural_style", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_index_changes_only_instruct_between_profiles() -> None:
    row = {"id": "TTS009", "category": "english_switch", "text": "表示文"}
    index = run.build_index(row, "a" * 64, "b" * 64)
    baseline, styled = index["variants"]

    assert index["source_text"] == "表示文"
    assert index["comparison_scope"]["single_changed_variable"] == "instruct"
    assert baseline["effective_parameters"]["instruct"] == ""
    assert styled["effective_parameters"]["instruct"] == run.STYLE_INSTRUCTION
    assert baseline["effective_parameters"]["seed"] == 8887
    assert styled["effective_parameters"]["seed"] == 8887
    assert baseline["operator_judgment"] == "unreviewed"
    assert styled["operator_judgment"] == "unreviewed"
    assert baseline["output_sha256"] == "sha256:" + "a" * 64
    assert styled["output_sha256"] == "sha256:" + "b" * 64


def test_style_instruction_is_one_fixed_japanese_value() -> None:
    assert run.STYLE_INSTRUCTION == (
        "自然な日常会話として、明るく親しみやすく、"
        "過剰に演技せずに話してください。"
    )


def test_child_home_cleanup_is_recursive() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "shutil.rmtree(child_home)" in source
    assert "child_home.rmdir()" not in source
