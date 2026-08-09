from __future__ import annotations

import json
import math
import os
import platform
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import RouteValidationError
from .registry import RegistryProfile

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_FORBIDDEN_KEY = re.compile(
    r"(^|_)(api_?key|authorization|bearer|credential|password|private_?key|"
    r"raw_?audio|secret|ticket|token|voice_?id|worker_?endpoint|"
    r"registry_?path|pcm_?payload|raw_?samples)($|_)",
    re.IGNORECASE,
)
_MISSING_DECISION_LANES = (
    "frozen_japanese_corpus",
    "content_preservation_stt",
    "authorized_speaker_change_evidence",
    "voice_and_artifact_governance_approval",
    "audio_integrity_listening_lane",
    "cold_and_warm_latency_distributions",
    "repeated_sample_count_and_failure_rate",
    "client_playout_and_native_fallback",
    "independent_review",
)


class MonotonicClock(Protocol):
    def monotonic_ns(self) -> int: ...


class SystemClock:
    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


@dataclass(slots=True)
class SteppingClock:
    current_ns: int = 1_000_000_000
    step_ns: int = 1_000_000

    def monotonic_ns(self) -> int:
        value = self.current_ns
        self.current_ns += self.step_ns
        return value


def _json_value(value: object, *, location: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RouteValidationError(f"non-finite trace value at {location}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RouteValidationError(f"non-text trace key at {location}")
            if _FORBIDDEN_KEY.search(key):
                raise RouteValidationError(
                    f"sensitive trace key is forbidden at {location}.{key}"
                )
            result[key] = _json_value(item, location=f"{location}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        return [
            _json_value(item, location=f"{location}[{index}]")
            for index, item in enumerate(value)
        ]
    raise RouteValidationError(
        f"unsupported trace value {type(value).__name__} at {location}"
    )


class TraceRecorder:
    """Metadata-only technical trace that can never declare an EXP-003 winner."""

    def __init__(
        self,
        profiles: Sequence[RegistryProfile],
        registry_document_hash: str,
        *,
        clock: MonotonicClock | None = None,
        client_clock_id: str = "exp003-client-monotonic",
        git_commit: str = "unrecorded",
        worktree_clean: bool = False,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", client_clock_id):
            raise ValueError("client_clock_id has an invalid format")
        self.clock = clock or SystemClock()
        self.client_clock_id = client_clock_id
        self._profiles = [
            _json_value(profile.safe_metadata(), location="profiles")
            for profile in profiles
        ]
        self.registry_document_hash = registry_document_hash
        self.git_commit = git_commit
        self.worktree_clean = worktree_clean
        self._events: list[dict[str, JsonValue]] = []
        self._results: list[dict[str, JsonValue]] = []
        self._technical_outcome = "not_run"

    @staticmethod
    def _case_id(value: str) -> str:
        if not value or len(value.encode("utf-8")) > 384:
            raise RouteValidationError("trace case_id must contain 1 to 384 bytes")
        return value

    def record(self, case_id: str, kind: str, details: Mapping[str, object]) -> None:
        self._events.append(
            {
                "index": len(self._events),
                "case_id": self._case_id(case_id),
                "kind": kind,
                "client_time": {
                    "clock_id": self.client_clock_id,
                    "monotonic_ns": self.clock.monotonic_ns(),
                },
                "details": _json_value(details, location="details"),
            }
        )

    def add_result(
        self, case_id: str, *, passed: bool, evidence: Mapping[str, object]
    ) -> None:
        if any(item["case_id"] == case_id for item in self._results):
            raise RouteValidationError(f"duplicate case result: {case_id}")
        self._results.append(
            {
                "case_id": self._case_id(case_id),
                "passed": passed,
                "evidence": _json_value(evidence, location="evidence"),
            }
        )

    def finish(self, passed: bool) -> None:
        self._technical_outcome = "passed" if passed else "failed"

    def document(self) -> dict[str, JsonValue]:
        completed = [str(item["case_id"]) for item in self._results]
        return {
            "schema_version": 1,
            "experiment_id": "EXP-003",
            "evidence_scope": "technical_route_smoke",
            "decision_status": "inconclusive",
            "technical_outcome": self._technical_outcome,
            "coverage": {
                "full_experiment_eligible": False,
                "completed_case_ids": completed,
                "missing_decision_lanes": list(_MISSING_DECISION_LANES),
            },
            "claims": {
                "voice_conversion_established": False,
                "speaker_change_established": False,
                "japanese_quality_established": False,
                "content_preservation_established": False,
                "latency_target_established": False,
                "production_readiness_established": False,
            },
            "environment": {
                "runner_revision": "0.1.0",
                "python_version": platform.python_version(),
                "platform_system": platform.system(),
                "platform_machine": platform.machine(),
                "git_commit": self.git_commit,
                "worktree_clean": self.worktree_clean,
            },
            "registry_document_hash": self.registry_document_hash,
            "client_clock_id": self.client_clock_id,
            "profiles": list(self._profiles),
            "events": list(self._events),
            "results": list(self._results),
        }

    def to_json(self) -> str:
        return (
            json.dumps(
                self.document(),
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )

    def write(self, destination: Path) -> Path:
        resolved = destination.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        temporary = resolved.with_name(f".{resolved.name}.tmp")
        temporary.write_text(self.to_json(), encoding="utf-8")
        os.replace(temporary, resolved)
        return resolved
