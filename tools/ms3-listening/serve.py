#!/usr/bin/env python3
"""Serve completed MS-3 listening artifacts through a loopback-only UI."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import socket
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

TOOL_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
COLLECTION_NOTES_PATH = TOOL_ROOT / "collection-notes.json"
SOURCE_EVALUATION_SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "experiments"
    / "EXP-020-human-rvc-actual-input"
    / "source-evaluation-script.v1.json"
)
DEFAULT_LIBRARY_ROOTS = (
    REPOSITORY_ROOT / "artifacts" / "ms3" / "job-queue" / "attempts",
    REPOSITORY_ROOT / "artifacts" / "ms3" / "listening",
    REPOSITORY_ROOT / "artifacts" / "xvc-best-of-demo",
)
SOURCE_CAPTURE_ROOT = REPOSITORY_ROOT / "artifacts" / "ms3" / "source-captures"
MAX_SOURCE_CAPTURE_FILE_BYTES = 256 * 1024 * 1024
MAX_SOURCE_CAPTURE_REQUEST_BYTES = MAX_SOURCE_CAPTURE_FILE_BYTES
MAX_SOURCE_CAPTURE_TOTAL_BYTES = 1024 * 1024 * 1024
_SOURCE_CAPTURE_ID_PATTERN = re.compile(r"capture-[0-9]{8}t[0-9]{6}z-[0-9a-f]{16}")
_SOURCE_CAPTURE_FILENAME_PATTERN = re.compile(r"chunk-[0-9]{4,6}\.webm")
_SOURCE_CAPTURE_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_SOURCE_CAPTURE_CONTENT_TYPES = frozenset({"audio/webm", "application/octet-stream"})
_SOURCE_CAPTURE_COPY_BYTES = 1024 * 1024
_SOURCE_CAPTURE_LOCK = threading.Lock()
_HOST_PATTERN = re.compile(
    r"(?P<host>localhost|127\.0\.0\.1|\[::1\])(?::(?P<port>[1-9][0-9]{0,4}))?"
)
_QUEUE_ATTEMPT_PATTERN = re.compile(r"attempt-(0*[1-9][0-9]*)")
_TEXT_ID_ORDER_PATTERN = re.compile(r"TTS([0-9]{3})")
_RENDER_BINDING_FIELDS = (
    "attempt_id",
    "utterance_id",
    "render_receipt_sha256",
    "route_parity_receipt_sha256",
    "route_status",
    "extension_eligible",
    "source_audio_sha256",
    "output_sha256",
    "collection_id",
    "candidate_id",
    "split",
    "candidate_lock_sha256",
    "review_bundle_sha256",
    "review_scope",
    "source_only",
    "evidence_schema",
    "official_display",
    "official_kana",
    "raw_asr",
    "risk_tier",
    "risk_flags",
    "audio_sha256",
    "manifest_sha256",
    "audit_sha256",
)


class SourceCaptureUploadError(ValueError):
    """A client-visible capture upload validation failure."""

    status = HTTPStatus.BAD_REQUEST
    code = "invalid_source_capture"


class SourceCaptureTooLargeError(SourceCaptureUploadError):
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "source_capture_too_large"


class SourceCaptureConflictError(SourceCaptureUploadError):
    status = HTTPStatus.CONFLICT
    code = "source_capture_conflict"


class SourceCaptureUnsupportedMediaError(SourceCaptureUploadError):
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "source_capture_content_type"


def listening_index(directory: Path) -> dict[str, object]:
    """Load a comparison index without changing the input artifact."""
    index_path = directory / "index.json"
    if not index_path.is_file():
        raise ValueError(f"listening directory must contain index.json: {directory}")
    document = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not (
        isinstance(document.get("variants"), list)
        or isinstance(document.get("conditions"), list)
    ):
        raise ValueError("index.json must contain variants or conditions")
    return enrich_with_effective_parameters(document)


def source_evaluation_script() -> dict[str, object]:
    """Project the fixed human-input script without exposing local metadata."""
    document = json.loads(SOURCE_EVALUATION_SCRIPT_PATH.read_text(encoding="utf-8"))
    utterances = document.get("utterances") if isinstance(document, dict) else None
    if not isinstance(utterances, list) or len(utterances) != 100:
        raise ValueError("source evaluation script must contain exactly 100 utterances")
    projected: list[dict[str, str]] = []
    for utterance in utterances:
        if not isinstance(utterance, dict):
            raise ValueError("source evaluation script contains an invalid utterance")
        identifier = utterance.get("id")
        category = utterance.get("category")
        text = utterance.get("text")
        if not all(
            isinstance(value, str) and value for value in (identifier, category, text)
        ):
            raise ValueError("source evaluation script has incomplete utterance fields")
        projected.append({"id": identifier, "category": category, "text": text})
    return {"schema_version": 1, "utterances": projected}


def _run_id(directory: Path) -> str:
    try:
        identity = directory.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        identity = directory.as_posix()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _queue_attempt(directory: Path) -> tuple[Path, int] | None:
    """Find the queue attempt that owns an index below its output directory."""
    for parent in (directory, *directory.parents):
        match = _QUEUE_ATTEMPT_PATTERN.fullmatch(parent.name)
        if match is None:
            continue
        try:
            directory.relative_to(parent / "output")
        except ValueError:
            continue
        return parent, int(match.group(1))
    return None


def _queue_attempt_succeeded(directory: Path) -> bool:
    """Require a consistent terminal success for queue-owned output only."""
    queue_attempt = _queue_attempt(directory)
    if queue_attempt is None:
        return True
    attempt_directory, expected_attempt = queue_attempt
    result_path = attempt_directory / "result.json"
    if not result_path.is_file():
        return False
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(result, dict)
        and type(result.get("schema_version")) is int
        and isinstance(result.get("job_id"), str)
        and result["job_id"]
        and type(result.get("attempt")) is int
        and result["attempt"] == expected_attempt
        and result.get("status") == "succeeded"
        and result.get("reason_code") is None
        and result.get("exit_code") == 0
        and result.get("timed_out") is False
        and isinstance(result.get("finished_at"), str)
        and result["finished_at"]
        and result.get("artifact_index") == "artifact-index.json"
    )


def _collection_identity(directory: Path, roots: list[Path]) -> tuple[str, Path, str]:
    """Return an opaque collection owner for queue and direct artifacts.

    Collection labels are intentionally only directory basenames.  The browser
    needs a stable way to group runs, but never receives an artifact path.
    """
    queue_attempt = _queue_attempt(directory)
    if queue_attempt is not None:
        attempt_directory, _ = queue_attempt
        job_directory = attempt_directory.parent
        return "queue_job", job_directory, job_directory.name

    containing_roots: list[Path] = []
    for root in roots:
        resolved_root = root.resolve()
        if resolved_root.is_file():
            resolved_root = resolved_root.parent
        try:
            directory.relative_to(resolved_root)
        except ValueError:
            continue
        containing_roots.append(resolved_root)
    if not containing_roots:
        return "artifact_collection", directory, directory.name
    root = max(containing_roots, key=lambda item: len(item.parts))
    relative = directory.relative_to(root)
    owner = root if not relative.parts else root / relative.parts[0]
    return "artifact_collection", owner, owner.name


def _collection_id(kind: str, owner: Path) -> str:
    return f"collection-{kind}-{_run_id(owner)}"


def collection_note(collection_title: str) -> dict[str, object] | None:
    """Return the most specific curated note matching an opaque collection title."""
    try:
        document = json.loads(COLLECTION_NOTES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    annotations = document.get("collections") if isinstance(document, dict) else None
    if not isinstance(annotations, list):
        return None
    normalized_title = collection_title.casefold()
    matches: list[tuple[tuple[int, int], dict[str, object]]] = []
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        match_all = annotation.get("match_all")
        if not (
            isinstance(match_all, list)
            and match_all
            and all(isinstance(part, str) and part for part in match_all)
        ):
            continue
        normalized_parts = [part.casefold() for part in match_all]
        if all(part in normalized_title for part in normalized_parts):
            matches.append(
                ((len(normalized_parts), sum(map(len, normalized_parts))), annotation)
            )
    return max(matches, key=lambda item: item[0])[1] if matches else None


def discover_listening_directories(roots: list[Path]) -> list[Path]:
    """Find finalized comparison directories without following arbitrary paths."""
    discovered: set[Path] = set()
    for raw_root in roots:
        root = raw_root.resolve()
        if root.is_file() and root.name == "index.json":
            candidates = [root]
        elif root.is_dir() and (root / "index.json").is_file():
            candidates = [root / "index.json"]
        elif root.is_dir():
            candidates = root.rglob("index.json")
        else:
            continue
        for index_path in candidates:
            directory = index_path.parent.resolve()
            if _queue_attempt_succeeded(directory):
                discovered.add(directory)
    return sorted(discovered, key=lambda path: path.stat().st_mtime, reverse=True)


def configured_library_roots(
    directory: Path | None, library_roots: list[Path]
) -> list[Path]:
    """Resolve explicit roots, or use the project-wide persistent library."""
    roots = [path.resolve() for path in library_roots]
    if directory is not None:
        roots.append(directory.resolve())
    return roots or [path.resolve() for path in DEFAULT_LIBRARY_ROOTS]


def library_roots_fingerprint(roots: list[Path]) -> tuple[tuple[str, int, int], ...]:
    """Cheaply detect atomic collection publication below configured roots."""
    values: list[tuple[str, int, int]] = []
    for raw_root in roots:
        root = raw_root.resolve()
        try:
            status = root.stat()
        except OSError:
            values.append((str(root), -1, -1))
            continue
        values.append((str(root), status.st_mtime_ns, status.st_size))
    return tuple(values)


def _condition_variants(document: dict[str, object]) -> list[dict[str, object]]:
    conditions = document.get("conditions")
    if not isinstance(conditions, list):
        return []
    variants: list[dict[str, object]] = []
    for order, condition in enumerate(conditions, start=1):
        if not isinstance(condition, dict):
            continue
        profile = condition.get("profile")
        gateway = condition.get("gateway")
        if not isinstance(profile, dict) or not isinstance(gateway, dict):
            continue
        profile_id = profile.get("profile_id")
        output_file = condition.get("output_file")
        if not isinstance(profile_id, str) or not isinstance(output_file, str):
            continue
        variants.append(
            {
                "variant_id": profile_id,
                "profile_id": profile_id,
                "profile_hash": profile.get("profile_hash"),
                "configuration_hash": profile.get("configuration_hash"),
                "display_name": profile_id.removeprefix("vc."),
                "display_order": order,
                "family_id": profile_id.split(".")[1]
                if profile_id.count(".") >= 2
                else "unknown",
                "output_file": output_file,
                "status": "passed",
                "absolute_peak": gateway.get("absolute_peak"),
                "wall_seconds": condition.get("wall_seconds"),
                "send_lateness_ms": gateway.get("send_lateness_ms"),
                "maximum_send_lateness_ms": gateway.get("maximum_send_lateness_ms"),
                **{field: condition.get(field) for field in _RENDER_BINDING_FIELDS},
            }
        )
    return variants


def _first_present(*values: object) -> object | None:
    return next((value for value in values if value is not None), None)


def _display_title(document: dict[str, object], directory: Path) -> str:
    """Return a stable run label while retaining legacy artifact labels."""
    title = document.get("title")
    if isinstance(title, str):
        return title
    run_kind = document.get("run_kind")
    if isinstance(run_kind, str):
        return run_kind
    utterance_id = document.get("utterance_id")
    q = document.get("q")
    if (
        isinstance(utterance_id, str)
        and utterance_id
        and isinstance(q, (int, float))
        and not isinstance(q, bool)
    ):
        return f"{utterance_id} / q={q}"
    return directory.name


def _run_display_order(document: dict[str, object]) -> int | None:
    """Project an explicit order for fixed text fixtures when one is available."""
    display_order = document.get("display_order")
    if type(display_order) is int and display_order >= 0:
        return display_order
    text_id = document.get("text_id")
    if isinstance(text_id, str):
        match = _TEXT_ID_ORDER_PATTERN.fullmatch(text_id)
        if match is not None:
            return int(match.group(1))
    return None


def _candidate_record(
    run_id: str, variant: dict[str, object], order: int
) -> dict[str, object] | None:
    status = variant.get("status")
    output_file = variant.get("output_file")
    if status not in {None, "passed", "completed"} or not isinstance(output_file, str):
        return None
    profile_id = variant.get("profile_id")
    variant_id = variant.get("variant_id")
    stable_id = variant_id if isinstance(variant_id, str) else profile_id
    if not isinstance(stable_id, str):
        stable_id = f"candidate-{order:03d}"
    parameters = (
        variant.get("effective_parameters")
        or variant.get("parameter_settings")
        or variant.get("parameters")
    )
    generations = variant.get("generations")
    generation = (
        generations[0]
        if isinstance(generations, list)
        and generations
        and isinstance(generations[0], dict)
        else {}
    )
    return {
        "id": f"{run_id}:{stable_id}:{order}",
        "kind": "candidate",
        "display_name": variant.get("display_name") or stable_id,
        "profile_id": profile_id or "unknown",
        "family_id": variant.get("family_id") or "unknown",
        "configuration_hash": variant.get("configuration_hash"),
        "profile_hash": variant.get("profile_hash"),
        "parameters": parameters if isinstance(parameters, dict) else None,
        "absolute_peak": _first_present(
            variant.get("absolute_peak"), generation.get("absolute_peak")
        ),
        "wall_seconds": variant.get("wall_seconds"),
        "send_lateness_ms": _first_present(
            variant.get("send_lateness_ms"), generation.get("send_lateness_ms")
        ),
        "maximum_send_lateness_ms": _first_present(
            variant.get("maximum_send_lateness_ms"),
            generation.get("maximum_send_lateness_ms"),
        ),
        "output_file": output_file,
        "audio_url": f"/runs/{run_id}/{quote(output_file, safe='/')}",
        "display_order": variant.get("display_order", order),
        **{field: variant.get(field) for field in _RENDER_BINDING_FIELDS},
    }


def _with_document_bindings(
    document: dict[str, object], variant: dict[str, object]
) -> dict[str, object]:
    """Allow an index-wide receipt binding to apply to its leaf candidates."""
    bound = dict(variant)
    for field in _RENDER_BINDING_FIELDS:
        if bound.get(field) is None and field in document:
            bound[field] = document[field]
    return bound


def listening_library(
    directories: list[Path], roots: list[Path] | None = None
) -> tuple[dict[str, object], dict[str, Path]]:
    """Build a safe, display-oriented projection over completed run artifacts."""
    runs: list[dict[str, object]] = []
    collections: dict[str, dict[str, object]] = {}
    mapped_directories: dict[str, Path] = {}
    collection_roots = roots or directories
    for directory in directories:
        try:
            document = listening_index(directory)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        run_id = _run_id(directory)
        collection_kind, collection_owner, collection_title = _collection_identity(
            directory, collection_roots
        )
        collection_id = _collection_id(collection_kind, collection_owner)
        raw_variants = document.get("variants")
        variants = (
            raw_variants
            if isinstance(raw_variants, list) and raw_variants
            else _condition_variants(document)
        )
        candidates = []
        for order, variant in enumerate(variants, start=1):
            if not isinstance(variant, dict):
                continue
            record = _candidate_record(
                run_id, _with_document_bindings(document, variant), order
            )
            if record is None:
                continue
            audio_file = confined(directory, record["output_file"])
            if audio_file is not None and audio_file.is_file():
                candidates.append(record)
        if not candidates:
            continue
        source_output = document.get("source_output_file")
        source_file = document.get("source_file")
        if not isinstance(source_output, str) and isinstance(source_file, str):
            default_source = directory / "00-source.wav"
            if default_source.is_file():
                source_output = default_source.name
        source_path = None
        if isinstance(source_output, str):
            source_path = confined(directory, source_output)
        if source_path is not None and source_path.is_file():
            candidates.insert(
                0,
                {
                    "id": f"{run_id}:source",
                    "kind": "source",
                    "display_name": f"Source: {source_file or source_output}",
                    "profile_id": "source",
                    "family_id": "source",
                    "parameters": None,
                    "source_file": source_file,
                    "duration_seconds": document.get("source_duration_seconds"),
                    "output_file": source_output,
                    "audio_url": f"/runs/{run_id}/{quote(source_output, safe='/')}",
                    "display_order": -1,
                },
            )
        artifact_name = directory.name
        if directory.name == "output" and directory.parent.name.startswith("attempt-"):
            artifact_name = f"{directory.parent.parent.name} / {directory.parent.name}"
        source = document.get("source")
        source_duration = document.get("source_duration_seconds")
        if source_duration is None and isinstance(source, dict):
            source_duration = source.get("duration_seconds")
        runs.append(
            {
                "id": run_id,
                "collection_id": collection_id,
                "title": _display_title(document, directory),
                "artifact_name": artifact_name,
                "status": document.get("status") or "completed",
                "source_file": source_file,
                "source_duration_seconds": source_duration,
                "candidate_count": len(
                    [item for item in candidates if item["kind"] == "candidate"]
                ),
                "candidates": candidates,
                "_display_order": _run_display_order(document),
            }
        )
        collection = collections.setdefault(
            collection_id,
            {
                "id": collection_id,
                "kind": collection_kind,
                "title": collection_title,
                "run_count": 0,
                "candidate_count": 0,
            },
        )
        collection["run_count"] = int(collection["run_count"]) + 1
        collection["candidate_count"] = int(collection["candidate_count"]) + int(
            runs[-1]["candidate_count"]
        )
        mapped_directories[run_id] = directory
    collection_positions = {
        collection_id: position for position, collection_id in enumerate(collections)
    }
    runs.sort(
        key=lambda run: (
            collection_positions[str(run["collection_id"])],
            run["_display_order"] is None,
            int(run["_display_order"] or 0),
            str(run["title"]),
        )
    )
    for run in runs:
        run.pop("_display_order")
    payload: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_count": len(runs),
        "candidate_count": sum(int(run["candidate_count"]) for run in runs),
        "collections": list(collections.values()),
        "runs": runs,
    }
    return payload, mapped_directories


def enrich_with_effective_parameters(document: dict[str, object]) -> dict[str, object]:
    """Attach sealed bundle settings when the listening index names that bundle.

    The comparison directory stays immutable. No settings are guessed from a
    display name: missing or nonmatching bundles simply leave variants untouched.
    """
    revision = document.get("bundle_revision")
    if not isinstance(revision, str) or not revision.startswith("sha256:"):
        return document
    digest = revision.removeprefix("sha256:")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        return document
    bundle_path = (
        REPOSITORY_ROOT / "artifacts" / "ms3" / "deployments" / digest / "bundle.json"
    )
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        profiles = bundle["gateway_profile_registry"]["profiles"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return document
    if not isinstance(profiles, list):
        return document
    settings_by_profile = {
        profile.get("profile_id"): profile.get("runtime", {})
        .get("configuration", {})
        .get("settings")
        for profile in profiles
        if isinstance(profile, dict)
    }
    variants = document.get("variants")
    if not isinstance(variants, list):
        return document
    enriched = {**document, "variants": []}
    for variant in variants:
        if not isinstance(variant, dict):
            enriched["variants"].append(variant)
            continue
        settings = settings_by_profile.get(variant.get("profile_id"))
        enriched["variants"].append(
            {**variant, "effective_parameters": settings}
            if isinstance(settings, dict)
            else variant
        )
    return enriched


def confined(root: Path, url_path: str) -> Path | None:
    """Resolve a URL path only when it remains under its mapped root."""
    relative = Path(unquote(url_path).lstrip("/"))
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _source_capture_raw_directory(capture_root: Path, capture_id: str) -> Path:
    """Create and verify the one directory that may receive a capture chunk."""
    if _SOURCE_CAPTURE_ID_PATTERN.fullmatch(capture_id) is None:
        raise SourceCaptureUploadError("capture id is not server-generated")
    try:
        capture_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SourceCaptureUploadError("capture root is unavailable") from error
    if capture_root.is_symlink() or not capture_root.is_dir():
        raise SourceCaptureUploadError("capture root must be a directory")
    capture_directory = capture_root / capture_id
    raw_directory = capture_directory / "raw"
    for directory in (capture_directory, raw_directory):
        try:
            directory.mkdir(exist_ok=True)
        except OSError as error:
            raise SourceCaptureUploadError(
                "capture directory is unavailable"
            ) from error
        if directory.is_symlink() or not directory.is_dir():
            raise SourceCaptureUploadError("capture directory must not be a symlink")
    return raw_directory


def _source_capture_total_bytes(raw_directory: Path) -> int:
    """Count existing chunks and reject a tampered capture directory."""
    total = 0
    try:
        children = list(raw_directory.iterdir())
    except OSError as error:
        raise SourceCaptureUploadError("capture directory is unreadable") from error
    for child in children:
        if child.is_symlink():
            raise SourceCaptureUploadError("capture directory contains a symlink")
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError as error:
                raise SourceCaptureUploadError("capture file is unreadable") from error
    return total


def _remove_empty_capture_directories(raw_directory: Path) -> None:
    """Leave failed uploads without an artifact or a partial-file residue."""
    try:
        raw_directory.rmdir()
        raw_directory.parent.rmdir()
    except OSError:
        pass


def store_source_capture(
    capture_root: Path,
    *,
    capture_id: str,
    filename: str,
    content_type: str,
    content_length: int,
    expected_sha256: str,
    stream: object,
) -> dict[str, object]:
    """Atomically persist one validated WebM/Opus capture chunk.

    `stream` is deliberately a tiny file-like contract (`read(size)`) so the
    handler never needs to buffer a user recording in memory.
    """
    if _SOURCE_CAPTURE_FILENAME_PATTERN.fullmatch(filename) is None:
        raise SourceCaptureUploadError("capture filename is not server-generated")
    if content_type not in _SOURCE_CAPTURE_CONTENT_TYPES:
        raise SourceCaptureUnsupportedMediaError("unsupported capture content type")
    if not 0 < content_length <= MAX_SOURCE_CAPTURE_REQUEST_BYTES:
        raise SourceCaptureTooLargeError("capture request exceeds the limit")
    if content_length > MAX_SOURCE_CAPTURE_FILE_BYTES:
        raise SourceCaptureTooLargeError("capture file exceeds the limit")
    if _SOURCE_CAPTURE_SHA256_PATTERN.fullmatch(expected_sha256) is None:
        raise SourceCaptureUploadError("capture digest is required")

    with _SOURCE_CAPTURE_LOCK:
        raw_directory = _source_capture_raw_directory(capture_root, capture_id)
        destination = raw_directory / filename
        if destination.exists() or destination.is_symlink():
            raise SourceCaptureConflictError("capture chunk already exists")
        if (
            _source_capture_total_bytes(raw_directory) + content_length
            > MAX_SOURCE_CAPTURE_TOTAL_BYTES
        ):
            raise SourceCaptureTooLargeError("capture total exceeds the limit")

        temporary = raw_directory / f".{filename}.{secrets.token_hex(12)}.uploading"
        digest = hashlib.sha256()
        written = 0
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output:
                while written < content_length:
                    chunk = stream.read(
                        min(_SOURCE_CAPTURE_COPY_BYTES, content_length - written)
                    )
                    if not isinstance(chunk, bytes) or not chunk:
                        raise SourceCaptureUploadError("capture body is incomplete")
                    output.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            actual_sha256 = digest.hexdigest()
            if actual_sha256 != expected_sha256:
                raise SourceCaptureUploadError("capture digest does not match body")
            os.replace(temporary, destination)
        except (OSError, SourceCaptureUploadError) as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            _remove_empty_capture_directories(raw_directory)
            if isinstance(error, SourceCaptureUploadError):
                raise
            raise SourceCaptureUploadError("capture could not be stored") from error

    return {
        "locator": (f"artifacts/ms3/source-captures/{capture_id}/raw/{filename}"),
        "bytes": written,
        "sha256": actual_sha256,
    }


def _allowed_hosts(bound_address: str) -> frozenset[str]:
    """Return names that can reach the loopback address actually bound."""
    if bound_address == "127.0.0.1":
        return frozenset({"127.0.0.1", "localhost"})
    if bound_address == "::1":
        return frozenset({"[::1]", "localhost"})
    return frozenset()


def _trusted_host(
    host_values: list[str] | None, *, bound_address: str, port: int
) -> bool:
    """Reject Host values that could turn a loopback server into a rebound origin."""
    if host_values is None or len(host_values) != 1:
        return False
    match = _HOST_PATTERN.fullmatch(host_values[0])
    if match is None or match.group("host") not in _allowed_hosts(bound_address):
        return False
    requested_port = match.group("port")
    return requested_port is None or int(requested_port) == port


def _origin_form_target(request_target: str) -> bool:
    """Only accept origin-form targets; absolute-form targets are ambiguous here."""
    parsed = urlsplit(request_target)
    return (
        request_target.startswith("/")
        and not request_target.startswith("//")
        and not parsed.scheme
        and not parsed.netloc
    )


def make_handler(roots: list[Path], capture_root: Path = SOURCE_CAPTURE_ROOT):
    library_lock = threading.Lock()
    library_cache: tuple[dict[str, object], dict[str, Path]] | None = None
    library_fingerprint: tuple[tuple[str, int, int], ...] | None = None

    def library_snapshot(*, refresh: bool = False):
        nonlocal library_cache, library_fingerprint
        observed = library_roots_fingerprint(roots) if refresh else None
        with library_lock:
            if library_cache is None or (
                refresh and observed != library_fingerprint
            ):
                directories = discover_listening_directories(roots)
                library_cache = listening_library(directories, roots)
                # Bind the cache to the state that authorized this scan. If a
                # collection is atomically published during discovery, the
                # next browser refresh must observe a mismatch and rescan.
                library_fingerprint = observed
            return library_cache

    class ListeningHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._route(send_body=True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._route(send_body=False)

        def do_POST(self) -> None:  # noqa: N802
            if not _origin_form_target(self.path) or not _trusted_host(
                self.headers.get_all("Host"),
                bound_address=self.server.server_address[0],
                port=self.server.server_port,
            ):
                self._reject_request()
                return
            path = urlsplit(self.path).path
            if not path.startswith("/source-captures/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            parts = path.removeprefix("/source-captures/").split("/")
            if len(parts) != 3 or parts[1] != "raw":
                self._send_upload_error(
                    SourceCaptureUploadError("invalid source capture endpoint")
                )
                return
            try:
                payload = store_source_capture(
                    capture_root,
                    capture_id=parts[0],
                    filename=parts[2],
                    content_type=self._source_capture_content_type(),
                    content_length=self._source_capture_content_length(),
                    expected_sha256=self._source_capture_digest(),
                    stream=self.rfile,
                )
            except SourceCaptureUploadError as error:
                self._send_upload_error(error)
                return
            self._send_json(payload, send_body=True, status=HTTPStatus.CREATED)

        def _route(self, *, send_body: bool) -> None:
            if not _origin_form_target(self.path) or not _trusted_host(
                self.headers.get_all("Host"),
                bound_address=self.server.server_address[0],
                port=self.server.server_port,
            ):
                self._reject_request()
                return
            path = urlsplit(self.path).path
            if path == "/source-evaluation-script.json":
                try:
                    self._send_json(source_evaluation_script(), send_body=send_body)
                except (OSError, ValueError, json.JSONDecodeError):
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if path == "/library/index.json":
                payload, _ = library_snapshot(refresh=True)
                self._send_json(payload, send_body=send_body)
                return
            if path.startswith("/runs/"):
                parts = path.removeprefix("/runs/").split("/", 1)
                if len(parts) != 2:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                _, mapped = library_snapshot()
                audio_path = (
                    confined(mapped[parts[0]], parts[1]) if parts[0] in mapped else None
                )
                self._send_file(
                    audio_path,
                    send_body=send_body,
                )
                return
            if path == "/run/index.json":
                directories = discover_listening_directories(roots)
                if len(directories) != 1:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_json(listening_index(directories[0]), send_body=send_body)
                return
            if path.startswith("/run/"):
                directories = discover_listening_directories(roots)
                self._send_file(
                    confined(directories[0], path.removeprefix("/run/"))
                    if len(directories) == 1
                    else None,
                    send_body=send_body,
                )
                return
            asset_path = "index.html" if path in {"", "/"} else path.lstrip("/")
            self._send_file(confined(TOOL_ROOT, asset_path), send_body=send_body)

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.client_address[0]} {format % args}")

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; base-uri 'none'; "
                "frame-ancestors 'none'; object-src 'none'",
            )
            super().end_headers()

        def _reject_request(self) -> None:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def _source_capture_content_type(self) -> str:
            values = self.headers.get_all("Content-Type")
            if values is None or len(values) != 1:
                raise SourceCaptureUnsupportedMediaError(
                    "capture content type is required"
                )
            return values[0].split(";", 1)[0].strip().lower()

        def _source_capture_content_length(self) -> int:
            values = self.headers.get_all("Content-Length")
            if values is None or len(values) != 1 or not values[0].isdigit():
                raise SourceCaptureUploadError("capture content length is required")
            return int(values[0])

        def _source_capture_digest(self) -> str:
            values = self.headers.get_all("X-Content-SHA256")
            if values is None or len(values) != 1:
                raise SourceCaptureUploadError("capture digest is required")
            return values[0]

        def _send_upload_error(self, error: SourceCaptureUploadError) -> None:
            self._send_json({"error": error.code}, send_body=True, status=error.status)

        def _send_json(
            self,
            payload: object,
            *,
            send_body: bool,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if send_body:
                self.wfile.write(body)

        def _send_file(self, path: Path | None, *, send_body: bool) -> None:
            if path is None or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = (
                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if send_body:
                self.wfile.write(data)

    return ListeningHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument(
        "--library-root",
        action="append",
        default=[],
        type=Path,
        help="root to scan recursively for completed listening index files",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="loopback host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", default=8878, type=int, help="TCP port (default: 8878)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("only loopback hosts are permitted")
    roots = configured_library_roots(args.directory, args.library_root)
    if not discover_listening_directories(roots):
        raise SystemExit(f"no completed listening index files found under: {roots}")
    ThreadingHTTPServer.allow_reuse_address = True
    server_class = ThreadingHTTPServer
    if args.host == "::1":

        class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
            address_family = socket.AF_INET6

        server_class = IPv6ThreadingHTTPServer
    try:
        server = server_class((args.host, args.port), make_handler(roots))
    except OSError as error:
        raise SystemExit(
            f"could not start MS-3 listener on {args.host}:{args.port}: {error}"
        ) from error
    print(f"MS-3 listener: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
