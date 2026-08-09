from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from workers.adapters.x_vc.backend import (
    ADAPTER_ROOT,
    ADAPTER_SOURCE_FILES,
    CHECKPOINT_SHA256,
    CONFIG_SHA256,
    CURRENT_SAMPLES,
    ERES_CONFIG_SHA256,
    ERES_MODEL_SHA256,
    GLM_CONFIG_SHA256,
    GLM_MODEL_SHA256,
    GLM_PREPROCESSOR_SHA256,
    INPUT_SAMPLE_RATE,
    SOURCE_REVISION,
    WINDOW_SAMPLES,
    DeterministicTestBackend,
    OfficialXvcBackend,
    XvcConfiguration,
    _verify_source,
    changed_configuration,
    load_target_authorization,
    sha256_file,
)
from workers.adapters.x_vc.real_smoke import _profile


def configuration() -> XvcConfiguration:
    return XvcConfiguration(
        source_root=Path("/pinned/source"),
        source_revision=SOURCE_REVISION,
        config_path=Path("/pinned/config.yaml"),
        config_sha256=CONFIG_SHA256,
        checkpoint_path=Path("/pinned/xvc.pt"),
        checkpoint_sha256=CHECKPOINT_SHA256,
        glm_root=Path("/workspace/liveconv/artifacts/x-vc/glm-4-voice-tokenizer"),
        glm_config_sha256=GLM_CONFIG_SHA256,
        glm_preprocessor_sha256=GLM_PREPROCESSOR_SHA256,
        glm_model_sha256=GLM_MODEL_SHA256,
        eres_root=Path("/workspace/liveconv/artifacts/x-vc/speech-eres2net"),
        eres_config_sha256=ERES_CONFIG_SHA256,
        eres_model_sha256=ERES_MODEL_SHA256,
        target_reference_path=Path("/authorized/target.wav"),
        target_reference_sha256="1" * 64,
        target_authorization_path=Path("/authorized/target-authorization.json"),
        target_authorization_sha256="2" * 64,
        adapter_source_sha256="3" * 64,
        runtime_lock_path=Path("/runtime/requirements-runtime.lock"),
        runtime_lock_sha256="4" * 64,
        worker_wheel_path=Path("/runtime/liveconv-worker.whl"),
        worker_wheel_sha256="5" * 64,
        interpreter_path=Path("/runtime/bin/python"),
        interpreter_sha256="6" * 64,
        python_implementation="CPython",
        python_version="3.12.3",
        worker_package_version="0.1.0",
    )


def authorization_document(target_sha256: str = "1" * 64) -> dict[str, object]:
    return {
        "schema_version": 1,
        "authorization_id": "test-synthetic-target-v1",
        "owner": "liveconv test project",
        "authorization_record": "test-manifest:synthetic-v1",
        "permitted_purpose": "technical voice-conversion validation only",
        "retention_policy": "retain only while adapter tests require the fixture",
        "deletion_path": "test-fixtures/target.wav",
        "classification": "project-authored-synthetic",
        "target_reference_sha256": target_sha256,
    }


def write_authorization(path: Path, target_sha256: str = "1" * 64) -> str:
    path.write_text(
        json.dumps(authorization_document(target_sha256), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha256_file(path)


def test_configuration_identity_binds_entire_runtime_and_authorization() -> None:
    original = configuration()
    variants = (
        changed_configuration(original, target_reference_sha256="a" * 64),
        changed_configuration(original, target_authorization_sha256="b" * 64),
        changed_configuration(original, adapter_source_sha256="c" * 64),
        changed_configuration(original, runtime_lock_sha256="d" * 64),
        changed_configuration(original, worker_wheel_sha256="e" * 64),
        changed_configuration(original, interpreter_sha256="f" * 64),
        changed_configuration(original, python_version="3.12.4"),
        changed_configuration(original, device="cuda:1"),
    )

    identities = {original.configuration_hash}
    identities.update(item.configuration_hash for item in variants)
    assert len(identities) == len(variants) + 1


@pytest.mark.parametrize(
    ("changes", "error_text"),
    [
        ({"checkpoint_sha256": "2" * 64}, "checkpoint digest"),
        ({"device": "cpu"}, "numbered CUDA device"),
    ],
)
def test_configuration_rejects_unapproved_identity(
    changes: dict[str, object], error_text: str
) -> None:
    invalid = changed_configuration(configuration(), **changes)

    with pytest.raises(ValueError, match=error_text):
        invalid.validate()


def test_target_authorization_requires_gov_record_and_matching_target(
    tmp_path: Path,
) -> None:
    authorization = tmp_path / "target-authorization.json"
    digest = write_authorization(authorization)

    record = load_target_authorization(authorization, digest, "1" * 64)

    assert record.owner == "liveconv test project"
    assert record.permitted_purpose == "technical voice-conversion validation only"
    with pytest.raises(ValueError, match="another target"):
        load_target_authorization(authorization, digest, "9" * 64)

    malformed = authorization_document()
    del malformed["deletion_path"]
    authorization.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected schema"):
        load_target_authorization(
            authorization,
            sha256_file(authorization),
            "1" * 64,
        )


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_source_verification_rejects_untracked_and_ignored_executable_code(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    (source / ".gitignore").write_text("ignored_module.py\n__pycache__/\n")
    (source / "model.py").write_text("revision = 1\n")
    _git(source, "add", ".gitignore", "model.py")
    _git(
        source,
        "-c",
        "user.name=liveconv test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    revision = _git(source, "rev-parse", "HEAD")
    _verify_source(source, revision)

    (source / "torch.py").write_text("raise RuntimeError('shadowed')\n")
    with pytest.raises(ValueError, match="pinned revision"):
        _verify_source(source, revision)
    (source / "torch.py").unlink()

    (source / "ignored_module.py").write_text("raise RuntimeError('ignored')\n")
    with pytest.raises(ValueError, match="pinned revision"):
        _verify_source(source, revision)


def test_adapter_digest_manifest_covers_every_shipped_python_module() -> None:
    actual = {path.name for path in ADAPTER_ROOT.glob("*.py")}
    assert set(ADAPTER_SOURCE_FILES) == actual


def test_official_backend_refuses_model_import_without_os_network_filter() -> None:
    with pytest.raises(RuntimeError, match="network isolation"):
        OfficialXvcBackend(configuration(), validate_configuration=False)


def test_real_profile_is_isolated_from_repo_and_disables_bytecode() -> None:
    profile = _profile(configuration())

    assert profile.cwd == Path("/tmp")
    assert profile.command[1:4] == ("-I", "-B", "-m")
    assert "PYTHONPATH" not in profile.environment


def test_seccomp_denies_ipv4_and_ipv6_but_allows_af_unix() -> None:
    module_path = ADAPTER_ROOT / "network_isolation.py"
    program = f"""
import runpy
namespace = runpy.run_path({str(module_path)!r})
namespace['deny_non_unix_sockets']()
import _socket
for domain in (_socket.AF_INET, _socket.AF_INET6):
    try:
        _socket.socket(domain, _socket.SOCK_DGRAM)
    except PermissionError:
        pass
    else:
        raise RuntimeError('non-Unix socket was allowed')
value = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
value.close()
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program],
        check=True,
        cwd="/tmp",
        env={"PYTHONUTF8": "1"},
        timeout=30,
    )


def test_sha256_file_reads_artifact_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"pinned-x-vc-artifact")

    assert sha256_file(artifact) == (
        "edf799f74c78537af71e20e472e64b1c57651a5e1c22a170228dfa97f4781f07"
    )


def test_deterministic_backend_returns_exact_current_window() -> None:
    backend = DeterministicTestBackend(gain=-0.5)
    window = [0.25] * WINDOW_SAMPLES

    result = backend.convert_window(window, INPUT_SAMPLE_RATE, None)

    assert len(result.samples) == CURRENT_SAMPLES
    assert result.samples == (-0.125,) * CURRENT_SAMPLES
