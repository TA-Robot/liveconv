from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from packaging.markers import Marker
from packaging.utils import canonicalize_name

from .evidence import SpeakerEvidenceError

RUNTIME_LOCK_REVISION = "liveconv-speaker-hash-locked-runtime-v1"
RUNTIME_LOCK_SHA256 = "036443cefaffc07492b31078f861d7bd5c816b96007819c63323968089760fd3"
TORCH_VERSION = "2.6.0"
TORCHAUDIO_VERSION = "2.6.0"
_PIN_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;\\]+)"
    r"(?:\s*;\s*(.+?))?\s*\\?$"
)
_HASH_RE = re.compile(r"^\s+--hash=sha256:[0-9a-f]{64}(?:\s+\\)?$")


@dataclass(frozen=True, slots=True)
class RuntimeLock:
    revision: str
    sha256: str
    packages: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "sha256": self.sha256,
            "packages": dict(sorted(self.packages.items())),
        }


def _lock_bytes() -> bytes:
    resource = importlib.resources.files("liveconv_speaker").joinpath(
        "runtime-requirements.txt"
    )
    return resource.read_bytes()


def _active_pins(content: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if not line or line.startswith(("#", " ")):
            continue
        match = _PIN_RE.fullmatch(line)
        if match is None:
            raise SpeakerEvidenceError("speaker runtime lock contains an invalid pin")
        if index + 1 >= len(lines) or _HASH_RE.fullmatch(lines[index + 1]) is None:
            raise SpeakerEvidenceError("speaker runtime lock contains an unhashed pin")
        marker = match.group(3)
        if marker is not None and not Marker(marker).evaluate():
            continue
        name = canonicalize_name(match.group(1))
        version = match.group(2)
        existing = pins.get(name)
        if existing is not None and existing != version:
            raise SpeakerEvidenceError("speaker runtime lock has conflicting pins")
        pins[name] = version
    return pins


def verify_runtime_lock(
    *, version_lookup: Callable[[str], str] = importlib.metadata.version
) -> RuntimeLock:
    content = _lock_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != RUNTIME_LOCK_SHA256:
        raise SpeakerEvidenceError("speaker runtime lock digest does not match")
    pins = _active_pins(content.decode("utf-8"))
    if (
        pins.get("torch") != TORCH_VERSION
        or pins.get("torchaudio") != TORCHAUDIO_VERSION
    ):
        raise SpeakerEvidenceError("speaker runtime lock has an unsupported Torch pair")
    if TORCH_VERSION != TORCHAUDIO_VERSION:
        raise SpeakerEvidenceError("Torch and TorchAudio releases must match")
    installed: dict[str, str] = {}
    for name, expected in pins.items():
        try:
            actual = version_lookup(name)
        except importlib.metadata.PackageNotFoundError:
            raise SpeakerEvidenceError(
                "speaker runtime closure is incomplete"
            ) from None
        if actual != expected:
            raise SpeakerEvidenceError("speaker runtime closure does not match lock")
        installed[name] = actual
    return RuntimeLock(RUNTIME_LOCK_REVISION, digest, installed)


def installed_runtime_smoke(path: str) -> dict[str, Any]:
    """Import the installed runtime, load PCM, and exercise the resampler."""

    runtime = verify_runtime_lock()
    try:
        import torch
        import torchaudio
        from speechbrain.inference.classifiers import EncoderClassifier

        if EncoderClassifier.__name__ != "EncoderClassifier":
            raise SpeakerEvidenceError("SpeechBrain classifier import is invalid")

        waveform, sample_rate = torchaudio.load(path)
        if (
            waveform.ndim != 2
            or waveform.numel() == 0
            or not torch.isfinite(waveform).all()
        ):
            raise SpeakerEvidenceError("speaker runtime loaded invalid audio")
        resampled = torchaudio.functional.resample(waveform, sample_rate, 16_000)
        if resampled.ndim != 2 or resampled.numel() == 0:
            raise SpeakerEvidenceError(
                "speaker runtime resampler returned invalid audio"
            )
    except SpeakerEvidenceError:
        raise
    except Exception:
        raise SpeakerEvidenceError("speaker installed runtime smoke failed") from None
    return {
        "runtime": runtime.to_dict(),
        "input_sample_rate_hz": sample_rate,
        "output_sample_rate_hz": 16_000,
        "output_frames": int(resampled.shape[-1]),
    }
