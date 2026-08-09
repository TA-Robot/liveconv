from __future__ import annotations

import json
import math
import os
import platform
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import ExperimentFailure

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_FORBIDDEN_DETAIL_KEYS = frozenset(
    {
        "api_token",
        "authorization",
        "bearer",
        "credential",
        "raw_audio",
        "samples",
        "secret",
        "ticket",
        "token",
        "voice_reference",
    }
)
_MISSING_EXP_002_LANES = (
    "local_loopback_control",
    "40_frozen_japanese_fixtures",
    "600_eligible_turns_per_variant",
    "stt_kana_cer_and_exact_entities",
    "integrity_rate_and_confidence_interval",
    "paired_latency_distribution",
    "queue_overflow_fault",
    "model_timeout_fault",
    "worker_crash_fault",
)


class MonotonicClock(Protocol):
    def monotonic_ns(self) -> int: ...


class SystemMonotonicClock:
    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


@dataclass(slots=True)
class SteppingClock:
    """Deterministic monotonic clock for tests and scripted runs."""

    current_ns: int = 1_000_000_000
    step_ns: int = 1_000_000

    def monotonic_ns(self) -> int:
        value = self.current_ns
        self.current_ns += self.step_ns
        return value


def _normalize_json(value: object, *, path: str = "details") -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ExperimentFailure(f"non-finite trace value at {path}")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ExperimentFailure(f"trace key at {path} must be text")
            if key.lower() in _FORBIDDEN_DETAIL_KEYS:
                raise ExperimentFailure(
                    f"sensitive trace key is forbidden: {path}.{key}"
                )
            normalized[key] = _normalize_json(item, path=f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        return [
            _normalize_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise ExperimentFailure(
        f"unsupported trace value at {path}: {type(value).__name__}"
    )


class TraceRecorder:
    """Collect a canonical metadata-only trace using disjoint clock domains."""

    def __init__(
        self,
        client_clock_id: str,
        *,
        clock: MonotonicClock | None = None,
        git_commit: str = "unrecorded",
        worktree_clean: bool = False,
    ) -> None:
        if not client_clock_id or len(client_clock_id.encode("utf-8")) > 128:
            raise ValueError("client_clock_id must contain 1 to 128 UTF-8 bytes")
        self.client_clock_id = client_clock_id
        self.clock = clock or SystemMonotonicClock()
        self.git_commit = git_commit
        self.worktree_clean = worktree_clean
        self._events: list[dict[str, JsonValue]] = []
        self._results: list[dict[str, JsonValue]] = []
        self._server_clock_ids: set[str] = set()

    def register_server_clock(self, clock_id: str) -> None:
        if not clock_id:
            raise ExperimentFailure("server clock_id must not be empty")
        self._server_clock_ids.add(clock_id)

    def record(
        self,
        case_id: str,
        direction: str,
        kind: str,
        details: Mapping[str, object],
        *,
        server_clock_id: str | None = None,
        server_monotonic_ns: int | None = None,
    ) -> None:
        if direction not in {"client_to_server", "server_to_client", "local"}:
            raise ValueError(f"unsupported trace direction: {direction}")
        event: dict[str, JsonValue] = {
            "index": len(self._events),
            "case_id": case_id,
            "direction": direction,
            "kind": kind,
            "client_time": {
                "clock_id": self.client_clock_id,
                "monotonic_ns": self.clock.monotonic_ns(),
            },
            "details": _normalize_json(details),
        }
        if (server_clock_id is None) != (server_monotonic_ns is None):
            raise ExperimentFailure(
                "server clock_id and monotonic_ns must be recorded together"
            )
        if server_clock_id is not None and server_monotonic_ns is not None:
            if server_monotonic_ns < 0:
                raise ExperimentFailure("server monotonic_ns must be non-negative")
            self.register_server_clock(server_clock_id)
            event["server_time"] = {
                "clock_id": server_clock_id,
                "monotonic_ns": server_monotonic_ns,
            }
        self._events.append(event)

    def add_result(
        self,
        case_id: str,
        *,
        passed: bool,
        evidence: Mapping[str, object],
    ) -> None:
        if any(result["case_id"] == case_id for result in self._results):
            raise ExperimentFailure(f"duplicate result for case {case_id}")
        self._results.append(
            {
                "case_id": case_id,
                "passed": passed,
                "evidence": _normalize_json(evidence, path="evidence"),
            }
        )

    def document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": 1,
            "experiment_id": "EXP-002",
            "run_scope": "route_smoke_v1",
            "decision_status": "inconclusive",
            "coverage": {
                "full_experiment_eligible": False,
                "completed_case_ids": [
                    str(result["case_id"]) for result in self._results
                ],
                "missing_required_lanes": list(_MISSING_EXP_002_LANES),
            },
            "environment": {
                "runner_revision": "0.1.0",
                "python_version": platform.python_version(),
                "platform_system": platform.system(),
                "platform_machine": platform.machine(),
                "git_commit": self.git_commit,
                "worktree_clean": self.worktree_clean,
            },
            "client_clock_id": self.client_clock_id,
            "server_clock_ids": sorted(self._server_clock_ids),
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

    def write(self, path: str | Path) -> Path:
        destination = Path(path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(self.to_json(), encoding="utf-8")
        os.replace(temporary, destination)
        return destination
