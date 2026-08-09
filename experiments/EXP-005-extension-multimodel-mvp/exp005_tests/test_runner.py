from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from liveconv_exp005_extension_multimodel_mvp.runner import (
    AttemptObservation,
    EvidenceValidationError,
    ExperimentRun,
    FakeRoute,
    content_digest,
    load_manual_audible_judgments,
    load_prompt_plan,
    load_roster,
    load_runtime_receipt,
    load_schema,
    run_fake_route,
)

_COMMIT = "a" * 40
_RECEIPT_ID = "11111111-1111-4111-8111-111111111111"
_PIPELINE_IDS = (
    "00000000-0000-4000-8000-000000000001",
    "00000000-0000-4000-8000-000000000002",
    "00000000-0000-4000-8000-000000000003",
    "00000000-0000-4000-8000-000000000004",
)


def _root() -> Path:
    return Path(__file__).parents[1]


def _roster_path() -> Path:
    return _root() / "fixtures" / "four-model-roster.json"


def _roster():
    return load_roster(_roster_path())


def _prompt_plan_path() -> Path:
    return _root() / "fixtures" / "operator-plan.json"


def _prompt_plan():
    return load_prompt_plan(_prompt_plan_path())


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _receipt_document() -> dict[str, object]:
    roster = _roster()
    attempts: list[dict[str, object]] = []
    for index, entry in enumerate(roster.entries, start=1):
        forced = entry.model_id == "x-vc"
        attempts.append(
            {
                "model_id": entry.model_id,
                "profile_id": entry.profile_id,
                "profile_hash": entry.profile_hash,
                "configuration_hash": entry.configuration_hash,
                "route_mode": entry.route_mode,
                "pipeline_id": _PIPELINE_IDS[index - 1],
                "generation_id": 10 + index,
                "finite_output_observed": not forced,
                "changed_output_observed": not forced,
                "stale_output_accepted": False,
                "exclusive_playout_observed": True,
                "end_triggered": entry.model_id == "openvoice-v2",
            }
        )
    openvoice = attempts[-1]
    return {
        "schema_version": 1,
        "source": "extension_gateway_runtime",
        "receipt_id": _RECEIPT_ID,
        "roster_revision": roster.roster_revision,
        "plan_revision": _prompt_plan().plan_revision,
        "chatgpt_tab": {
            "chatgpt_com_audible_tab_observed": True,
            "capture_started_after_user_gesture": True,
        },
        "ssh_loopback": {
            "configured_local_forward_reached_gateway": True,
            "client_loopback_only": True,
            "remote_gateway_loopback_only": True,
            "pinned_server_identity_configured": True,
        },
        "gateway_authentication": {
            "gateway_session_authenticated": True,
            "single_use_session_grant_authenticated": True,
            "exact_extension_origin_verified": True,
            "max_sessions": 1,
        },
        "attempts": attempts,
        "forced_failure_event": {
            "event_type": "fallback.required",
            "model_id": "openvoice-v2",
            "profile_id": openvoice["profile_id"],
            "profile_hash": openvoice["profile_hash"],
            "configuration_hash": openvoice["configuration_hash"],
            "pipeline_id": _PIPELINE_IDS[3],
            "generation_id": 15,
            "failure_injected": True,
            "fallback_required_observed": True,
        },
        "native_fallback_event": {
            "event_type": "extension.native_fallback_activated",
            "model_id": "openvoice-v2",
            "profile_id": openvoice["profile_id"],
            "profile_hash": openvoice["profile_hash"],
            "configuration_hash": openvoice["configuration_hash"],
            "pipeline_id": _PIPELINE_IDS[3],
            "generation_id": 15,
            "native_route_active": True,
            "remote_route_active": False,
        },
    }


def _manual_judgments_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": "manual_operator",
        "receipt_id": _RECEIPT_ID,
        "chatgpt_account_authenticated_asserted": True,
        "ssh_tunnel_established_asserted": True,
        "ssh_pinned_server_identity_verified_asserted": True,
        "judgments": [
            {
                "model_id": "rvc-v2",
                "pipeline_id": _PIPELINE_IDS[0],
                "generation_id": 11,
                "audible_changed_output": True,
            },
            {
                "model_id": "beatrice-2",
                "pipeline_id": _PIPELINE_IDS[1],
                "generation_id": 12,
                "audible_changed_output": True,
            },
            {
                "model_id": "x-vc",
                "pipeline_id": _PIPELINE_IDS[2],
                "generation_id": 13,
                "audible_changed_output": False,
            },
            {
                "model_id": "openvoice-v2",
                "pipeline_id": _PIPELINE_IDS[3],
                "generation_id": 14,
                "audible_changed_output": True,
            },
        ],
    }


def _runtime_run(tmp_path: Path) -> ExperimentRun:
    roster = _roster()
    plan = _prompt_plan()
    receipt = load_runtime_receipt(
        _write_json(tmp_path / "receipt.json", _receipt_document()),
        roster=roster,
        prompt_plan=plan,
    )
    judgments = load_manual_audible_judgments(
        _write_json(tmp_path / "judgments.json", _manual_judgments_document()),
        receipt=receipt,
    )
    run = ExperimentRun(
        roster=roster,
        prompt_plan=plan,
        git_commit=_COMMIT,
        persisted_evidence_verified=True,
    )
    run.attach_runtime_evidence(receipt, judgments)
    return run


def test_frozen_fixture_has_exact_four_model_roster_without_pipeline_identity() -> None:
    raw = json.loads(_roster_path().read_text(encoding="utf-8"))
    revision = raw.pop("roster_revision")

    roster = _roster()

    assert revision == content_digest(raw)
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
    assert "pipeline_hash" not in json.dumps(raw)


def test_operator_plan_revision_is_a_digest_of_the_frozen_content() -> None:
    raw = json.loads(_prompt_plan_path().read_text(encoding="utf-8"))
    revision = raw.pop("plan_revision")
    plan = _prompt_plan()

    assert revision == content_digest(raw)
    assert plan.sample_count_per_model == 1
    assert plan.automatic_turn_detection is False
    assert plan.model_ids == ("rvc-v2", "beatrice-2", "x-vc", "openvoice-v2")
    assert raw["prompt_sequence"][-1] == {
        "step_id": "forced-native-fallback",
        "model_id": "openvoice-v2",
        "generation_control": "next_inject_failure",
    }


def test_deterministic_fake_is_only_a_contract_test_never_a_technical_pass() -> None:
    roster = _roster()
    run = ExperimentRun(roster=roster, prompt_plan=_prompt_plan(), git_commit=_COMMIT)
    route = FakeRoute(
        {
            entry.model_id: AttemptObservation(
                finite_output_observed=True,
                changed_output_observed=True,
                end_triggered=entry.model_id == "openvoice-v2",
            )
            for entry in roster.entries
        }
    )

    run_fake_route(run, route)
    document = run.finish()

    assert route.invoked_model_ids == list(entry.model_id for entry in roster.entries)
    assert document["evidence_kind"] == "contract_test"
    assert document["technical_outcome"] == "inconclusive"
    assert document["runtime_receipt"] is None
    assert document["manual_audible_judgments"] is None
    jsonschema.Draft202012Validator(load_schema()).validate(document)


def test_runtime_receipt_and_separate_manual_judgments_can_pass(tmp_path: Path) -> None:
    document = _runtime_run(tmp_path).finish()

    assert document["evidence_kind"] == "runtime_receipt"
    assert document["technical_outcome"] == "passed"
    assert document["runtime_receipt"]["source"] == "extension_gateway_runtime"
    assert document["attempts"][0]["pipeline_id"] == _PIPELINE_IDS[0]
    assert document["attempts"][0]["generation_id"] == 11
    assert document["metrics"] == {
        "prepared_models_attempted": 4,
        "live_profiles_with_finite_changed_output": 2,
        "live_profiles_with_audible_changed_output": 2,
        "openvoice_buffered_preview_completed": True,
        "accepted_stale_frames": 0,
        "exclusive_playout_for_all_attempts": True,
        "forced_failure_native_fallback": True,
    }
    jsonschema.Draft202012Validator(load_schema()).validate(document)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda value: value["chatgpt_tab"].pop("chatgpt_com_audible_tab_observed"),
            "ChatGPT tab observation",
        ),
        (
            lambda value: value.__setitem__("source", "manual_operator"),
            "source",
        ),
        (
            lambda value: value["attempts"][0].__setitem__(
                "profile_hash", "sha256:" + "0" * 64
            ),
            "profile_hash",
        ),
        (
            lambda value: value["attempts"][0].__setitem__("pipeline_id", "fixed"),
            "pipeline_id",
        ),
        (
            lambda value: value["attempts"][1].__setitem__("generation_id", 11),
            "strictly increasing",
        ),
        (
            lambda value: value["forced_failure_event"].pop(
                "fallback_required_observed"
            ),
            "forced failure",
        ),
        (
            lambda value: value["native_fallback_event"].__setitem__(
                "remote_route_active", True
            ),
            "exclusive native",
        ),
        (
            lambda value: value["ssh_loopback"].__setitem__(
                "local_forward_established", True
            ),
            "SSH-loopback",
        ),
    ],
)
def test_runtime_receipt_rejects_missing_or_mutated_machine_evidence(
    mutate, match: str, tmp_path: Path
) -> None:
    value = _receipt_document()
    mutate(value)

    with pytest.raises(EvidenceValidationError, match=match):
        load_runtime_receipt(
            _write_json(tmp_path / "receipt.json", value),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )


def test_runtime_receipt_rejects_missing_attempt_fact_and_invalid_failure_probe(
    tmp_path: Path,
) -> None:
    missing_fact = _receipt_document()
    missing_fact["attempts"][0].pop("finite_output_observed")
    with pytest.raises(EvidenceValidationError, match="unsupported metadata"):
        load_runtime_receipt(
            _write_json(tmp_path / "missing-fact.json", missing_fact),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )

    bound_to_attempt_event = _receipt_document()
    bound_to_attempt_event["forced_failure_event"]["generation_id"] = 14
    with pytest.raises(EvidenceValidationError, match="post-attempt generation"):
        load_runtime_receipt(
            _write_json(tmp_path / "bound-event.json", bound_to_attempt_event),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )

    wrong_profile_context = _receipt_document()
    wrong_profile_context["forced_failure_event"]["model_id"] = "x-vc"
    with pytest.raises(EvidenceValidationError, match="OpenVoice profile context"):
        load_runtime_receipt(
            _write_json(tmp_path / "wrong-profile-event.json", wrong_profile_context),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )

    spontaneous_failure = _receipt_document()
    spontaneous_failure["forced_failure_event"]["failure_injected"] = False
    with pytest.raises(EvidenceValidationError, match="forced failure facts"):
        load_runtime_receipt(
            _write_json(tmp_path / "spontaneous-failure.json", spontaneous_failure),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )


def test_manual_boolean_judgments_cannot_substitute_for_a_runtime_receipt(
    tmp_path: Path,
) -> None:
    boolean_only = {
        "attempts": {
            "rvc-v2": {"audible_changed_output": True, "end_triggered": False},
            "beatrice-2": {"audible_changed_output": True, "end_triggered": False},
            "x-vc": {"audible_changed_output": False, "end_triggered": False},
            "openvoice-v2": {"audible_changed_output": True, "end_triggered": True},
        },
        "forced_failure": {"native_fallback_observed": True},
    }

    with pytest.raises(EvidenceValidationError, match="unsupported metadata"):
        load_runtime_receipt(
            _write_json(tmp_path / "boolean-only.json", boolean_only),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )


def test_manual_judgments_must_bind_receipt_attempt_ids(tmp_path: Path) -> None:
    roster = _roster()
    plan = _prompt_plan()
    receipt = load_runtime_receipt(
        _write_json(tmp_path / "receipt.json", _receipt_document()),
        roster=roster,
        prompt_plan=plan,
    )
    judgments = _manual_judgments_document()
    judgments["judgments"][0]["generation_id"] = 99

    with pytest.raises(EvidenceValidationError, match="does not bind"):
        load_manual_audible_judgments(
            _write_json(tmp_path / "judgments.json", judgments), receipt=receipt
        )


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda value: value.__setitem__(
                "chatgpt_account_authenticated_asserted", False
            ),
            "chatgpt_account_authenticated_asserted",
        ),
        (
            lambda value: value.pop("ssh_tunnel_established_asserted"),
            "ssh_tunnel_established_asserted",
        ),
        (
            lambda value: value.__setitem__(
                "ssh_pinned_server_identity_verified_asserted", False
            ),
            "ssh_pinned_server_identity_verified_asserted",
        ),
    ],
)
def test_manual_operator_must_explicitly_assert_account_and_ssh_facts(
    mutate, match: str, tmp_path: Path
) -> None:
    roster = _roster()
    plan = _prompt_plan()
    receipt = load_runtime_receipt(
        _write_json(tmp_path / "receipt.json", _receipt_document()),
        roster=roster,
        prompt_plan=plan,
    )
    judgments = _manual_judgments_document()
    mutate(judgments)

    with pytest.raises(EvidenceValidationError, match=match):
        load_manual_audible_judgments(
            _write_json(tmp_path / "judgments.json", judgments), receipt=receipt
        )


def test_stale_or_nonexclusive_output_cannot_pass(tmp_path: Path) -> None:
    receipt_document = _receipt_document()
    receipt_document["attempts"][0]["stale_output_accepted"] = True
    receipt_document["attempts"][1]["exclusive_playout_observed"] = False
    roster = _roster()
    plan = _prompt_plan()
    receipt = load_runtime_receipt(
        _write_json(tmp_path / "receipt.json", receipt_document),
        roster=roster,
        prompt_plan=plan,
    )
    judgments = load_manual_audible_judgments(
        _write_json(tmp_path / "judgments.json", _manual_judgments_document()),
        receipt=receipt,
    )
    run = ExperimentRun(roster=roster, prompt_plan=plan, git_commit=_COMMIT)
    run.attach_runtime_evidence(receipt, judgments)

    assert run.finish()["technical_outcome"] == "failed"


def test_schema_rejects_a_forged_pass_without_runtime_receipt(tmp_path: Path) -> None:
    document = _runtime_run(tmp_path).finish()
    forged = copy.deepcopy(document)
    forged["runtime_receipt"] = None

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(load_schema()).validate(forged)


def test_schema_requires_the_openvoice_dedicated_failure_probe(tmp_path: Path) -> None:
    document = _runtime_run(tmp_path).finish()
    document["runtime_receipt"]["forced_failure_event"]["model_id"] = "x-vc"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(load_schema()).validate(document)


def test_schema_rejects_a_contract_test_forged_to_pass() -> None:
    roster = _roster()
    run = ExperimentRun(roster=roster, prompt_plan=_prompt_plan(), git_commit=_COMMIT)
    run_fake_route(
        run,
        FakeRoute(
            {
                entry.model_id: AttemptObservation(
                    finite_output_observed=True,
                    changed_output_observed=True,
                    end_triggered=entry.model_id == "openvoice-v2",
                )
                for entry in roster.entries
            }
        ),
    )
    document = run.finish()
    document["technical_outcome"] = "passed"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(load_schema()).validate(document)


def test_report_rejects_sensitive_free_form_metadata_and_requires_verified_write(
    tmp_path: Path,
) -> None:
    value = _receipt_document()
    value["host"] = "not-permitted"
    with pytest.raises(EvidenceValidationError, match="forbidden"):
        load_runtime_receipt(
            _write_json(tmp_path / "sensitive.json", value),
            roster=_roster(),
            prompt_plan=_prompt_plan(),
        )

    roster = _roster()
    run = ExperimentRun(roster=roster, prompt_plan=_prompt_plan(), git_commit=_COMMIT)
    run_fake_route(
        run,
        FakeRoute(
            {
                entry.model_id: AttemptObservation(
                    finite_output_observed=False,
                    changed_output_observed=False,
                    end_triggered=entry.model_id == "openvoice-v2",
                )
                for entry in roster.entries
            }
        ),
    )
    with pytest.raises(EvidenceValidationError, match="verified clean checkout"):
        run.write(tmp_path / "result.json")
