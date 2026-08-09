from __future__ import annotations

import hashlib
import math
import wave
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


class SpeakerEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AudioArtifact:
    sha256: str
    bytes: int
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int


@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    label: str
    status: str
    min_target_similarity: float
    min_target_gain: float
    min_target_advantage: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise SpeakerEvidenceError("policy label must not be empty")
        if self.status not in {"proposed", "approved"}:
            raise SpeakerEvidenceError("policy status must be proposed or approved")
        for name in (
            "min_target_similarity",
            "min_target_gain",
            "min_target_advantage",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not -1.0 <= value <= 1.0:
                raise SpeakerEvidenceError(f"{name} must be finite and in [-1, 1]")


@dataclass(frozen=True, slots=True)
class SpeakerEvidence:
    source_to_target: float
    source_to_output: float
    target_to_output: float
    target_similarity_gain: float
    target_advantage: float
    status: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence"] = list(self.evidence)
        return value


class EmbeddingBackend(Protocol):
    def embed(self, path: Path) -> Sequence[float]: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_model_tree(path: str | Path) -> str:
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise SpeakerEvidenceError("model artifact must be a directory")
    digest = hashlib.sha256(b"liveconv-speaker-model-tree-v1\0")
    files: list[Path] = []
    for item in root.rglob("*"):
        if item.is_symlink():
            raise SpeakerEvidenceError("model artifact must not contain symlinks")
        if item.is_file():
            files.append(item)
        elif not item.is_dir():
            raise SpeakerEvidenceError("model artifact contains a non-regular entry")
    if not files:
        raise SpeakerEvidenceError("model artifact must not be empty")
    for item in sorted(files, key=lambda value: value.relative_to(root).as_posix()):
        relative = item.relative_to(root).as_posix().encode("utf-8")
        size = item.stat().st_size
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with item.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def inspect_pcm_wav(path: str | Path) -> AudioArtifact:
    artifact = Path(path).resolve(strict=True)
    with wave.open(str(artifact), "rb") as audio:
        if audio.getcomptype() != "NONE" or audio.getsampwidth() != 2:
            raise SpeakerEvidenceError("audio must be uncompressed PCM16 WAV")
        frames = audio.getnframes()
        sample_rate = audio.getframerate()
        channels = audio.getnchannels()
    if sample_rate <= 0 or channels <= 0 or frames <= 0:
        raise SpeakerEvidenceError("audio format must be positive and non-empty")
    return AudioArtifact(
        sha256=sha256_file(artifact),
        bytes=artifact.stat().st_size,
        duration_seconds=round(frames / sample_rate, 9),
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=2,
    )


def _normalized(values: Sequence[float]) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if not result or any(not math.isfinite(value) for value in result):
        raise SpeakerEvidenceError("embedding must be finite and non-empty")
    norm = math.sqrt(sum(value * value for value in result))
    if not math.isfinite(norm) or norm <= 0:
        raise SpeakerEvidenceError("embedding norm must be positive")
    return tuple(value / norm for value in result)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    normalized_left = _normalized(left)
    normalized_right = _normalized(right)
    if len(normalized_left) != len(normalized_right):
        raise SpeakerEvidenceError("embedding dimensions must match")
    return max(
        -1.0,
        min(1.0, sum(a * b for a, b in zip(normalized_left, normalized_right))),
    )


def compare_embeddings(
    source: Sequence[float],
    target: Sequence[float],
    output: Sequence[float],
    policy: ComparisonPolicy,
) -> SpeakerEvidence:
    source_to_target = _cosine(source, target)
    source_to_output = _cosine(source, output)
    target_to_output = _cosine(target, output)
    target_gain = target_to_output - source_to_target
    advantage = target_to_output - source_to_output
    target_passed = target_to_output >= policy.min_target_similarity
    gain_passed = target_gain >= policy.min_target_gain
    advantage_passed = advantage >= policy.min_target_advantage
    status = "pass" if target_passed and gain_passed and advantage_passed else "fail"
    return SpeakerEvidence(
        source_to_target=source_to_target,
        source_to_output=source_to_output,
        target_to_output=target_to_output,
        target_similarity_gain=target_gain,
        target_advantage=advantage,
        status=status,
        evidence=(
            f"target_to_output={target_to_output:.8f} >= "
            f"{policy.min_target_similarity:.8f}",
            f"target_similarity_gain={target_gain:.8f} >= {policy.min_target_gain:.8f}",
            f"target_advantage={advantage:.8f} >= {policy.min_target_advantage:.8f}",
        ),
    )
