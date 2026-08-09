"""Backend-neutral Japanese transcription and evidence construction."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .audio import InputLimits, PcmAudio, read_pcm_wav
from .errors import BackendExecutionError, ConfigurationError, SttError
from .models import BUNDLE_SCHEMA_VERSION, SttEvidenceRecord, TranscriptionBundle
from .normalization import (
    NORMALIZATION_REVISION,
    compare_exact_entities,
    normalize_japanese,
)

_ENGINE_REVISION = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}==[0-9]+(?:\.[0-9]+){1,3}(?:[A-Za-z0-9_.+-]*)$"
)
_MODEL_REVISION = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,191}@sha256:([0-9a-f]{64})$"
)
_SENSITIVE_KEY = re.compile(
    r"(?:"
    r"authorization|credential|hotword|password|prompt|raw[_-]?audio|secret|"
    r"token|transcript|(?:api|access|private)[_-]?key"
    r")",
    re.IGNORECASE,
)
_TOKENIZERS_PROVENANCE_PATH = ("runtime_packages", "tokenizers")
MAX_DECODE_CONFIG_BYTES = 64 * 1024
MAX_TRANSCRIPT_CHARACTERS = 200_000


class SttBackend(Protocol):
    """A backend must expose its fully resolved decode configuration."""

    def canonicalize_decode_config(
        self, config: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def transcribe(
        self,
        audio: PcmAudio,
        *,
        language: str,
        decode_config: Mapping[str, Any],
    ) -> str: ...


def validate_engine_revision(revision: str) -> None:
    if not _ENGINE_REVISION.fullmatch(revision):
        raise ConfigurationError("engine revision must be pinned as name==version")


def validate_model_revision(revision: str, artifact_sha256: str | None) -> None:
    match = _MODEL_REVISION.fullmatch(revision)
    if match is None:
        raise ConfigurationError(
            "model revision must end with @sha256:<lowercase digest>"
        )
    if artifact_sha256 is not None and match.group(1) != artifact_sha256:
        raise ConfigurationError(
            "model revision digest does not match the model artifact"
        )


def _validate_no_sensitive_keys(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ConfigurationError("decode configuration keys must be strings")
            child_path = (*path, key)
            if child_path != _TOKENIZERS_PROVENANCE_PATH and _SENSITIVE_KEY.search(key):
                raise ConfigurationError(
                    "decode configuration contains a forbidden sensitive field"
                )
            _validate_no_sensitive_keys(child, child_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _validate_no_sensitive_keys(child, (*path, "<sequence>"))
    elif isinstance(value, float) and not math.isfinite(value):
        raise ConfigurationError("decode configuration numbers must be finite")


def canonical_json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ConfigurationError("decode configuration must be a non-empty object")
    candidate = dict(value)
    _validate_no_sensitive_keys(candidate)
    try:
        encoded = json.dumps(
            candidate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ConfigurationError(
            "decode configuration must contain JSON values"
        ) from None
    if len(encoded) > MAX_DECODE_CONFIG_BYTES:
        raise ConfigurationError("decode configuration exceeds the size limit")
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ConfigurationError("decode configuration must be an object")
    return decoded


def _timestamp(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConfigurationError(
            "transcription clock must return a timezone-aware timestamp"
        )
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def transcribe_pcm_wav(
    path: str | Path,
    *,
    backend: SttBackend,
    engine_revision: str,
    model_revision: str,
    decode_config: Mapping[str, Any],
    role: str,
    model_artifact_sha256: str | None = None,
    exact_entities: Iterable[str] = (),
    language: str = "ja",
    limits: InputLimits | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> TranscriptionBundle:
    """Transcribe one artifact without logging audio, paths, or transcript text."""

    if role not in {"source", "output"}:
        raise ConfigurationError("role must be source or output")
    if language not in {"ja", "ja-JP"}:
        raise ConfigurationError("language must identify Japanese")
    validate_engine_revision(engine_revision)
    validate_model_revision(model_revision, model_artifact_sha256)
    supplied_config = canonical_json_object(decode_config)
    try:
        resolved_config = backend.canonicalize_decode_config(supplied_config)
        canonical_config = canonical_json_object(resolved_config)
    except SttError:
        raise
    except Exception:
        raise ConfigurationError(
            "STT backend rejected the decode configuration"
        ) from None

    audio = read_pcm_wav(path, limits=limits)
    try:
        transcript = backend.transcribe(
            audio,
            language=language,
            decode_config=canonical_config,
        )
    except Exception:
        raise BackendExecutionError("STT backend execution failed") from None
    if not isinstance(transcript, str):
        raise BackendExecutionError("STT backend returned an invalid result")
    if len(transcript) > MAX_TRANSCRIPT_CHARACTERS:
        raise BackendExecutionError("STT backend result exceeds the size limit")

    normalized_transcript = normalize_japanese(transcript)
    if len(normalized_transcript) > MAX_TRANSCRIPT_CHARACTERS:
        raise BackendExecutionError("normalized STT result exceeds the size limit")

    try:
        entity_result = compare_exact_entities(exact_entities, transcript)
    except ValueError as error:
        raise ConfigurationError(str(error)) from None
    transcribed_at = _timestamp(clock)
    evidence = SttEvidenceRecord(
        provider=engine_revision,
        model_revision=model_revision,
        decode_config=canonical_config,
        language=language,
        transcribed_at=transcribed_at,
        normalization_revision=NORMALIZATION_REVISION,
    )
    return TranscriptionBundle(
        schema_version=BUNDLE_SCHEMA_VERSION,
        role=role,
        engine_revision=engine_revision,
        model_revision=model_revision,
        model_artifact_sha256=model_artifact_sha256,
        audio_artifact=audio.artifact,
        transcript=transcript,
        normalized_transcript=normalized_transcript,
        exact_entities=entity_result,
        stt_evidence=evidence,
    )
