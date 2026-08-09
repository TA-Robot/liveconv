from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from liveconv_evaluation.transcript import (
    NORMALIZATION_REVISION,
    compare_exact_entities,
    normalize_japanese,
)

CORPUS_DIR = Path(__file__).parents[1] / "corpus"
CORPUS_PATH = CORPUS_DIR / "lv-001-ja-smoke-v1.json"
SCHEMA_PATH = CORPUS_DIR / "lv-001-corpus.schema.json"

EXPECTED_CATEGORY_TARGETS = {
    "ordinary_conversation": 6,
    "contact_center_language": 5,
    "telephone_and_postal_numbers": 5,
    "addresses": 4,
    "dates_times_money_and_units": 5,
    "proper_nouns_and_polyphonic_kanji": 5,
    "code_switching_and_identifiers": 4,
    "interruption_scenarios": 4,
    "noise_and_degraded_transport": 2,
}
EXPECTED_JP_REQUIREMENTS = {f"JP-{number:03d}" for number in range(1, 9)}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _corpus() -> dict[str, Any]:
    return _load_json(CORPUS_PATH)


def _validator() -> Draft202012Validator:
    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _canonical_digest(corpus: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in corpus.items()
        if key not in {"revision", "integrity"}
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def test_lv001_corpus_is_valid_against_its_json_schema():
    errors = sorted(
        _validator().iter_errors(_corpus()),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == []


def test_corpus_has_exactly_40_unique_utterances():
    utterances = _corpus()["utterances"]

    assert len(utterances) == 40
    assert len({item["id"] for item in utterances}) == 40
    assert len({item["display_text"] for item in utterances}) == 40
    assert len({item["expected_spoken_text"] for item in utterances}) == 40
    assert [item["id"] for item in utterances] == [
        f"LV001-JA-{number:03d}" for number in range(1, 41)
    ]


def test_every_evaluation_category_meets_the_documented_smoke_minimum():
    corpus = _corpus()
    actual = Counter(item["primary_category"] for item in corpus["utterances"])

    assert corpus["category_targets"] == EXPECTED_CATEGORY_TARGETS
    assert sum(EXPECTED_CATEGORY_TARGETS.values()) == 40
    for category, minimum in EXPECTED_CATEGORY_TARGETS.items():
        assert actual[category] >= minimum


def test_entries_cover_every_japanese_speech_requirement():
    corpus = _corpus()
    covered = {
        requirement
        for item in corpus["utterances"]
        for requirement in item["requirements"]
    }

    assert set(corpus["requirements_covered"]) == EXPECTED_JP_REQUIREMENTS
    assert covered == EXPECTED_JP_REQUIREMENTS


def test_expected_spoken_forms_match_the_executable_normalization_revision():
    corpus = _corpus()
    assert corpus["normalization_revision"] == NORMALIZATION_REVISION

    for item in corpus["utterances"]:
        normalized = normalize_japanese(item["expected_spoken_text"])
        assert normalized == item["canonical_kana"]


def test_exact_entities_bind_display_surface_to_reviewed_spoken_form():
    corpus = _corpus()
    exact_required_categories = {
        "telephone_and_postal_numbers",
        "addresses",
        "dates_times_money_and_units",
        "proper_nouns_and_polyphonic_kanji",
        "code_switching_and_identifiers",
        "noise_and_degraded_transport",
    }

    for item in corpus["utterances"]:
        entities = item["exact_entities"]
        if item["primary_category"] in exact_required_categories:
            assert entities, item["id"]

        normalized_entities = []
        for entity in entities:
            assert entity["surface"] in item["display_text"]
            normalized = normalize_japanese(entity["expected_spoken"])
            assert normalized == entity["normalized_spoken"]
            assert normalized in item["canonical_kana"]
            assert (
                compare_exact_entities(
                    [entity["expected_spoken"]], item["expected_spoken_text"]
                )["exact_match_rate"]
                == 1.0
            )
            normalized_entities.append(normalized)
        assert len(normalized_entities) == len(set(normalized_entities))


def test_interruption_entries_have_reproducible_beginning_middle_and_end_anchors():
    utterances = _corpus()["utterances"]
    interruption_items = [
        item
        for item in utterances
        if item["primary_category"] == "interruption_scenarios"
    ]

    assert Counter(item["interruption"]["position"] for item in interruption_items) == {
        "beginning": 1,
        "middle": 2,
        "end": 1,
    }

    for item in interruption_items:
        metadata = item["interruption"]
        assert item["display_text"].startswith(metadata["after_display_text"])
        assert item["expected_spoken_text"].startswith(
            metadata["after_expected_spoken_text"]
        )

        fraction = len(metadata["after_display_text"]) / len(item["display_text"])
        if metadata["position"] == "beginning":
            assert fraction <= 0.25
        elif metadata["position"] == "middle":
            assert 0.30 <= fraction <= 0.85
        else:
            assert fraction >= 0.75

    non_interruption_items = [
        item
        for item in utterances
        if item["primary_category"] != "interruption_scenarios"
    ]
    assert all("interruption" not in item for item in non_interruption_items)


def test_degraded_transport_entries_are_metadata_only_and_deterministic():
    corpus = _corpus()
    items = [
        item
        for item in corpus["utterances"]
        if item["primary_category"] == "noise_and_degraded_transport"
    ]

    assert corpus["audio_assets"] == {
        "included": False,
        "status": "not-generated",
        "checksum_manifest_status": "not-applicable",
    }
    assert {item["transport_condition"]["parameters"]["mode"] for item in items} == {
        "narrowband_pcm",
        "deterministic_packet_jitter",
    }
    assert all(
        item["transport_condition"]["audio_artifact_state"] == "absent"
        for item in items
    )


def test_corpus_contains_no_null_or_unresolved_promotion_placeholders():
    unresolved = re.compile(
        r"\b(?:tbd|todo|unknown|to be determined)\b|未定|要確認", re.I
    )

    for value in _walk(_corpus()):
        assert value is not None
        if isinstance(value, str):
            assert not unresolved.search(value), value


def test_corpus_is_ci_redistributable_without_customer_or_voice_material():
    corpus = _corpus()

    assert corpus["classification"] == "synthetic"
    assert corpus["artifact_kind"] == "text-metadata-only"
    assert corpus["license"] == {
        "spdx_id": "CC0-1.0",
        "scope": "corpus text and metadata authored for LV-001",
        "redistribution": "permitted-without-restriction",
        "third_party_material": False,
    }
    assert corpus["provenance"]["contains_customer_data"] is False
    assert corpus["provenance"]["contains_recorded_voice"] is False
    assert (
        corpus["provenance"]["reading_review"]["native_speaker_validation"]
        == "not-performed"
    )


def test_content_addressed_revision_and_checksum_are_intact():
    corpus = _corpus()
    digest = _canonical_digest(corpus)

    assert corpus["integrity"] == {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8-json-sort-keys-compact-without-revision-and-integrity-v1"
        ),
        "digest_scope": "complete document excluding revision and integrity",
        "sha256": digest,
    }
    assert corpus["revision"] == (
        f"lv-001-ja-smoke-v{corpus['version']}+sha256.{digest[:16]}"
    )

    mutated = copy.deepcopy(corpus)
    mutated["utterances"][0]["display_text"] += "変更"
    assert _canonical_digest(mutated) != digest


def test_schema_rejects_incomplete_or_misclassified_corpus_entries():
    validator = _validator()
    corpus = _corpus()

    too_short = copy.deepcopy(corpus)
    too_short["utterances"].pop()
    assert list(validator.iter_errors(too_short))

    missing_anchor = copy.deepcopy(corpus)
    del missing_anchor["utterances"][34]["interruption"]
    assert list(validator.iter_errors(missing_anchor))

    misplaced_transport = copy.deepcopy(corpus)
    misplaced_transport["utterances"][0]["transport_condition"] = copy.deepcopy(
        corpus["utterances"][38]["transport_condition"]
    )
    assert list(validator.iter_errors(misplaced_transport))
