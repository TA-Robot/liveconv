from __future__ import annotations

from pathlib import Path

from workers.adapters.rvc_v2.backend import (
    ADAPTER_REVISION,
    AdapterRuntimeBinding,
    RvcConfiguration,
)
from workers.adapters.rvc_v2.tools.real_smoke import locked_packages, profile_for


def test_runtime_lock_parser_normalizes_exact_pins(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# generated\nExample_Package==1.2.3 \\\n    --hash=sha256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )

    assert locked_packages(lock) == {"example-package": "1.2.3"}


def test_profile_uses_installed_worker_without_repository_imports(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    hubert = source / "assets/hubert_base"
    rmvpe = source / "assets/rmvpe"
    hubert.mkdir(parents=True)
    rmvpe.mkdir(parents=True)
    for path in (
        hubert / "config.json",
        hubert / "preprocessor_config.json",
        hubert / "pytorch_model.bin",
        rmvpe / "rmvpe.pt",
    ):
        path.write_bytes(path.name.encode("ascii"))
    checkpoint = tmp_path / "target.pth"
    checkpoint.write_bytes(b"checkpoint")
    configuration = RvcConfiguration(
        source_root=source,
        checkpoint_path=checkpoint,
        source_revision="a" * 40,
        checkpoint_sha256="b" * 64,
        adapter_runtime=AdapterRuntimeBinding(
            worker_wheel_path=tmp_path / "worker.whl",
            worker_wheel_sha256="d" * 64,
            worker_wheel_record_sha256="e" * 64,
            worker_module_sha256="f" * 64,
            backend_module_sha256="1" * 64,
            network_isolation_module_sha256="2" * 64,
            requirements_lock_sha256="3" * 64,
        ),
    )

    worker_cwd = Path("/tmp")
    profile = profile_for(configuration, Path("/runtime/bin/python"), worker_cwd)

    assert profile.command == (
        "/runtime/bin/python",
        "-m",
        "workers.adapters.rvc_v2.worker",
    )
    assert profile.cwd == worker_cwd
    assert "PYTHONPATH" not in profile.environment
    assert "LIVECONV_RVC_V2_PROTECT" not in profile.environment
    assert profile.environment["LIVECONV_RVC_V2_WORKER_WHEEL_PATH"] == str(
        configuration.adapter_runtime.worker_wheel_path
    )
    assert {artifact.env_var for artifact in profile.artifacts} == {
        "LIVECONV_RVC_V2_CHECKPOINT_PATH",
        "LIVECONV_RVC_V2_WORKER_WHEEL_PATH",
    }
    assert profile.configuration_hash == configuration.configuration_hash
    assert profile.input_capacity_frames == 25
    assert profile.implementation_revision == (
        f"{ADAPTER_REVISION}+rvc.{configuration.source_revision}"
    )
