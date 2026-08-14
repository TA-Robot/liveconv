from __future__ import annotations

import importlib.util
import json
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


def test_consensus_repetition_does_not_promote_one_decoder_hallucination() -> None:
    unstable = SCREEN.consensus_repetition(
        "笑いかけながら一二歩近寄った",
        "三四三四三四三四三四三四",
    )
    agreed = SCREEN.consensus_repetition(
        "三四三四三四三四",
        "三四三四三四三四三四",
    )

    assert unstable["greedy_gross_repetition"] is False
    assert unstable["beam5_gross_repetition"] is True
    assert unstable["gross_repetition"] is False
    assert agreed["gross_repetition"] is True


def test_aggregate_is_groupwise_and_never_invents_quality_score() -> None:
    rows = [
        {
            "group": "clean",
            "variant": variant,
            "source_relative_distance": distance,
            "repetition": {"gross_repetition": repetition},
            "known_text_distance": distance + 0.1,
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
    assert result["macro"]["base"]["mean_known_text_distance"] == 0.30000000000000004
    assert "quality" not in str(result).lower()


def test_aggregate_separates_decoder_unstable_content_rows() -> None:
    rows = [
        {
            "group": "clean",
            "variant": "candidate",
            "source_relative_distance": distance,
            "known_text_distance": distance,
            "decoder_unstable": unstable,
            "repetition": {"gross_repetition": False},
        }
        for distance, unstable in ((0.2, False), (20.0, True))
    ]

    result = SCREEN.aggregate_rows(rows)["macro"]["candidate"]

    assert result["rows"] == 2
    assert result["decoder_stable_rows"] == 1
    assert result["decoder_unstable_rows"] == 1
    assert result["stable_mean_source_relative_distance"] == 0.2
    assert result["stable_mean_known_text_distance"] == 0.2


def test_evaluation_loader_keeps_external_evaluation_kind(tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    path.write_text(
        '{"kind":"liveconv-exp034-commonvoice25-ja-unseen/v1","items":[]}',
        encoding="utf-8",
    )

    result = SCREEN._load_evaluation(path)

    assert result["kind"] == "liveconv-exp034-commonvoice25-ja-unseen/v1"


def test_listener_variants_are_discovered_from_index(tmp_path: Path) -> None:
    (tmp_path / "index.json").write_text(
        json.dumps(
            {
                "source_output_file": "00-source.wav",
                "variants": [
                    {"variant_id": "base", "output_file": "10-base.wav"},
                    {"variant_id": "cv12", "output_file": "20-cv12.wav"},
                ],
            }
        ),
        encoding="utf-8",
    )

    source, variants = SCREEN._load_listener_variants(tmp_path)

    assert source == "00-source.wav"
    assert variants == {"base": "10-base.wav", "cv12": "20-cv12.wav"}
