from __future__ import annotations

import hashlib
import importlib.resources
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from .evidence import SpeakerEvidenceError

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_INTEGRITY_CANONICALIZATION = "utf8-json-sort-keys-compact-excluding-integrity-v1"
REVIEWED_TARGET_REGISTRY_SHA256 = (
    "2f17c9c58604f9fdb698ebe1abf58936a6e4c6e2e1eab77d5a03aa677edf25a9"
)
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


@dataclass(frozen=True, slots=True)
class TargetAuthorization:
    authorization_type: str
    authorization_id: str
    record_sha256: str
    target_artifact_sha256: str
    status: str = "approved"

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.authorization_type,
            "authorization_id": self.authorization_id,
            "record_sha256": self.record_sha256,
            "target_artifact_sha256": self.target_artifact_sha256,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ReviewedTarget:
    value: dict[str, Any]
    record_sha256: str


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise SpeakerEvidenceError(f"{label} has missing or unknown fields")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpeakerEvidenceError(f"{label} must be a non-empty string")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise SpeakerEvidenceError(f"{field} must be lowercase SHA-256")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SpeakerEvidenceError(f"{label} must be a positive integer")
    return value


def _positive_number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise SpeakerEvidenceError(f"{label} must be a positive finite number")
    return float(value)


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
        raise SpeakerEvidenceError("authorization data is not canonical JSON") from None
    return hashlib.sha256(encoded).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise SpeakerEvidenceError("authorization JSON contains duplicate fields")
        value[key] = child
    return value


def _decode_object(content: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"invalid JSON number: {constant}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError, ValueError):
        raise SpeakerEvidenceError(f"{label} is invalid JSON") from None
    if not isinstance(value, dict):
        raise SpeakerEvidenceError(f"{label} must be an object")
    return value


def _read_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink():
        raise SpeakerEvidenceError(f"{label} must be a regular non-symlink file")
    record_path = path.resolve(strict=True)
    if not record_path.is_file():
        raise SpeakerEvidenceError(f"{label} must be a regular non-symlink file")
    try:
        content = record_path.read_text(encoding="utf-8")
    except UnicodeError:
        raise SpeakerEvidenceError(f"{label} is invalid JSON") from None
    return _decode_object(content, label)


def _validate_integrity(value: dict[str, Any], label: str) -> dict[str, Any]:
    integrity = _object(
        value.get("integrity"),
        {"algorithm", "canonicalization", "sha256"},
        f"{label} integrity",
    )
    if (
        integrity["algorithm"] != "sha256"
        or integrity["canonicalization"] != _INTEGRITY_CANONICALIZATION
    ):
        raise SpeakerEvidenceError(f"{label} integrity policy is invalid")
    expected = _digest(integrity["sha256"], f"{label} integrity digest")
    unsigned = {key: child for key, child in value.items() if key != "integrity"}
    if _canonical_digest(unsigned) != expected:
        raise SpeakerEvidenceError(f"{label} integrity digest is invalid")
    return unsigned


def _validate_reviewed_record(value: Any) -> dict[str, Any]:
    record = _object(value, _REVIEWED_RECORD_FIELDS, "reviewed target record")
    if record["schema_version"] != 1:
        raise SpeakerEvidenceError("reviewed target schema version is invalid")
    if record["record_type"] != "reviewed-target-authorization":
        raise SpeakerEvidenceError("reviewed target record type is invalid")
    if record["type"] not in {
        "target-voice-authorization",
        "synthetic-corpus-manifest",
    }:
        raise SpeakerEvidenceError("reviewed target authorization type is invalid")
    if record["status"] != "approved":
        raise SpeakerEvidenceError("reviewed target is not approved")
    for field in (
        "authorization_id",
        "owner",
        "permitted_purpose",
        "retention_policy",
        "deletion_path",
        "source_id",
    ):
        _string(record[field], f"reviewed target {field}")
    _digest(record["target_artifact_sha256"], "reviewed target artifact digest")
    if (
        record["type"] == "synthetic-corpus-manifest"
        and record["source_id"] != record["authorization_id"]
    ):
        raise SpeakerEvidenceError("reviewed synthetic target identity is inconsistent")
    return record


@cache
def _reviewed_authorizations() -> tuple[ReviewedTarget, ...]:
    resource = importlib.resources.files("liveconv_speaker").joinpath(
        "authorizations/reviewed-targets.json"
    )
    registry_bytes = resource.read_bytes()
    if hashlib.sha256(registry_bytes).hexdigest() != REVIEWED_TARGET_REGISTRY_SHA256:
        raise SpeakerEvidenceError("reviewed registry code-bound digest is invalid")
    try:
        registry = _decode_object(registry_bytes.decode("utf-8"), "reviewed registry")
    except UnicodeError:
        raise SpeakerEvidenceError("reviewed registry is invalid JSON") from None
    _object(
        registry,
        {"schema_version", "registry_type", "records", "integrity"},
        "reviewed registry",
    )
    if (
        registry["schema_version"] != 1
        or registry["registry_type"] != "liveconv-reviewed-target-authorizations"
    ):
        raise SpeakerEvidenceError("reviewed registry identity is invalid")
    _validate_integrity(registry, "reviewed registry")
    records = registry["records"]
    if not isinstance(records, list) or not records:
        raise SpeakerEvidenceError("reviewed registry must contain records")
    reviewed = tuple(
        ReviewedTarget(record, _canonical_digest(record))
        for record in (_validate_reviewed_record(item) for item in records)
    )
    identities = {
        (
            item.value["type"],
            item.value["authorization_id"],
            item.value["target_artifact_sha256"],
        )
        for item in reviewed
    }
    digests = {item.record_sha256 for item in reviewed}
    if len(identities) != len(reviewed) or len(digests) != len(reviewed):
        raise SpeakerEvidenceError("reviewed registry contains duplicate records")
    return reviewed


def _reviewed_match(
    *,
    authorization_type: str,
    authorization_id: str,
    target_sha256: str,
    source_id: str,
    supplied_record: dict[str, Any] | None = None,
) -> ReviewedTarget:
    matches = [
        item
        for item in _reviewed_authorizations()
        if item.value["type"] == authorization_type
        and item.value["authorization_id"] == authorization_id
        and item.value["target_artifact_sha256"] == target_sha256
        and item.value["source_id"] == source_id
    ]
    if supplied_record is not None:
        matches = [item for item in matches if item.value == supplied_record]
    if len(matches) != 1:
        raise SpeakerEvidenceError(
            "target authorization is not a package-reviewed allowlist member"
        )
    return matches[0]


def _artifact_locator(value: Any, *, tree: bool = False) -> dict[str, Any]:
    fields = {"locator", "sha256"} | ({"digest_revision"} if tree else set())
    artifact = _object(value, fields, "synthetic runtime artifact")
    digest = _digest(artifact["sha256"], "synthetic runtime artifact digest")
    prefix = "artifact-tree:sha256:" if tree else "artifact:sha256:"
    if artifact["locator"] != prefix + digest:
        raise SpeakerEvidenceError("synthetic runtime locator does not bind its digest")
    if tree and artifact["digest_revision"] != "liveconv-synthetic-runtime-tree-v1":
        raise SpeakerEvidenceError("synthetic runtime tree revision is invalid")
    return artifact


def _audio_record(value: Any, role: str) -> dict[str, Any]:
    record = _object(
        value,
        {
            "path",
            "sha256",
            "frames",
            "duration_seconds",
            "settings",
            "utterance_id",
            "role",
        },
        f"synthetic {role} record",
    )
    artifact_path = _string(record["path"], "synthetic artifact path")
    relative = Path(artifact_path)
    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
        raise SpeakerEvidenceError("synthetic artifact path is unsafe")
    _digest(record["sha256"], "synthetic artifact digest")
    frames = _positive_int(record["frames"], "synthetic artifact frames")
    duration = _positive_number(
        record["duration_seconds"], "synthetic artifact duration"
    )
    if not math.isclose(duration, frames / 24_000, abs_tol=5e-7):
        raise SpeakerEvidenceError("synthetic artifact duration is inconsistent")
    _string(record["utterance_id"], "synthetic artifact utterance id")
    if record["role"] != role:
        raise SpeakerEvidenceError("synthetic artifact role is invalid")
    if role == "target-reference":
        settings = _object(
            record["settings"], {"composition"}, "synthetic reference settings"
        )
        if settings["composition"] != "ordered-wave-concatenation":
            raise SpeakerEvidenceError("synthetic reference composition is invalid")
    else:
        settings = _object(
            record["settings"],
            {"voice", "speed", "pitch", "gap"},
            "synthetic render settings",
        )
        if settings["voice"] != "ja":
            raise SpeakerEvidenceError("synthetic render voice is invalid")
        for field in ("speed", "pitch", "gap"):
            _positive_int(settings[field], f"synthetic render {field}")
    return record


def _validate_synthetic_manifest(value: dict[str, Any]) -> tuple[str, str]:
    _object(
        value,
        {
            "schema_version",
            "corpus_id",
            "purpose",
            "authorization",
            "source_text",
            "generator",
            "runtime",
            "source",
            "target_training",
            "target_reference",
            "totals",
            "integrity",
        },
        "synthetic corpus manifest",
    )
    if value["schema_version"] != 1:
        raise SpeakerEvidenceError("synthetic corpus schema version is invalid")
    corpus_id = _string(value["corpus_id"], "synthetic corpus id")
    if (
        corpus_id != "liveconv-project-authored-synthetic-ja-v1"
        or value["purpose"] != "technical voice-conversion validation only"
    ):
        raise SpeakerEvidenceError("synthetic corpus identity is invalid")
    authorization = _object(
        value["authorization"],
        {
            "classification",
            "status",
            "contains_human_voice",
            "production_target_approval",
        },
        "synthetic corpus authorization",
    )
    if authorization != {
        "classification": "project-authored-synthetic",
        "status": "approved",
        "contains_human_voice": False,
        "production_target_approval": "not-applicable-to-this-corpus",
    }:
        raise SpeakerEvidenceError("synthetic corpus authorization is invalid")

    source_text = _object(
        value["source_text"],
        {"locator", "sha256", "revision", "utterance_count"},
        "synthetic source text",
    )
    source_digest = _digest(source_text["sha256"], "synthetic source text digest")
    if source_text["locator"] != f"artifact:sha256:{source_digest}":
        raise SpeakerEvidenceError("synthetic source locator is invalid")
    _string(source_text["revision"], "synthetic source revision")
    utterance_count = _positive_int(
        source_text["utterance_count"], "synthetic utterance count"
    )

    generator = _object(
        value["generator"],
        {"implementation", "repository_commit", "script"},
        "synthetic generator",
    )
    if generator["implementation"] != "liveconv-synthetic-ja-corpus-v1":
        raise SpeakerEvidenceError("synthetic generator implementation is invalid")
    if (
        not isinstance(generator["repository_commit"], str)
        or _COMMIT_RE.fullmatch(generator["repository_commit"]) is None
    ):
        raise SpeakerEvidenceError("synthetic generator commit is invalid")
    _artifact_locator(generator["script"])

    runtime = _object(
        value["runtime"],
        {"espeak_ng", "ffmpeg", "sample_rate_hz", "channels", "sample_format"},
        "synthetic runtime",
    )
    if (
        runtime["sample_rate_hz"] != 24_000
        or runtime["channels"] != 1
        or runtime["sample_format"] != "pcm_s16le"
    ):
        raise SpeakerEvidenceError("synthetic audio runtime is invalid")
    espeak = _object(
        runtime["espeak_ng"],
        {
            "version",
            "executable",
            "voice",
            "voice_data",
            "ja_voice_inventory_sha256",
        },
        "synthetic espeak runtime",
    )
    _string(espeak["version"], "synthetic espeak version")
    if espeak["voice"] != "ja":
        raise SpeakerEvidenceError("synthetic espeak voice is invalid")
    _artifact_locator(espeak["executable"])
    _artifact_locator(espeak["voice_data"], tree=True)
    _digest(espeak["ja_voice_inventory_sha256"], "synthetic voice inventory digest")
    ffmpeg = _object(
        runtime["ffmpeg"], {"version", "executable"}, "synthetic ffmpeg runtime"
    )
    _string(ffmpeg["version"], "synthetic ffmpeg version")
    _artifact_locator(ffmpeg["executable"])

    source = value["source"]
    training = value["target_training"]
    if not isinstance(source, list) or not isinstance(training, list):
        raise SpeakerEvidenceError("synthetic artifact collections must be arrays")
    source_records = [_audio_record(item, "source-evaluation") for item in source]
    training_records = [_audio_record(item, "target-training") for item in training]
    if len(source_records) != utterance_count or not training_records:
        raise SpeakerEvidenceError("synthetic artifact collection counts are invalid")
    source_ids = {item["utterance_id"] for item in source_records}
    if any(item["utterance_id"] not in source_ids for item in training_records):
        raise SpeakerEvidenceError(
            "synthetic training utterance is not in the source corpus"
        )
    reference = _audio_record(value["target_reference"], "target-reference")
    paths = [
        *(item["path"] for item in source_records),
        *(item["path"] for item in training_records),
        reference["path"],
    ]
    if len(paths) != len(set(paths)):
        raise SpeakerEvidenceError("synthetic artifact paths must be unique")

    totals = _object(
        value["totals"],
        {"source_seconds", "target_training_seconds", "file_count"},
        "synthetic totals",
    )
    if totals["file_count"] != len(paths):
        raise SpeakerEvidenceError("synthetic file count is inconsistent")
    if not math.isclose(
        _positive_number(totals["source_seconds"], "synthetic source total"),
        round(sum(item["duration_seconds"] for item in source_records), 6),
        abs_tol=5e-7,
    ) or not math.isclose(
        _positive_number(totals["target_training_seconds"], "synthetic training total"),
        round(sum(item["duration_seconds"] for item in training_records), 6),
        abs_tol=5e-7,
    ):
        raise SpeakerEvidenceError("synthetic duration totals are inconsistent")
    _validate_integrity(value, "synthetic corpus manifest")
    return corpus_id, _digest(reference["sha256"], "synthetic target artifact digest")


def bind_target_authorization(
    target_sha256: str,
    *,
    authorization_record: Path | None = None,
    synthetic_corpus_manifest: Path | None = None,
) -> TargetAuthorization:
    _digest(target_sha256, "target artifact digest")
    if (authorization_record is None) == (synthetic_corpus_manifest is None):
        raise SpeakerEvidenceError(
            "exactly one target authorization or synthetic corpus manifest is required"
        )

    if authorization_record is not None:
        value = _read_object(authorization_record, "target authorization record")
        _object(
            value,
            _REVIEWED_RECORD_FIELDS | {"integrity"},
            "target authorization record",
        )
        unsigned = _validate_integrity(value, "target authorization record")
        record = _validate_reviewed_record(unsigned)
        if record["type"] != "target-voice-authorization":
            raise SpeakerEvidenceError("target authorization record type is invalid")
        if record["target_artifact_sha256"] != target_sha256:
            raise SpeakerEvidenceError(
                "target authorization does not bind the target artifact"
            )
        reviewed = _reviewed_match(
            authorization_type=record["type"],
            authorization_id=record["authorization_id"],
            target_sha256=target_sha256,
            source_id=record["source_id"],
            supplied_record=record,
        )
    else:
        assert synthetic_corpus_manifest is not None
        manifest = _read_object(synthetic_corpus_manifest, "synthetic corpus manifest")
        corpus_id, manifest_target = _validate_synthetic_manifest(manifest)
        if manifest_target != target_sha256:
            raise SpeakerEvidenceError(
                "synthetic corpus manifest does not bind the target artifact"
            )
        reviewed = _reviewed_match(
            authorization_type="synthetic-corpus-manifest",
            authorization_id=corpus_id,
            target_sha256=target_sha256,
            source_id=corpus_id,
        )

    return TargetAuthorization(
        reviewed.value["type"],
        reviewed.value["authorization_id"],
        reviewed.record_sha256,
        target_sha256,
    )


__all__: Sequence[str] = (
    "TargetAuthorization",
    "bind_target_authorization",
)
