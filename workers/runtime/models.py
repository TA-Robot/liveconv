from __future__ import annotations

import math
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONFIGURATION_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ENVIRONMENT_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _unsigned(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an unsigned integer")


def _positive(name: str, value: int) -> None:
    _unsigned(name, value)
    if value == 0:
        raise ValueError(f"{name} must be greater than zero")


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    env_var: str
    sha256: str

    def __post_init__(self) -> None:
        if not _ENVIRONMENT_NAME_RE.fullmatch(self.env_var):
            raise ValueError("artifact env_var must be an uppercase environment name")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError(
                "artifact sha256 must be 64 lowercase hexadecimal characters"
            )


@dataclass(frozen=True, slots=True)
class AudioFrame:
    generation_id: int
    sequence: int
    sample_rate: int
    channels: int
    samples_per_channel: int
    source_monotonic_ns: int
    pcm_f32le: bytes

    def __post_init__(self) -> None:
        _unsigned("generation_id", self.generation_id)
        _unsigned("sequence", self.sequence)
        _positive("sample_rate", self.sample_rate)
        _positive("channels", self.channels)
        _positive("samples_per_channel", self.samples_per_channel)
        _unsigned("source_monotonic_ns", self.source_monotonic_ns)
        if self.channels != 1:
            raise ValueError("worker audio must be mono")
        expected_bytes = self.channels * self.samples_per_channel * 4
        if len(self.pcm_f32le) != expected_bytes:
            raise ValueError(f"pcm_f32le must contain exactly {expected_bytes} bytes")
        if any(not math.isfinite(value) for value in self.unpack_samples()):
            raise ValueError("pcm_f32le contains a non-finite sample")

    @classmethod
    def from_samples(
        cls,
        *,
        generation_id: int,
        sequence: int,
        sample_rate: int,
        channels: int,
        samples_per_channel: int,
        source_monotonic_ns: int,
        samples: Sequence[float],
    ) -> AudioFrame:
        expected_samples = channels * samples_per_channel
        if len(samples) != expected_samples:
            raise ValueError(f"samples must contain exactly {expected_samples} values")
        values = tuple(float(value) for value in samples)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("samples contains a non-finite value")
        return cls(
            generation_id=generation_id,
            sequence=sequence,
            sample_rate=sample_rate,
            channels=channels,
            samples_per_channel=samples_per_channel,
            source_monotonic_ns=source_monotonic_ns,
            pcm_f32le=struct.pack(f"<{len(values)}f", *values),
        )

    def unpack_samples(self) -> tuple[float, ...]:
        count = self.channels * self.samples_per_channel
        return struct.unpack(f"<{count}f", self.pcm_f32le)


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    profile_id: str
    pipeline_id: str
    configuration_hash: str
    command: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str]
    implementation_revision: str
    weight_revision: str | None
    frame_ms: int
    queue_budget_ms: int
    startup_timeout_ms: int
    first_output_timeout_ms: int
    stall_timeout_ms: int
    cancel_timeout_ms: int
    close_grace_ms: int
    terminate_grace_ms: int
    restart_limit: int = 3
    restart_window_ms: int = 60_000
    artifacts: tuple[ArtifactSpec, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.profile_id or len(self.profile_id) > 256:
            raise ValueError("profile_id must be between 1 and 256 characters")
        if not self.pipeline_id or len(self.pipeline_id) > 256:
            raise ValueError("pipeline_id must be between 1 and 256 characters")
        if not _CONFIGURATION_HASH_RE.fullmatch(self.configuration_hash):
            raise ValueError("configuration_hash must be a sha256-prefixed digest")
        if not self.command or any(not item for item in self.command):
            raise ValueError("command must not be empty")
        if not isinstance(self.cwd, Path):
            object.__setattr__(self, "cwd", Path(self.cwd))
        for name, value in self.environment.items():
            if not isinstance(name, str) or not isinstance(value, str) or "=" in name:
                raise ValueError("environment must map valid string names to strings")
        for name in (
            "frame_ms",
            "queue_budget_ms",
            "startup_timeout_ms",
            "first_output_timeout_ms",
            "stall_timeout_ms",
            "cancel_timeout_ms",
            "close_grace_ms",
            "terminate_grace_ms",
            "restart_window_ms",
        ):
            _positive(name, getattr(self, name))
        _unsigned("restart_limit", self.restart_limit)
        if self.queue_budget_ms % self.frame_ms:
            raise ValueError("queue_budget_ms must be divisible by frame_ms")
        if any(not isinstance(artifact, ArtifactSpec) for artifact in self.artifacts):
            raise ValueError("artifacts must contain ArtifactSpec values")

    @property
    def input_capacity_frames(self) -> int:
        return self.queue_budget_ms // self.frame_ms


@dataclass(frozen=True, slots=True)
class WorkerReady:
    profile_id: str
    pipeline_id: str
    implementation_revision: str
    weight_revision: str | None
    configuration_hash: str


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    ready: bool
    active_generation_id: int | None
    queue_depth_frames: int
    capacity_frames: int


@dataclass(frozen=True, slots=True)
class GenerationResult:
    generation_id: int
