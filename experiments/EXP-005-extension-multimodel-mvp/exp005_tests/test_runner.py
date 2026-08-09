from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from liveconv_exp005_extension_multimodel_mvp.runner import (
    AttemptObservation,
    EvidenceValidationError,
    ExperimentRun,
    FakeRoute,
    ForcedFailureObservation,
    load_prompt_plan,
    load_roster,
    load_schema,
    run_fake_route,
)

_COMMIT = "a" * 40


def _roster_path() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "four-model-roster.json"


def _roster():
    return load_roster(_roster_path())


def _prompt_plan_path() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "operator-plan.json"


def _prompt_plan():
    return load_prompt_plan(_prompt_plan_path())


def _passing_observations() -> dict[str, AttemptObservation]:
    return {
        "rvc-v2": AttemptObservation(audible_changed_output=True),
        "beatrice-2": AttemptObservation(audible_changed_output=True),
        "x-vc": AttemptObservation(audible_changed_output=False),
        "openvoice-v2": AttemptObservation(
            audible_changed_output=True, end_triggered=True
        ),
    }


def test_frozen_fixture_has_exact_four_model_roster_and_safe_identities() -> None:
    roster = _roster()

    assert [entry.model_id for entry in roster.entries] == [
        "rvc-v2",
        "beatrice-2",
        "x-vc",
        "openvoice-v2",
    ]
    assert [entry.route_mode for entry in roster.entries] == [
        "live",
        "live",
        "live",
        "buffered_preview_after_end",
    ]
    assert all(entry.profile_hash.startswith("sha256:") for entry in roster.entries)
    assert all(
        entry.configuration_hash.startswith("sha256:") for entry in roster.entries
    )
    assert all(entry.pipeline_hash.startswith("sha256:") for entry in roster.entries)
    assert all(entry.execution_state == "prepared" for entry in roster.entries)


def test_operator_plan_freezes_one_manual_sample_for_each_roster_model() -> None:
    plan = _prompt_plan()

    assert plan.sample_count_per_model == 1
    assert plan.automatic_turn_detection is False
    assert plan.model_ids == ("rvc-v2", "beatrice-2", "x-vc", "openvoice-v2")


def test_fake_route_records_every_attempt_and_a_passing_technical_result() -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )
    route = FakeRoute(_passing_observations())

    run_fake_route(run, route)
    run.record_forced_failure(ForcedFailureObservation(native_fallback_observed=True))
    document = run.finish()

    assert route.invoked_model_ids == [
        "rvc-v2",
        "beatrice-2",
        "x-vc",
        "openvoice-v2",
    ]
    assert document["technical_outcome"] == "passed"
    assert document["prompt_plan"]["sample_count_per_model"] == 1
    assert document["metrics"] == {
        "prepared_models_attempted": 4,
        "live_profiles_with_audible_changed_output": 2,
        "openvoice_buffered_preview_completed": True,
        "accepted_stale_frames": 0,
        "forced_failure_native_fallback": True,
    }
    jsonschema.Draft202012Validator(load_schema()).validate(document)


def test_schema_rejects_a_forged_pass_that_misses_the_live_output_gate() -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )
    observations = _passing_observations()
    observations["beatrice-2"] = AttemptObservation(audible_changed_output=False)
    run_fake_route(run, FakeRoute(observations))
    run.record_forced_failure(ForcedFailureObservation(native_fallback_observed=True))
    document = run.finish()
    document["technical_outcome"] = "passed"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(load_schema()).validate(document)


def test_manual_operator_observations_have_the_same_contract_as_fake_routes() -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )
    for model_id, observation in _passing_observations().items():
        run.record_manual_attempt(model_id, observation)
    run.record_forced_failure(ForcedFailureObservation(native_fallback_observed=True))

    document = run.finish()

    assert all(
        attempt["observation_source"] == "manual_operator"
        for attempt in document["attempts"]
    )
    assert document["attempts"][-1]["end_triggered"] is True


def test_finish_fails_when_any_roster_entry_is_not_attempted() -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )
    run.record_manual_attempt("rvc-v2", AttemptObservation(audible_changed_output=True))

    with pytest.raises(EvidenceValidationError, match="all four roster entries"):
        run.finish()


def test_openvoice_cannot_be_recorded_as_live_or_without_explicit_end() -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )

    with pytest.raises(EvidenceValidationError, match="End-triggered"):
        run.record_manual_attempt(
            "openvoice-v2", AttemptObservation(audible_changed_output=True)
        )


def test_fewer_than_two_live_audible_profiles_cannot_pass() -> None:
    observations = _passing_observations()
    observations["beatrice-2"] = AttemptObservation(audible_changed_output=False)
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )

    run_fake_route(run, FakeRoute(observations))
    run.record_forced_failure(ForcedFailureObservation(native_fallback_observed=True))

    assert run.finish()["technical_outcome"] == "failed"


def test_missing_openvoice_preview_output_or_native_fallback_cannot_pass() -> None:
    observations = _passing_observations()
    observations["openvoice-v2"] = AttemptObservation(
        audible_changed_output=False, end_triggered=True
    )
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )

    run_fake_route(run, FakeRoute(observations))
    run.record_forced_failure(ForcedFailureObservation(native_fallback_observed=False))

    assert run.finish()["technical_outcome"] == "failed"


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda value: value["entries"].pop(), "exactly four"),
        (
            lambda value: value["entries"][0].__setitem__(
                "execution_state", "unavailable"
            ),
            "prepared",
        ),
        (
            lambda value: value["entries"][0].__setitem__("artifact_path", "/tmp/a"),
            "forbidden",
        ),
        (
            lambda value: value["entries"][0].__setitem__("profile_id", "voice.secret"),
            "profile_id",
        ),
    ],
)
def test_roster_rejects_unavailable_or_sensitive_metadata(
    mutator, match: str, tmp_path: Path
) -> None:
    value = json.loads(_roster_path().read_text(encoding="utf-8"))
    mutator(value)
    destination = tmp_path / "roster.json"
    destination.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match=match):
        load_roster(destination)


def test_report_rejects_sensitive_free_form_evidence_and_requires_verified_write(
    tmp_path: Path,
) -> None:
    run = ExperimentRun(
        roster=_roster(), prompt_plan=_prompt_plan(), git_commit=_COMMIT
    )
    with pytest.raises(EvidenceValidationError, match="free-form"):
        run.record_manual_attempt(
            "rvc-v2",
            AttemptObservation(
                audible_changed_output=True, note="heard at /tmp/audio.wav"
            ),
        )
    with pytest.raises(EvidenceValidationError, match="verified clean checkout"):
        run.write(tmp_path / "result.json")
