"""Revision-pinned Japanese STT evidence generation."""

from .audio import AudioArtifact, InputLimits, PcmAudio, read_pcm_wav
from .errors import (
    ArtifactVerificationError,
    AudioValidationError,
    BackendExecutionError,
    ConfigurationError,
    SttError,
)
from .model_artifact import MODEL_TREE_DIGEST_REVISION, sha256_model_tree
from .models import BUNDLE_SCHEMA_VERSION, SttEvidenceRecord, TranscriptionBundle
from .normalization import (
    NORMALIZATION_REVISION,
    compare_exact_entities,
    normalize_japanese,
)
from .runner import SttBackend, transcribe_pcm_wav

__all__ = [
    "ArtifactVerificationError",
    "AudioArtifact",
    "AudioValidationError",
    "BUNDLE_SCHEMA_VERSION",
    "BackendExecutionError",
    "ConfigurationError",
    "InputLimits",
    "MODEL_TREE_DIGEST_REVISION",
    "NORMALIZATION_REVISION",
    "PcmAudio",
    "SttBackend",
    "SttError",
    "SttEvidenceRecord",
    "TranscriptionBundle",
    "compare_exact_entities",
    "normalize_japanese",
    "read_pcm_wav",
    "sha256_model_tree",
    "transcribe_pcm_wav",
]
