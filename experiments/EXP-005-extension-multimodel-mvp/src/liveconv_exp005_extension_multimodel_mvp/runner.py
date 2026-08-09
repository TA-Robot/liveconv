from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

_MODEL_ORDER = ("rvc-v2", "beatrice-2", "x-vc", "openvoice-v2")
_LIVE_MODELS = frozenset(_MODEL_ORDER[:3])
_OPENVOICE_MODE = "buffered_preview_after_end"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_PROFILE_ID = re.compile(
    r"^vc\.(?:rvc-v2|rvc|beatrice-2|beatrice|x-vc|x-vc|openvoice-v2)"
    r"\.[a-z0-9][a-z0-9.-]{0,63}\.v1$"
)
_FORBIDDEN_KEY = re.compile(
    r"(^|_)(audio|artifact|bearer|credential|directory|endpoint|file|host|"
    r"password|path|payload|pcm|raw|reference|secret|target|ticket|token|"
    r"voice|weight|worker)($|_)",
    re.IGNORECASE,
)


class EvidenceValidationError(ValueError):
    """Raised when evidence would be incomplete, unsafe, or overclaiming."""


@dataclass(frozen=True, slots=True)
class RosterEntry:
    model_id: str
    profile_id: str
    execution_state: str
    route_mode: str
    profile_hash: str
    configuration_hash: str

    def document(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "profile_id": self.profile_id,
            "execution_state": self.execution_state,
            "route_mode": self.route_mode,
            "profile_hash": self.profile_hash,
            "configuration_hash": self.configuration_hash,
        }


@dataclass(frozen=True, slots=True)
class Roster:
    roster_revision: str
    entries: tuple[RosterEntry, ...]

    def entry(self, model_id: str) -> RosterEntry:
        for entry in self.entries:
            if entry.model_id == model_id:
                return entry
        raise EvidenceValidationError(f"unknown roster model: {model_id}")

    def document(self) -> dict[str, object]:
        return {
            "roster_revision": self.roster_revision,
            "entries": [entry.document() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class PromptPlan:
    plan_revision: str
    sample_count_per_model: int
    automatic_turn_detection: bool
    model_ids: tuple[str, ...]

    def document(self) -> dict[str, object]:
        return {
            "plan_revision": self.plan_revision,
            "sample_count_per_model": self.sample_count_per_model,
            "automatic_turn_detection": self.automatic_turn_detection,
            "model_ids": list(self.model_ids),
        }


@dataclass(frozen=True, slots=True)
class AttemptObservation:
    """A deterministic contract-test outcome; it is never runtime evidence."""

    finite_output_observed: bool
    changed_output_observed: bool
    stale_output_accepted: bool = False
    exclusive_playout_observed: bool = True
    end_triggered: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeReceipt:
    """Validated facts emitted by Extension and Gateway instrumentation."""

    document: dict[str, object]


@dataclass(frozen=True, slots=True)
class ManualAudibleJudgments:
    """Validated operator listening judgments, bound to a runtime receipt."""

    document: dict[str, object]


class ModelRoute(Protocol):
    def attempt(self, entry: RosterEntry) -> AttemptObservation: ...


@dataclass(slots=True)
class FakeRoute:
    """Deterministic route double for the roster contract, never an MS-2 run."""

    observations: Mapping[str, AttemptObservation]
    invoked_model_ids: list[str] = field(default_factory=list)

    def attempt(self, entry: RosterEntry) -> AttemptObservation:
        self.invoked_model_ids.append(entry.model_id)
        try:
            return self.observations[entry.model_id]
        except KeyError as error:
            raise EvidenceValidationError(
                f"fake route has no observation for {entry.model_id}"
            ) from error


@dataclass(slots=True)
class ExperimentRun:
    roster: Roster
    prompt_plan: PromptPlan
    git_commit: str
    persisted_evidence_verified: bool = False
    _contract_attempts: dict[str, AttemptObservation] = field(default_factory=dict)
    _runtime_receipt: RuntimeReceipt | None = None
    _manual_audible_judgments: ManualAudibleJudgments | None = None

    def __post_init__(self) -> None:
        if _COMMIT.fullmatch(self.git_commit) is None:
            raise EvidenceValidationError(
                "report requires a lowercase 40-character Git commit"
            )
        if self.prompt_plan.model_ids != tuple(
            entry.model_id for entry in self.roster.entries
        ):
            raise EvidenceValidationError("prompt plan does not bind the frozen roster")

    def record_route_attempt(
        self, model_id: str, observation: AttemptObservation
    ) -> None:
        """Record fake-route behavior for a contract test only."""

        entry = self.roster.entry(model_id)
        if model_id in self._contract_attempts:
            raise EvidenceValidationError(f"duplicate model attempt: {model_id}")
        if entry.route_mode == _OPENVOICE_MODE and not observation.end_triggered:
            raise EvidenceValidationError(
                "OpenVoice contract test must be explicitly End-triggered"
            )
        if entry.route_mode == "live" and observation.end_triggered:
            raise EvidenceValidationError(
                "live contract test cannot be represented as buffered"
            )
        self._contract_attempts[model_id] = observation

    def attach_runtime_evidence(
        self,
        receipt: RuntimeReceipt,
        manual_audible_judgments: ManualAudibleJudgments,
    ) -> None:
        if self._contract_attempts:
            raise EvidenceValidationError(
                "contract-test attempts cannot be mixed with runtime evidence"
            )
        if (
            self._runtime_receipt is not None
            or self._manual_audible_judgments is not None
        ):
            raise EvidenceValidationError("runtime evidence is already attached")
        self._runtime_receipt = receipt
        self._manual_audible_judgments = manual_audible_judgments

    def finish(self) -> dict[str, object]:
        if self._runtime_receipt is None:
            return self._contract_test_document()
        if self._manual_audible_judgments is None:
            raise EvidenceValidationError(
                "runtime receipt requires manual audible judgments"
            )
        return _runtime_report_document(
            roster=self.roster,
            prompt_plan=self.prompt_plan,
            git_commit=self.git_commit,
            worktree_clean=self.persisted_evidence_verified,
            receipt=self._runtime_receipt,
            manual_audible_judgments=self._manual_audible_judgments,
        )

    def _contract_test_document(self) -> dict[str, object]:
        if set(self._contract_attempts) != set(_MODEL_ORDER):
            raise EvidenceValidationError(
                "all four roster entries must be exercised by a contract test"
            )
        attempts = [
            _contract_attempt_document(
                self.roster.entry(model_id), self._contract_attempts[model_id]
            )
            for model_id in _MODEL_ORDER
        ]
        return _report_document(
            roster=self.roster,
            prompt_plan=self.prompt_plan,
            git_commit=self.git_commit,
            worktree_clean=self.persisted_evidence_verified,
            evidence_kind="contract_test",
            technical_outcome="inconclusive",
            attempts=attempts,
            runtime_receipt=None,
            manual_audible_judgments=None,
            metrics={
                "prepared_models_attempted": 4,
                "live_profiles_with_finite_changed_output": sum(
                    item["finite_output_observed"] is True
                    and item["changed_output_observed"] is True
                    for item in attempts
                    if item["model_id"] in _LIVE_MODELS
                ),
                "live_profiles_with_audible_changed_output": 0,
                "openvoice_buffered_preview_completed": False,
                "accepted_stale_frames": sum(
                    item["stale_output_accepted"] is True for item in attempts
                ),
                "exclusive_playout_for_all_attempts": all(
                    item["exclusive_playout_observed"] is True for item in attempts
                ),
                "forced_failure_native_fallback": False,
            },
        )

    def to_json(self) -> str:
        return (
            json.dumps(self.finish(), ensure_ascii=True, indent=2, sort_keys=True)
            + "\n"
        )

    def write(self, destination: Path, *, repository: Path | None = None) -> Path:
        if not self.persisted_evidence_verified:
            raise EvidenceValidationError(
                "persisted report requires a verified clean checkout"
            )
        resolved = destination.expanduser().resolve()
        if repository is not None and resolved.is_relative_to(repository.resolve()):
            raise EvidenceValidationError(
                "persisted report must be outside the repository"
            )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        temporary = resolved.with_name(f".{resolved.name}.tmp")
        temporary.write_text(self.to_json(), encoding="utf-8")
        temporary.replace(resolved)
        return resolved


def run_fake_route(run: ExperimentRun, route: ModelRoute) -> None:
    """Exercise the roster against a fake that can yield only a contract test."""

    for entry in run.roster.entries:
        run.record_route_attempt(entry.model_id, route.attempt(entry))


def load_roster(source: Path) -> Roster:
    raw = _load_json_object(source, "roster")
    _reject_forbidden_keys(raw)
    if set(raw) != {"schema_version", "roster_revision", "entries"}:
        raise EvidenceValidationError("roster has unsupported metadata fields")
    if raw["schema_version"] != 1:
        raise EvidenceValidationError("roster schema_version must be 1")
    revision = _require_sha256(raw["roster_revision"], "roster_revision")
    if revision != content_digest(_without(raw, "roster_revision")):
        raise EvidenceValidationError("roster_revision does not digest roster content")
    entries_value = raw["entries"]
    if not isinstance(entries_value, list) or len(entries_value) != len(_MODEL_ORDER):
        raise EvidenceValidationError("roster requires exactly four prepared entries")
    entries = tuple(
        _load_entry(value, index) for index, value in enumerate(entries_value)
    )
    if tuple(entry.model_id for entry in entries) != _MODEL_ORDER:
        raise EvidenceValidationError(
            "roster entries must use the frozen four-model order"
        )
    expected_modes = ("live", "live", "live", _OPENVOICE_MODE)
    if tuple(entry.route_mode for entry in entries) != expected_modes:
        raise EvidenceValidationError(
            "roster route modes do not match the frozen live/preview plan"
        )
    return Roster(roster_revision=revision, entries=entries)


def load_prompt_plan(source: Path) -> PromptPlan:
    raw = _load_json_object(source, "prompt plan")
    _reject_forbidden_keys(raw)
    expected = {
        "schema_version",
        "plan_revision",
        "sample_count_per_model",
        "automatic_turn_detection",
        "prompt_sequence",
    }
    if set(raw) != expected or raw["schema_version"] != 1:
        raise EvidenceValidationError("prompt plan has unsupported metadata fields")
    revision = _require_sha256(raw["plan_revision"], "plan_revision")
    if revision != content_digest(_without(raw, "plan_revision")):
        raise EvidenceValidationError(
            "plan_revision does not digest prompt-plan content"
        )
    if raw["sample_count_per_model"] != 1:
        raise EvidenceValidationError(
            "prompt plan requires exactly one sample per model"
        )
    if raw["automatic_turn_detection"] is not False:
        raise EvidenceValidationError("prompt plan must use manual lifecycle controls")
    sequence = raw["prompt_sequence"]
    if not isinstance(sequence, list) or len(sequence) != 6:
        raise EvidenceValidationError("prompt plan requires the six frozen steps")
    model_ids = _validate_prompt_sequence(sequence)
    return PromptPlan(
        plan_revision=revision,
        sample_count_per_model=1,
        automatic_turn_detection=False,
        model_ids=model_ids,
    )


def load_runtime_receipt(
    source: Path, *, roster: Roster, prompt_plan: PromptPlan
) -> RuntimeReceipt:
    """Load a producer-emitted receipt, never an operator-authored substitute."""

    raw = _load_json_object(source, "runtime receipt")
    _reject_forbidden_keys(raw)
    expected = {
        "schema_version",
        "source",
        "receipt_id",
        "roster_revision",
        "plan_revision",
        "chatgpt_tab",
        "ssh_loopback",
        "gateway_authentication",
        "attempts",
        "forced_failure_event",
        "native_fallback_event",
    }
    if set(raw) != expected or raw["schema_version"] != 1:
        raise EvidenceValidationError("runtime receipt has unsupported metadata fields")
    if raw["source"] != "extension_gateway_runtime":
        raise EvidenceValidationError(
            "runtime receipt source must be extension_gateway_runtime"
        )
    receipt_id = _require_uuid(raw["receipt_id"], "receipt_id")
    if raw["roster_revision"] != roster.roster_revision:
        raise EvidenceValidationError("runtime receipt roster revision does not match")
    if raw["plan_revision"] != prompt_plan.plan_revision:
        raise EvidenceValidationError("runtime receipt plan revision does not match")
    _require_true_facts(
        raw["chatgpt_tab"],
        "ChatGPT tab observation",
        {
            "chatgpt_com_audible_tab_observed",
            "capture_started_after_user_gesture",
        },
    )
    _require_true_facts(
        raw["ssh_loopback"],
        "SSH-loopback",
        {
            "configured_local_forward_reached_gateway",
            "client_loopback_only",
            "remote_gateway_loopback_only",
            "pinned_server_identity_configured",
        },
    )
    gateway = raw["gateway_authentication"]
    if not isinstance(gateway, dict) or set(gateway) != {
        "gateway_session_authenticated",
        "single_use_session_grant_authenticated",
        "exact_extension_origin_verified",
        "max_sessions",
    }:
        raise EvidenceValidationError("Gateway authentication facts are invalid")
    if (
        gateway["gateway_session_authenticated"] is not True
        or gateway["single_use_session_grant_authenticated"] is not True
        or gateway["exact_extension_origin_verified"] is not True
        or gateway["max_sessions"] != 1
    ):
        raise EvidenceValidationError("Gateway authentication facts are incomplete")

    attempts_value = raw["attempts"]
    if not isinstance(attempts_value, list) or len(attempts_value) != len(_MODEL_ORDER):
        raise EvidenceValidationError("runtime receipt requires exactly four attempts")
    attempts = [
        _load_runtime_attempt(value, index=index, roster_entry=roster.entries[index])
        for index, value in enumerate(attempts_value)
    ]
    pipeline_ids = [item["pipeline_id"] for item in attempts]
    if len(set(pipeline_ids)) != len(pipeline_ids):
        raise EvidenceValidationError(
            "runtime attempt pipeline IDs must be dynamic and unique"
        )
    generation_ids = [item["generation_id"] for item in attempts]
    if generation_ids != sorted(generation_ids) or len(set(generation_ids)) != len(
        generation_ids
    ):
        raise EvidenceValidationError(
            "runtime attempt generation IDs must be strictly increasing"
        )
    forced_failure = _load_forced_failure_event(raw["forced_failure_event"], attempts)
    native_fallback = _load_native_fallback_event(
        raw["native_fallback_event"], forced_failure
    )
    return RuntimeReceipt(
        document={
            "schema_version": 1,
            "source": "extension_gateway_runtime",
            "receipt_id": receipt_id,
            "roster_revision": roster.roster_revision,
            "plan_revision": prompt_plan.plan_revision,
            "chatgpt_tab": raw["chatgpt_tab"],
            "ssh_loopback": raw["ssh_loopback"],
            "gateway_authentication": gateway,
            "attempts": attempts,
            "forced_failure_event": forced_failure,
            "native_fallback_event": native_fallback,
        }
    )


def load_manual_audible_judgments(
    source: Path, *, receipt: RuntimeReceipt
) -> ManualAudibleJudgments:
    """Load listening judgments only after the runtime receipt has been verified."""

    raw = _load_json_object(source, "manual audible judgments")
    _reject_forbidden_keys(raw)
    expected = {
        "schema_version",
        "source",
        "receipt_id",
        "chatgpt_account_authenticated_asserted",
        "ssh_tunnel_established_asserted",
        "ssh_pinned_server_identity_verified_asserted",
        "judgments",
    }
    missing = expected.difference(raw)
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise EvidenceValidationError(
            f"manual judgments are missing required assertions: {missing_fields}"
        )
    if set(raw) != expected or raw["schema_version"] != 1:
        raise EvidenceValidationError(
            "manual audible judgments have unsupported metadata fields"
        )
    if raw["source"] != "manual_operator":
        raise EvidenceValidationError("manual judgments source must be manual_operator")
    if raw["receipt_id"] != receipt.document["receipt_id"]:
        raise EvidenceValidationError(
            "manual judgments do not bind the runtime receipt"
        )
    for field_name in (
        "chatgpt_account_authenticated_asserted",
        "ssh_tunnel_established_asserted",
        "ssh_pinned_server_identity_verified_asserted",
    ):
        if raw[field_name] is not True:
            raise EvidenceValidationError(
                f"manual judgment {field_name} must be explicitly asserted"
            )
    values = raw["judgments"]
    receipt_attempts = _require_list(receipt.document["attempts"], "receipt attempts")
    if not isinstance(values, list) or len(values) != len(receipt_attempts):
        raise EvidenceValidationError("manual judgments require exactly four attempts")
    judgments: list[dict[str, object]] = []
    for index, (value, attempt) in enumerate(
        zip(values, receipt_attempts, strict=True)
    ):
        if not isinstance(value, dict) or set(value) != {
            "model_id",
            "pipeline_id",
            "generation_id",
            "audible_changed_output",
        }:
            raise EvidenceValidationError(f"manual judgment {index} is invalid")
        if (
            value["model_id"] != attempt["model_id"]
            or value["pipeline_id"] != attempt["pipeline_id"]
            or value["generation_id"] != attempt["generation_id"]
            or not isinstance(value["audible_changed_output"], bool)
        ):
            raise EvidenceValidationError(
                f"manual judgment {index} does not bind its runtime attempt"
            )
        judgments.append(dict(value))
    return ManualAudibleJudgments(
        document={
            "schema_version": 1,
            "source": "manual_operator",
            "receipt_id": receipt.document["receipt_id"],
            "chatgpt_account_authenticated_asserted": True,
            "ssh_tunnel_established_asserted": True,
            "ssh_pinned_server_identity_verified_asserted": True,
            "judgments": judgments,
        }
    )


def _runtime_report_document(
    *,
    roster: Roster,
    prompt_plan: PromptPlan,
    git_commit: str,
    worktree_clean: bool,
    receipt: RuntimeReceipt,
    manual_audible_judgments: ManualAudibleJudgments,
) -> dict[str, object]:
    receipt_document = receipt.document
    attempts = _require_list(receipt_document["attempts"], "receipt attempts")
    judgments = _require_list(
        manual_audible_judgments.document["judgments"], "manual judgments"
    )
    judgment_by_model = {value["model_id"]: value for value in judgments}

    valid_changed_attempts = [
        value
        for value in attempts
        if value["finite_output_observed"] is True
        and value["changed_output_observed"] is True
        and value["stale_output_accepted"] is False
        and value["exclusive_playout_observed"] is True
    ]
    live_machine_changed = sum(
        value["model_id"] in _LIVE_MODELS for value in valid_changed_attempts
    )
    live_audible_changed = sum(
        value["model_id"] in _LIVE_MODELS
        and judgment_by_model[value["model_id"]]["audible_changed_output"] is True
        for value in valid_changed_attempts
    )
    openvoice = attempts[-1]
    openvoice_preview_completed = (
        openvoice in valid_changed_attempts
        and openvoice["end_triggered"] is True
        and judgment_by_model["openvoice-v2"]["audible_changed_output"] is True
    )
    accepted_stale_frames = sum(
        value["stale_output_accepted"] is True for value in attempts
    )
    exclusive_playout = all(
        value["exclusive_playout_observed"] is True for value in attempts
    )
    failure_event = _object(receipt_document["forced_failure_event"], "failure event")
    fallback_event = _object(
        receipt_document["native_fallback_event"], "fallback event"
    )
    fallback_observed = (
        failure_event["failure_injected"] is True
        and failure_event["fallback_required_observed"] is True
        and fallback_event["native_route_active"] is True
        and fallback_event["remote_route_active"] is False
    )
    operator_access_assertions = all(
        manual_audible_judgments.document.get(field_name) is True
        for field_name in (
            "chatgpt_account_authenticated_asserted",
            "ssh_tunnel_established_asserted",
            "ssh_pinned_server_identity_verified_asserted",
        )
    )
    technical_passed = (
        live_machine_changed >= 2
        and live_audible_changed >= 2
        and openvoice_preview_completed
        and accepted_stale_frames == 0
        and exclusive_playout
        and fallback_observed
        and operator_access_assertions
    )
    report_attempts = [
        {
            **attempt,
            "audible_changed_output": judgment_by_model[attempt["model_id"]][
                "audible_changed_output"
            ],
        }
        for attempt in attempts
    ]
    return _report_document(
        roster=roster,
        prompt_plan=prompt_plan,
        git_commit=git_commit,
        worktree_clean=worktree_clean,
        evidence_kind="runtime_receipt",
        technical_outcome="passed" if technical_passed else "failed",
        attempts=report_attempts,
        runtime_receipt=receipt_document,
        manual_audible_judgments=manual_audible_judgments.document,
        metrics={
            "prepared_models_attempted": 4,
            "live_profiles_with_finite_changed_output": live_machine_changed,
            "live_profiles_with_audible_changed_output": live_audible_changed,
            "openvoice_buffered_preview_completed": openvoice_preview_completed,
            "accepted_stale_frames": accepted_stale_frames,
            "exclusive_playout_for_all_attempts": exclusive_playout,
            "forced_failure_native_fallback": fallback_observed,
        },
    )


def _report_document(
    *,
    roster: Roster,
    prompt_plan: PromptPlan,
    git_commit: str,
    worktree_clean: bool,
    evidence_kind: str,
    technical_outcome: str,
    attempts: list[dict[str, object]],
    runtime_receipt: dict[str, object] | None,
    manual_audible_judgments: dict[str, object] | None,
    metrics: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "experiment_id": "EXP-005",
        "evidence_scope": "technical_extension_multimodel_mvp",
        "evidence_kind": evidence_kind,
        "decision_status": "inconclusive",
        "technical_outcome": technical_outcome,
        "commit": git_commit,
        "worktree_clean": worktree_clean,
        "roster": roster.document(),
        "prompt_plan": prompt_plan.document(),
        "attempts": attempts,
        "runtime_receipt": runtime_receipt,
        "manual_audible_judgments": manual_audible_judgments,
        "metrics": metrics,
        "claims": {
            "voice_conversion_established": False,
            "speaker_change_established": False,
            "japanese_quality_established": False,
            "content_preservation_established": False,
            "latency_target_established": False,
            "authorization_established": False,
            "license_established": False,
            "security_established": False,
            "production_readiness_established": False,
        },
    }


def _contract_attempt_document(
    entry: RosterEntry, observation: AttemptObservation
) -> dict[str, object]:
    return {
        "model_id": entry.model_id,
        "profile_id": entry.profile_id,
        "profile_hash": entry.profile_hash,
        "configuration_hash": entry.configuration_hash,
        "route_mode": entry.route_mode,
        "pipeline_id": None,
        "generation_id": None,
        "finite_output_observed": observation.finite_output_observed,
        "changed_output_observed": observation.changed_output_observed,
        "stale_output_accepted": observation.stale_output_accepted,
        "exclusive_playout_observed": observation.exclusive_playout_observed,
        "end_triggered": observation.end_triggered,
        "audible_changed_output": None,
    }


def _validate_prompt_sequence(sequence: list[object]) -> tuple[str, ...]:
    expected_steps = (
        ("native-baseline", "native", "start_end"),
        ("rvc-v2-trial", "rvc-v2", "start_end_next"),
        ("beatrice-2-trial", "beatrice-2", "start_end_next"),
        ("x-vc-trial", "x-vc", "start_end_next"),
        ("openvoice-v2-preview", "openvoice-v2", "start_end"),
        ("forced-native-fallback", "openvoice-v2", "next_inject_failure"),
    )
    model_ids: list[str] = []
    for index, (value, expected_step) in enumerate(
        zip(sequence, expected_steps, strict=True)
    ):
        if not isinstance(value, dict):
            raise EvidenceValidationError(f"prompt plan step {index} must be an object")
        _reject_forbidden_keys(value)
        step_id, route_or_model, control = expected_step
        if (
            value.get("step_id") != step_id
            or value.get("generation_control") != control
        ):
            raise EvidenceValidationError(
                "prompt plan step does not match the frozen sequence"
            )
        if route_or_model == "native":
            if (
                set(value) != {"step_id", "route", "generation_control"}
                or value.get("route") != "native"
            ):
                raise EvidenceValidationError("prompt plan native step is invalid")
        elif (
            set(value) != {"step_id", "model_id", "generation_control"}
            or value.get("model_id") != route_or_model
        ):
            raise EvidenceValidationError("prompt plan model step is invalid")
        elif index < len(_MODEL_ORDER) + 1:
            model_ids.append(route_or_model)
    return tuple(model_ids)


def _load_entry(value: object, index: int) -> RosterEntry:
    if not isinstance(value, dict):
        raise EvidenceValidationError(f"roster entry {index} must be an object")
    _reject_forbidden_keys(value)
    expected = {
        "model_id",
        "profile_id",
        "execution_state",
        "route_mode",
        "profile_hash",
        "configuration_hash",
    }
    if set(value) != expected:
        raise EvidenceValidationError(f"roster entry {index} has unsupported metadata")
    model_id = value["model_id"]
    profile_id = value["profile_id"]
    execution_state = value["execution_state"]
    route_mode = value["route_mode"]
    if not isinstance(model_id, str) or model_id not in _MODEL_ORDER:
        raise EvidenceValidationError(f"roster entry {index} model_id is invalid")
    if not isinstance(profile_id, str) or _PROFILE_ID.fullmatch(profile_id) is None:
        raise EvidenceValidationError(f"roster entry {index} profile_id is invalid")
    if execution_state != "prepared":
        raise EvidenceValidationError(f"roster entry {index} must be prepared")
    if not isinstance(route_mode, str):
        raise EvidenceValidationError(f"roster entry {index} route_mode is invalid")
    return RosterEntry(
        model_id=model_id,
        profile_id=profile_id,
        execution_state=execution_state,
        route_mode=route_mode,
        profile_hash=_require_sha256(value["profile_hash"], "profile_hash"),
        configuration_hash=_require_sha256(
            value["configuration_hash"], "configuration_hash"
        ),
    )


def _load_runtime_attempt(
    value: object, *, index: int, roster_entry: RosterEntry
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EvidenceValidationError(f"runtime attempt {index} must be an object")
    _reject_forbidden_keys(value)
    expected = {
        "model_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "route_mode",
        "pipeline_id",
        "generation_id",
        "finite_output_observed",
        "changed_output_observed",
        "stale_output_accepted",
        "exclusive_playout_observed",
        "end_triggered",
    }
    if set(value) != expected:
        raise EvidenceValidationError(
            f"runtime attempt {index} has unsupported metadata"
        )
    for field_name, expected_value in (
        ("model_id", roster_entry.model_id),
        ("profile_id", roster_entry.profile_id),
        ("profile_hash", roster_entry.profile_hash),
        ("configuration_hash", roster_entry.configuration_hash),
        ("route_mode", roster_entry.route_mode),
    ):
        if value[field_name] != expected_value:
            raise EvidenceValidationError(
                f"runtime attempt {index} {field_name} does not bind the roster"
            )
    pipeline_id = _require_uuid(value["pipeline_id"], "pipeline_id")
    generation_id = _require_generation_id(value["generation_id"])
    for field_name in (
        "finite_output_observed",
        "changed_output_observed",
        "stale_output_accepted",
        "exclusive_playout_observed",
        "end_triggered",
    ):
        if not isinstance(value[field_name], bool):
            raise EvidenceValidationError(
                f"runtime attempt {index} {field_name} must be boolean"
            )
    if roster_entry.route_mode == _OPENVOICE_MODE:
        if value["end_triggered"] is not True:
            raise EvidenceValidationError(
                "OpenVoice runtime attempt must be End-triggered"
            )
    elif value["end_triggered"] is not False:
        raise EvidenceValidationError("live runtime attempt cannot be End-triggered")
    return {
        "model_id": roster_entry.model_id,
        "profile_id": roster_entry.profile_id,
        "profile_hash": roster_entry.profile_hash,
        "configuration_hash": roster_entry.configuration_hash,
        "route_mode": roster_entry.route_mode,
        "pipeline_id": pipeline_id,
        "generation_id": generation_id,
        "finite_output_observed": value["finite_output_observed"],
        "changed_output_observed": value["changed_output_observed"],
        "stale_output_accepted": value["stale_output_accepted"],
        "exclusive_playout_observed": value["exclusive_playout_observed"],
        "end_triggered": value["end_triggered"],
    }


def _load_forced_failure_event(
    value: object, attempts: list[dict[str, object]]
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "event_type",
        "model_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "pipeline_id",
        "generation_id",
        "failure_injected",
        "fallback_required_observed",
    }:
        raise EvidenceValidationError("forced failure event is invalid")
    if value["event_type"] != "fallback.required":
        raise EvidenceValidationError("forced failure event must be fallback.required")
    if (
        value["failure_injected"] is not True
        or value["fallback_required_observed"] is not True
    ):
        raise EvidenceValidationError("forced failure facts are incomplete")
    openvoice_attempt = attempts[-1]
    for key in (
        "model_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "pipeline_id",
    ):
        if value[key] != openvoice_attempt[key]:
            raise EvidenceValidationError(
                "forced failure event does not bind the OpenVoice profile context"
            )
    generation_id = _require_generation_id(value["generation_id"])
    if generation_id <= max(attempt["generation_id"] for attempt in attempts):
        raise EvidenceValidationError(
            "forced failure probe must use a post-attempt generation"
        )
    return {**value, "generation_id": generation_id}


def _load_native_fallback_event(
    value: object, forced_failure: dict[str, object]
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "event_type",
        "model_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "pipeline_id",
        "generation_id",
        "native_route_active",
        "remote_route_active",
    }:
        raise EvidenceValidationError("native fallback event is invalid")
    if value["event_type"] != "extension.native_fallback_activated":
        raise EvidenceValidationError("native fallback event type is invalid")
    for key in (
        "model_id",
        "profile_id",
        "profile_hash",
        "configuration_hash",
        "pipeline_id",
        "generation_id",
    ):
        if value[key] != forced_failure[key]:
            raise EvidenceValidationError(
                "native fallback event does not bind the forced failure"
            )
    if (
        value["native_route_active"] is not True
        or value["remote_route_active"] is not False
    ):
        raise EvidenceValidationError(
            "native fallback did not restore exclusive native"
        )
    return dict(value)


def _require_true_facts(value: object, label: str, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise EvidenceValidationError(f"{label} facts are invalid")
    if any(value[field] is not True for field in expected):
        raise EvidenceValidationError(f"{label} facts are incomplete")


def _require_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise EvidenceValidationError(
            f"{field_name} must be a lowercase sha256 identity"
        )
    return value


def _require_uuid(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _UUID.fullmatch(value) is None:
        raise EvidenceValidationError(f"{field_name} must be a canonical UUID")
    return value


def _require_generation_id(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= 2**32 - 1
    ):
        raise EvidenceValidationError("generation_id must be a protocol-v1 unsigned ID")
    return value


def _load_json_object(source: Path, label: str) -> dict[str, object]:
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(f"cannot load {label}: {source.name}") from error
    if not isinstance(raw, dict):
        raise EvidenceValidationError(f"{label} must be an object")
    return raw


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EvidenceValidationError(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise EvidenceValidationError(f"{label} must be a list of objects")
    return value


def _without(value: Mapping[str, object], field_name: str) -> dict[str, object]:
    return {key: nested for key, nested in value.items() if key != field_name}


def content_digest(value: Mapping[str, object]) -> str:
    """Return the documented canonical SHA-256 for a frozen safe JSON object."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise EvidenceValidationError(
            "revision input cannot be canonically encoded"
        ) from error
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _reject_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or _FORBIDDEN_KEY.search(key):
                raise EvidenceValidationError(f"forbidden metadata key: {key!r}")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested)


def load_schema() -> dict[str, object]:
    return json.loads(Path(__file__).with_name("report.schema.json").read_text("utf-8"))


def verify_clean_checkout(*, repository: Path, git_commit: str) -> None:
    if _COMMIT.fullmatch(git_commit) is None:
        raise EvidenceValidationError(
            "report requires a lowercase 40-character Git commit"
        )
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise EvidenceValidationError("cannot verify the Git checkout") from error
    if head != git_commit or status:
        raise EvidenceValidationError(
            "report requires an exact clean checked-out commit"
        )
