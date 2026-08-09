"""Offline-only adapter for the revision-pinned faster-whisper engine."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..audio import PcmAudio
from ..errors import ArtifactVerificationError, ConfigurationError
from ..model_artifact import verify_model_tree

ENGINE_PACKAGE = "faster-whisper"
ENGINE_VERSION = "1.2.1"
ENGINE_REVISION = f"{ENGINE_PACKAGE}=={ENGINE_VERSION}"
_RUNTIME_LOCK_RESOURCE = "real-run-requirements.txt"
_REQUIRED_LOCAL_FILES = ("config.json", "model.bin", "tokenizer.json")
_DEFAULT_DECODE_CONFIG: dict[str, Any] = {
    "beam_size": 5,
    "best_of": 5,
    "condition_on_previous_text": False,
    "length_penalty": 1.0,
    "no_repeat_ngram_size": 0,
    "patience": 1.0,
    "repetition_penalty": 1.0,
    "temperature": 0.0,
    "vad_filter": False,
    "without_timestamps": True,
}
_DECODE_KEYS = frozenset(_DEFAULT_DECODE_CONFIG)
_RUNTIME_KEYS = frozenset(
    {
        "compute_type",
        "cpu_threads",
        "device",
        "num_workers",
        "runtime_lock_sha256",
        "runtime_packages",
    }
)


@lru_cache(maxsize=1)
def _runtime_lock() -> tuple[str, dict[str, str]]:
    """Load the packaged, hash-locked runtime closure for this platform."""

    encoded = (
        importlib.resources.files("liveconv_stt")
        .joinpath(_RUNTIME_LOCK_RESOURCE)
        .read_bytes()
    )
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    try:
        from packaging.markers import default_environment
        from packaging.requirements import Requirement
    except ImportError:
        raise ConfigurationError(
            "install the hash-locked liveconv-stt inference runtime"
        ) from None

    environment = default_environment()
    versions: dict[str, str] = {}
    for raw_line in encoded.decode("utf-8").splitlines():
        if not raw_line or raw_line[0].isspace() or raw_line.startswith("#"):
            continue
        requirement = Requirement(raw_line.removesuffix("\\").rstrip())
        if requirement.marker is not None and not requirement.marker.evaluate(
            environment
        ):
            continue
        specifiers = list(requirement.specifier)
        if len(specifiers) != 1 or specifiers[0].operator != "==":
            raise ConfigurationError("STT runtime lock contains an unpinned package")
        versions[requirement.name] = specifiers[0].version
    if ENGINE_PACKAGE not in versions or versions[ENGINE_PACKAGE] != ENGINE_VERSION:
        raise ConfigurationError("STT runtime lock does not match the engine revision")
    return digest, dict(sorted(versions.items()))


def _integer(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ConfigurationError(f"{name} is outside the supported range")
    return value


def _number(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{name} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"{name} is outside the supported range")
    return result


class FasterWhisperBackend:
    """Run a verified local CTranslate2 Whisper model without network fallback."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        expected_sha256: str,
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        num_workers: int = 1,
    ) -> None:
        self._model_path = Path(model_path)
        verify_model_tree(self._model_path, expected_sha256)
        missing = [
            name
            for name in _REQUIRED_LOCAL_FILES
            if not (self._model_path / name).is_file()
        ]
        if missing:
            raise ArtifactVerificationError("local model artifact is incomplete")
        runtime_lock_sha256, expected_versions = _runtime_lock()
        try:
            installed_versions = {
                name: importlib.metadata.version(name) for name in expected_versions
            }
        except importlib.metadata.PackageNotFoundError:
            raise ConfigurationError(
                "install the hash-locked liveconv-stt inference runtime"
            ) from None
        if installed_versions != expected_versions:
            raise ConfigurationError("installed STT runtime revisions do not match")
        if device not in {"cpu", "cuda"}:
            raise ConfigurationError("faster-whisper device must be cpu or cuda")
        if compute_type not in {
            "auto",
            "bfloat16",
            "default",
            "float16",
            "float32",
            "int16",
            "int8",
            "int8_bfloat16",
            "int8_float16",
            "int8_float32",
        }:
            raise ConfigurationError("faster-whisper compute type is unsupported")
        _integer(cpu_threads, name="cpu_threads", minimum=1, maximum=256)
        _integer(num_workers, name="num_workers", minimum=1, maximum=32)

        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                str(self._model_path),
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                num_workers=num_workers,
                local_files_only=True,
            )
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError(
                "failed to initialize the verified local STT model"
            ) from None
        self._runtime_config = {
            "compute_type": compute_type,
            "cpu_threads": cpu_threads,
            "device": device,
            "num_workers": num_workers,
            "runtime_lock_sha256": runtime_lock_sha256,
            "runtime_packages": dict(sorted(installed_versions.items())),
        }

    def canonicalize_decode_config(
        self, config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        unknown = set(config) - _DECODE_KEYS
        if unknown:
            raise ConfigurationError(
                "faster-whisper decode configuration has unknown fields"
            )
        resolved = {**_DEFAULT_DECODE_CONFIG, **dict(config)}
        resolved["beam_size"] = _integer(
            resolved["beam_size"], name="beam_size", minimum=1, maximum=20
        )
        resolved["best_of"] = _integer(
            resolved["best_of"], name="best_of", minimum=1, maximum=20
        )
        resolved["no_repeat_ngram_size"] = _integer(
            resolved["no_repeat_ngram_size"],
            name="no_repeat_ngram_size",
            minimum=0,
            maximum=20,
        )
        resolved["temperature"] = _number(
            resolved["temperature"], name="temperature", minimum=0.0, maximum=1.0
        )
        resolved["patience"] = _number(
            resolved["patience"], name="patience", minimum=0.0, maximum=10.0
        )
        resolved["length_penalty"] = _number(
            resolved["length_penalty"],
            name="length_penalty",
            minimum=-10.0,
            maximum=10.0,
        )
        resolved["repetition_penalty"] = _number(
            resolved["repetition_penalty"],
            name="repetition_penalty",
            minimum=0.1,
            maximum=10.0,
        )
        for name in ("condition_on_previous_text", "vad_filter", "without_timestamps"):
            if not isinstance(resolved[name], bool):
                raise ConfigurationError(f"{name} must be boolean")
        return {**resolved, **self._runtime_config}

    def transcribe(
        self,
        audio: PcmAudio,
        *,
        language: str,
        decode_config: Mapping[str, Any],
    ) -> str:
        import numpy as np

        samples = np.frombuffer(audio.pcm_s16le, dtype="<i2").astype(np.float32)
        samples /= 32768.0
        options = {
            key: value
            for key, value in decode_config.items()
            if key not in _RUNTIME_KEYS
        }
        segments, _ = self._model.transcribe(
            samples,
            language="ja" if language == "ja-JP" else language,
            task="transcribe",
            log_progress=False,
            word_timestamps=False,
            **options,
        )
        parts: list[str] = []
        for segment in segments:
            text = getattr(segment, "text", None)
            if not isinstance(text, str):
                raise RuntimeError("backend segment text is invalid")
            parts.append(text)
        return "".join(parts).strip()
