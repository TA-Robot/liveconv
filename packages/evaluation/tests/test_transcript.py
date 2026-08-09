from liveconv_evaluation.transcript import (
    compare_exact_entities,
    compare_transcripts,
    normalize_japanese,
)


def test_japanese_normalization_is_deterministic_without_guessing_kanji():
    assert normalize_japanese(" ＡＢＣ１２３、カタカナ。\n") == "abc123かたかな"
    assert normalize_japanese("日本") == "日本"


def test_transcript_substitution_counts():
    metrics = compare_transcripts("あいう", "あえう")
    assert metrics.substitutions == 1
    assert metrics.insertions == 0
    assert metrics.deletions == 0
    assert metrics.character_error_rate == 1 / 3


def test_transcript_insertion_and_deletion_counts():
    insertion = compare_transcripts("あいう", "あいうえ")
    deletion = compare_transcripts("あいう", "あう")

    assert (insertion.substitutions, insertion.insertions, insertion.deletions) == (
        0,
        1,
        0,
    )
    assert (deletion.substitutions, deletion.insertions, deletion.deletions) == (
        0,
        0,
        1,
    )


def test_empty_reference_has_no_fabricated_finite_cer():
    assert compare_transcripts("", "").character_error_rate == 0.0
    assert compare_transcripts("", "音声").character_error_rate is None


def test_exact_entity_detects_one_character_identifier_corruption():
    metrics = compare_exact_entities(["090-1234-5678"], "電話番号は090-1234-5679です")

    assert metrics["exact_match_rate"] == 0.0
    assert metrics["matched"] == []
    assert metrics["missing"] == ["090-1234-5678"]


def test_exact_entity_rejects_a_match_inside_a_longer_identifier():
    metrics = compare_exact_entities(["ABC123"], "かくにんこーどはXABC1234です")

    assert metrics["matched"] == []
    assert metrics["missing"] == ["ABC123"]
    assert metrics["exact_match_rate"] == 0.0


def test_empty_exact_entity_set_passes_vacuously():
    assert (
        compare_exact_entities([], "じゅうようなIDはありません")["exact_match_rate"]
        == 1.0
    )
