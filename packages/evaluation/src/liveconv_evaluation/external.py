"""Strict, render-bound ingestion for independently produced evidence lanes."""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import math
import re
from functools import cache
from pathlib import Path
from typing import Any

from .verdict import LaneVerdict, VerdictStatus, _validated_external_lane

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODEL_REVISION_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}@sha256:([0-9a-f]{64})$"
)
_EVALUATOR_REVISION_RE = re.compile(
    r"(?:^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}==[0-9]+(?:\.[0-9]+){1,3}$)"
    r"|(?:^[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}@sha256:[0-9a-f]{64}$)"
)
_PACKAGE_VERSION_RE = re.compile(r"^[0-9][A-Za-z0-9_.+\-]*$")
_SPEAKER_RUNTIME_LOCK_SHA256 = (
    "036443cefaffc07492b31078f861d7bd5c816b96007819c63323968089760fd3"
)
REVIEWED_TARGET_REGISTRY_SHA256 = (
    "2f17c9c58604f9fdb698ebe1abf58936a6e4c6e2e1eab77d5a03aa677edf25a9"
)
_INTEGRITY_CANONICALIZATION = "utf8-json-sort-keys-compact-excluding-integrity-v1"
_REVIEWED_RECORD_FIELDS = {
    "schema_version",
    "record_type",
    "type",
    "authorization_id",
    "status",
    "owner",
    "permitted_purpose",
    "retention_policy",
    "deletion_path",
    "target_artifact_sha256",
    "source_id",
}


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has missing or unknown fields")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


def _lane(value: Any, *, evidence_count: int | None = None) -> LaneVerdict:
    lane = _object(value, {"status", "summary", "evidence"}, "evaluation lane")
    summary = _string(lane["summary"], "evaluation lane summary")
    evidence = lane["evidence"]
    if not isinstance(evidence, list) or any(
        not isinstance(item, str) or not item.strip() for item in evidence
    ):
        raise ValueError("evaluation lane evidence must contain non-empty strings")
    try:
        status = VerdictStatus(lane["status"])
    except (TypeError, ValueError):
        raise ValueError("evaluation lane status is invalid") from None
    if status is VerdictStatus.UNASSESSED or not evidence:
        raise ValueError("external lane evidence must be assessed and non-empty")
    if evidence_count is not None and len(evidence) != evidence_count:
        raise ValueError("evaluation lane evidence count is invalid")
    return LaneVerdict(status, summary, tuple(evidence))


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("reviewed authorization is not canonical JSON") from None
    return hashlib.sha256(encoded).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("evidence JSON contains duplicate fields")
        value[key] = child
    return value


def _decode_json(content: str, label: str) -> Any:
    try:
        return json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"invalid JSON number: {constant}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError, ValueError):
        raise ValueError(f"{label} is invalid JSON") from None


def _read_json(path: Path, label: str) -> Any:
    if path.is_symlink():
        raise ValueError(f"{label} must be a regular non-symlink file")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} must be a regular non-symlink file")
    try:
        return _decode_json(resolved.read_text(encoding="utf-8"), label)
    except UnicodeError:
        raise ValueError(f"{label} is invalid JSON") from None


@cache
def _reviewed_authorizations() -> tuple[dict[str, Any], ...]:
    resource = importlib.resources.files("liveconv_evaluation").joinpath(
        "authorizations/reviewed-targets.json"
    )
    registry_bytes = resource.read_bytes()
    if hashlib.sha256(registry_bytes).hexdigest() != REVIEWED_TARGET_REGISTRY_SHA256:
        raise ValueError("reviewed target registry code-bound digest is invalid")
    try:
        registry = _decode_json(
            registry_bytes.decode("utf-8"), "reviewed target registry"
        )
    except UnicodeError:
        raise ValueError("reviewed target registry is invalid JSON") from None
    _object(
        registry,
        {"schema_version", "registry_type", "records", "integrity"},
        "reviewed target registry",
    )
    if (
        registry["schema_version"] != 1
        or registry["registry_type"] != "liveconv-reviewed-target-authorizations"
    ):
        raise ValueError("reviewed target registry identity is invalid")
    integrity = _object(
        registry["integrity"],
        {"algorithm", "canonicalization", "sha256"},
        "reviewed target registry integrity",
    )
    if (
        integrity["algorithm"] != "sha256"
        or integrity["canonicalization"] != _INTEGRITY_CANONICALIZATION
    ):
        raise ValueError("reviewed target registry integrity policy is invalid")
    expected = _sha256(integrity["sha256"], "reviewed target registry digest")
    unsigned = {key: child for key, child in registry.items() if key != "integrity"}
    if _canonical_digest(unsigned) != expected:
        raise ValueError("reviewed target registry integrity digest is invalid")
    records = registry["records"]
    if not isinstance(records, list) or not records:
        raise ValueError("reviewed target registry must contain records")
    validated: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str]] = set()
    digests: set[str] = set()
    for value in records:
        record = _object(value, _REVIEWED_RECORD_FIELDS, "reviewed target record")
        if (
            record["schema_version"] != 1
            or record["record_type"] != "reviewed-target-authorization"
            or record["type"]
            not in {"target-voice-authorization", "synthetic-corpus-manifest"}
            or record["status"] != "approved"
        ):
            raise ValueError("reviewed target record identity is invalid")
        for field in (
            "authorization_id",
            "owner",
            "permitted_purpose",
            "retention_policy",
            "deletion_path",
            "source_id",
        ):
            _string(record[field], f"reviewed target {field}")
        target_digest = _sha256(
            record["target_artifact_sha256"], "reviewed target artifact digest"
        )
        identity = (record["type"], record["authorization_id"], target_digest)
        record_digest = _canonical_digest(record)
        if identity in identities or record_digest in digests:
            raise ValueError("reviewed target registry contains duplicate records")
        identities.add(identity)
        digests.add(record_digest)
        validated.append(record)
    return tuple(validated)


def _validate_reviewed_authorization(
    authorization: dict[str, Any], *, target_sha256: str
) -> None:
    record_digest = _sha256(
        authorization["record_sha256"], "target authorization record digest"
    )
    matches = [
        record
        for record in _reviewed_authorizations()
        if record["type"] == authorization["type"]
        and record["authorization_id"] == authorization["authorization_id"]
        and record["target_artifact_sha256"] == target_sha256
        and _canonical_digest(record) == record_digest
    ]
    if len(matches) != 1:
        raise ValueError("speaker target authorization is not package-reviewed")


def _runtime_lock(value: Any, *, speaker: bool) -> dict[str, Any]:
    runtime = _object(value, {"revision", "sha256", "packages"}, "runtime lock")
    revision = _string(runtime["revision"], "runtime lock revision")
    _sha256(runtime["sha256"], "runtime lock digest")
    packages = runtime["packages"]
    if (
        not isinstance(packages, dict)
        or not packages
        or any(
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(version, str)
            or not version.strip()
            for name, version in packages.items()
        )
    ):
        raise ValueError("runtime lock packages must bind non-empty versions")
    if speaker:
        if revision != "liveconv-speaker-hash-locked-runtime-v1":
            raise ValueError("speaker runtime lock revision is invalid")
        if packages.get("speechbrain") != "1.0.3":
            raise ValueError("speaker runtime does not bind SpeechBrain")
        if runtime["sha256"] != _SPEAKER_RUNTIME_LOCK_SHA256:
            raise ValueError("speaker runtime lock digest is not approved")
        if packages.get("requests") != "2.32.5":
            raise ValueError("speaker runtime does not bind required HTTP support")
        if packages.get("torch") != "2.6.0" or packages.get("torchaudio") != "2.6.0":
            raise ValueError("speaker Torch and TorchAudio releases are invalid")
        if len(packages) < 4 or any(
            _PACKAGE_VERSION_RE.fullmatch(version) is None
            for version in packages.values()
        ):
            raise ValueError("speaker runtime package versions are invalid")
    return runtime


def _audio_artifact(value: Any, label: str) -> dict[str, Any]:
    artifact = _object(
        value,
        {
            "sha256",
            "bytes",
            "duration_seconds",
            "sample_rate_hz",
            "channels",
            "sample_width_bytes",
        },
        label,
    )
    _sha256(artifact["sha256"], f"{label} digest")
    for field in ("bytes", "sample_rate_hz", "channels", "sample_width_bytes"):
        if (
            isinstance(artifact[field], bool)
            or not isinstance(artifact[field], int)
            or artifact[field] <= 0
        ):
            raise ValueError(f"{label} {field} must be positive")
    if artifact["bytes"] < 45:
        raise ValueError(f"{label} bytes must contain a WAV header and sample")
    duration = artifact["duration_seconds"]
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise ValueError(f"{label} duration must be positive")
    if artifact["sample_width_bytes"] != 2:
        raise ValueError(f"{label} must be PCM16")
    return artifact


def load_speaker_lane(
    path: Path | None, *, source_sha256: str, output_sha256: str
) -> LaneVerdict | None:
    if path is None:
        return None
    value = _read_json(path, "speaker evidence envelope")
    report = _object(
        value,
        {
            "schema_version",
            "report_type",
            "evaluator",
            "artifacts",
            "target_authorization",
            "policy",
            "speaker_change",
            "evaluation_lane",
            "limitations",
        },
        "speaker evidence envelope",
    )
    if (
        report["schema_version"] != 1
        or report["report_type"] != "speaker-change-evidence"
    ):
        raise ValueError("speaker evidence report type or schema version is invalid")
    lane = _lane(report["evaluation_lane"], evidence_count=3)

    evaluator = _object(
        report["evaluator"],
        {
            "implementation",
            "model_revision",
            "model_sha256",
            "runtime_lock",
            "device",
            "embedding_dimensions",
            "embeddings_persisted",
        },
        "speaker evaluator",
    )
    if (
        evaluator["implementation"] != "liveconv-speaker-ecapa-v1"
        or evaluator["device"] not in {"cpu", "cuda"}
        or evaluator["embedding_dimensions"] != 192
        or evaluator["embeddings_persisted"] is not False
    ):
        raise ValueError("speaker evaluator identity or configuration is invalid")
    model_sha256 = _sha256(evaluator["model_sha256"], "speaker model digest")
    revision = evaluator["model_revision"]
    match = (
        _MODEL_REVISION_RE.fullmatch(revision) if isinstance(revision, str) else None
    )
    if match is None or match.group(1) != model_sha256:
        raise ValueError("speaker model revision is not bound to its artifact")
    _runtime_lock(evaluator["runtime_lock"], speaker=True)

    artifacts = _object(
        report["artifacts"], {"source", "target", "output"}, "speaker artifacts"
    )
    for role in ("source", "target", "output"):
        _audio_artifact(artifacts[role], f"speaker {role} artifact")
    if artifacts["source"]["sha256"] != source_sha256:
        raise ValueError("speaker evidence source artifact does not match render")
    if artifacts["output"]["sha256"] != output_sha256:
        raise ValueError("speaker evidence output artifact does not match render")

    authorization = _object(
        report["target_authorization"],
        {
            "type",
            "authorization_id",
            "record_sha256",
            "target_artifact_sha256",
            "status",
        },
        "target authorization",
    )
    if (
        authorization["type"]
        not in {
            "target-voice-authorization",
            "synthetic-corpus-manifest",
        }
        or authorization["status"] != "approved"
    ):
        raise ValueError("speaker target is not authorized")
    _string(authorization["authorization_id"], "target authorization id")
    if (
        _sha256(
            authorization["target_artifact_sha256"],
            "authorized target artifact digest",
        )
        != artifacts["target"]["sha256"]
    ):
        raise ValueError("target authorization does not match speaker target")
    _validate_reviewed_authorization(
        authorization, target_sha256=artifacts["target"]["sha256"]
    )

    policy = _object(
        report["policy"],
        {
            "label",
            "status",
            "min_target_similarity",
            "min_target_gain",
            "min_target_advantage",
        },
        "speaker policy",
    )
    _string(policy["label"], "speaker policy label")
    if policy["status"] not in {"proposed", "approved"}:
        raise ValueError("speaker policy status is invalid")
    for field in (
        "min_target_similarity",
        "min_target_gain",
        "min_target_advantage",
    ):
        threshold = policy[field]
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not -1 <= threshold <= 1
        ):
            raise ValueError("speaker policy thresholds are invalid")
    if lane.status is VerdictStatus.PASS and policy["status"] != "approved":
        raise ValueError("proposed speaker policy cannot supply passing evidence")

    comparison = _object(
        report["speaker_change"],
        {
            "source_to_target",
            "source_to_output",
            "target_to_output",
            "target_similarity_gain",
            "target_advantage",
            "status",
            "evidence",
        },
        "speaker comparison",
    )
    if comparison["status"] != lane.status.value or comparison["evidence"] != list(
        lane.evidence
    ):
        raise ValueError("speaker comparison and evaluation lane disagree")
    for field in ("source_to_target", "source_to_output", "target_to_output"):
        metric = comparison[field]
        if (
            isinstance(metric, bool)
            or not isinstance(metric, (int, float))
            or not math.isfinite(metric)
            or not -1 <= metric <= 1
        ):
            raise ValueError("speaker comparison metrics are invalid")
    for field in ("target_similarity_gain", "target_advantage"):
        metric = comparison[field]
        if (
            isinstance(metric, bool)
            or not isinstance(metric, (int, float))
            or not math.isfinite(metric)
            or not -2 <= metric <= 2
        ):
            raise ValueError("speaker comparison derived metrics are invalid")
    expected_gain = comparison["target_to_output"] - comparison["source_to_target"]
    expected_advantage = comparison["target_to_output"] - comparison["source_to_output"]
    if not math.isclose(
        comparison["target_similarity_gain"], expected_gain, abs_tol=1e-12
    ) or not math.isclose(
        comparison["target_advantage"], expected_advantage, abs_tol=1e-12
    ):
        raise ValueError("speaker comparison derived metrics are inconsistent")
    passed = (
        comparison["target_to_output"] >= policy["min_target_similarity"]
        and comparison["target_similarity_gain"] >= policy["min_target_gain"]
        and comparison["target_advantage"] >= policy["min_target_advantage"]
    )
    if (lane.status is VerdictStatus.PASS) != passed:
        raise ValueError("speaker comparison status does not match policy thresholds")
    limitations = report["limitations"]
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(item, str) or not item.strip() for item in limitations)
    ):
        raise ValueError("speaker evidence limitations are missing")

    provenance = {
        "schema_version": report["schema_version"],
        "report_type": report["report_type"],
        "binding": {
            "verified": True,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
        },
        "evaluator": evaluator,
        "artifacts": artifacts,
        "target_authorization": authorization,
        "policy": policy,
    }
    return _validated_external_lane(lane, provenance)


def load_streaming_lane(
    path: Path | None, *, source_sha256: str, output_sha256: str
) -> LaneVerdict | None:
    if path is None:
        return None
    value = _read_json(path, "streaming evidence envelope")
    report = _object(
        value,
        {
            "schema_version",
            "report_type",
            "evaluator",
            "artifacts",
            "policy",
            "streaming_operations",
            "evaluation_lane",
            "limitations",
        },
        "streaming evidence envelope",
    )
    if (
        report["schema_version"] != 1
        or report["report_type"] != "streaming-operations-evidence"
    ):
        raise ValueError("streaming evidence report type or schema version is invalid")
    lane = _lane(report["evaluation_lane"])
    evaluator = _object(
        report["evaluator"],
        {"implementation", "revision", "runtime_lock"},
        "streaming evaluator",
    )
    _string(evaluator["implementation"], "streaming evaluator implementation")
    revision = evaluator["revision"]
    if (
        not isinstance(revision, str)
        or _EVALUATOR_REVISION_RE.fullmatch(revision) is None
    ):
        raise ValueError("streaming evaluator revision must be immutable")
    _runtime_lock(evaluator["runtime_lock"], speaker=False)

    artifacts = _object(
        report["artifacts"], {"source_sha256", "output_sha256"}, "streaming artifacts"
    )
    if _sha256(artifacts["source_sha256"], "streaming source digest") != source_sha256:
        raise ValueError("streaming evidence source artifact does not match render")
    if _sha256(artifacts["output_sha256"], "streaming output digest") != output_sha256:
        raise ValueError("streaming evidence output artifact does not match render")

    policy = _object(report["policy"], {"label", "status"}, "streaming policy")
    _string(policy["label"], "streaming policy label")
    if policy["status"] not in {"proposed", "approved"}:
        raise ValueError("streaming policy status is invalid")
    if lane.status is VerdictStatus.PASS and policy["status"] != "approved":
        raise ValueError("proposed streaming policy cannot supply passing evidence")

    operations = _object(
        report["streaming_operations"],
        {"trace_sha256", "checks"},
        "streaming operations",
    )
    _sha256(operations["trace_sha256"], "streaming trace digest")
    checks = _object(
        operations["checks"],
        {"bounded_queues", "stale_generation_discard", "interruption_cancel"},
        "streaming checks",
    )
    if any(not isinstance(value, bool) for value in checks.values()):
        raise ValueError("streaming checks must be boolean")
    if lane.status is VerdictStatus.PASS and not all(checks.values()):
        raise ValueError("passing streaming evidence has failed checks")
    limitations = report["limitations"]
    if (
        not isinstance(limitations, list)
        or not limitations
        or any(not isinstance(item, str) or not item.strip() for item in limitations)
    ):
        raise ValueError("streaming evidence limitations are missing")

    provenance = {
        "schema_version": report["schema_version"],
        "report_type": report["report_type"],
        "binding": {
            "verified": True,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
        },
        "evaluator": evaluator,
        "artifacts": artifacts,
        "policy": policy,
        "streaming_operations": operations,
    }
    return _validated_external_lane(lane, provenance)
