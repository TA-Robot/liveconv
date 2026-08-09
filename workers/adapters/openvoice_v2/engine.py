from __future__ import annotations

import base64
import csv
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import platform
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Protocol

_CUDA_DEVICE = re.compile(r"^cuda:(0|[1-9][0-9]*)$")
_NORMALIZED_NAME = re.compile(r"[-_.]+")
_MINIMUM_OUTPUT_RATIO = 0.75
_MAXIMUM_OUTPUT_RATIO = 1.25
_DISTRIBUTION_NAME = "liveconv-worker-runtime"
_ADAPTER_ROOT = Path(__file__).resolve().parent
_IMPLEMENTATION_SOURCE_FILES = (
    "workers/adapters/openvoice_v2/__init__.py",
    "workers/adapters/openvoice_v2/__main__.py",
    "workers/adapters/openvoice_v2/engine.py",
    "workers/adapters/openvoice_v2/network_isolation.py",
    "workers/adapters/openvoice_v2/worker.py",
    "workers/runtime/codec.py",
)
RUNTIME_LOCK_PATH = _ADAPTER_ROOT / "requirements-runtime.lock"


class ConversionModel(Protocol):
    hps: object

    def extract_se(self, ref_wav_list: str) -> object: ...

    def convert(
        self,
        audio_src_path: str,
        src_se: object,
        tgt_se: object,
        output_path: None = None,
        tau: float = 0.3,
        message: str = "default",
    ) -> object: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_source_tree(path: Path) -> str:
    """Hash the imported OpenVoice Python tree without Git metadata."""

    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*.py") if item.is_file())
    if not files:
        raise ValueError("OpenVoice source tree contains no Python files")
    for item in files:
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        encoded = item.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _sha256_manifest(files: tuple[tuple[str, bytes], ...]) -> str:
    digest = hashlib.sha256()
    for relative, encoded in sorted(files):
        encoded_relative = relative.encode("utf-8")
        digest.update(len(encoded_relative).to_bytes(4, "big"))
        digest.update(encoded_relative)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _normalized_distribution_name(value: str) -> str:
    return _NORMALIZED_NAME.sub("-", value).lower()


def _safe_record_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} contains an unsafe path")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"{label} contains a non-canonical path")
    return normalized


def _decode_record_hash(value: str, label: str) -> bytes:
    algorithm, separator, encoded = value.partition("=")
    if separator != "=" or algorithm != "sha256" or not encoded:
        raise ValueError(f"{label} must use SHA-256 RECORD hashes")
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except ValueError as error:
        raise ValueError(f"{label} contains an invalid RECORD hash") from error
    if len(decoded) != hashlib.sha256().digest_size:
        raise ValueError(f"{label} contains an invalid RECORD hash")
    return decoded


@dataclass(frozen=True, slots=True)
class _RecordEntry:
    path: str
    digest: bytes | None
    size: int | None


def _parse_record(encoded: bytes, label: str) -> dict[str, _RecordEntry]:
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} is not UTF-8") from error
    entries: dict[str, _RecordEntry] = {}
    try:
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        for row in rows:
            if len(row) != 3:
                raise ValueError(f"{label} contains a malformed row")
            relative = _safe_record_path(row[0], label)
            if relative in entries:
                raise ValueError(f"{label} contains a duplicate path")
            if bool(row[1]) != bool(row[2]):
                raise ValueError(f"{label} contains incomplete integrity metadata")
            if row[1]:
                digest = _decode_record_hash(row[1], label)
                if not row[2].isascii() or not row[2].isdigit():
                    raise ValueError(f"{label} contains an invalid size")
                size = int(row[2])
            else:
                digest = None
                size = None
            entries[relative] = _RecordEntry(relative, digest, size)
    except csv.Error as error:
        raise ValueError(f"{label} is malformed") from error
    if not entries:
        raise ValueError(f"{label} is empty")
    return entries


def _verify_bytes(encoded: bytes, entry: _RecordEntry, label: str) -> None:
    if entry.digest is None or entry.size is None:
        raise ValueError(f"{label} is missing integrity metadata")
    if len(encoded) != entry.size or hashlib.sha256(encoded).digest() != entry.digest:
        raise ValueError(f"{label} digest mismatch")


@dataclass(frozen=True, slots=True)
class DistributionAttestation:
    version: str
    wheel_sha256: str
    wheel_record_sha256: str
    installed_record_sha256: str
    distribution_manifest_sha256: str
    implementation_sha256: str


def attest_worker_distribution(
    wheel_path: Path,
    expected_wheel_sha256: str,
    *,
    installed_root: Path | None = None,
) -> DistributionAttestation:
    """Verify the wheel, both RECORDs, and every installed wheel member."""

    wheel_path = wheel_path.resolve(strict=True)
    if sha256_file(wheel_path) != expected_wheel_sha256:
        raise ValueError("worker wheel digest mismatch")

    try:
        with zipfile.ZipFile(wheel_path) as archive:
            members = tuple(item for item in archive.infolist() if not item.is_dir())
            member_names = tuple(item.filename for item in members)
            if len(member_names) != len(set(member_names)):
                raise ValueError("worker wheel contains duplicate members")
            for name in member_names:
                _safe_record_path(name, "worker wheel")
            record_names = tuple(
                name for name in member_names if name.endswith(".dist-info/RECORD")
            )
            metadata_names = tuple(
                name for name in member_names if name.endswith(".dist-info/METADATA")
            )
            if len(record_names) != 1 or len(metadata_names) != 1:
                raise ValueError("worker wheel has invalid distribution metadata")
            record_name = record_names[0]
            wheel_record_bytes = archive.read(record_name)
            wheel_record = _parse_record(wheel_record_bytes, "wheel RECORD")
            if set(wheel_record) != set(member_names):
                raise ValueError("wheel RECORD does not enumerate the archive exactly")
            for member in members:
                encoded = archive.read(member)
                entry = wheel_record[member.filename]
                if member.filename == record_name:
                    if entry.digest is not None or entry.size is not None:
                        raise ValueError("wheel RECORD must not hash itself")
                else:
                    _verify_bytes(encoded, entry, f"wheel member {member.filename}")

            metadata = Parser().parsestr(
                archive.read(metadata_names[0]).decode("utf-8")
            )
            name = metadata.get("Name", "")
            version = metadata.get("Version", "")
            if _normalized_distribution_name(name) != _DISTRIBUTION_NAME or not version:
                raise ValueError("worker wheel distribution identity mismatch")

            if installed_root is None:
                distribution = importlib.metadata.distribution(_DISTRIBUTION_NAME)
                installed_root = Path(distribution.locate_file("")).resolve(strict=True)
                if distribution.version != version:
                    raise ValueError("installed worker distribution version mismatch")
            else:
                installed_root = installed_root.resolve(strict=True)

            installed_record_path = installed_root / record_name
            if (
                not installed_record_path.is_file()
                or installed_record_path.is_symlink()
            ):
                raise ValueError("installed worker RECORD is unavailable")
            installed_record_bytes = installed_record_path.read_bytes()
            installed_record = _parse_record(installed_record_bytes, "installed RECORD")
            installed_self = installed_record.get(record_name)
            if installed_self is None or installed_self.digest is not None:
                raise ValueError("installed RECORD must contain an unhashed self entry")

            installed_files: list[tuple[str, bytes]] = []
            for relative, entry in installed_record.items():
                candidate = installed_root / relative
                if candidate.is_symlink():
                    raise ValueError("installed worker distribution contains a symlink")
                path = candidate.resolve(strict=True)
                if not path.is_relative_to(installed_root) or not path.is_file():
                    raise ValueError(
                        "installed RECORD path escapes the distribution root"
                    )
                encoded = path.read_bytes()
                if entry.digest is not None:
                    _verify_bytes(encoded, entry, f"installed member {relative}")
                elif relative != record_name and not relative.endswith(".pyc"):
                    raise ValueError("installed RECORD contains an unhashed member")
                installed_files.append((relative, encoded))

            archive_files: dict[str, bytes] = {}
            for member in members:
                relative = member.filename
                if relative == record_name:
                    continue
                installed_entry = installed_record.get(relative)
                if installed_entry is None:
                    raise ValueError("installed RECORD omits a wheel member")
                wheel_entry = wheel_record[relative]
                if (
                    installed_entry.digest != wheel_entry.digest
                    or installed_entry.size != wheel_entry.size
                ):
                    raise ValueError("installed RECORD differs from wheel RECORD")
                encoded = archive.read(member)
                installed_path = (installed_root / relative).resolve(strict=True)
                if installed_path.read_bytes() != encoded:
                    raise ValueError(f"installed member {relative} differs from wheel")
                archive_files[relative] = encoded
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ValueError("worker wheel attestation failed") from error

    missing_implementation = set(_IMPLEMENTATION_SOURCE_FILES) - set(archive_files)
    if missing_implementation:
        raise ValueError("worker wheel omits an implementation source")
    implementation_files = tuple(
        (relative, archive_files[relative]) for relative in _IMPLEMENTATION_SOURCE_FILES
    )
    return DistributionAttestation(
        version=version,
        wheel_sha256=expected_wheel_sha256,
        wheel_record_sha256=hashlib.sha256(wheel_record_bytes).hexdigest(),
        installed_record_sha256=hashlib.sha256(installed_record_bytes).hexdigest(),
        distribution_manifest_sha256=_sha256_manifest(tuple(installed_files)),
        implementation_sha256=_sha256_manifest(implementation_files),
    )


def _required_file(name: str) -> Path:
    raw = os.environ.get(name)
    if not raw:
        raise ValueError(f"{name} is required")
    path = Path(raw).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{name} must name a regular file")
    return path


def _required_directory(name: str) -> Path:
    raw = os.environ.get(name)
    if not raw:
        raise ValueError(f"{name} is required")
    path = Path(raw).resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{name} must name a directory")
    return path


def _required_digest(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _verify_digest(path: Path, expected: str, label: str) -> None:
    if sha256_file(path) != expected:
        raise ValueError(f"{label} digest mismatch")


def _pyvenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = raw_line.partition("=")
        if separator != "=":
            raise ValueError("runtime pyvenv.cfg is malformed")
        normalized = key.strip().lower()
        if not normalized or normalized in values:
            raise ValueError("runtime pyvenv.cfg is malformed")
        values[normalized] = value.strip()
    return values


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    prefix: Path
    pyvenv_sha256: str
    worker_wheel_path: Path
    worker_wheel_sha256: str
    wheel_record_sha256: str
    installed_record_sha256: str
    distribution_manifest_sha256: str
    implementation_sha256: str
    distribution_version: str

    @classmethod
    def from_environment(cls) -> RuntimeIdentity:
        if os.environ.get("PYTHONPATH"):
            raise ValueError("PYTHONPATH is forbidden for the installed worker runtime")
        prefix = _required_directory("LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX")
        pyvenv_sha256 = _required_digest("LIVECONV_OPENVOICE_V2_PYVENV_SHA256")
        wheel_path = _required_file("LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH")
        wheel_sha256 = _required_digest("LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256")
        attestation = attest_worker_distribution(wheel_path, wheel_sha256)
        expected = {
            "wheel_record_sha256": _required_digest(
                "LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256"
            ),
            "installed_record_sha256": _required_digest(
                "LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256"
            ),
            "distribution_manifest_sha256": _required_digest(
                "LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256"
            ),
            "implementation_sha256": _required_digest(
                "LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256"
            ),
        }
        for field, digest in expected.items():
            if getattr(attestation, field) != digest:
                label = field.removesuffix("_sha256")
                raise ValueError(f"worker {label} digest mismatch")
        result = cls(
            prefix=prefix,
            pyvenv_sha256=pyvenv_sha256,
            worker_wheel_path=wheel_path,
            worker_wheel_sha256=attestation.wheel_sha256,
            wheel_record_sha256=attestation.wheel_record_sha256,
            installed_record_sha256=attestation.installed_record_sha256,
            distribution_manifest_sha256=attestation.distribution_manifest_sha256,
            implementation_sha256=attestation.implementation_sha256,
            distribution_version=attestation.version,
        )
        result.verify()
        return result

    def verify(self) -> None:
        prefix = Path(sys.prefix).resolve(strict=True)
        if prefix != self.prefix:
            raise ValueError("worker is not executing from the declared runtime prefix")
        if Path(sys.base_prefix).resolve(strict=True) == prefix:
            raise ValueError("worker runtime is not an isolated virtual environment")
        executable = Path(sys.executable).absolute()
        if not executable.is_relative_to(self.prefix):
            raise ValueError("worker executable is outside the declared runtime prefix")
        pyvenv_path = self.prefix / "pyvenv.cfg"
        _verify_digest(pyvenv_path, self.pyvenv_sha256, "runtime pyvenv.cfg")
        pyvenv = _pyvenv_values(pyvenv_path)
        if pyvenv.get("include-system-site-packages", "").lower() != "false":
            raise ValueError("worker runtime enables system site packages")
        if pyvenv.get("version_info") != platform.python_version():
            raise ValueError("worker runtime Python version mismatch")

        actual = attest_worker_distribution(
            self.worker_wheel_path,
            self.worker_wheel_sha256,
        )
        for field in (
            "wheel_record_sha256",
            "installed_record_sha256",
            "distribution_manifest_sha256",
            "implementation_sha256",
        ):
            if getattr(actual, field) != getattr(self, field):
                label = field.removesuffix("_sha256")
                raise ValueError(f"worker {label} digest mismatch")
        if actual.version != self.distribution_version:
            raise ValueError("installed worker distribution version mismatch")

        distribution = importlib.metadata.distribution(_DISTRIBUTION_NAME)
        installed_root = Path(distribution.locate_file("")).resolve(strict=True)
        if not installed_root.is_relative_to(self.prefix):
            raise ValueError(
                "worker distribution is outside the declared runtime prefix"
            )
        expected_engine = (installed_root / _IMPLEMENTATION_SOURCE_FILES[2]).resolve()
        if Path(__file__).resolve() != expected_engine:
            raise ValueError("adapter engine was not imported from the installed wheel")
        codec_spec = importlib.util.find_spec("workers.runtime.codec")
        expected_codec = (installed_root / _IMPLEMENTATION_SOURCE_FILES[-1]).resolve()
        if codec_spec is None or codec_spec.origin is None:
            raise ValueError("workers.runtime.codec is unavailable")
        if Path(codec_spec.origin).resolve() != expected_codec:
            raise ValueError(
                "workers.runtime.codec was not imported from the installed wheel"
            )


@dataclass(frozen=True, slots=True)
class EngineConfiguration:
    source_root: Path
    source_tree_sha256: str
    config_path: Path
    config_sha256: str
    checkpoint_path: Path
    checkpoint_sha256: str
    target_reference_path: Path
    target_reference_sha256: str
    runtime_identity: RuntimeIdentity
    runtime_lock_sha256: str
    device: str = "cuda:0"
    tau: float = 0.3
    seed: int = 0

    @classmethod
    def from_environment(cls) -> EngineConfiguration:
        source_root = _required_directory("LIVECONV_OPENVOICE_V2_SOURCE_ROOT")
        source_tree_sha256 = _required_digest(
            "LIVECONV_OPENVOICE_V2_SOURCE_TREE_SHA256"
        )
        config_path = _required_file("LIVECONV_OPENVOICE_V2_CONFIG_PATH")
        config_sha256 = _required_digest("LIVECONV_OPENVOICE_V2_CONFIG_SHA256")
        checkpoint_path = _required_file("LIVECONV_OPENVOICE_V2_CHECKPOINT_PATH")
        checkpoint_sha256 = _required_digest("LIVECONV_OPENVOICE_V2_CHECKPOINT_SHA256")
        target_path = _required_file("LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_PATH")
        target_sha256 = _required_digest(
            "LIVECONV_OPENVOICE_V2_TARGET_REFERENCE_SHA256"
        )
        runtime_identity = RuntimeIdentity.from_environment()
        runtime_lock_sha256 = _required_digest(
            "LIVECONV_OPENVOICE_V2_RUNTIME_LOCK_SHA256"
        )
        device = os.environ.get("LIVECONV_OPENVOICE_V2_DEVICE", "cuda:0")
        if device != "cpu" and not _CUDA_DEVICE.fullmatch(device):
            raise ValueError("LIVECONV_OPENVOICE_V2_DEVICE must be cpu or cuda:N")
        raw_tau = os.environ.get("LIVECONV_OPENVOICE_V2_TAU", "0.3")
        try:
            tau = float(raw_tau)
        except ValueError as error:
            raise ValueError("LIVECONV_OPENVOICE_V2_TAU must be numeric") from error
        if not math.isfinite(tau) or not 0.0 <= tau <= 1.0:
            raise ValueError("LIVECONV_OPENVOICE_V2_TAU must be between 0 and 1")
        raw_seed = os.environ.get("LIVECONV_OPENVOICE_V2_SEED", "0")
        try:
            seed = int(raw_seed)
        except ValueError as error:
            raise ValueError(
                "LIVECONV_OPENVOICE_V2_SEED must be an unsigned integer"
            ) from error
        if seed < 0 or seed > 2**63 - 1:
            raise ValueError("LIVECONV_OPENVOICE_V2_SEED must fit an unsigned int63")

        result = cls(
            source_root=source_root,
            source_tree_sha256=source_tree_sha256,
            config_path=config_path,
            config_sha256=config_sha256,
            checkpoint_path=checkpoint_path,
            checkpoint_sha256=checkpoint_sha256,
            target_reference_path=target_path,
            target_reference_sha256=target_sha256,
            runtime_identity=runtime_identity,
            runtime_lock_sha256=runtime_lock_sha256,
            device=device,
            tau=tau,
            seed=seed,
        )
        result.verify()
        return result

    def verify(self) -> None:
        source_digest = sha256_source_tree(self.source_root / "openvoice")
        if source_digest != self.source_tree_sha256:
            raise ValueError("OpenVoice source tree digest mismatch")
        _verify_digest(self.config_path, self.config_sha256, "converter config")
        _verify_digest(self.checkpoint_path, self.checkpoint_sha256, "converter weight")
        _verify_digest(
            self.target_reference_path,
            self.target_reference_sha256,
            "target reference",
        )
        self.runtime_identity.verify()
        _verify_digest(RUNTIME_LOCK_PATH, self.runtime_lock_sha256, "runtime lock")

    @property
    def weight_revision(self) -> str:
        identity = hashlib.sha256()
        for digest in (
            self.source_tree_sha256,
            self.config_sha256,
            self.checkpoint_sha256,
            self.target_reference_sha256,
        ):
            identity.update(bytes.fromhex(digest))
        return f"sha256:{identity.hexdigest()}"

    @property
    def configuration_hash(self) -> str:
        runtime = self.runtime_identity
        payload = {
            "checkpoint_sha256": self.checkpoint_sha256,
            "config_sha256": self.config_sha256,
            "device": self.device,
            "distribution_manifest_sha256": runtime.distribution_manifest_sha256,
            "implementation_sha256": runtime.implementation_sha256,
            "installed_record_sha256": runtime.installed_record_sha256,
            "pyvenv_sha256": runtime.pyvenv_sha256,
            "runtime_lock_sha256": self.runtime_lock_sha256,
            "seed": self.seed,
            "source_tree_sha256": self.source_tree_sha256,
            "target_reference_sha256": self.target_reference_sha256,
            "tau": self.tau,
            "wheel_record_sha256": runtime.wheel_record_sha256,
            "worker_wheel_sha256": runtime.worker_wheel_sha256,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _load_openvoice(configuration: EngineConfiguration) -> tuple[ModuleType, object]:
    source = str(configuration.source_root)
    if source not in sys.path:
        sys.path.insert(0, source)
    api = importlib.import_module("openvoice.api")
    converter_class = api.ToneColorConverter

    # Upstream commit 74a1d147 forwards enable_watermark to a base constructor
    # that does not accept it. Constructing the base explicitly disables the
    # optional third-party watermark model without modifying pinned source.
    model = converter_class.__new__(converter_class)
    api.OpenVoiceBaseClass.__init__(
        model,
        str(configuration.config_path),
        device=configuration.device,
    )
    model.watermark_model = None
    model.version = getattr(model.hps, "_version_", "v1")
    model.load_ckpt(str(configuration.checkpoint_path))
    return api, model


class OpenVoiceV2Engine:
    """Whole-utterance OpenVoice converter with immutable local artifacts."""

    def __init__(
        self,
        configuration: EngineConfiguration,
        *,
        model: ConversionModel | None = None,
    ) -> None:
        self.configuration = configuration
        if model is None:
            _, model = _load_openvoice(configuration)
        self._model = model
        self._target_se = model.extract_se(str(configuration.target_reference_path))
        data = getattr(model.hps, "data")
        self.native_sample_rate = int(getattr(data, "sampling_rate"))

    @classmethod
    def from_environment(cls) -> OpenVoiceV2Engine:
        return cls(EngineConfiguration.from_environment())

    @property
    def weight_revision(self) -> str:
        return self.configuration.weight_revision

    @property
    def configuration_hash(self) -> str:
        return self.configuration.configuration_hash

    @property
    def implementation_sha256(self) -> str:
        return self.configuration.runtime_identity.implementation_sha256

    def convert(self, samples: object, sample_rate: int) -> object:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        numpy = importlib.import_module("numpy")
        soundfile = importlib.import_module("soundfile")
        librosa = importlib.import_module("librosa")
        source = numpy.asarray(samples, dtype=numpy.float32)
        if source.ndim != 1 or source.size == 0:
            raise ValueError("source audio must be a non-empty mono vector")
        if not numpy.isfinite(source).all() or numpy.max(numpy.abs(source)) > 1.0:
            raise ValueError("source audio must contain normalized finite PCM")

        with tempfile.TemporaryDirectory(prefix="liveconv-openvoice-") as directory:
            input_path = Path(directory) / "source.wav"
            soundfile.write(input_path, source, sample_rate, subtype="PCM_16")
            source_se = self._model.extract_se(str(input_path))
            torch = importlib.import_module("torch")
            devices = (
                [int(self.configuration.device.removeprefix("cuda:"))]
                if self.configuration.device.startswith("cuda:")
                else []
            )
            with torch.random.fork_rng(devices=devices):
                torch.manual_seed(self.configuration.seed)
                converted = self._model.convert(
                    str(input_path),
                    source_se,
                    self._target_se,
                    output_path=None,
                    tau=self.configuration.tau,
                    message="",
                )

        output = numpy.asarray(converted, dtype=numpy.float32)
        if output.ndim != 1 or output.size == 0 or not numpy.isfinite(output).all():
            raise RuntimeError("OpenVoice returned invalid PCM")
        if self.native_sample_rate != sample_rate:
            output = librosa.resample(
                output,
                orig_sr=self.native_sample_rate,
                target_sr=sample_rate,
            )
        if output.size == 0 or not numpy.isfinite(output).all():
            raise RuntimeError("OpenVoice resampling returned invalid PCM")
        output_ratio = output.size / source.size
        if not _MINIMUM_OUTPUT_RATIO <= output_ratio <= _MAXIMUM_OUTPUT_RATIO:
            raise RuntimeError("OpenVoice returned an implausible PCM duration")
        if output.size < source.size:
            output = numpy.pad(output, (0, source.size - output.size))
        elif output.size > source.size:
            output = output[: source.size]
        output = numpy.clip(output, -1.0, 1.0).astype(numpy.float32, copy=False)
        if output.size != source.size or not numpy.isfinite(output).all():
            raise RuntimeError("OpenVoice returned invalid PCM")
        return output
