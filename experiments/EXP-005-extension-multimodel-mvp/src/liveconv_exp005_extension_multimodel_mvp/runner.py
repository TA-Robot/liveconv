from __future__ import annotations

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
_PROFILE_ID = re.compile(
    r"^vc\.(?:rvc-v2|beatrice-2|x-vc|openvoice-v2)\.[a-z0-9][a-z0-9.-]{0,63}\.v1$"
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
    pipeline_hash: str

    def document(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "profile_id": self.profile_id,
            "execution_state": self.execution_state,
            "route_mode": self.route_mode,
            "profile_hash": self.profile_hash,
            "configuration_hash": self.configuration_hash,
            "pipeline_hash": self.pipeline_hash,
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
    """One manual or deterministic metadata-only model invocation outcome."""

    audible_changed_output: bool
    end_triggered: bool = False
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ForcedFailureObservation:
    native_fallback_observed: bool
    native_remote_overlap_observed: bool = False


class ModelRoute(Protocol):
    def attempt(self, entry: RosterEntry) -> AttemptObservation: ...


@dataclass(slots=True)
class FakeRoute:
    """Deterministic route double; it carries outcomes but never media."""

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
    _attempts: dict[str, dict[str, object]] = field(default_factory=dict)
    _forced_failure: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if _COMMIT.fullmatch(self.git_commit) is None:
            raise EvidenceValidationError(
                "report requires a lowercase 40-character Git commit"
            )
        if self.prompt_plan.model_ids != tuple(
            entry.model_id for entry in self.roster.entries
        ):
            raise EvidenceValidationError("prompt plan does not bind the frozen roster")

    def record_manual_attempt(
        self, model_id: str, observation: AttemptObservation
    ) -> None:
        self._record_attempt(
            model_id, observation, observation_source="manual_operator"
        )

    def record_route_attempt(
        self, model_id: str, observation: AttemptObservation
    ) -> None:
        self._record_attempt(
            model_id, observation, observation_source="deterministic_fake"
        )

    def _record_attempt(
        self,
        model_id: str,
        observation: AttemptObservation,
        *,
        observation_source: str,
    ) -> None:
        entry = self.roster.entry(model_id)
        if model_id in self._attempts:
            raise EvidenceValidationError(f"duplicate model attempt: {model_id}")
        if observation.note is not None:
            raise EvidenceValidationError("free-form evidence is forbidden")
        if entry.route_mode == _OPENVOICE_MODE and not observation.end_triggered:
            raise EvidenceValidationError(
                "OpenVoice preview must be explicitly End-triggered"
            )
        if entry.route_mode == "live" and observation.end_triggered:
            raise EvidenceValidationError(
                "live route evidence cannot be represented as buffered"
            )
        self._attempts[model_id] = {
            "model_id": model_id,
            "route_mode": entry.route_mode,
            "attempted": True,
            "observation_source": observation_source,
            "audible_changed_output": observation.audible_changed_output,
            "end_triggered": observation.end_triggered,
        }

    def record_forced_failure(self, observation: ForcedFailureObservation) -> None:
        if observation.native_remote_overlap_observed:
            raise EvidenceValidationError(
                "forced fallback evidence cannot accept native and transformed overlap"
            )
        self._forced_failure = {
            "remote_failure_forced": True,
            "native_fallback_observed": observation.native_fallback_observed,
            "native_remote_overlap_observed": False,
        }

    def finish(self) -> dict[str, object]:
        if set(self._attempts) != set(_MODEL_ORDER):
            raise EvidenceValidationError(
                "all four roster entries must be invoked and attempted"
            )
        if self._forced_failure is None:
            raise EvidenceValidationError("one forced remote failure is required")
        attempts = [self._attempts[model_id] for model_id in _MODEL_ORDER]
        live_audible_profiles = sum(
            attempt["audible_changed_output"]
            for attempt in attempts
            if attempt["model_id"] in _LIVE_MODELS
        )
        openvoice_attempt = attempts[-1]
        fallback_observed = self._forced_failure["native_fallback_observed"] is True
        openvoice_preview_completed = (
            openvoice_attempt["end_triggered"] is True
            and openvoice_attempt["audible_changed_output"] is True
        )
        technical_passed = (
            live_audible_profiles >= 2
            and openvoice_preview_completed
            and fallback_observed
        )
        return {
            "schema_version": 1,
            "experiment_id": "EXP-005",
            "evidence_scope": "technical_extension_multimodel_mvp",
            "decision_status": "inconclusive",
            "technical_outcome": "passed" if technical_passed else "failed",
            "commit": self.git_commit,
            "worktree_clean": self.persisted_evidence_verified,
            "roster": self.roster.document(),
            "prompt_plan": self.prompt_plan.document(),
            "attempts": attempts,
            "metrics": {
                "prepared_models_attempted": len(attempts),
                "live_profiles_with_audible_changed_output": live_audible_profiles,
                "openvoice_buffered_preview_completed": openvoice_preview_completed,
                "accepted_stale_frames": 0,
                "forced_failure_native_fallback": fallback_observed,
            },
            "forced_failure": self._forced_failure,
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
    """Exercise the complete frozen roster against a deterministic metadata fake."""

    for entry in run.roster.entries:
        run.record_route_attempt(entry.model_id, route.attempt(entry))


def load_roster(source: Path) -> Roster:
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(f"cannot load roster: {source.name}") from error
    if not isinstance(raw, dict):
        raise EvidenceValidationError("roster must be an object")
    _reject_forbidden_keys(raw)
    if set(raw) != {"schema_version", "roster_revision", "entries"}:
        raise EvidenceValidationError("roster has unsupported metadata fields")
    if raw["schema_version"] != 1:
        raise EvidenceValidationError("roster schema_version must be 1")
    revision = _require_sha256(raw["roster_revision"], "roster_revision")
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
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(
            f"cannot load prompt plan: {source.name}"
        ) from error
    if not isinstance(raw, dict):
        raise EvidenceValidationError("prompt plan must be an object")
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


def _validate_prompt_sequence(sequence: list[object]) -> tuple[str, ...]:
    expected_steps = (
        ("native-baseline", "native", "start_end"),
        ("rvc-v2-trial", "rvc-v2", "start_end_next"),
        ("beatrice-2-trial", "beatrice-2", "start_end_next"),
        ("x-vc-trial", "x-vc", "start_end_next"),
        ("openvoice-v2-preview", "openvoice-v2", "start_end"),
        ("forced-native-fallback", "native", "interrupt"),
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
        else:
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
        "pipeline_hash",
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
        pipeline_hash=_require_sha256(value["pipeline_hash"], "pipeline_hash"),
    )


def _require_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise EvidenceValidationError(
            f"{field_name} must be a lowercase sha256 identity"
        )
    return value


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
