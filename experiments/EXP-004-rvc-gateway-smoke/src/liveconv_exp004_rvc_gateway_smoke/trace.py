from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .errors import RouteValidationError

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_FORBIDDEN_KEY = re.compile(
    r"(^|_)(api_?key|artifact|authorization|bearer|credential|directory|"
    r"endpoint|file|password|path|pcm|payload|private_?key|raw|runtime|"
    r"sample|secret|ticket|token|voice_?id|worker)($|_)",
    re.IGNORECASE,
)
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _json_value(value: object, *, location: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RouteValidationError(f"trace has a non-finite value at {location}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RouteValidationError(f"trace has a non-text key at {location}")
            if _FORBIDDEN_KEY.search(key):
                raise RouteValidationError(
                    f"trace key is forbidden at {location}.{key}"
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
        f"trace does not support {type(value).__name__} at {location}"
    )


@dataclass(slots=True)
class TraceRecorder:
    """A narrow metadata trace that cannot carry route inputs or secrets."""

    git_commit: str
    profile_id: str
    persisted_evidence_verified: bool = False
    profile_hash: str | None = None
    configuration_hash: str | None = None
    _results: list[dict[str, JsonValue]] = field(default_factory=list)
    _technical_outcome: str = "not_run"

    def __post_init__(self) -> None:
        if _COMMIT.fullmatch(self.git_commit) is None:
            raise ValueError("trace requires a verified lowercase Git commit")

    def set_profile_identity(
        self, *, profile_hash: str, configuration_hash: str
    ) -> None:
        self.profile_hash = profile_hash
        self.configuration_hash = configuration_hash

    def add_result(
        self, case_id: str, *, passed: bool, evidence: Mapping[str, object]
    ) -> None:
        if not re.fullmatch(r"[a-z0-9_.-]{1,96}", case_id):
            raise RouteValidationError("trace result ID is invalid")
        if any(item["case_id"] == case_id for item in self._results):
            raise RouteValidationError(f"duplicate trace result: {case_id}")
        self._results.append(
            {
                "case_id": case_id,
                "passed": passed,
                "evidence": _json_value(evidence, location=f"results.{case_id}"),
            }
        )

    def finish(self, passed: bool) -> None:
        self._technical_outcome = "passed" if passed else "failed"

    def document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": 1,
            "experiment_id": "EXP-004",
            "evidence_scope": "technical_rvc_gateway_smoke",
            "decision_status": "inconclusive",
            "technical_outcome": self._technical_outcome,
            "commit": self.git_commit,
            "worktree_clean": self.persisted_evidence_verified,
            "protocol_version": 1,
            "profile": {
                "profile_id": self.profile_id,
                "profile_hash": self.profile_hash,
                "configuration_hash": self.configuration_hash,
            },
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
        if not self.persisted_evidence_verified:
            raise RouteValidationError(
                "persisted trace requires exact clean Git commit verification"
            )
        resolved = destination.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        temporary = resolved.with_name(f".{resolved.name}.tmp")
        temporary.write_text(self.to_json(), encoding="utf-8")
        os.replace(temporary, resolved)
        return resolved
