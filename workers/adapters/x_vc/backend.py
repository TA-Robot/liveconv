from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from .network_isolation import require_non_unix_socket_denial

IMPLEMENTATION_REVISION = "x-vc-streaming-adapter-v1"
WORKER_PACKAGE_NAME = "liveconv-worker-runtime"
WORKER_PACKAGE_VERSION = "0.1.0"
SOURCE_REVISION = "49df8c591eafc48b096e466d96f9839f9c0dd739"
CHECKPOINT_SHA256 = "1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687"
CONFIG_SHA256 = "5f9aae0487ffcf1b69f5833317d068bfe62c6de1a12b0921abebe742b39c3be7"
GLM_CONFIG_SHA256 = "5a5181fcc293ced0a1e7455f6e3503ce4e8be9229922ea34aeb785f62720c0aa"
GLM_PREPROCESSOR_SHA256 = (
    "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"
)
GLM_MODEL_SHA256 = "2800bd503f52b51e45f0c53cfd5c31dcfe8ef7f13d22b396aa3d53e0280dd1e4"
ERES_CONFIG_SHA256 = "bbd0c639f5c73325ad9f080d9f8866b613f739546216dc090eabe65ed0bbdd18"
ERES_MODEL_SHA256 = "d8941f5952e31820173c8854562cb6d7897aaa58cd65c18f30d5a2e52d30847d"
PINNED_GLM_ROOT = Path("/workspace/liveconv/artifacts/x-vc/glm-4-voice-tokenizer")
PINNED_ERES_ROOT = Path("/workspace/liveconv/artifacts/x-vc/speech-eres2net")

INPUT_SAMPLE_RATE = 48_000
NATIVE_SAMPLE_RATE = 16_000
FRAME_MS = 20
WINDOW_MS = 2_400
CURRENT_MS = 120
SMOOTH_MS = 20
FUTURE_MS = 100
HISTORY_MS = WINDOW_MS - CURRENT_MS - SMOOTH_MS - FUTURE_MS
LATENT_HOP_LENGTH = 1_280
FRAME_SAMPLES = INPUT_SAMPLE_RATE * FRAME_MS // 1_000
WINDOW_SAMPLES = INPUT_SAMPLE_RATE * WINDOW_MS // 1_000
CURRENT_SAMPLES = INPUT_SAMPLE_RATE * CURRENT_MS // 1_000
NATIVE_CURRENT_SAMPLES = NATIVE_SAMPLE_RATE * CURRENT_MS // 1_000
NATIVE_SMOOTH_SAMPLES = NATIVE_SAMPLE_RATE * SMOOTH_MS // 1_000
NATIVE_LOOKAHEAD_SAMPLES = NATIVE_SAMPLE_RATE * (SMOOTH_MS + FUTURE_MS) // 1_000
OUTPUT_RESAMPLER_REVISION = "torchaudio-sinc-hann-overlap-v1"
SOURCE_PREPROCESSING_REVISION = "xvc-bounded-official-functions-v1"

ADAPTER_ROOT = Path(__file__).resolve().parent
ADAPTER_SOURCE_FILES = (
    "__init__.py",
    "__main__.py",
    "backend.py",
    "network_isolation.py",
    "real_smoke.py",
    "worker.py",
)
RUNTIME_LOCK_PATH = ADAPTER_ROOT / "requirements-runtime.lock"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DEVICE_RE = re.compile(r"^cuda:[0-9]+$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_adapter_source(path: Path = ADAPTER_ROOT) -> str:
    """Hash every executable Python file shipped by the X-VC adapter."""

    digest = hashlib.sha256()
    for relative in ADAPTER_SOURCE_FILES:
        encoded_name = relative.encode("utf-8")
        encoded_file = (path / relative).read_bytes()
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        digest.update(len(encoded_file).to_bytes(8, "big"))
        digest.update(encoded_file)
    return digest.hexdigest()


def _required_file(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{name} must identify a file")
    return path


def _required_executable(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"{name} must identify an executable file")
    return path


def _required_directory(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{name} must identify a directory")
    return path


def _sha256(name: str, value: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _verify_file(name: str, path: Path, expected_sha256: str) -> None:
    if sha256_file(path) != expected_sha256:
        raise ValueError(f"{name} digest does not match")


def _verify_source(source_root: Path, expected_revision: str) -> None:
    try:
        revision = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            [
                "git",
                "-C",
                str(source_root),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignored=matching",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("X-VC source checkout could not be verified") from error
    if revision != expected_revision or dirty:
        raise ValueError("X-VC source checkout does not match the pinned revision")


@dataclass(frozen=True, slots=True)
class TargetAuthorization:
    authorization_id: str
    owner: str
    authorization_record: str
    permitted_purpose: str
    retention_policy: str
    deletion_path: str
    classification: str
    target_reference_sha256: str


def load_target_authorization(
    path: Path, expected_sha256: str, target_reference_sha256: str
) -> TargetAuthorization:
    _verify_file("X-VC target authorization", path, expected_sha256)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("X-VC target authorization is not valid JSON") from error
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
        raise ValueError("X-VC target authorization has an unexpected schema")
    if document["schema_version"] != 1:
        raise ValueError("X-VC target authorization schema version is unsupported")
    string_fields = required - {"schema_version"}
    if any(
        not isinstance(document[name], str) or not document[name].strip()
        for name in string_fields
    ):
        raise ValueError("X-VC target authorization fields must be nonempty strings")
    record_target = _sha256(
        "target authorization target_reference_sha256",
        document["target_reference_sha256"],
    )
    if record_target != target_reference_sha256:
        raise ValueError("X-VC target authorization identifies another target")
    return TargetAuthorization(
        authorization_id=document["authorization_id"],
        owner=document["owner"],
        authorization_record=document["authorization_record"],
        permitted_purpose=document["permitted_purpose"],
        retention_policy=document["retention_policy"],
        deletion_path=document["deletion_path"],
        classification=document["classification"],
        target_reference_sha256=record_target,
    )


@dataclass(frozen=True, slots=True)
class XvcConfiguration:
    source_root: Path
    source_revision: str
    config_path: Path
    config_sha256: str
    checkpoint_path: Path
    checkpoint_sha256: str
    glm_root: Path
    glm_config_sha256: str
    glm_preprocessor_sha256: str
    glm_model_sha256: str
    eres_root: Path
    eres_config_sha256: str
    eres_model_sha256: str
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
    python_implementation: str
    python_version: str
    worker_package_version: str
    device: str = "cuda:0"

    @classmethod
    def from_environment(cls) -> XvcConfiguration:
        configuration = cls(
            source_root=_required_directory(
                "LIVECONV_XVC_SOURCE_ROOT",
                os.environ.get("LIVECONV_XVC_SOURCE_ROOT", ""),
            ),
            source_revision=os.environ.get("LIVECONV_XVC_SOURCE_REVISION", ""),
            config_path=_required_file(
                "LIVECONV_XVC_CONFIG_PATH",
                os.environ.get("LIVECONV_XVC_CONFIG_PATH", ""),
            ),
            config_sha256=_sha256(
                "LIVECONV_XVC_CONFIG_SHA256",
                os.environ.get("LIVECONV_XVC_CONFIG_SHA256", ""),
            ),
            checkpoint_path=_required_file(
                "LIVECONV_XVC_CHECKPOINT_PATH",
                os.environ.get("LIVECONV_XVC_CHECKPOINT_PATH", ""),
            ),
            checkpoint_sha256=_sha256(
                "LIVECONV_XVC_CHECKPOINT_SHA256",
                os.environ.get("LIVECONV_XVC_CHECKPOINT_SHA256", ""),
            ),
            glm_root=_required_directory(
                "LIVECONV_XVC_GLM_ROOT",
                os.environ.get("LIVECONV_XVC_GLM_ROOT", ""),
            ),
            glm_config_sha256=_sha256(
                "LIVECONV_XVC_GLM_CONFIG_SHA256",
                os.environ.get("LIVECONV_XVC_GLM_CONFIG_SHA256", ""),
            ),
            glm_preprocessor_sha256=_sha256(
                "LIVECONV_XVC_GLM_PREPROCESSOR_SHA256",
                os.environ.get("LIVECONV_XVC_GLM_PREPROCESSOR_SHA256", ""),
            ),
            glm_model_sha256=_sha256(
                "LIVECONV_XVC_GLM_MODEL_SHA256",
                os.environ.get("LIVECONV_XVC_GLM_MODEL_SHA256", ""),
            ),
            eres_root=_required_directory(
                "LIVECONV_XVC_ERES_ROOT",
                os.environ.get("LIVECONV_XVC_ERES_ROOT", ""),
            ),
            eres_config_sha256=_sha256(
                "LIVECONV_XVC_ERES_CONFIG_SHA256",
                os.environ.get("LIVECONV_XVC_ERES_CONFIG_SHA256", ""),
            ),
            eres_model_sha256=_sha256(
                "LIVECONV_XVC_ERES_MODEL_SHA256",
                os.environ.get("LIVECONV_XVC_ERES_MODEL_SHA256", ""),
            ),
            target_reference_path=_required_file(
                "LIVECONV_XVC_TARGET_REFERENCE_PATH",
                os.environ.get("LIVECONV_XVC_TARGET_REFERENCE_PATH", ""),
            ),
            target_reference_sha256=_sha256(
                "LIVECONV_XVC_TARGET_REFERENCE_SHA256",
                os.environ.get("LIVECONV_XVC_TARGET_REFERENCE_SHA256", ""),
            ),
            target_authorization_path=_required_file(
                "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH",
                os.environ.get("LIVECONV_XVC_TARGET_AUTHORIZATION_PATH", ""),
            ),
            target_authorization_sha256=_sha256(
                "LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256",
                os.environ.get("LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256", ""),
            ),
            adapter_source_sha256=_sha256(
                "LIVECONV_XVC_ADAPTER_SOURCE_SHA256",
                os.environ.get("LIVECONV_XVC_ADAPTER_SOURCE_SHA256", ""),
            ),
            runtime_lock_path=_required_file(
                "LIVECONV_XVC_RUNTIME_LOCK_PATH",
                os.environ.get("LIVECONV_XVC_RUNTIME_LOCK_PATH", ""),
            ),
            runtime_lock_sha256=_sha256(
                "LIVECONV_XVC_RUNTIME_LOCK_SHA256",
                os.environ.get("LIVECONV_XVC_RUNTIME_LOCK_SHA256", ""),
            ),
            worker_wheel_path=_required_file(
                "LIVECONV_XVC_WORKER_WHEEL_PATH",
                os.environ.get("LIVECONV_XVC_WORKER_WHEEL_PATH", ""),
            ),
            worker_wheel_sha256=_sha256(
                "LIVECONV_XVC_WORKER_WHEEL_SHA256",
                os.environ.get("LIVECONV_XVC_WORKER_WHEEL_SHA256", ""),
            ),
            interpreter_path=_required_executable(
                "LIVECONV_XVC_INTERPRETER_PATH",
                os.environ.get("LIVECONV_XVC_INTERPRETER_PATH", ""),
            ),
            interpreter_sha256=_sha256(
                "LIVECONV_XVC_INTERPRETER_SHA256",
                os.environ.get("LIVECONV_XVC_INTERPRETER_SHA256", ""),
            ),
            python_implementation=os.environ.get(
                "LIVECONV_XVC_PYTHON_IMPLEMENTATION", ""
            ),
            python_version=os.environ.get("LIVECONV_XVC_PYTHON_VERSION", ""),
            worker_package_version=os.environ.get(
                "LIVECONV_XVC_WORKER_PACKAGE_VERSION", ""
            ),
            device=os.environ.get("LIVECONV_XVC_DEVICE", "cuda:0"),
        )
        configuration.validate()
        return configuration

    @property
    def weight_revision(self) -> str:
        return f"sha256:{self.checkpoint_sha256}"

    @property
    def implementation_revision(self) -> str:
        return f"{IMPLEMENTATION_REVISION}+sha256:{self.adapter_source_sha256}"

    @property
    def configuration_hash(self) -> str:
        identity = {
            "adapter_revision": IMPLEMENTATION_REVISION,
            "adapter_source_sha256": self.adapter_source_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "config_sha256": self.config_sha256,
            "current_ms": CURRENT_MS,
            "device": self.device,
            "ema_load": False,
            "eres_config_sha256": self.eres_config_sha256,
            "eres_model_sha256": self.eres_model_sha256,
            "future_ms": FUTURE_MS,
            "glm_config_sha256": self.glm_config_sha256,
            "glm_model_sha256": self.glm_model_sha256,
            "glm_preprocessor_sha256": self.glm_preprocessor_sha256,
            "input_sample_rate": INPUT_SAMPLE_RATE,
            "latent_hop_length": LATENT_HOP_LENGTH,
            "mask_target_condition": False,
            "output_resampler_revision": OUTPUT_RESAMPLER_REVISION,
            "interpreter_sha256": self.interpreter_sha256,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "runtime_lock_sha256": self.runtime_lock_sha256,
            "smooth_ms": SMOOTH_MS,
            "source_preprocessing_revision": SOURCE_PREPROCESSING_REVISION,
            "source_revision": self.source_revision,
            "target_authorization_sha256": self.target_authorization_sha256,
            "target_reference_sha256": self.target_reference_sha256,
            "window_ms": WINDOW_MS,
            "worker_package_version": self.worker_package_version,
            "worker_wheel_sha256": self.worker_wheel_sha256,
        }
        payload = json.dumps(
            identity,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    def validate(self) -> None:
        if self.source_revision != SOURCE_REVISION:
            raise ValueError("X-VC source revision is not approved")
        if self.config_sha256 != CONFIG_SHA256:
            raise ValueError("X-VC configuration digest is not approved")
        if self.checkpoint_sha256 != CHECKPOINT_SHA256:
            raise ValueError("X-VC checkpoint digest is not approved")
        if (
            self.glm_config_sha256 != GLM_CONFIG_SHA256
            or self.glm_preprocessor_sha256 != GLM_PREPROCESSOR_SHA256
            or self.glm_model_sha256 != GLM_MODEL_SHA256
        ):
            raise ValueError("X-VC GLM artifact digest is not approved")
        if (
            self.eres_config_sha256 != ERES_CONFIG_SHA256
            or self.eres_model_sha256 != ERES_MODEL_SHA256
        ):
            raise ValueError("X-VC ERes2Net artifact digest is not approved")
        if self.glm_root != PINNED_GLM_ROOT or self.eres_root != PINNED_ERES_ROOT:
            raise ValueError("X-VC local dependency roots do not match pinned config")
        if not _DEVICE_RE.fullmatch(self.device):
            raise ValueError("X-VC worker requires a numbered CUDA device")

        load_target_authorization(
            self.target_authorization_path,
            self.target_authorization_sha256,
            self.target_reference_sha256,
        )
        if sha256_adapter_source() != self.adapter_source_sha256:
            raise ValueError("X-VC adapter source digest does not match")
        _verify_file(
            "X-VC runtime lock", self.runtime_lock_path, self.runtime_lock_sha256
        )
        _verify_file(
            "installed X-VC runtime lock", RUNTIME_LOCK_PATH, self.runtime_lock_sha256
        )
        _verify_file(
            "liveconv worker wheel", self.worker_wheel_path, self.worker_wheel_sha256
        )
        running_interpreter = Path(sys.executable).resolve(strict=True)
        if not self.interpreter_path.samefile(running_interpreter):
            raise ValueError("X-VC interpreter path is not the running interpreter")
        _verify_file("X-VC interpreter", running_interpreter, self.interpreter_sha256)
        if (
            self.python_implementation != platform.python_implementation()
            or self.python_version != platform.python_version()
            or sys.version_info[:2] != (3, 12)
        ):
            raise ValueError("X-VC worker requires the bound CPython 3.12 runtime")
        if (
            self.worker_package_version != WORKER_PACKAGE_VERSION
            or importlib.metadata.version(WORKER_PACKAGE_NAME)
            != self.worker_package_version
        ):
            raise ValueError("X-VC installed worker wheel version does not match")

        _verify_source(self.source_root, self.source_revision)
        for name, path, expected in (
            ("X-VC configuration", self.config_path, self.config_sha256),
            ("X-VC checkpoint", self.checkpoint_path, self.checkpoint_sha256),
            (
                "X-VC GLM configuration",
                self.glm_root / "config.json",
                self.glm_config_sha256,
            ),
            (
                "X-VC GLM preprocessor",
                self.glm_root / "preprocessor_config.json",
                self.glm_preprocessor_sha256,
            ),
            (
                "X-VC GLM weights",
                self.glm_root / "model.safetensors",
                self.glm_model_sha256,
            ),
            (
                "X-VC ERes2Net configuration",
                self.eres_root / "configuration.json",
                self.eres_config_sha256,
            ),
            (
                "X-VC ERes2Net weights",
                self.eres_root / "pretrained_eres2net.ckpt",
                self.eres_model_sha256,
            ),
            (
                "X-VC target reference",
                self.target_reference_path,
                self.target_reference_sha256,
            ),
            (
                "X-VC target authorization",
                self.target_authorization_path,
                self.target_authorization_sha256,
            ),
        ):
            _verify_file(name, path.resolve(strict=True), expected)

    def worker_environment(self) -> dict[str, str]:
        return {
            "LIVECONV_XVC_SOURCE_ROOT": str(self.source_root),
            "LIVECONV_XVC_SOURCE_REVISION": self.source_revision,
            "LIVECONV_XVC_CONFIG_PATH": str(self.config_path),
            "LIVECONV_XVC_CONFIG_SHA256": self.config_sha256,
            "LIVECONV_XVC_CHECKPOINT_PATH": str(self.checkpoint_path),
            "LIVECONV_XVC_CHECKPOINT_SHA256": self.checkpoint_sha256,
            "LIVECONV_XVC_GLM_ROOT": str(self.glm_root),
            "LIVECONV_XVC_GLM_CONFIG_SHA256": self.glm_config_sha256,
            "LIVECONV_XVC_GLM_PREPROCESSOR_SHA256": self.glm_preprocessor_sha256,
            "LIVECONV_XVC_GLM_MODEL_SHA256": self.glm_model_sha256,
            "LIVECONV_XVC_ERES_ROOT": str(self.eres_root),
            "LIVECONV_XVC_ERES_CONFIG_SHA256": self.eres_config_sha256,
            "LIVECONV_XVC_ERES_MODEL_SHA256": self.eres_model_sha256,
            "LIVECONV_XVC_TARGET_REFERENCE_PATH": str(self.target_reference_path),
            "LIVECONV_XVC_TARGET_REFERENCE_SHA256": self.target_reference_sha256,
            "LIVECONV_XVC_TARGET_AUTHORIZATION_PATH": str(
                self.target_authorization_path
            ),
            "LIVECONV_XVC_TARGET_AUTHORIZATION_SHA256": (
                self.target_authorization_sha256
            ),
            "LIVECONV_XVC_ADAPTER_SOURCE_SHA256": self.adapter_source_sha256,
            "LIVECONV_XVC_RUNTIME_LOCK_PATH": str(self.runtime_lock_path),
            "LIVECONV_XVC_RUNTIME_LOCK_SHA256": self.runtime_lock_sha256,
            "LIVECONV_XVC_WORKER_WHEEL_PATH": str(self.worker_wheel_path),
            "LIVECONV_XVC_WORKER_WHEEL_SHA256": self.worker_wheel_sha256,
            "LIVECONV_XVC_INTERPRETER_PATH": str(self.interpreter_path),
            "LIVECONV_XVC_INTERPRETER_SHA256": self.interpreter_sha256,
            "LIVECONV_XVC_PYTHON_IMPLEMENTATION": self.python_implementation,
            "LIVECONV_XVC_PYTHON_VERSION": self.python_version,
            "LIVECONV_XVC_WORKER_PACKAGE_VERSION": self.worker_package_version,
            "LIVECONV_XVC_DEVICE": self.device,
        }


@dataclass(frozen=True, slots=True)
class WindowResult:
    samples: tuple[float, ...]
    tail: object | None


@dataclass(frozen=True, slots=True)
class XvcWindowState:
    smoothing_tail: tuple[float, ...]
    resample_left: tuple[float, ...]


def resample_current_with_context(
    torch: object,
    torchaudio: object,
    current: object,
    lookahead: object,
    resample_left: object,
) -> object:
    """Resample one current chunk with explicit per-generation edge context."""
    if current.shape[-1] != NATIVE_CURRENT_SAMPLES:
        raise ValueError("X-VC resampler current context has the wrong length")
    if lookahead.shape[-1] != NATIVE_LOOKAHEAD_SAMPLES:
        raise ValueError("X-VC resampler right context has the wrong length")
    if resample_left.shape[-1] != NATIVE_SMOOTH_SAMPLES:
        raise ValueError("X-VC resampler left context has the wrong length")
    resample_input = torch.cat((resample_left, current, lookahead), dim=-1)
    resampled = torchaudio.functional.resample(
        resample_input,
        NATIVE_SAMPLE_RATE,
        INPUT_SAMPLE_RATE,
        lowpass_filter_width=6,
        rolloff=0.99,
        resampling_method="sinc_interp_hann",
    )
    crop_start = NATIVE_SMOOTH_SAMPLES * INPUT_SAMPLE_RATE // NATIVE_SAMPLE_RATE
    converted = resampled[..., crop_start : crop_start + CURRENT_SAMPLES]
    if converted.shape[-1] != CURRENT_SAMPLES:
        raise RuntimeError("X-VC output resampling changed current length")
    return converted


class ConversionBackend(Protocol):
    implementation_revision: str
    weight_revision: str
    configuration_hash: str

    def convert_window(
        self,
        samples: Sequence[float],
        sample_rate: int,
        prior_tail: object | None,
    ) -> WindowResult: ...

    def close(self) -> None: ...


class OfficialXvcBackend:
    """Pinned official X-VC window forward with precomputed target conditions."""

    def __init__(
        self, configuration: XvcConfiguration, *, validate_configuration: bool = True
    ) -> None:
        if validate_configuration:
            configuration.validate()
        require_non_unix_socket_denial()
        self.configuration = configuration
        self.implementation_revision = configuration.implementation_revision
        self.weight_revision = configuration.weight_revision
        self.configuration_hash = configuration.configuration_hash
        self._closed = False
        source_root = str(configuration.source_root)
        if source_root not in sys.path:
            sys.path.insert(0, source_root)

        upstream_output = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        try:
            with contextlib.redirect_stdout(upstream_output):
                torch = importlib.import_module("torch")
                if not torch.cuda.is_available():
                    raise RuntimeError("X-VC requires CUDA")
                device = torch.device(configuration.device)
                torch.cuda.set_device(device)
                infer_utils = importlib.import_module("bins.infer_utils")
                sac_utils = importlib.import_module("models.codec.sac.utils")
                cfg, model, loaded_device = infer_utils.load_xvc(
                    str(configuration.config_path),
                    str(configuration.checkpoint_path),
                    device.index,
                    False,
                )
                if str(loaded_device) != str(device):
                    raise RuntimeError("X-VC loaded on an unexpected device")
                if int(cfg["sample_rate"]) != NATIVE_SAMPLE_RATE:
                    raise RuntimeError("X-VC configuration changed native sample rate")
                if not bool(cfg.get("volume_normalize", False)):
                    raise RuntimeError(
                        "X-VC configuration disabled volume normalization"
                    )
                if float(cfg.get("highpass_cutoff_freq", 0.0)) != 40.0:
                    raise RuntimeError("X-VC configuration changed high-pass cutoff")
                target = sac_utils.process_audio(
                    str(configuration.target_reference_path),
                    cfg,
                    LATENT_HOP_LENGTH,
                )
                target_wav = (
                    torch.from_numpy(target)
                    .unsqueeze(0)
                    .unsqueeze(1)
                    .float()
                    .to(device)
                )
                speaker_condition, frame_condition = infer_utils.precompute_conditions(
                    model,
                    target_wav,
                    target_wav,
                )
        except Exception:
            upstream_output.close()
            raise

        self._upstream_output = upstream_output
        self._torch = torch
        self._device = device
        self._model = model
        self._run_stream_chunk_forward = infer_utils.run_stream_chunk_forward
        audio_utils = importlib.import_module("utils.audio")
        self._audio_highpass_filter = audio_utils.audio_highpass_filter
        self._audio_volume_normalize = audio_utils.audio_volume_normalize
        self._torchaudio = importlib.import_module("torchaudio")
        self._speaker_condition = speaker_condition
        self._frame_condition = frame_condition

    def convert_window(
        self,
        samples: Sequence[float],
        sample_rate: int,
        prior_tail: object | None,
    ) -> WindowResult:
        if self._closed:
            raise RuntimeError("X-VC backend is closed")
        if sample_rate != INPUT_SAMPLE_RATE or len(samples) != WINDOW_SAMPLES:
            raise ValueError("X-VC requires one 2.4 s 48 kHz window")

        np = importlib.import_module("numpy")
        soxr = importlib.import_module("soxr")
        source = np.asarray(samples, dtype=np.float32)
        if (
            source.ndim != 1
            or not np.isfinite(source).all()
            or float(np.max(np.abs(source))) > 1.0
        ):
            raise ValueError("X-VC input must be finite normalized mono PCM")
        source = soxr.resample(
            source,
            INPUT_SAMPLE_RATE,
            NATIVE_SAMPLE_RATE,
            quality="VHQ",
        ).astype(np.float32, copy=False)
        expected_native = NATIVE_SAMPLE_RATE * WINDOW_MS // 1_000
        if source.size != expected_native:
            raise RuntimeError("X-VC source resampling changed window length")
        source = self._audio_volume_normalize(source)
        source = self._audio_highpass_filter(source, NATIVE_SAMPLE_RATE, 40.0)
        source_wav = (
            self._torch.from_numpy(source.copy())
            .unsqueeze(0)
            .unsqueeze(1)
            .float()
            .to(self._device)
        )

        with (
            self._torch.inference_mode(),
            contextlib.redirect_stdout(self._upstream_output),
        ):
            output = self._run_stream_chunk_forward(
                self._model,
                source_wav,
                self._speaker_condition,
                self._frame_condition,
            )
            history_samples = NATIVE_SAMPLE_RATE * HISTORY_MS // 1_000
            current = output[
                ...,
                history_samples : history_samples + NATIVE_CURRENT_SAMPLES,
            ]
            lookahead = output[
                ...,
                history_samples + NATIVE_CURRENT_SAMPLES : history_samples
                + NATIVE_CURRENT_SAMPLES
                + NATIVE_LOOKAHEAD_SAMPLES,
            ]
            if current.shape[-1] != NATIVE_CURRENT_SAMPLES:
                raise RuntimeError("X-VC returned a short current window")
            if lookahead.shape[-1] != NATIVE_LOOKAHEAD_SAMPLES:
                raise RuntimeError("X-VC returned a short lookahead window")
            if prior_tail is not None:
                if not isinstance(prior_tail, XvcWindowState):
                    raise ValueError("X-VC window state has the wrong type")
                prior = self._torch.as_tensor(
                    prior_tail.smoothing_tail,
                    dtype=current.dtype,
                    device=self._device,
                ).reshape(1, 1, -1)
                if prior.shape[-1] != NATIVE_SMOOTH_SAMPLES:
                    raise ValueError("X-VC smoothing state has the wrong length")
                fade_in = 0.5 * (
                    1
                    - self._torch.cos(
                        self._torch.pi
                        * self._torch.linspace(
                            0,
                            1,
                            NATIVE_SMOOTH_SAMPLES,
                            device=self._device,
                        )
                    )
                )
                current[..., :NATIVE_SMOOTH_SAMPLES] = (
                    prior * (1 - fade_in)
                    + current[..., :NATIVE_SMOOTH_SAMPLES] * fade_in
                )

            if prior_tail is None:
                resample_left = self._torch.zeros(
                    (1, 1, NATIVE_SMOOTH_SAMPLES),
                    dtype=current.dtype,
                    device=self._device,
                )
            else:
                resample_left = self._torch.as_tensor(
                    prior_tail.resample_left,
                    dtype=current.dtype,
                    device=self._device,
                ).reshape(1, 1, -1)
                if resample_left.shape[-1] != NATIVE_SMOOTH_SAMPLES:
                    raise ValueError("X-VC resampler state has the wrong length")
            converted_tensor = resample_current_with_context(
                self._torch,
                self._torchaudio,
                current,
                lookahead,
                resample_left,
            )
            converted = (
                converted_tensor.squeeze().to("cpu", dtype=self._torch.float32).numpy()
            )
            next_tail = XvcWindowState(
                smoothing_tail=tuple(
                    float(value)
                    for value in lookahead[..., :NATIVE_SMOOTH_SAMPLES]
                    .squeeze()
                    .to("cpu", dtype=self._torch.float32)
                    .tolist()
                ),
                resample_left=tuple(
                    float(value)
                    for value in current[..., -NATIVE_SMOOTH_SAMPLES:]
                    .squeeze()
                    .to("cpu", dtype=self._torch.float32)
                    .tolist()
                ),
            )

        if not np.isfinite(converted).all():
            raise RuntimeError("X-VC returned non-finite PCM")
        converted = np.clip(converted, -1.0, 1.0)
        return WindowResult(
            tuple(float(value) for value in converted),
            next_tail,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        del self._model
        del self._speaker_condition
        del self._frame_condition
        self._torch.cuda.empty_cache()
        self._upstream_output.close()


class DeterministicTestBackend:
    implementation_revision = "x-vc-deterministic-test-backend-v1"
    weight_revision = "sha256:" + "0" * 64
    configuration_hash = "sha256:" + "f" * 64

    def __init__(self, gain: float = -0.5) -> None:
        self.gain = gain
        self.closed = False

    def convert_window(
        self,
        samples: Sequence[float],
        sample_rate: int,
        prior_tail: object | None,
    ) -> WindowResult:
        if self.closed:
            raise RuntimeError("test backend is closed")
        if sample_rate != INPUT_SAMPLE_RATE or len(samples) != WINDOW_SAMPLES:
            raise ValueError("test backend received a malformed window")
        history = INPUT_SAMPLE_RATE * HISTORY_MS // 1_000
        current = [
            float(value) * self.gain
            for value in samples[history : history + CURRENT_SAMPLES]
        ]
        smooth = INPUT_SAMPLE_RATE * SMOOTH_MS // 1_000
        next_tail = tuple(
            float(value) * self.gain
            for value in samples[
                history + CURRENT_SAMPLES : history + CURRENT_SAMPLES + smooth
            ]
        )
        if prior_tail is not None:
            if not isinstance(prior_tail, XvcWindowState):
                raise ValueError("test window state has the wrong type")
            old_tail = prior_tail.smoothing_tail
            if len(old_tail) != smooth:
                raise ValueError("test smoothing state has the wrong length")
            for index in range(smooth):
                fade_in = 0.5 * (1 - math.cos(math.pi * index / (smooth - 1)))
                current[index] = (
                    old_tail[index] * (1 - fade_in) + current[index] * fade_in
                )
        return WindowResult(
            tuple(current),
            XvcWindowState(next_tail, tuple(current[-smooth:])),
        )

    def close(self) -> None:
        self.closed = True


def changed_configuration(
    configuration: XvcConfiguration, **changes: object
) -> XvcConfiguration:
    """Return a changed immutable configuration for identity-focused tests."""
    return replace(configuration, **changes)
