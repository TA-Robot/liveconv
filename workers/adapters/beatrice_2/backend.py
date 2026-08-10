from __future__ import annotations

import base64
import contextlib
import csv
import gzip
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import threading
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Protocol

FRAME_MS = 20
MINIMUM_INFERENCE_MS = 60
CONFIGURATION_SCHEMA = "liveconv-beatrice-2-worker-configuration-v2"
ADAPTER_REVISION = "beatrice-2-worker-v3"
ADAPTER_ROOT = Path(__file__).resolve().parent
RUNTIME_LOCK_PATH = ADAPTER_ROOT / "requirements-runtime.lock.txt"
WORKER_DISTRIBUTION = "liveconv-worker-runtime"
_LOCKED_REQUIREMENT = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)")
_EXECUTED_PROJECT_MODULES = (
    "workers/__init__.py",
    "workers/adapters/__init__.py",
    "workers/adapters/beatrice_2/__init__.py",
    "workers/adapters/beatrice_2/backend.py",
    "workers/adapters/beatrice_2/worker.py",
    "workers/runtime/__init__.py",
    "workers/runtime/codec.py",
)


class ConversionBackend(Protocol):
    implementation_revision: str
    weight_revision: str
    configuration_hash: str

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]: ...

    def reset(self) -> None: ...

    def close(self) -> None: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_package_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256_manifest(files: Sequence[tuple[str, bytes]]) -> str:
    encoded = json.dumps(
        {
            "files": {
                relative: hashlib.sha256(content).hexdigest()
                for relative, content in files
            },
            "schema": "liveconv-beatrice-2-file-manifest-v1",
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def source_tree_manifest_sha256(source_root: Path) -> str:
    files: list[tuple[str, bytes]] = []
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if relative.parts and relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            raise ValueError("Beatrice source tree must not contain symlinks")
        if path.is_file():
            files.append((relative.as_posix(), path.read_bytes()))
        elif not path.is_dir():
            raise ValueError("Beatrice source tree contains an unsupported entry")
    if not files:
        raise ValueError("Beatrice source tree is empty")
    return _sha256_manifest(files)


def _locked_packages(content: bytes) -> dict[str, str]:
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Beatrice runtime lock is not UTF-8") from error
    packages: dict[str, str] = {}
    for line in lines:
        match = _LOCKED_REQUIREMENT.match(line)
        if match is not None:
            packages[_canonical_package_name(match.group(1))] = match.group(2)
    if not packages:
        raise ValueError("Beatrice runtime lock contains no exact package pins")
    return packages


def _package_inventory_sha256(packages: dict[str, str]) -> str:
    encoded = json.dumps(
        {
            "packages": packages,
            "schema": "liveconv-beatrice-2-package-inventory-v1",
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _safe_record_path(value: str, label: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} contains an unsafe path")
    return value


def _record_rows(content: bytes, label: str) -> dict[str, tuple[str, str]]:
    try:
        rows = csv.reader(io.StringIO(content.decode("utf-8")), strict=True)
        parsed: dict[str, tuple[str, str]] = {}
        for row in rows:
            if len(row) != 3:
                raise ValueError(f"{label} contains a malformed row")
            relative = _safe_record_path(row[0], label)
            if relative in parsed:
                raise ValueError(f"{label} contains a duplicate path")
            if bool(row[1]) != bool(row[2]):
                raise ValueError(f"{label} contains incomplete integrity metadata")
            if row[1]:
                algorithm, separator, digest = row[1].partition("=")
                if algorithm != "sha256" or not separator or not digest:
                    raise ValueError(f"{label} contains an unsupported digest")
                try:
                    value_bytes = base64.urlsafe_b64decode(
                        digest + "=" * (-len(digest) % 4)
                    )
                except (ValueError, UnicodeError) as error:
                    raise ValueError(f"{label} contains an invalid digest") from error
                if len(value_bytes) != 32 or not row[2].isdigit():
                    raise ValueError(f"{label} contains invalid integrity metadata")
            parsed[relative] = (row[1], row[2])
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError(f"{label} is malformed") from error
    if not parsed:
        raise ValueError(f"{label} is empty")
    return parsed


def _verify_record_member(content: bytes, row: tuple[str, str], label: str) -> None:
    digest, size = row
    if not digest and not size:
        raise ValueError(f"{label} is missing integrity metadata")
    algorithm, separator, encoded = digest.partition("=")
    if algorithm != "sha256" or not separator or not encoded:
        raise ValueError(f"{label} contains an unsupported digest")
    expected = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    if len(content) != int(size) or hashlib.sha256(content).digest() != expected:
        raise ValueError(f"{label} digest does not match")


def _installed_packages() -> dict[str, str]:
    return {
        _canonical_package_name(distribution.metadata["Name"]): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    }


@dataclass(frozen=True, slots=True)
class WorkerRuntimeBinding:
    worker_wheel_path: Path
    worker_wheel_sha256: str
    wheel_record_sha256: str
    installed_record_sha256: str
    distribution_manifest_sha256: str
    executed_project_modules_sha256: str
    runtime_codec_sha256: str
    requirements_lock_sha256: str
    installed_distribution_inventory_sha256: str
    distribution_version: str

    @classmethod
    def inspect(
        cls,
        wheel_path: Path,
        expected_wheel_sha256: str,
        *,
        installed_root: Path | None = None,
        installed_packages: dict[str, str] | None = None,
    ) -> WorkerRuntimeBinding:
        wheel_path = wheel_path.resolve(strict=True)
        if not wheel_path.is_file():
            raise ValueError("Beatrice worker wheel must identify a file")
        actual_wheel_sha256 = sha256_file(wheel_path)
        if actual_wheel_sha256 != expected_wheel_sha256:
            raise ValueError("Beatrice worker wheel digest does not match")

        try:
            with zipfile.ZipFile(wheel_path) as archive:
                members = tuple(
                    item for item in archive.infolist() if not item.is_dir()
                )
                member_names = tuple(item.filename for item in members)
                if len(member_names) != len(set(member_names)):
                    raise ValueError("Beatrice worker wheel contains duplicate members")
                for name in member_names:
                    _safe_record_path(name, "worker wheel")
                record_names = tuple(
                    name for name in member_names if name.endswith(".dist-info/RECORD")
                )
                metadata_names = tuple(
                    name
                    for name in member_names
                    if name.endswith(".dist-info/METADATA")
                )
                if len(record_names) != 1 or len(metadata_names) != 1:
                    raise ValueError("Beatrice worker wheel has invalid metadata")
                record_name = record_names[0]
                wheel_record_bytes = archive.read(record_name)
                wheel_record = _record_rows(wheel_record_bytes, "wheel RECORD")
                if set(wheel_record) != set(member_names):
                    raise ValueError(
                        "wheel RECORD does not enumerate the archive exactly"
                    )
                archive_files: dict[str, bytes] = {}
                for member in members:
                    content = archive.read(member)
                    row = wheel_record[member.filename]
                    if member.filename == record_name:
                        if row != ("", ""):
                            raise ValueError("wheel RECORD must not hash itself")
                    else:
                        _verify_record_member(
                            content, row, f"wheel member {member.filename}"
                        )
                        archive_files[member.filename] = content
                metadata = Parser().parsestr(
                    archive.read(metadata_names[0]).decode("utf-8", errors="strict")
                )
                distribution_name = metadata.get("Name", "")
                version = metadata.get("Version", "")
                if (
                    _canonical_package_name(distribution_name) != WORKER_DISTRIBUTION
                    or not version
                ):
                    raise ValueError(
                        "worker wheel distribution identity does not match"
                    )

                if installed_root is None:
                    distribution = importlib.metadata.distribution(WORKER_DISTRIBUTION)
                    if distribution.version != version:
                        raise ValueError(
                            "installed worker distribution version does not match"
                        )
                    installed_root = Path(distribution.locate_file("")).resolve(
                        strict=True
                    )
                else:
                    installed_root = installed_root.resolve(strict=True)

                installed_record_path = installed_root / record_name
                if (
                    not installed_record_path.is_file()
                    or installed_record_path.is_symlink()
                ):
                    raise ValueError("installed worker RECORD is unavailable")
                installed_record_bytes = installed_record_path.read_bytes()
                installed_record = _record_rows(
                    installed_record_bytes, "installed RECORD"
                )
                if installed_record.get(record_name) != ("", ""):
                    raise ValueError("installed RECORD must not hash itself")

                installed_files: list[tuple[str, bytes]] = []
                dist_info_prefix = record_name.rsplit("/", 1)[0] + "/"
                for relative, installed_row in installed_record.items():
                    if relative not in wheel_record and not relative.startswith(
                        dist_info_prefix
                    ):
                        raise ValueError(
                            "installed RECORD contains an unbound distribution member"
                        )
                    candidate = installed_root / relative
                    if candidate.is_symlink():
                        raise ValueError(
                            "installed worker distribution contains a symlink"
                        )
                    installed_path = candidate.resolve(strict=True)
                    if (
                        not installed_path.is_relative_to(installed_root)
                        or not installed_path.is_file()
                    ):
                        raise ValueError(
                            "installed RECORD path escapes the distribution root"
                        )
                    content = installed_path.read_bytes()
                    if relative != record_name:
                        _verify_record_member(
                            content, installed_row, f"installed member {relative}"
                        )
                    installed_files.append((relative, content))
                for relative, wheel_row in wheel_record.items():
                    if installed_record.get(relative) != wheel_row:
                        raise ValueError("installed RECORD differs from wheel RECORD")
                    if relative != record_name and (
                        (installed_root / relative).read_bytes()
                        != archive_files[relative]
                    ):
                        raise ValueError(
                            f"installed worker member differs from wheel: {relative}"
                        )
        except (
            OSError,
            UnicodeError,
            ValueError,
            zipfile.BadZipFile,
            KeyError,
        ) as error:
            if isinstance(error, ValueError) and str(error).startswith("Beatrice"):
                raise
            raise ValueError("Beatrice worker wheel attestation failed") from error

        missing_modules = set(_EXECUTED_PROJECT_MODULES) - set(archive_files)
        if missing_modules:
            raise ValueError("worker wheel omits an executed project module")
        lock_content = archive_files.get(
            "workers/adapters/beatrice_2/requirements-runtime.lock.txt"
        )
        if lock_content is None:
            raise ValueError("worker wheel omits the Beatrice runtime lock")
        expected_packages = _locked_packages(lock_content)
        expected_packages[WORKER_DISTRIBUTION] = version
        actual_packages = (
            installed_packages
            if installed_packages is not None
            else _installed_packages()
        )
        if actual_packages != expected_packages:
            raise ValueError(
                "installed Beatrice runtime differs from its packaged lock"
            )
        executed_files = tuple(
            (relative, archive_files[relative])
            for relative in _EXECUTED_PROJECT_MODULES
        )
        return cls(
            worker_wheel_path=wheel_path,
            worker_wheel_sha256=actual_wheel_sha256,
            wheel_record_sha256=hashlib.sha256(wheel_record_bytes).hexdigest(),
            installed_record_sha256=hashlib.sha256(installed_record_bytes).hexdigest(),
            distribution_manifest_sha256=_sha256_manifest(tuple(installed_files)),
            executed_project_modules_sha256=_sha256_manifest(executed_files),
            runtime_codec_sha256=hashlib.sha256(
                archive_files["workers/runtime/codec.py"]
            ).hexdigest(),
            requirements_lock_sha256=hashlib.sha256(lock_content).hexdigest(),
            installed_distribution_inventory_sha256=_package_inventory_sha256(
                actual_packages
            ),
            distribution_version=version,
        )

    def validate(self) -> None:
        current = type(self).inspect(self.worker_wheel_path, self.worker_wheel_sha256)
        if current != self:
            raise ValueError("Beatrice worker runtime binding changed")
        distribution = importlib.metadata.distribution(WORKER_DISTRIBUTION)
        installed_root = Path(distribution.locate_file("")).resolve(strict=True)
        expected_backend = (
            installed_root / "workers/adapters/beatrice_2/backend.py"
        ).resolve(strict=True)
        if Path(__file__).resolve() != expected_backend:
            raise ValueError(
                "Beatrice backend was not imported from the installed wheel"
            )
        codec_spec = importlib.util.find_spec("workers.runtime.codec")
        expected_codec = (installed_root / "workers/runtime/codec.py").resolve(
            strict=True
        )
        if (
            codec_spec is None
            or codec_spec.origin is None
            or Path(codec_spec.origin).resolve() != expected_codec
        ):
            raise ValueError(
                "workers.runtime.codec was not imported from the installed wheel"
            )


def _file(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{name} must identify a file")
    return path


def _directory(name: str, value: str) -> Path:
    if not value:
        raise ValueError(f"{name} is required")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{name} must identify a directory")
    return path


def _digest(name: str, value: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _validate_source_revision(
    source_root: Path, expected_revision: str, expected_source_tree_sha256: str
) -> None:
    if source_tree_manifest_sha256(source_root) != expected_source_tree_sha256:
        raise ValueError("Beatrice source tree manifest does not match")
    try:
        head = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status = subprocess.run(
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
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # A complete verified source-tree manifest is an equivalent import boundary
        # when the deployment artifact is an export rather than a full checkout.
        return
    if head == expected_revision and not status:
        return


@dataclass(frozen=True, slots=True)
class BeatriceConfiguration:
    source_root: Path
    source_revision: str
    source_sha256: str
    source_tree_sha256: str
    phone_checkpoint: Path
    phone_sha256: str
    pitch_checkpoint: Path
    pitch_sha256: str
    converter_checkpoint: Path
    converter_sha256: str
    runtime_lock_sha256: str
    worker_runtime: WorkerRuntimeBinding
    target_speaker_id: int = 46
    sample_rate: int = 48_000
    batch_ms: int = 500
    device: str = "cpu"

    @classmethod
    def from_environment(
        cls, *, require_installed_record: bool = True
    ) -> BeatriceConfiguration:
        source_root = _directory(
            "LIVECONV_BEATRICE_SOURCE_ROOT",
            os.environ.get("LIVECONV_BEATRICE_SOURCE_ROOT", ""),
        )
        source_module = _file(
            "LIVECONV_BEATRICE_SOURCE_MODULE",
            os.environ.get("LIVECONV_BEATRICE_SOURCE_MODULE", ""),
        )
        expected_source_module = (
            source_root / "beatrice_trainer" / "__main__.py"
        ).resolve(strict=True)
        if source_module != expected_source_module:
            raise ValueError(
                "Beatrice source module must be inside the pinned source root"
            )
        worker_wheel = _file(
            "LIVECONV_BEATRICE_WORKER_WHEEL",
            os.environ.get("LIVECONV_BEATRICE_WORKER_WHEEL", ""),
        )
        worker_wheel_sha256 = _digest(
            "LIVECONV_BEATRICE_WORKER_WHEEL_SHA256",
            os.environ.get("LIVECONV_BEATRICE_WORKER_WHEEL_SHA256", ""),
        )
        configuration = cls(
            source_root=source_root,
            source_revision=os.environ.get("LIVECONV_BEATRICE_SOURCE_REVISION", ""),
            source_sha256=_digest(
                "LIVECONV_BEATRICE_SOURCE_SHA256",
                os.environ.get("LIVECONV_BEATRICE_SOURCE_SHA256", ""),
            ),
            source_tree_sha256=_digest(
                "LIVECONV_BEATRICE_SOURCE_TREE_SHA256",
                os.environ.get("LIVECONV_BEATRICE_SOURCE_TREE_SHA256", ""),
            ),
            phone_checkpoint=_file(
                "LIVECONV_BEATRICE_PHONE_CHECKPOINT",
                os.environ.get("LIVECONV_BEATRICE_PHONE_CHECKPOINT", ""),
            ),
            phone_sha256=_digest(
                "LIVECONV_BEATRICE_PHONE_SHA256",
                os.environ.get("LIVECONV_BEATRICE_PHONE_SHA256", ""),
            ),
            pitch_checkpoint=_file(
                "LIVECONV_BEATRICE_PITCH_CHECKPOINT",
                os.environ.get("LIVECONV_BEATRICE_PITCH_CHECKPOINT", ""),
            ),
            pitch_sha256=_digest(
                "LIVECONV_BEATRICE_PITCH_SHA256",
                os.environ.get("LIVECONV_BEATRICE_PITCH_SHA256", ""),
            ),
            converter_checkpoint=_file(
                "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT",
                os.environ.get("LIVECONV_BEATRICE_CONVERTER_CHECKPOINT", ""),
            ),
            converter_sha256=_digest(
                "LIVECONV_BEATRICE_CONVERTER_SHA256",
                os.environ.get("LIVECONV_BEATRICE_CONVERTER_SHA256", ""),
            ),
            runtime_lock_sha256=_digest(
                "LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256",
                os.environ.get("LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256", ""),
            ),
            worker_runtime=WorkerRuntimeBinding.inspect(
                worker_wheel, worker_wheel_sha256
            ),
            target_speaker_id=int(
                os.environ.get("LIVECONV_BEATRICE_TARGET_SPEAKER_ID", "46")
            ),
            sample_rate=int(os.environ.get("LIVECONV_BEATRICE_SAMPLE_RATE", "48000")),
            batch_ms=int(os.environ.get("LIVECONV_BEATRICE_BATCH_MS", "500")),
            device=os.environ.get("LIVECONV_BEATRICE_DEVICE", "cpu"),
        )
        configuration.validate(require_installed_record=require_installed_record)
        return configuration

    def validate(self, *, require_installed_record: bool = False) -> None:
        del require_installed_record
        self.worker_runtime.validate()
        if len(self.source_revision) != 40 or any(
            character not in "0123456789abcdef" for character in self.source_revision
        ):
            raise ValueError("source revision must be a Git commit")
        _validate_source_revision(
            self.source_root, self.source_revision, self.source_tree_sha256
        )
        source_module = self.source_root / "beatrice_trainer" / "__main__.py"
        if (
            not source_module.is_file()
            or sha256_file(source_module) != self.source_sha256
        ):
            raise ValueError("Beatrice source module digest does not match")
        for path, expected in (
            (self.phone_checkpoint, self.phone_sha256),
            (self.pitch_checkpoint, self.pitch_sha256),
            (self.converter_checkpoint, self.converter_sha256),
        ):
            if sha256_file(path) != expected:
                raise ValueError("Beatrice checkpoint digest does not match")
        if self.runtime_lock_sha256 != self.worker_runtime.requirements_lock_sha256:
            raise ValueError("Beatrice runtime lock digest does not match")
        if not 0 <= self.target_speaker_id < 200:
            raise ValueError("target speaker ID must be between 0 and 199")
        if self.sample_rate != 48_000:
            raise ValueError("worker-v1 Beatrice input must be 48 kHz")
        if self.batch_ms != 500:
            raise ValueError("worker-v1 Beatrice batch must be 500 ms")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("Beatrice device must be cpu or cuda")

    @property
    def canonical_payload(self) -> dict[str, int | str]:
        return {
            "adapter_revision": ADAPTER_REVISION,
            "distribution_manifest_sha256": (
                self.worker_runtime.distribution_manifest_sha256
            ),
            "installed_distribution_inventory_sha256": (
                self.worker_runtime.installed_distribution_inventory_sha256
            ),
            "executed_project_modules_sha256": (
                self.worker_runtime.executed_project_modules_sha256
            ),
            "batch_ms": self.batch_ms,
            "converter_sha256": self.converter_sha256,
            "device": self.device,
            "frame_ms": FRAME_MS,
            "installed_record_sha256": self.worker_runtime.installed_record_sha256,
            "minimum_inference_ms": MINIMUM_INFERENCE_MS,
            "phone_sha256": self.phone_sha256,
            "pitch_sha256": self.pitch_sha256,
            "runtime_lock_sha256": self.runtime_lock_sha256,
            "runtime_codec_sha256": self.worker_runtime.runtime_codec_sha256,
            "sample_rate": self.sample_rate,
            "schema": CONFIGURATION_SCHEMA,
            "source_revision": self.source_revision,
            "source_sha256": self.source_sha256,
            "source_tree_sha256": self.source_tree_sha256,
            "target_speaker_id": self.target_speaker_id,
            "wheel_record_sha256": self.worker_runtime.wheel_record_sha256,
            "worker_wheel_sha256": self.worker_runtime.worker_wheel_sha256,
        }

    @property
    def configuration_hash(self) -> str:
        encoded = json.dumps(
            self.canonical_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class UpstreamBeatriceBackend:
    """Load the pinned MIT trainer implementation as an inference-only backend."""

    def __init__(self, configuration: BeatriceConfiguration) -> None:
        configuration.validate()
        self.configuration = configuration
        self.implementation_revision = configuration.source_revision
        self.weight_revision = f"sha256:{configuration.converter_sha256}"
        self.configuration_hash = configuration.configuration_hash
        self._lock = threading.Lock()
        self._closed = False
        self._upstream_output = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

        root = str(configuration.source_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            with contextlib.redirect_stdout(self._upstream_output):
                import torch
                from beatrice_trainer.__main__ import (
                    ConverterNetwork,
                    PhoneExtractor,
                    PitchEstimator,
                )

                if configuration.device == "cuda" and not torch.cuda.is_available():
                    raise RuntimeError("Beatrice CUDA was requested but is unavailable")
                self._torch = torch
                self._device = torch.device(configuration.device)
                phone = PhoneExtractor().to(self._device).eval().requires_grad_(False)
                phone_checkpoint = torch.load(
                    configuration.phone_checkpoint,
                    map_location="cpu",
                    weights_only=True,
                )
                phone_state = self._checkpoint_state(
                    phone_checkpoint, "phone_extractor"
                )
                phone.load_state_dict(phone_state, strict=True)
                pitch = PitchEstimator().to(self._device).eval().requires_grad_(False)
                pitch_checkpoint = torch.load(
                    configuration.pitch_checkpoint,
                    map_location="cpu",
                    weights_only=True,
                )
                pitch_state = self._checkpoint_state(
                    pitch_checkpoint, "pitch_estimator"
                )
                pitch.load_state_dict(pitch_state, strict=True)
                network = ConverterNetwork(phone, pitch, 200, 448, 256)
                network = network.to(self._device).eval().requires_grad_(False)
                with gzip.open(configuration.converter_checkpoint, "rb") as stream:
                    converter_checkpoint = torch.load(
                        stream,
                        map_location="cpu",
                        weights_only=True,
                    )
                converter_state = self._checkpoint_state(converter_checkpoint, "net_g")
                network.load_state_dict(converter_state, strict=True)
                network.enable_hook()
                self._network = network
                self._target = torch.tensor(
                    [configuration.target_speaker_id],
                    device=self._device,
                    dtype=torch.long,
                )
                self._formant = torch.zeros(1, device=self._device)
        except Exception:
            self._upstream_output.close()
            raise

    @staticmethod
    def _checkpoint_state(checkpoint: object, key: str) -> dict[str, object]:
        if not isinstance(checkpoint, dict):
            raise ValueError("Beatrice checkpoint must contain a state dictionary")
        state = checkpoint.get(key)
        if not isinstance(state, dict) or not state:
            raise ValueError(f"Beatrice checkpoint is missing {key}")
        return state

    @property
    def device(self) -> str:
        return str(self._device)

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        if self._closed:
            raise RuntimeError("Beatrice backend is closed")
        if sample_rate != self.configuration.sample_rate:
            raise ValueError("Beatrice sample rate does not match its profile")

        import numpy as np
        import torchaudio

        audio = np.asarray(samples, dtype=np.float32)
        frame_samples = self.configuration.sample_rate * FRAME_MS // 1000
        maximum_samples = (
            self.configuration.sample_rate * self.configuration.batch_ms // 1000
        )
        if (
            audio.ndim != 1
            or audio.size == 0
            or audio.size > maximum_samples
            or audio.size % frame_samples
            or not np.isfinite(audio).all()
            or float(np.max(np.abs(audio))) > 1.0
        ):
            raise ValueError(
                "Beatrice input must be 20 ms-aligned finite normalized mono PCM "
                "within the 500 ms batch limit"
            )
        expected = int(audio.size)
        minimum_samples = self.configuration.sample_rate * MINIMUM_INFERENCE_MS // 1000
        inference_audio = audio
        if audio.size < minimum_samples:
            inference_audio = np.pad(audio, (0, minimum_samples - audio.size))
        with self._lock, self._torch.inference_mode():
            waveform = self._torch.from_numpy(inference_audio.copy()).to(self._device)[
                None, :
            ]
            waveform = torchaudio.functional.resample(waveform, sample_rate, 16_000)
            remainder = waveform.shape[-1] % 160
            if remainder:
                waveform = self._torch.nn.functional.pad(waveform, (0, 160 - remainder))
            with contextlib.redirect_stdout(self._upstream_output):
                converted = self._network(
                    waveform.unsqueeze(0),
                    self._target,
                    self._formant,
                ).squeeze(0)
            converted = torchaudio.functional.resample(converted, 24_000, sample_rate)
            values = converted.squeeze(0).to("cpu", dtype=self._torch.float32).numpy()
        if values.size < expected:
            values = np.pad(values, (0, expected - values.size))
        values = values[:expected]
        if not np.isfinite(values).all():
            raise RuntimeError("Beatrice produced non-finite PCM")
        peak = float(np.max(np.abs(values)))
        if peak > 0.99:
            values = values * (0.99 / peak)
        return values.astype(np.float32, copy=False).tolist()

    def reset(self) -> None:
        # The trainer graph is window-stateless; target IDs are set on each forward.
        return

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            del self._network
            if self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()
        self._upstream_output.close()


class DeterministicTestBackend:
    implementation_revision = "beatrice-2-test-backend"
    weight_revision = "sha256:" + "0" * 64
    configuration_hash = "sha256:" + "4" * 64

    def __init__(self, gain: float = -0.5) -> None:
        self.gain = gain

    def convert(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        del sample_rate
        return [float(sample) * self.gain for sample in samples]

    def reset(self) -> None:
        return None

    def close(self) -> None:
        return None
