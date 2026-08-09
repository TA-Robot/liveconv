from __future__ import annotations

import base64
import hashlib
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from workers.adapters.beatrice_2 import backend


def _record_digest(content: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(
        hashlib.sha256(content).digest()
    ).decode("ascii").rstrip("=")


def runtime_binding(tmp_path: Path) -> backend.WorkerRuntimeBinding:
    distribution = "liveconv_worker_runtime-0.1.0.dist-info"
    record_name = f"{distribution}/RECORD"
    files = {
        "workers/__init__.py": b"# workers\n",
        "workers/adapters/__init__.py": b"# adapters\n",
        "workers/adapters/beatrice_2/__init__.py": b"# beatrice\n",
        "workers/adapters/beatrice_2/backend.py": b"# backend\n",
        "workers/adapters/beatrice_2/worker.py": b"# worker\n",
        "workers/runtime/__init__.py": b"# runtime\n",
        "workers/runtime/codec.py": b"# codec\n",
        "workers/adapters/beatrice_2/requirements-runtime.lock.txt": (
            b"example-runtime==1.0\n"
        ),
        f"{distribution}/METADATA": (
            b"Metadata-Version: 2.1\nName: liveconv-worker-runtime\nVersion: 0.1.0\n"
        ),
        f"{distribution}/WHEEL": b"Wheel-Version: 1.0\n",
    }
    rows = [
        f"{relative},{_record_digest(content)},{len(content)}"
        for relative, content in sorted(files.items())
    ]
    files[record_name] = ("\n".join((*rows, f"{record_name},,")) + "\n").encode("ascii")
    wheel = tmp_path / "liveconv_worker_runtime-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for relative, content in files.items():
            archive.writestr(relative, content)
    installed_root = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed_root)
    return backend.WorkerRuntimeBinding.inspect(
        wheel,
        backend.sha256_file(wheel),
        installed_root=installed_root,
        installed_packages={
            "example-runtime": "1.0",
            "liveconv-worker-runtime": "0.1.0",
        },
    )


def source_checkout(tmp_path: Path) -> tuple[Path, str]:
    source_root = tmp_path / "source"
    module = source_root / "beatrice_trainer" / "__main__.py"
    module.parent.mkdir(parents=True)
    module.write_text("# pinned source\n", encoding="ascii")
    (module.parent / "__init__.py").write_text("# package\n", encoding="ascii")
    subprocess.run(["git", "init", "-q", str(source_root)], check=True)
    subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "-c",
            "user.name=Liveconv Test",
            "-c",
            "user.email=liveconv@example.invalid",
            "commit",
            "-qm",
            "pinned source",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return source_root, revision


def configuration(tmp_path: Path) -> backend.BeatriceConfiguration:
    source_root, source_revision = source_checkout(tmp_path)
    module = source_root / "beatrice_trainer" / "__main__.py"
    phone = tmp_path / "phone.pt"
    pitch = tmp_path / "pitch.pt"
    converter = tmp_path / "converter.pt.gz"
    for path, value in ((phone, b"phone"), (pitch, b"pitch"), (converter, b"model")):
        path.write_bytes(value)
    binding = runtime_binding(tmp_path)
    return backend.BeatriceConfiguration(
        source_root=source_root,
        source_revision=source_revision,
        source_sha256=backend.sha256_file(module),
        source_tree_sha256=backend.source_tree_manifest_sha256(source_root),
        phone_checkpoint=phone,
        phone_sha256=backend.sha256_file(phone),
        pitch_checkpoint=pitch,
        pitch_sha256=backend.sha256_file(pitch),
        converter_checkpoint=converter,
        converter_sha256=backend.sha256_file(converter),
        runtime_lock_sha256=binding.requirements_lock_sha256,
        worker_runtime=binding,
    )


def test_digest_requires_lowercase_sha256() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        backend._digest("TEST_DIGEST", "A" * 64)


def test_runtime_binding_attests_full_wheel_record_codec_and_lock_inventory(
    tmp_path: Path,
) -> None:
    binding = runtime_binding(tmp_path)

    assert binding.distribution_version == "0.1.0"
    assert binding.worker_wheel_sha256 == backend.sha256_file(binding.worker_wheel_path)
    assert binding.runtime_codec_sha256 == hashlib.sha256(b"# codec\n").hexdigest()
    assert len(binding.executed_project_modules_sha256) == 64
    assert len(binding.distribution_manifest_sha256) == 64


@pytest.mark.parametrize("target", ("record", "codec", "inventory"))
def test_runtime_binding_rejects_record_codec_and_inventory_tampering(
    tmp_path: Path, target: str
) -> None:
    binding = runtime_binding(tmp_path)
    installed_root = binding.worker_wheel_path.parent / "installed"
    packages = {"example-runtime": "1.0", "liveconv-worker-runtime": "0.1.0"}
    if target == "record":
        record = installed_root / "liveconv_worker_runtime-0.1.0.dist-info/RECORD"
        record.write_bytes(record.read_bytes() + b"extra,,\n")
    elif target == "codec":
        codec = installed_root / "workers/runtime/codec.py"
        codec.write_bytes(codec.read_bytes() + b"# tampered\n")
    else:
        packages["unexpected"] = "1.0"

    with pytest.raises(ValueError, match="(attestation|installed|runtime)"):
        backend.WorkerRuntimeBinding.inspect(
            binding.worker_wheel_path,
            binding.worker_wheel_sha256,
            installed_root=installed_root,
            installed_packages=packages,
        )


def test_configuration_validates_pinned_source_and_all_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = configuration(tmp_path)
    monkeypatch.setattr(backend.WorkerRuntimeBinding, "validate", lambda self: None)

    config.validate()


def test_configuration_hash_binds_artifacts_runtime_and_execution_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = configuration(tmp_path)
    monkeypatch.setattr(backend.WorkerRuntimeBinding, "validate", lambda self: None)
    config.validate()
    baseline = config.configuration_hash

    for field, value in (
        ("source_sha256", "2" * 64),
        ("phone_sha256", "3" * 64),
        ("pitch_sha256", "4" * 64),
        ("converter_sha256", "5" * 64),
        ("runtime_lock_sha256", "6" * 64),
        ("target_speaker_id", 38),
        ("sample_rate", 24_000),
        ("batch_ms", 400),
        ("device", "cuda"),
    ):
        assert replace(config, **{field: value}).configuration_hash != baseline

    changed_runtime = replace(
        config.worker_runtime,
        executed_project_modules_sha256="7" * 64,
        installed_record_sha256="8" * 64,
        installed_distribution_inventory_sha256="9" * 64,
        runtime_codec_sha256="8" * 64,
    )
    assert (
        replace(config, worker_runtime=changed_runtime).configuration_hash != baseline
    )


@pytest.mark.parametrize("shadow_name", ("torch.py", "numpy.py"))
def test_source_checkout_rejects_untracked_import_shadow(
    tmp_path: Path, shadow_name: str
) -> None:
    source_root, revision = source_checkout(tmp_path)
    manifest = backend.source_tree_manifest_sha256(source_root)
    (source_root / shadow_name).write_text(
        "raise RuntimeError('shadow')\n", encoding="ascii"
    )

    with pytest.raises(ValueError, match="source tree manifest"):
        backend._validate_source_revision(source_root, revision, manifest)


def test_configuration_rejects_checkpoint_and_runtime_lock_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = configuration(tmp_path)
    monkeypatch.setattr(backend.WorkerRuntimeBinding, "validate", lambda self: None)
    config.phone_checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint digest"):
        config.validate()

    changed = replace(config, phone_sha256=backend.sha256_file(config.phone_checkpoint))
    with pytest.raises(ValueError, match="runtime lock digest"):
        replace(changed, runtime_lock_sha256="6" * 64).validate()


@pytest.mark.parametrize(
    ("changes", "error_text"),
    [
        ({"sample_rate": 24_000}, "48 kHz"),
        ({"batch_ms": 400}, "500 ms"),
        ({"target_speaker_id": 200}, "speaker ID"),
        ({"device": "mps"}, "device"),
    ],
)
def test_configuration_rejects_incompatible_runtime_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    error_text: str,
) -> None:
    config = configuration(tmp_path)
    monkeypatch.setattr(backend.WorkerRuntimeBinding, "validate", lambda self: None)

    with pytest.raises(ValueError, match=error_text):
        replace(config, **changes).validate()
