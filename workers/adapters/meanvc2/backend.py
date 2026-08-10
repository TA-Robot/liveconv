from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .network_isolation import require_non_unix_socket_denial

INPUT_SAMPLE_RATE = 48_000
NATIVE_SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = INPUT_SAMPLE_RATE * FRAME_MS // 1_000
INFERENCE_FRAMES = 8
INFERENCE_SAMPLES = INFERENCE_FRAMES * FRAME_SAMPLES
CAPACITY_FRAMES = 25
SOURCE_REVISION = "0d39c8ae416a37edb9884db67334e4b9d0c3e308"
IMPLEMENTATION_PREFIX = "meanvc2-streaming-adapter-v1"

ADAPTER_ROOT = Path(__file__).resolve().parent
ADAPTER_SOURCE_FILES = (
    "__init__.py",
    "__main__.py",
    "backend.py",
    "network_isolation.py",
    "worker.py",
)
UPSTREAM_SOURCE_FILES = (
    "runtime/run_rt.py",
    "runtime/src/__init__.py",
    "runtime/src/dit.py",
    "runtime/src/dit_modules.py",
    "runtime/src/modules.py",
    "runtime/src/speaker.py",
    "src/config/config_40ms_40ms.json",
)
_SHA256_LENGTH = 64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_named_files(root: Path, names: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for name in names:
        encoded_name = name.encode("utf-8")
        content = (root / name).read_bytes()
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def sha256_adapter_source(root: Path = ADAPTER_ROOT) -> str:
    return sha256_named_files(root, ADAPTER_SOURCE_FILES)


def _required_file(environment: Mapping[str, str], name: str) -> Path:
    value = environment.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{name} must identify a regular file")
    return path


def _required_directory(environment: Mapping[str, str], name: str) -> Path:
    value = environment.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{name} must identify a directory")
    return path


def _digest(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "")
    if len(value) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _verify_file(label: str, path: Path, digest: str) -> None:
    if sha256_file(path) != digest:
        raise ValueError(f"{label} digest does not match")


def _verify_source(root: Path, revision: str, source_sha256: str) -> None:
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("MeanVC2 source checkout could not be verified") from error
    if head != revision or dirty:
        raise ValueError("MeanVC2 source checkout is not the pinned clean revision")
    if sha256_named_files(root, UPSTREAM_SOURCE_FILES) != source_sha256:
        raise ValueError("MeanVC2 executed source digest does not match")


def _load_authorization(path: Path, digest: str, target_digest: str) -> None:
    _verify_file("MeanVC2 target authorization", path, digest)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("MeanVC2 target authorization is not valid JSON") from error
    required = {
        "schema_version",
        "authorization_id",
        "owner",
        "authorization_record",
        "permitted_purpose",
        "retention_policy",
        "deletion_path",
        "classification",
        "target_reference_sha256",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("MeanVC2 target authorization has an unexpected schema")
    if document["schema_version"] != 1:
        raise ValueError("MeanVC2 target authorization schema is unsupported")
    if document["target_reference_sha256"] != target_digest:
        raise ValueError("MeanVC2 target authorization identifies another voice")
    for key in required - {"schema_version"}:
        if not isinstance(document[key], str) or not document[key].strip():
            raise ValueError("MeanVC2 target authorization fields must be nonempty")


@dataclass(frozen=True, slots=True)
class Meanvc2Configuration:
    source_root: Path
    source_revision: str
    source_sha256: str
    config_path: Path
    config_sha256: str
    asr_path: Path
    asr_sha256: str
    checkpoint_path: Path
    checkpoint_sha256: str
    vocoder_path: Path
    vocoder_sha256: str
    speaker_config_path: Path
    speaker_config_sha256: str
    speaker_checkpoint_path: Path
    speaker_checkpoint_sha256: str
    target_reference_path: Path
    target_reference_sha256: str
    target_authorization_path: Path
    target_authorization_sha256: str
    adapter_source_sha256: str
    runtime_lock_path: Path
    runtime_lock_sha256: str
    worker_wheel_path: Path
    worker_wheel_sha256: str
    interpreter_path: Path
    interpreter_sha256: str
    device: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> Meanvc2Configuration:
        values = os.environ if environment is None else environment
        configuration = cls(
            source_root=_required_directory(values, "LIVECONV_MEANVC2_SOURCE_ROOT"),
            source_revision=values.get("LIVECONV_MEANVC2_SOURCE_REVISION", ""),
            source_sha256=_digest(values, "LIVECONV_MEANVC2_SOURCE_SHA256"),
            config_path=_required_file(values, "LIVECONV_MEANVC2_CONFIG_PATH"),
            config_sha256=_digest(values, "LIVECONV_MEANVC2_CONFIG_SHA256"),
            asr_path=_required_file(values, "LIVECONV_MEANVC2_ASR_PATH"),
            asr_sha256=_digest(values, "LIVECONV_MEANVC2_ASR_SHA256"),
            checkpoint_path=_required_file(values, "LIVECONV_MEANVC2_CHECKPOINT_PATH"),
            checkpoint_sha256=_digest(values, "LIVECONV_MEANVC2_CHECKPOINT_SHA256"),
            vocoder_path=_required_file(values, "LIVECONV_MEANVC2_VOCODER_PATH"),
            vocoder_sha256=_digest(values, "LIVECONV_MEANVC2_VOCODER_SHA256"),
            speaker_config_path=_required_file(
                values, "LIVECONV_MEANVC2_SPEAKER_CONFIG_PATH"
            ),
            speaker_config_sha256=_digest(
                values, "LIVECONV_MEANVC2_SPEAKER_CONFIG_SHA256"
            ),
            speaker_checkpoint_path=_required_file(
                values, "LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_PATH"
            ),
            speaker_checkpoint_sha256=_digest(
                values, "LIVECONV_MEANVC2_SPEAKER_CHECKPOINT_SHA256"
            ),
            target_reference_path=_required_file(
                values, "LIVECONV_MEANVC2_TARGET_REFERENCE_PATH"
            ),
            target_reference_sha256=_digest(
                values, "LIVECONV_MEANVC2_TARGET_REFERENCE_SHA256"
            ),
            target_authorization_path=_required_file(
                values, "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_PATH"
            ),
            target_authorization_sha256=_digest(
                values, "LIVECONV_MEANVC2_TARGET_AUTHORIZATION_SHA256"
            ),
            adapter_source_sha256=_digest(
                values, "LIVECONV_MEANVC2_ADAPTER_SOURCE_SHA256"
            ),
            runtime_lock_path=_required_file(
                values, "LIVECONV_MEANVC2_RUNTIME_LOCK_PATH"
            ),
            runtime_lock_sha256=_digest(values, "LIVECONV_MEANVC2_RUNTIME_LOCK_SHA256"),
            worker_wheel_path=_required_file(
                values, "LIVECONV_MEANVC2_WORKER_WHEEL_PATH"
            ),
            worker_wheel_sha256=_digest(values, "LIVECONV_MEANVC2_WORKER_WHEEL_SHA256"),
            interpreter_path=_required_file(
                values, "LIVECONV_MEANVC2_INTERPRETER_PATH"
            ),
            interpreter_sha256=_digest(values, "LIVECONV_MEANVC2_INTERPRETER_SHA256"),
            device=values.get("LIVECONV_MEANVC2_DEVICE", ""),
        )
        configuration.validate()
        return configuration

    @property
    def implementation_revision(self) -> str:
        return f"{IMPLEMENTATION_PREFIX}+sha256:{self.adapter_source_sha256}"

    @property
    def weight_revision(self) -> str:
        material = {
            "asr_sha256": self.asr_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "speaker_checkpoint_sha256": self.speaker_checkpoint_sha256,
            "speaker_config_sha256": self.speaker_config_sha256,
            "vocoder_sha256": self.vocoder_sha256,
        }
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
                    "ascii"
                )
            ).hexdigest()
        )

    @property
    def configuration_payload(self) -> dict[str, object]:
        return {
            "adapter_source_sha256": self.adapter_source_sha256,
            "asr_sha256": self.asr_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "config_sha256": self.config_sha256,
            "device": self.device,
            "inference_frames": INFERENCE_FRAMES,
            "native_sample_rate": NATIVE_SAMPLE_RATE,
            "output_sample_rate": INPUT_SAMPLE_RATE,
            "queue_capacity_frames": CAPACITY_FRAMES,
            "runtime_lock_sha256": self.runtime_lock_sha256,
            "source_revision": self.source_revision,
            "source_sha256": self.source_sha256,
            "speaker_checkpoint_sha256": self.speaker_checkpoint_sha256,
            "speaker_config_sha256": self.speaker_config_sha256,
            "target_authorization_sha256": self.target_authorization_sha256,
            "target_reference_sha256": self.target_reference_sha256,
            "vocoder_sha256": self.vocoder_sha256,
            "worker_wheel_sha256": self.worker_wheel_sha256,
        }

    @property
    def configuration_hash(self) -> str:
        encoded = json.dumps(
            self.configuration_payload, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def validate(self) -> None:
        require_non_unix_socket_denial()
        if self.source_revision != SOURCE_REVISION:
            raise ValueError("MeanVC2 source revision is not approved")
        if self.device != "cuda:0":
            raise ValueError("MeanVC2 device must be cuda:0")
        _verify_source(self.source_root, self.source_revision, self.source_sha256)
        bindings = (
            ("configuration", self.config_path, self.config_sha256),
            ("ASR", self.asr_path, self.asr_sha256),
            ("checkpoint", self.checkpoint_path, self.checkpoint_sha256),
            ("vocoder", self.vocoder_path, self.vocoder_sha256),
            ("speaker config", self.speaker_config_path, self.speaker_config_sha256),
            (
                "speaker checkpoint",
                self.speaker_checkpoint_path,
                self.speaker_checkpoint_sha256,
            ),
            (
                "target reference",
                self.target_reference_path,
                self.target_reference_sha256,
            ),
            ("runtime lock", self.runtime_lock_path, self.runtime_lock_sha256),
            ("worker wheel", self.worker_wheel_path, self.worker_wheel_sha256),
            ("interpreter", self.interpreter_path, self.interpreter_sha256),
        )
        for label, path, digest in bindings:
            _verify_file(f"MeanVC2 {label}", path, digest)
        _load_authorization(
            self.target_authorization_path,
            self.target_authorization_sha256,
            self.target_reference_sha256,
        )
        if sha256_adapter_source() != self.adapter_source_sha256:
            raise ValueError("MeanVC2 adapter source digest does not match")
        if self.interpreter_path.resolve() != Path(sys.executable).resolve():
            raise ValueError("MeanVC2 is running under another interpreter")


class ConversionBackend(Protocol):
    implementation_revision: str
    weight_revision: str
    configuration_hash: str

    def start_generation(self) -> None: ...

    def process_batch(
        self, samples: Sequence[float], sample_rate: int, *, final: bool
    ) -> tuple[float, ...]: ...

    def close(self) -> None: ...


class DeterministicTestBackend:
    implementation_revision = "meanvc2-test-backend-v1"
    weight_revision = "sha256:" + "1" * 64
    configuration_hash = "sha256:" + "2" * 64

    def start_generation(self) -> None:
        return None

    def process_batch(
        self, samples: Sequence[float], sample_rate: int, *, final: bool
    ) -> tuple[float, ...]:
        del final
        if sample_rate != INPUT_SAMPLE_RATE:
            raise ValueError("test backend sample rate differs")
        return tuple(-0.5 * float(sample) for sample in samples)

    def close(self) -> None:
        return None


class OfficialMeanvc2Backend:
    """Pinned upstream 40+40 ms route with one prepared target voice."""

    def __init__(self, configuration: Meanvc2Configuration) -> None:
        configuration.validate()
        self.configuration = configuration
        self.implementation_revision = configuration.implementation_revision
        self.weight_revision = configuration.weight_revision
        self.configuration_hash = configuration.configuration_hash
        self._closed = False
        runtime_root = configuration.source_root / "runtime"
        dependency_root = os.environ.get("LIVECONV_MEANVC2_DEPENDENCY_ROOT", "")
        if dependency_root:
            dependency_path = Path(dependency_root).resolve(strict=True)
            if not dependency_path.is_dir() or dependency_path.is_symlink():
                raise ValueError("MeanVC2 dependency root is unsafe")
            sys.path.insert(0, str(dependency_path))
        sys.path.insert(0, str(runtime_root))
        upstream_output = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        try:
            with contextlib.redirect_stdout(upstream_output):
                spec = importlib.util.spec_from_file_location(
                    "liveconv_meanvc2_upstream", runtime_root / "run_rt.py"
                )
                if spec is None or spec.loader is None:
                    raise RuntimeError("MeanVC2 upstream runtime could not be loaded")
                upstream = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(upstream)
                upstream.VOCODER_PATH = str(configuration.vocoder_path)
                upstream.SPEAKER_MODEL_PATH = str(configuration.speaker_checkpoint_path)
                upstream.WAVLM_CONFIG_PATH = str(configuration.speaker_config_path)
                upstream.MODEL_PATHS["40ms"]["ckpt"] = str(
                    configuration.checkpoint_path
                )
                upstream.MODEL_PATHS["40ms"]["config"] = str(configuration.config_path)
                upstream.MODEL_PATHS["40ms"]["asr_ckpt"] = str(configuration.asr_path)
                runner = upstream.VCRunner(
                    str(configuration.target_reference_path),
                    device="cuda",
                    model="40ms",
                )
                torch = upstream.torch
                if not torch.cuda.is_available():
                    raise RuntimeError("MeanVC2 requires CUDA")
                soxr = __import__("soxr")
        except Exception:
            upstream_output.close()
            raise
        self._upstream_output = upstream_output
        self._upstream = upstream
        self._runner = runner
        self._torch = torch
        self._soxr = soxr
        self.start_generation()

    def start_generation(self) -> None:
        if self._closed:
            raise RuntimeError("MeanVC2 backend is closed")
        self._runner._init_cache()  # noqa: SLF001
        self._torch.manual_seed(42)
        self._torch.cuda.manual_seed_all(42)

    def process_batch(
        self, samples: Sequence[float], sample_rate: int, *, final: bool
    ) -> tuple[float, ...]:
        if self._closed:
            raise RuntimeError("MeanVC2 backend is closed")
        if sample_rate != INPUT_SAMPLE_RATE or len(samples) > INFERENCE_SAMPLES:
            raise ValueError("MeanVC2 requires at most eight 20 ms 48 kHz frames")
        np = __import__("numpy")
        source = np.asarray(samples, dtype=np.float32)
        if (
            source.ndim != 1
            or not np.isfinite(source).all()
            or (source.size and float(np.max(np.abs(source))) > 1.0)
        ):
            raise ValueError("MeanVC2 input must be finite normalized mono PCM")
        padded = np.zeros(INFERENCE_SAMPLES, dtype=np.float32)
        padded[: source.size] = source
        native = self._soxr.resample(
            padded, INPUT_SAMPLE_RATE, NATIVE_SAMPLE_RATE, quality="VHQ"
        ).astype(np.float32, copy=False)
        if native.size != 2_560:
            raise RuntimeError("MeanVC2 input resampling changed batch length")
        output_parts: list[object] = []
        with (
            self._torch.inference_mode(),
            contextlib.redirect_stdout(self._upstream_output),
        ):
            produced = self._runner.process_chunk(native)
            if produced is not None:
                output_parts.append(produced)
            if final:
                output_parts.extend(self._drain())
        if not output_parts:
            return ()
        output = np.concatenate(output_parts).astype(np.float32, copy=False)
        output = self._soxr.resample(
            output, NATIVE_SAMPLE_RATE, INPUT_SAMPLE_RATE, quality="VHQ"
        ).astype(np.float32, copy=False)
        if not np.isfinite(output).all():
            raise RuntimeError("MeanVC2 returned non-finite PCM")
        output = np.clip(output, -1.0, 1.0)
        return tuple(float(value) for value in output)

    def _drain(self) -> list[object]:
        runner = self._runner
        torch = self._torch
        parts: list[object] = []
        while (
            runner.bn_buffer is not None
            and runner.bn_buffer.shape[1] >= runner.chunk_size
        ):
            current = runner.bn_buffer[:, : runner.chunk_size, :]
            if runner.bn_buffer.shape[1] > runner.chunk_size:
                future = runner.bn_buffer[
                    :, runner.chunk_size : runner._min_bn_len, :  # noqa: SLF001
                ]
            else:
                future = runner.bn_buffer[:, -1:, :].repeat(1, runner.block_size, 1)
            condition = torch.cat([current, future], dim=1)
            runner.bn_buffer = runner.bn_buffer[:, runner.chunk_size :, :]
            if runner.bn_buffer.shape[1] == 0:
                runner.bn_buffer = None
            parts.append(runner._decode_mel(runner._vc_step(condition)))  # noqa: SLF001
        if runner.bn_buffer is not None and runner.bn_buffer.shape[1] > 0:
            remaining = runner.bn_buffer.shape[1]
            last = runner.bn_buffer[:, -1:, :]
            current = last.repeat(1, runner.chunk_size, 1)
            current[:, :remaining, :] = runner.bn_buffer
            future = last.repeat(1, runner.block_size, 1)
            runner.bn_buffer = None
            condition = torch.cat([current, future], dim=1)
            parts.append(runner._decode_mel(runner._vc_step(condition)))  # noqa: SLF001
        if runner.last_wav is not None:
            parts.append(runner.last_wav)
            runner.last_wav = None
        return parts

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runner = None
        self._torch.cuda.empty_cache()
        self._upstream_output.close()


def validate_pcm(samples: Sequence[float]) -> None:
    if any(
        not math.isfinite(float(value)) or abs(float(value)) > 1.0 for value in samples
    ):
        raise ValueError("PCM must contain finite normalized samples")
