from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "screen.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_source_diversity_screen", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCREEN
SPEC.loader.exec_module(SCREEN)


def test_normalized_distance_ignores_kana_width_case_and_punctuation() -> None:
    assert SCREEN.normalized_distance(" ＡＩ、カタカナ。", "ai かたかな") == 0.0


def test_repetition_metrics_flags_gross_character_and_ngram_loops() -> None:
    assert SCREEN.repetition_metrics("ああああああ")["gross_repetition"] is True
    assert (
        SCREEN.repetition_metrics("やばいやばいやばいやばい")["gross_repetition"]
        is True
    )
    assert SCREEN.repetition_metrics("今日は晴れです")["gross_repetition"] is False


def test_aggregate_is_groupwise_and_never_invents_quality_score() -> None:
    rows = [
        {
            "group": "clean",
            "variant": variant,
            "source_relative_distance": distance,
            "repetition": {"gross_repetition": repetition},
        }
        for variant, distance, repetition in (
            ("base", 0.2, False),
            ("human87-control69-e12", 0.3, True),
            ("jvs3-generated-pairs", 0.1, False),
        )
    ]

    result = SCREEN.aggregate_rows(rows)

    assert result["by_group"]["clean"]["base"]["mean_source_relative_distance"] == 0.2
    assert result["macro"]["human87-control69-e12"]["gross_repetition_rows"] == 1
    assert "quality" not in str(result).lower()
