"""Evidence records emitted by the STT runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .audio import AudioArtifact

BUNDLE_SCHEMA_VERSION = "liveconv-stt-bundle-v1"


@dataclass(frozen=True)
class SttEvidenceRecord:
    """The exact six-field shape accepted by liveconv_evaluation.SttEvidence."""

    provider: str
    model_revision: str
    decode_config: dict[str, Any]
    language: str
    transcribed_at: str
    normalization_revision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_revision": self.model_revision,
            "decode_config": dict(self.decode_config),
            "language": self.language,
            "transcribed_at": self.transcribed_at,
            "normalization_revision": self.normalization_revision,
        }


@dataclass(frozen=True)
class TranscriptionBundle:
    schema_version: str
    role: str
    engine_revision: str
    model_revision: str
    model_artifact_sha256: str | None
    audio_artifact: AudioArtifact
    transcript: str
    normalized_transcript: str
    exact_entities: dict[str, Any]
    stt_evidence: SttEvidenceRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "engine_revision": self.engine_revision,
            "model_revision": self.model_revision,
            "model_artifact_sha256": self.model_artifact_sha256,
            "audio_artifact": self.audio_artifact.to_dict(),
            "transcript": self.transcript,
            "normalized_transcript": self.normalized_transcript,
            "exact_entities": dict(self.exact_entities),
            "stt_evidence": self.stt_evidence.to_dict(),
        }
