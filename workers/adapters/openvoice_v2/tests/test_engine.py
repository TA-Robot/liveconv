from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from workers.adapters.openvoice_v2.engine import (
    RUNTIME_LOCK_PATH,
    DistributionAttestation,
    EngineConfiguration,
    OpenVoiceV2Engine,
    RuntimeIdentity,
    attest_worker_distribution,
    sha256_file,
    sha256_source_tree,
)


class FakeModel:
    hps = SimpleNamespace(data=SimpleNamespace(sampling_rate=16_000))

    def extract_se(self, path: str):
        return (Path(path).name,)

    def convert(self, *_args, **_kwargs):
        return [0.25, -0.25, 0.1, -0.1]


class ResultModel(FakeModel):
    def __init__(self, result) -> None:
        self.result = result

    def convert(self, *_args, **_kwargs):
        return self.result


class TorchRandomModel(FakeModel):
    def convert(self, *_args, **_kwargs):
        torch = pytest.importorskip("torch")
        return torch.rand(4).numpy()


def fake_runtime_identity(tmp_path: Path) -> RuntimeIdentity:
    wheel = tmp_path / "worker.whl"
    wheel.write_bytes(b"wheel")
    return RuntimeIdentity(
        prefix=Path(sys.prefix).resolve(),
        pyvenv_sha256="1" * 64,
        worker_wheel_path=wheel,
        worker_wheel_sha256="2" * 64,
        wheel_record_sha256="3" * 64,
        installed_record_sha256="4" * 64,
        distribution_manifest_sha256="5" * 64,
        implementation_sha256="6" * 64,
        distribution_version="0.1.0",
    )


def configuration(tmp_path: Path) -> EngineConfiguration:
    source = tmp_path / "source" / "openvoice"
    source.mkdir(parents=True)
    (source / "api.py").write_text("revision = 1\n", encoding="ascii")
    config = tmp_path / "config.json"
    checkpoint = tmp_path / "checkpoint.pth"
    target = tmp_path / "target.wav"
    config.write_text("{}", encoding="ascii")
    checkpoint.write_bytes(b"weight")
    target.write_bytes(b"target")
    return EngineConfiguration(
        source_root=source.parent,
        source_tree_sha256=sha256_source_tree(source),
        config_path=config,
        config_sha256=sha256_file(config),
        checkpoint_path=checkpoint,
        checkpoint_sha256=sha256_file(checkpoint),
        target_reference_path=target,
        target_reference_sha256=sha256_file(target),
        runtime_identity=fake_runtime_identity(tmp_path),
        runtime_lock_sha256=sha256_file(RUNTIME_LOCK_PATH),
        device="cpu",
        seed=17,
    )


def test_configuration_verifies_all_immutable_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RuntimeIdentity, "verify", lambda _self: None)
    value = configuration(tmp_path)
    value.verify()
    assert value.weight_revision.startswith("sha256:")
    assert value.configuration_hash.startswith("sha256:")
    assert value.configuration_hash != replace(value, seed=18).configuration_hash
    assert (
        value.configuration_hash
        != replace(
            value,
            runtime_identity=replace(
                value.runtime_identity,
                implementation_sha256="0" * 64,
            ),
        ).configuration_hash
    )
    assert (
        value.configuration_hash
        != replace(
            value,
            runtime_identity=replace(
                value.runtime_identity,
                worker_wheel_sha256="0" * 64,
            ),
        ).configuration_hash
    )
    assert (
        value.configuration_hash
        != replace(
            value,
            runtime_lock_sha256="0" * 64,
        ).configuration_hash
    )
    with pytest.raises(ValueError, match="runtime lock digest mismatch"):
        replace(value, runtime_lock_sha256="0" * 64).verify()

    value.checkpoint_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="converter weight digest mismatch"):
        value.verify()


def test_engine_preserves_shape_and_normalizes_pcm(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    engine = OpenVoiceV2Engine(configuration(tmp_path), model=FakeModel())
    output = engine.convert([0.1, -0.1, 0.2, -0.2], 16_000)
    assert output.tolist() == pytest.approx([0.25, -0.25, 0.1, -0.1])


@pytest.mark.parametrize(
    "result",
    (
        [],
        [float("inf"), 0.0, 0.0, 0.0],
        [[0.0, 0.0], [0.0, 0.0]],
        [0.1],
    ),
)
def test_engine_rejects_invalid_or_implausible_model_output(
    tmp_path: Path, result
) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    engine = OpenVoiceV2Engine(configuration(tmp_path), model=ResultModel(result))
    with pytest.raises(RuntimeError, match="OpenVoice returned"):
        engine.convert([0.1, -0.1, 0.2, -0.2], 16_000)


def test_engine_resets_rng_for_reproducible_conversion(tmp_path: Path) -> None:
    numpy = pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    engine = OpenVoiceV2Engine(configuration(tmp_path), model=TorchRandomModel())
    first = engine.convert([0.1, -0.1, 0.2, -0.2], 16_000)
    second = engine.convert([0.1, -0.1, 0.2, -0.2], 16_000)
    assert numpy.array_equal(first, second)


def _worker_wheel() -> Path:
    configured = os.environ.get("LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH")
    if configured:
        return Path(configured).resolve(strict=True)
    repository_root = Path(__file__).resolve().parents[4]
    wheels = tuple(
        (repository_root / "artifacts/openvoice-v2/wheels").glob(
            "liveconv_worker_runtime-*.whl"
        )
    )
    assert len(wheels) == 1, "build exactly one liveconv worker wheel"
    return wheels[0].resolve(strict=True)


def _attestation_environment(
    wheel: Path, attestation: DistributionAttestation
) -> dict[str, str]:
    prefix = Path(sys.prefix).resolve(strict=True)
    return {
        "LIVECONV_OPENVOICE_V2_RUNTIME_PREFIX": str(prefix),
        "LIVECONV_OPENVOICE_V2_PYVENV_SHA256": sha256_file(prefix / "pyvenv.cfg"),
        "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH": str(wheel),
        "LIVECONV_OPENVOICE_V2_WORKER_WHEEL_SHA256": attestation.wheel_sha256,
        "LIVECONV_OPENVOICE_V2_WHEEL_RECORD_SHA256": (attestation.wheel_record_sha256),
        "LIVECONV_OPENVOICE_V2_INSTALLED_RECORD_SHA256": (
            attestation.installed_record_sha256
        ),
        "LIVECONV_OPENVOICE_V2_DISTRIBUTION_MANIFEST_SHA256": (
            attestation.distribution_manifest_sha256
        ),
        "LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256": (
            attestation.implementation_sha256
        ),
    }


def test_runtime_identity_attests_installed_wheel_prefix_and_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Path.cwd().resolve() == Path("/tmp")
    assert not os.environ.get("PYTHONPATH")
    wheel = _worker_wheel()
    wheel_sha256 = sha256_file(wheel)
    attestation = attest_worker_distribution(wheel, wheel_sha256)
    for name, value in _attestation_environment(wheel, attestation).items():
        monkeypatch.setenv(name, value)

    identity = RuntimeIdentity.from_environment()
    assert identity.prefix == Path(sys.prefix).resolve(strict=True)
    assert identity.worker_wheel_sha256 == wheel_sha256
    assert identity.distribution_manifest_sha256 == (
        attestation.distribution_manifest_sha256
    )
    assert identity.implementation_sha256 == attestation.implementation_sha256
    assert identity.distribution_version == "0.1.0"


@pytest.mark.parametrize(
    "target",
    (
        "outer_wheel",
        "wheel_record",
        "engine",
        "installed_record",
        "installed_codec",
    ),
)
def test_distribution_attestation_rejects_archive_and_install_tampering(
    tmp_path: Path, target: str
) -> None:
    wheel = _worker_wheel()
    wheel_sha256 = sha256_file(wheel)
    if target == "outer_wheel":
        tampered_wheel = tmp_path / "tampered.whl"
        shutil.copy2(wheel, tampered_wheel)
        with tampered_wheel.open("ab") as stream:
            stream.write(b"tampered")
        with pytest.raises(ValueError, match="worker wheel digest mismatch"):
            attest_worker_distribution(tampered_wheel, wheel_sha256)
        return
    with zipfile.ZipFile(wheel) as source:
        record_name = next(
            name for name in source.namelist() if name.endswith(".dist-info/RECORD")
        )
        installed_root = tmp_path / "installed"
        source.extractall(installed_root)

        if target in {"wheel_record", "engine"}:
            tampered_wheel = tmp_path / "tampered.whl"
            with zipfile.ZipFile(tampered_wheel, "w") as destination:
                for member in source.infolist():
                    encoded = source.read(member)
                    if target == "wheel_record" and member.filename == record_name:
                        encoded += b"\n"
                    if target == "engine" and member.filename.endswith(
                        "openvoice_v2/engine.py"
                    ):
                        encoded += b"# tampered\n"
                    destination.writestr(member, encoded)
            with pytest.raises(ValueError, match="wheel"):
                attest_worker_distribution(
                    tampered_wheel,
                    sha256_file(tampered_wheel),
                    installed_root=installed_root,
                )
            return

    if target == "installed_record":
        record_path = installed_root / record_name
        encoded = record_path.read_bytes()
        record_path.write_bytes(encoded.replace(b"sha256=", b"sha256=A", 1))
    else:
        codec_path = installed_root / "workers/runtime/codec.py"
        codec_path.write_bytes(codec_path.read_bytes() + b"# tampered\n")
    with pytest.raises(ValueError, match="installed"):
        attest_worker_distribution(
            wheel,
            wheel_sha256,
            installed_root=installed_root,
        )


def test_runtime_identity_rejects_prefix_and_declared_digest_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PYTHONPATH", raising=False)
    wheel = _worker_wheel()
    attestation = attest_worker_distribution(wheel, sha256_file(wheel))
    for name, value in _attestation_environment(wheel, attestation).items():
        monkeypatch.setenv(name, value)
    identity = RuntimeIdentity.from_environment()

    with pytest.raises(ValueError, match="runtime prefix"):
        replace(identity, prefix=tmp_path).verify()
    with pytest.raises(ValueError, match="pyvenv.cfg digest mismatch"):
        replace(identity, pyvenv_sha256="0" * 64).verify()
    monkeypatch.setenv("LIVECONV_OPENVOICE_V2_IMPLEMENTATION_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="implementation digest mismatch"):
        RuntimeIdentity.from_environment()


_ENGINE_TESTS = (
    test_configuration_verifies_all_immutable_inputs,
    test_engine_preserves_shape_and_normalizes_pcm,
    test_engine_rejects_invalid_or_implausible_model_output,
    test_engine_resets_rng_for_reproducible_conversion,
    test_runtime_identity_attests_installed_wheel_prefix_and_records,
    test_distribution_attestation_rejects_archive_and_install_tampering,
    test_runtime_identity_rejects_prefix_and_declared_digest_tampering,
)
_RUNTIME_DEPENDENCIES = ("librosa", "numpy", "soundfile", "torch")

if not all(importlib.util.find_spec(name) for name in _RUNTIME_DEPENDENCIES):
    for test_function in _ENGINE_TESTS:
        test_function.__test__ = False

    def test_engine_suite_executes_in_dedicated_runtime() -> None:
        repository_root = Path(__file__).resolve().parents[4]
        default_python = repository_root / "artifacts/openvoice-v2/runtime/bin/python"
        runtime_python = Path(
            os.environ.get(
                "LIVECONV_OPENVOICE_V2_TEST_PYTHON",
                str(default_python),
            )
        ).absolute()
        if not runtime_python.is_file():
            pytest.skip("create the digest-locked OpenVoice test runtime")
        wheel = next(
            (repository_root / "artifacts/openvoice-v2/wheels").glob(
                "liveconv_worker_runtime-*.whl"
            ),
            None,
        )
        if wheel is None:
            pytest.skip("build the liveconv worker wheel")
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["LIVECONV_OPENVOICE_V2_WORKER_WHEEL_PATH"] = str(wheel)
        with tempfile.TemporaryDirectory(
            prefix="liveconv-openvoice-tests-", dir="/tmp"
        ) as directory:
            copied_test = Path(directory) / "test_engine.py"
            shutil.copy2(Path(__file__), copied_test)
            result = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-m",
                    "pytest",
                    "--import-mode=importlib",
                    "-q",
                    str(copied_test),
                ],
                cwd="/tmp",
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        assert result.returncode == 0, result.stdout + result.stderr
