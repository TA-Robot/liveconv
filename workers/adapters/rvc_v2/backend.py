from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import os
import re
import subprocess
import sys
import threading
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .network_isolation import require_non_unix_socket_denial

ADAPTER_REVISION = "liveconv-rvc-v2-worker-v1.4"
INFERENCE_BATCH_FRAMES = 25
RESIDENT_CAPACITY_FRAMES = 50
TEST_CONFIGURATION_HASH = "sha256:" + "2" * 64
_PACKAGE_NAME = "liveconv-worker-runtime"
_PACKAGE_VERSION = "0.1.0"
_WHEEL_MEMBERS = (
    "workers/adapters/rvc_v2/backend.py",
    "workers/adapters/rvc_v2/network_isolation.py",
    "workers/adapters/rvc_v2/worker.py",
    "workers/adapters/rvc_v2/requirements-runtime.lock",
)
_LOCKED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)")


class ConversionBackend(Protocol):
    implementation_revision: str
    weight_revision: str
    configuration_hash: str

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...


class CooperativeConversionCanceled(Exception):
    """Raised only when a backend explicitly cooperates with generation cancel."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_file(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{name} must identify a file")
    return path


def _resolved_directory(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{name} must identify a directory")
    return path


def _canonical_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _locked_packages(content: bytes) -> dict[str, str]:
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise ValueError("RVC runtime lock is not UTF-8") from None
    packages: dict[str, str] = {}
    for line in lines:
        match = _LOCKED_REQUIREMENT.match(line)
        if match is not None:
            packages[_canonical_package_name(match.group(1))] = match.group(2)
    if not packages:
        raise ValueError("RVC runtime lock contains no exact package pins")
    return packages


def _record_rows(content: bytes) -> dict[str, tuple[str, str]]:
    try:
        rows = csv.reader(io.StringIO(content.decode("utf-8")))
        parsed = {row[0]: (row[1], row[2]) for row in rows if len(row) == 3}
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("worker package RECORD is invalid") from None
    if not parsed:
        raise ValueError("worker package RECORD is empty")
    return parsed


@dataclass(frozen=True, slots=True)
class AdapterRuntimeBinding:
    worker_wheel_path: Path
    worker_wheel_sha256: str
    worker_wheel_record_sha256: str
    worker_module_sha256: str
    backend_module_sha256: str
    network_isolation_module_sha256: str
    requirements_lock_sha256: str

    @classmethod
    def inspect(
        cls, wheel_path: Path, expected_wheel_sha256: str
    ) -> AdapterRuntimeBinding:
        wheel_path = wheel_path.resolve(strict=True)
        if not wheel_path.is_file():
            raise ValueError("RVC worker wheel must identify a file")
        actual_wheel_sha256 = sha256_file(wheel_path)
        if actual_wheel_sha256 != expected_wheel_sha256:
            raise ValueError("RVC worker wheel SHA-256 does not match")

        try:
            distribution = importlib.metadata.distribution(_PACKAGE_NAME)
        except importlib.metadata.PackageNotFoundError:
            raise ValueError("liveconv worker package is not installed") from None
        if distribution.version != _PACKAGE_VERSION:
            raise ValueError("liveconv worker package version does not match")

        try:
            with zipfile.ZipFile(wheel_path) as archive:
                names = set(archive.namelist())
                record_names = [
                    name for name in names if name.endswith(".dist-info/RECORD")
                ]
                if len(record_names) != 1 or any(
                    member not in names for member in _WHEEL_MEMBERS
                ):
                    raise ValueError("RVC worker wheel is incomplete")
                if any(
                    Path(name).is_absolute() or ".." in Path(name).parts
                    for name in names
                ):
                    raise ValueError("RVC worker wheel contains an unsafe path")
                record_name = record_names[0]
                wheel_record = archive.read(record_name)
                wheel_files = {
                    name: archive.read(name)
                    for name in names
                    if not name.endswith("/") and name != record_name
                }
        except (OSError, zipfile.BadZipFile, KeyError):
            raise ValueError("RVC worker wheel could not be inspected") from None

        files = distribution.files or ()
        installed_record = next(
            (item for item in files if str(item).endswith(".dist-info/RECORD")),
            None,
        )
        if installed_record is None:
            raise ValueError("installed worker package has no RECORD")
        installed_record_path = Path(distribution.locate_file(installed_record))
        installed_rows = _record_rows(installed_record_path.read_bytes())
        wheel_rows = _record_rows(wheel_record)
        for member, row in wheel_rows.items():
            if member == record_name:
                continue
            if installed_rows.get(member) != row:
                raise ValueError("installed worker RECORD differs from retained wheel")

        for member, wheel_content in wheel_files.items():
            installed_path = Path(distribution.locate_file(member)).resolve(strict=True)
            if installed_path.read_bytes() != wheel_content:
                raise ValueError(f"installed worker file differs from wheel: {member}")

        lock_content = wheel_files["workers/adapters/rvc_v2/requirements-runtime.lock"]
        expected_packages = _locked_packages(lock_content)
        expected_packages[_PACKAGE_NAME] = _PACKAGE_VERSION
        installed_packages = {
            _canonical_package_name(item.metadata["Name"]): item.version
            for item in importlib.metadata.distributions()
            if item.metadata.get("Name")
        }
        if installed_packages != expected_packages:
            raise ValueError("installed RVC runtime differs from its packaged lock")

        return cls(
            worker_wheel_path=wheel_path,
            worker_wheel_sha256=actual_wheel_sha256,
            worker_wheel_record_sha256=hashlib.sha256(wheel_record).hexdigest(),
            worker_module_sha256=hashlib.sha256(
                wheel_files["workers/adapters/rvc_v2/worker.py"]
            ).hexdigest(),
            backend_module_sha256=hashlib.sha256(
                wheel_files["workers/adapters/rvc_v2/backend.py"]
            ).hexdigest(),
            network_isolation_module_sha256=hashlib.sha256(
                wheel_files["workers/adapters/rvc_v2/network_isolation.py"]
            ).hexdigest(),
            requirements_lock_sha256=hashlib.sha256(lock_content).hexdigest(),
        )

    def validate(self) -> None:
        if self != type(self).inspect(self.worker_wheel_path, self.worker_wheel_sha256):
            raise ValueError("RVC adapter runtime binding changed")


def _validate_source_checkout(source_root: Path, expected_revision: str) -> None:
    try:
        head = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        clean = subprocess.run(
            [
                "git",
                "-C",
                str(source_root),
                "diff",
                "--quiet",
                "--no-ext-diff",
                expected_revision,
                "--",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("RVC source checkout could not be verified") from error
    if head != expected_revision:
        raise ValueError("RVC source checkout is at the wrong revision")
    if clean != 0:
        raise ValueError("RVC tracked source differs from the pinned revision")


@dataclass(frozen=True, slots=True)
class RvcConfiguration:
    source_root: Path
    checkpoint_path: Path
    source_revision: str
    checkpoint_sha256: str
    adapter_runtime: AdapterRuntimeBinding
    index_path: Path | None = None
    index_sha256: str | None = None
    speaker_id: int = 0
    pitch_shift: int = 0
    f0_method: str = "rmvpe"
    index_rate: float = 0.0
    rms_mix_rate: float = 1.0
    sample_rate: int = 48_000
    block_ms: int = 500
    crossfade_ms: int = 50
    context_ms: int = 2_500
    # `None` preserves the retained v1.4 identity shape.  New reviewed
    # quality profiles set an explicit value, including 0.0, and therefore
    # receive a distinct configuration identity.
    input_gain_db: float | None = None
    threshold_dbfs: float = -60.0
    # RVC samples its latent representation during inference.  An explicit
    # seed makes separate conversation generations reproducible; `None` keeps
    # the retained stochastic profile identity unchanged.
    inference_seed: int | None = None

    @classmethod
    def from_environment(cls) -> RvcConfiguration:
        if "LIVECONV_RVC_V2_PROTECT" in os.environ:
            raise ValueError("realtime RVC does not support a protect setting")
        source_root = _resolved_directory(
            "LIVECONV_RVC_SOURCE_ROOT", os.environ.get("LIVECONV_RVC_SOURCE_ROOT", "")
        )
        checkpoint_path = _resolved_file(
            "LIVECONV_RVC_V2_CHECKPOINT_PATH",
            os.environ.get("LIVECONV_RVC_V2_CHECKPOINT_PATH", ""),
        )
        checkpoint_sha256 = os.environ.get(
            "LIVECONV_RVC_V2_CHECKPOINT_SHA256", ""
        ).lower()
        worker_wheel_path = _resolved_file(
            "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
            os.environ.get("LIVECONV_RVC_V2_WORKER_WHEEL_PATH", ""),
        )
        worker_wheel_sha256 = os.environ.get(
            "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256", ""
        ).lower()
        adapter_runtime = AdapterRuntimeBinding.inspect(
            worker_wheel_path, worker_wheel_sha256
        )
        source_revision = os.environ.get("LIVECONV_RVC_SOURCE_REVISION", "")
        index_value = os.environ.get("LIVECONV_RVC_V2_INDEX_PATH", "")
        index_path = (
            _resolved_file("LIVECONV_RVC_V2_INDEX_PATH", index_value)
            if index_value
            else None
        )
        index_sha256 = os.environ.get("LIVECONV_RVC_V2_INDEX_SHA256") or None
        input_gain = os.environ.get("LIVECONV_RVC_V2_INPUT_GAIN_DB")
        inference_seed = os.environ.get("LIVECONV_RVC_V2_INFERENCE_SEED")
        configuration = cls(
            source_root=source_root,
            checkpoint_path=checkpoint_path,
            source_revision=source_revision,
            checkpoint_sha256=checkpoint_sha256,
            adapter_runtime=adapter_runtime,
            index_path=index_path,
            index_sha256=index_sha256.lower() if index_sha256 else None,
            speaker_id=int(os.environ.get("LIVECONV_RVC_V2_SPEAKER_ID", "0")),
            pitch_shift=int(os.environ.get("LIVECONV_RVC_V2_PITCH_SHIFT", "0")),
            f0_method=os.environ.get("LIVECONV_RVC_V2_F0_METHOD", "rmvpe"),
            index_rate=float(os.environ.get("LIVECONV_RVC_V2_INDEX_RATE", "0")),
            rms_mix_rate=float(os.environ.get("LIVECONV_RVC_V2_RMS_MIX_RATE", "1")),
            sample_rate=int(os.environ.get("LIVECONV_RVC_V2_SAMPLE_RATE", "48000")),
            block_ms=int(os.environ.get("LIVECONV_RVC_V2_BLOCK_MS", "500")),
            crossfade_ms=int(os.environ.get("LIVECONV_RVC_V2_CROSSFADE_MS", "50")),
            context_ms=int(os.environ.get("LIVECONV_RVC_V2_CONTEXT_MS", "2500")),
            input_gain_db=float(input_gain) if input_gain is not None else None,
            threshold_dbfs=float(
                os.environ.get("LIVECONV_RVC_V2_THRESHOLD_DBFS", "-60")
            ),
            inference_seed=(
                int(inference_seed) if inference_seed is not None else None
            ),
        )
        configuration.validate()
        return configuration

    def validate(self, *, verify_adapter_runtime: bool = True) -> None:
        if verify_adapter_runtime:
            self.adapter_runtime.validate()
        if len(self.source_revision) != 40 or any(
            character not in "0123456789abcdef" for character in self.source_revision
        ):
            raise ValueError("LIVECONV_RVC_SOURCE_REVISION must be a Git commit")
        _validate_source_checkout(self.source_root, self.source_revision)
        if len(self.checkpoint_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.checkpoint_sha256
        ):
            raise ValueError("checkpoint SHA-256 must be lowercase hexadecimal")
        if sha256_file(self.checkpoint_path) != self.checkpoint_sha256:
            raise ValueError("checkpoint SHA-256 does not match")
        if self.index_path is None and self.index_rate != 0:
            raise ValueError("index_rate must be zero when no index is configured")
        if self.index_path is not None:
            if not self.index_sha256:
                raise ValueError(
                    "index SHA-256 is required when an index is configured"
                )
            if sha256_file(self.index_path) != self.index_sha256:
                raise ValueError("index SHA-256 does not match")
        if self.speaker_id != 0:
            raise ValueError("realtime worker-v1 currently requires speaker_id zero")
        if self.f0_method not in {"pm", "rmvpe"}:
            raise ValueError("f0_method must be pm or rmvpe")
        if not 0 <= self.index_rate <= 1:
            raise ValueError("index_rate must be between zero and one")
        if not 0 <= self.rms_mix_rate <= 1:
            raise ValueError("rms_mix_rate must be between zero and one")
        if self.input_gain_db is not None and (
            not math.isfinite(self.input_gain_db)
            or not -24.0 <= self.input_gain_db <= 24.0
        ):
            raise ValueError("input_gain_db must be finite and between -24 and 24")
        if (
            not math.isfinite(self.threshold_dbfs)
            or not -120.0 <= self.threshold_dbfs <= 0.0
        ):
            raise ValueError("threshold_dbfs must be finite and between -120 and 0")
        if self.inference_seed is not None and (
            isinstance(self.inference_seed, bool)
            or not 0 <= self.inference_seed < 2**63
        ):
            raise ValueError("inference_seed must be an integer from 0 to 2^63-1")
        if self.sample_rate < 16_000 or self.sample_rate > 192_000:
            raise ValueError("sample_rate is outside the supported range")
        if self.block_ms != 500:
            raise ValueError("worker-v1 RVC block_ms must be 500")
        if not 0 <= self.crossfade_ms <= 100:
            raise ValueError("crossfade_ms is outside the supported range")
        if not 500 <= self.context_ms <= 10_000:
            raise ValueError("context_ms is outside the supported range")
        for relative in (
            "configs/config.py",
            "infer/vc/modules.py",
            "infer/hubert.py",
            "assets/hubert_base/config.json",
            "assets/hubert_base/preprocessor_config.json",
            "assets/hubert_base/pytorch_model.bin",
            "assets/rmvpe/rmvpe.pt",
        ):
            if not (self.source_root / relative).is_file():
                raise ValueError(f"RVC source installation is incomplete: {relative}")

    def identity_material(self) -> dict[str, object]:
        hubert_root = self.source_root / "assets/hubert_base"
        material: dict[str, object] = {
            "worker_module": "workers.adapters.rvc_v2.worker",
            "adapter_revision": ADAPTER_REVISION,
            "source_revision": self.source_revision,
            "artifacts": {
                "checkpoint_sha256": self.checkpoint_sha256,
                "index_sha256": self.index_sha256,
                "hubert_config_sha256": sha256_file(hubert_root / "config.json"),
                "hubert_preprocessor_sha256": sha256_file(
                    hubert_root / "preprocessor_config.json"
                ),
                "hubert_weights_sha256": sha256_file(hubert_root / "pytorch_model.bin"),
                "rmvpe_sha256": sha256_file(self.source_root / "assets/rmvpe/rmvpe.pt"),
                "worker_wheel_sha256": self.adapter_runtime.worker_wheel_sha256,
                "worker_wheel_record_sha256": (
                    self.adapter_runtime.worker_wheel_record_sha256
                ),
                "worker_module_sha256": self.adapter_runtime.worker_module_sha256,
                "backend_module_sha256": self.adapter_runtime.backend_module_sha256,
                "network_isolation_module_sha256": (
                    self.adapter_runtime.network_isolation_module_sha256
                ),
                "requirements_lock_sha256": (
                    self.adapter_runtime.requirements_lock_sha256
                ),
            },
            "settings": {
                "speaker_id": self.speaker_id,
                "pitch_shift": self.pitch_shift,
                "f0_method": self.f0_method,
                "index_rate": self.index_rate,
                "rms_mix_rate": self.rms_mix_rate,
                "sample_rate": self.sample_rate,
                "block_ms": self.block_ms,
                "crossfade_ms": self.crossfade_ms,
                "context_ms": self.context_ms,
                "frame_ms": 20,
                "inference_batch_frames": INFERENCE_BATCH_FRAMES,
                "queue_capacity_frames": INFERENCE_BATCH_FRAMES,
                "resident_capacity_frames": RESIDENT_CAPACITY_FRAMES,
                "formant_shift": 0.0,
                # The upstream realtime engine treats -60 dBFS as its disabled
                # gate sentinel.  Keep that retained value byte-for-byte for
                # legacy profiles while binding every quality-profile override.
                "threshold_dbfs": self.threshold_dbfs,
            },
        }
        if self.input_gain_db is not None:
            material["settings"]["input_gain_db"] = self.input_gain_db
        if self.inference_seed is not None:
            material["settings"]["inference_seed"] = self.inference_seed
        return material

    @property
    def configuration_hash(self) -> str:
        serialized = json.dumps(
            self.identity_material(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return "sha256:" + hashlib.sha256(serialized).hexdigest()

    def worker_environment(self) -> dict[str, str]:
        environment = {
            "LIVECONV_RVC_SOURCE_ROOT": str(self.source_root),
            "LIVECONV_RVC_SOURCE_REVISION": self.source_revision,
            "LIVECONV_RVC_V2_CHECKPOINT_PATH": str(self.checkpoint_path),
            "LIVECONV_RVC_V2_CHECKPOINT_SHA256": self.checkpoint_sha256,
            "LIVECONV_RVC_V2_WORKER_WHEEL_PATH": str(
                self.adapter_runtime.worker_wheel_path
            ),
            "LIVECONV_RVC_V2_WORKER_WHEEL_SHA256": (
                self.adapter_runtime.worker_wheel_sha256
            ),
            "LIVECONV_RVC_V2_SPEAKER_ID": str(self.speaker_id),
            "LIVECONV_RVC_V2_PITCH_SHIFT": str(self.pitch_shift),
            "LIVECONV_RVC_V2_F0_METHOD": self.f0_method,
            "LIVECONV_RVC_V2_INDEX_RATE": str(self.index_rate),
            "LIVECONV_RVC_V2_RMS_MIX_RATE": str(self.rms_mix_rate),
            "LIVECONV_RVC_V2_SAMPLE_RATE": str(self.sample_rate),
            "LIVECONV_RVC_V2_BLOCK_MS": str(self.block_ms),
            "LIVECONV_RVC_V2_CROSSFADE_MS": str(self.crossfade_ms),
            "LIVECONV_RVC_V2_CONTEXT_MS": str(self.context_ms),
            "LIVECONV_RVC_V2_THRESHOLD_DBFS": str(self.threshold_dbfs),
        }
        if self.input_gain_db is not None:
            environment["LIVECONV_RVC_V2_INPUT_GAIN_DB"] = str(self.input_gain_db)
        if self.inference_seed is not None:
            environment["LIVECONV_RVC_V2_INFERENCE_SEED"] = str(
                self.inference_seed
            )
        if self.index_path is not None:
            assert self.index_sha256 is not None
            environment.update(
                {
                    "LIVECONV_RVC_V2_INDEX_PATH": str(self.index_path),
                    "LIVECONV_RVC_V2_INDEX_SHA256": self.index_sha256,
                }
            )
        return environment


class UpstreamRvcBackend:
    """Thin process-local wrapper around a pinned upstream RVC checkout."""

    def __init__(self, configuration: RvcConfiguration) -> None:
        require_non_unix_socket_denial()
        configuration.validate()
        self.configuration = configuration
        self.implementation_revision = (
            f"{ADAPTER_REVISION}+rvc.{configuration.source_revision}"
        )
        self.weight_revision = f"sha256:{configuration.checkpoint_sha256}"
        self.configuration_hash = configuration.configuration_hash
        self._lock = threading.Lock()
        self._closed = False
        self._reset_requested = threading.Event()
        self._upstream_output = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

        root = str(configuration.source_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        # Upstream still resolves locale and several model assets from process cwd.
        # This adapter owns a dedicated subprocess, so pinning its cwd is isolated.
        os.chdir(configuration.source_root)
        os.environ["weight_root"] = str(configuration.checkpoint_path.parent)
        os.environ["index_root"] = (
            str(configuration.index_path.parent)
            if configuration.index_path
            else str(configuration.source_root / "logs")
        )
        os.environ["outside_index_root"] = os.environ["index_root"]
        os.environ["rmvpe_root"] = str(configuration.source_root / "assets" / "rmvpe")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

        self._validate_checkpoint()
        original_argv = sys.argv[:]
        sys.argv = [sys.argv[0]]
        try:
            with contextlib.redirect_stdout(self._upstream_output):
                from RVCRealtimeVST.worker.rvc_worker import RVCStreamEngine

                self._engine = RVCStreamEngine(
                    {
                        "rvc_root": str(configuration.source_root),
                        "model_path": str(configuration.checkpoint_path),
                        "index_path": (
                            str(configuration.index_path)
                            if configuration.index_path
                            else ""
                        ),
                        "sample_rate": configuration.sample_rate,
                        "block_ms": configuration.block_ms,
                        "crossfade_ms": configuration.crossfade_ms,
                        "extra_ms": configuration.context_ms,
                    }
                )
                if self._engine.rvc.net_g is None:
                    raise RuntimeError("upstream realtime engine did not load RVC")
                self._engine.prewarm()
        finally:
            sys.argv = original_argv

    @property
    def device(self) -> str:
        return str(self._engine.config.device)

    @property
    def native_sample_rate(self) -> int:
        return int(self._engine.rvc.tgt_sr)

    def _validate_checkpoint(self) -> None:
        import torch

        checkpoint = torch.load(
            str(self.configuration.checkpoint_path),
            map_location="cpu",
            weights_only=True,
        )
        if not isinstance(checkpoint, dict) or checkpoint.get("version") != "v2":
            raise ValueError("checkpoint must be an extracted RVC v2 model")
        if checkpoint.get("f0") != 1:
            raise ValueError("checkpoint must support pitch-guided inference")
        weights = checkpoint.get("weight")
        embedding = weights.get("emb_g.weight") if isinstance(weights, dict) else None
        if embedding is None or len(embedding.shape) != 2:
            raise ValueError("checkpoint has no speaker embedding")
        if self.configuration.speaker_id >= int(embedding.shape[0]):
            raise ValueError("speaker_id is not present in checkpoint")

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        if self._closed:
            raise RuntimeError("RVC backend is closed")
        if sample_rate != self.configuration.sample_rate:
            raise ValueError("RVC input sample rate does not match its profile")

        import numpy as np

        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim != 1 or audio.size == 0 or not np.isfinite(audio).all():
            raise ValueError("RVC input must contain finite mono samples")
        if self.configuration.input_gain_db not in (None, 0.0):
            gain = np.float32(10.0 ** (self.configuration.input_gain_db / 20.0))
            audio = audio * gain
        maximum = float(np.max(np.abs(audio))) / 0.95
        if maximum > 1:
            audio = audio / maximum

        with self._lock:
            if self._reset_requested.is_set():
                self._reset_state()
                self._reset_requested.clear()
            converted_chunks: list[np.ndarray] = []
            block = int(self._engine.block_frame)
            method = {"rmvpe": 0, "pm": 2}[self.configuration.f0_method]
            for offset in range(0, audio.size, block):
                chunk = audio[offset : offset + block]
                valid = int(chunk.size)
                if valid < block:
                    chunk = np.pad(chunk, (0, block - valid))
                with contextlib.redirect_stdout(self._upstream_output):
                    converted = self._engine.process(
                        chunk,
                        float(self.configuration.pitch_shift),
                        0.0,
                        self.configuration.index_rate,
                        self.configuration.rms_mix_rate,
                        self.configuration.threshold_dbfs,
                        method,
                    )
                converted_chunks.append(np.asarray(converted, dtype=np.float32)[:valid])
        result = np.concatenate(converted_chunks)
        if result.ndim != 1 or result.size == 0 or not np.isfinite(result).all():
            raise RuntimeError("RVC produced invalid PCM")
        return result.tolist()

    def reset(self) -> None:
        self._reset_requested.set()

    def _reset_state(self) -> None:
        if self.configuration.inference_seed is not None:
            # The upstream synthesizer calls torch.randn_like() for every
            # realtime block. Reset its generator at the generation boundary,
            # before any buffered audio reaches the model.
            self._engine.torch.manual_seed(self.configuration.inference_seed)
        self._engine.input_wav.zero_()
        self._engine.input_wav_res.zero_()
        self._engine.rms_buffer.fill(0.0)
        self._engine.sola_buffer.zero_()
        if hasattr(self._engine.rvc, "cache_pitch"):
            self._engine.rvc.cache_pitch.zero_()
        if hasattr(self._engine.rvc, "cache_pitchf"):
            self._engine.rvc.cache_pitchf.zero_()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            with contextlib.suppress(Exception):
                del self._engine.rvc.net_g
                del self._engine.rvc.model
            with contextlib.suppress(Exception):
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        self._upstream_output.close()


class DeterministicTestBackend:
    implementation_revision = "rvc-v2-test-backend"
    weight_revision = "sha256:" + "0" * 64
    configuration_hash = TEST_CONFIGURATION_HASH

    def __init__(self, gain: float = -0.5) -> None:
        self.gain = gain

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        del sample_rate
        return [float(sample) * self.gain for sample in samples]

    def reset(self) -> None:
        return

    def close(self) -> None:
        return
