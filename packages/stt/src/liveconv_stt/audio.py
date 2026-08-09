"""Bounded, deterministic PCM WAV ingestion."""

from __future__ import annotations

import hashlib
import io
import wave
from dataclasses import dataclass
from pathlib import Path

from .errors import AudioValidationError

DEFAULT_MAX_INPUT_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_DURATION_SECONDS = 300.0
HARD_MAX_INPUT_BYTES = 64 * 1024 * 1024
HARD_MAX_DURATION_SECONDS = 600.0
MIN_SAMPLE_RATE_HZ = 8_000
MAX_SAMPLE_RATE_HZ = 192_000


@dataclass(frozen=True)
class InputLimits:
    """Caller-selectable limits capped by non-bypassable package ceilings."""

    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS

    def __post_init__(self) -> None:
        if not 1 <= self.max_input_bytes <= HARD_MAX_INPUT_BYTES:
            raise AudioValidationError("max input bytes is outside the safe range")
        if not 0 < self.max_duration_seconds <= HARD_MAX_DURATION_SECONDS:
            raise AudioValidationError("max duration is outside the safe range")


@dataclass(frozen=True)
class AudioArtifact:
    sha256: str
    bytes: int
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    duration_seconds: float

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "sha256": self.sha256,
            "bytes": self.bytes,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "sample_width_bytes": self.sample_width_bytes,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class PcmAudio:
    """Validated mono signed 16-bit little-endian samples and provenance."""

    pcm_s16le: bytes
    artifact: AudioArtifact


def read_pcm_wav(path: str | Path, *, limits: InputLimits | None = None) -> PcmAudio:
    """Read a regular mono PCM16 WAV once, enforcing byte and duration limits."""

    policy = limits or InputLimits()
    artifact_path = Path(path)
    try:
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise AudioValidationError("input must be a regular non-symlink file")
        size = artifact_path.stat().st_size
        if size > policy.max_input_bytes:
            raise AudioValidationError("input WAV exceeds the configured byte limit")
        with artifact_path.open("rb") as source:
            encoded = source.read(policy.max_input_bytes + 1)
    except AudioValidationError:
        raise
    except OSError:
        raise AudioValidationError("input WAV could not be read") from None

    if len(encoded) > policy.max_input_bytes:
        raise AudioValidationError("input WAV exceeds the configured byte limit")
    if not encoded:
        raise AudioValidationError("input WAV must not be empty")

    try:
        with wave.open(io.BytesIO(encoded), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            compression = wav.getcomptype()
            if compression != "NONE":
                raise AudioValidationError("input WAV must use uncompressed PCM")
            if channels != 1:
                raise AudioValidationError("input WAV must be mono")
            if sample_width != 2:
                raise AudioValidationError("input WAV must use signed 16-bit PCM")
            if not MIN_SAMPLE_RATE_HZ <= sample_rate <= MAX_SAMPLE_RATE_HZ:
                raise AudioValidationError(
                    "input WAV sample rate is outside the safe range"
                )
            if frame_count <= 0:
                raise AudioValidationError("input WAV must contain at least one frame")
            duration = frame_count / sample_rate
            if duration > policy.max_duration_seconds:
                raise AudioValidationError(
                    "input WAV exceeds the configured duration limit"
                )
            pcm = wav.readframes(frame_count)
    except AudioValidationError:
        raise
    except (EOFError, wave.Error):
        raise AudioValidationError("input is not a valid PCM WAV") from None

    expected_pcm_bytes = frame_count * channels * sample_width
    if len(pcm) != expected_pcm_bytes:
        raise AudioValidationError("input WAV contains truncated PCM data")

    return PcmAudio(
        pcm_s16le=pcm,
        artifact=AudioArtifact(
            sha256=hashlib.sha256(encoded).hexdigest(),
            bytes=len(encoded),
            sample_rate_hz=sample_rate,
            channels=channels,
            sample_width_bytes=sample_width,
            frame_count=frame_count,
            duration_seconds=duration,
        ),
    )
