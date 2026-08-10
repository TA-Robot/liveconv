from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "config" / "ms3-voice-variant-candidates.json"
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "voice-variant-catalog.schema.json"
BUNDLE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "deployment-bundle.schema.json"
AUTHORIZATION_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "voice-authorization-registry.schema.json"
)
ROSTER_PATH = REPOSITORY_ROOT / "config" / "model-roster.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_voice_variant_catalog_matches_schema() -> None:
    errors = sorted(
        Draft202012Validator(_load(SCHEMA_PATH)).iter_errors(_load(CATALOG_PATH)),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == []


def test_first_wave_is_bounded_youthful_and_cross_family() -> None:
    catalog = _load(CATALOG_PATH)
    objective = catalog["objective"]
    variants = catalog["variants"]
    first_wave = [
        variant
        for variant in variants
        if variant["wave"] == "first" and variant["candidate_role"] == "primary"
    ]

    assert objective["minimum_listenable_variants"] == 9
    assert objective["minimum_families"] == 4
    assert objective["minimum_listenable_variants"] <= len(first_wave)
    assert len(first_wave) <= objective["maximum_listenable_variants"]
    assert (
        len({variant["family_id"] for variant in first_wave})
        >= objective["minimum_families"]
    )
    assert all(
        "youthful-feminine" in variant["target_presentation"] for variant in first_wave
    )
    assert all(variant["lane"] == "voice-conversion" for variant in first_wave)
    assert len({variant["priority"] for variant in first_wave}) == len(first_wave)
    assert catalog["policy"]["counted_protocol_version"] == 1
    assert catalog["policy"]["counted_lane"] == "voice-conversion-only"


def test_tts_candidates_cannot_count_before_a_transport_decision() -> None:
    catalog = _load(CATALOG_PATH)
    tts_variants = [
        variant
        for variant in catalog["variants"]
        if variant["lane"] == "text-to-speech"
    ]

    assert tts_variants
    assert catalog["policy"]["text_to_speech_requires_accepted_transport_decision"]
    assert all(variant["wave"] != "first" for variant in tts_variants)
    assert all(variant["candidate_role"] != "primary" for variant in tts_variants)
    assert all(variant["readiness"] != "runnable-control" for variant in tts_variants)
    first_wave_priorities = [
        variant["priority"]
        for variant in catalog["variants"]
        if variant["wave"] == "first" and variant["candidate_role"] == "primary"
    ]
    assert max(first_wave_priorities) < min(
        variant["priority"] for variant in tts_variants
    )


def test_deployment_bundle_schema_is_valid() -> None:
    Draft202012Validator.check_schema(_load(BUNDLE_SCHEMA_PATH))
    Draft202012Validator.check_schema(_load(AUTHORIZATION_SCHEMA_PATH))


def test_variant_ids_are_unique_and_runnable_entries_are_fully_bound() -> None:
    variants = _load(CATALOG_PATH)["variants"]
    variant_ids = [variant["variant_id"] for variant in variants]

    assert len(variant_ids) == len(set(variant_ids))
    for variant in variants:
        if variant["readiness"] == "runnable-control":
            assert variant["profile_id"] is not None
            assert variant["expected_profile_hash"] is not None
            assert variant["expected_configuration_hash"] is not None


def test_existing_control_identities_match_the_deployment_roster() -> None:
    catalog_variants = {
        variant["profile_id"]: variant
        for variant in _load(CATALOG_PATH)["variants"]
        if variant["source_kind"] == "existing-profile"
    }
    roster_models = {
        model["profile_id"]: model for model in _load(ROSTER_PATH)["models"]
    }

    for profile_id, variant in catalog_variants.items():
        roster = roster_models[profile_id]
        assert variant["expected_profile_hash"] == roster["expected_profile_hash"]
        assert (
            variant["expected_configuration_hash"]
            == roster["expected_configuration_hash"]
        )


def test_catalog_contains_no_runtime_or_secret_locators() -> None:
    document = _load(CATALOG_PATH)
    serialized = json.dumps(document, ensure_ascii=True, sort_keys=True)

    for forbidden in (
        '"artifact_path"',
        '"checkpoint_path"',
        '"reference_audio"',
        '"runtime_path"',
        '"token"',
        '"voice_id"',
    ):
        assert forbidden not in serialized

    for variant in document["variants"]:
        assert all(
            source.startswith("https://") for source in variant["official_sources"]
        )
