from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from workers.adapters.rvc_v2.backend import AdapterRuntimeBinding, RvcConfiguration

ADAPTER_ROOT = Path(__file__).resolve().parents[1]


def test_adapter_runtime_rejects_unbound_wheel(tmp_path: Path) -> None:
    wheel = tmp_path / "worker.whl"
    wheel.write_bytes(b"not-the-declared-wheel")

    with pytest.raises(ValueError, match="wheel SHA-256"):
        AdapterRuntimeBinding.inspect(wheel, "0" * 64)


def configuration(tmp_path: Path) -> RvcConfiguration:
    source = tmp_path / "source"
    hubert = source / "assets/hubert_base"
    rmvpe = source / "assets/rmvpe"
    hubert.mkdir(parents=True)
    rmvpe.mkdir(parents=True)
    for path, value in (
        (hubert / "config.json", b"config"),
        (hubert / "preprocessor_config.json", b"preprocessor"),
        (hubert / "pytorch_model.bin", b"hubert"),
        (rmvpe / "rmvpe.pt", b"rmvpe"),
    ):
        path.write_bytes(value)
    checkpoint = tmp_path / "target.pth"
    checkpoint.write_bytes(b"checkpoint")
    index = tmp_path / "target.index"
    index.write_bytes(b"index")
    return RvcConfiguration(
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
        index_path=index,
        index_sha256="c" * 64,
        index_rate=0.75,
    )


def test_configuration_identity_binds_settings_and_materials(tmp_path: Path) -> None:
    value = configuration(tmp_path)
    material = value.identity_material()
    assert set(material) == {
        "worker_module",
        "adapter_revision",
        "source_revision",
        "artifacts",
        "settings",
    }
    assert set(material["artifacts"]) == {
        "checkpoint_sha256",
        "index_sha256",
        "hubert_config_sha256",
        "hubert_preprocessor_sha256",
        "hubert_weights_sha256",
        "rmvpe_sha256",
        "worker_wheel_sha256",
        "worker_wheel_record_sha256",
        "worker_module_sha256",
        "backend_module_sha256",
        "network_isolation_module_sha256",
        "requirements_lock_sha256",
    }
    assert set(material["settings"]) == {
        "speaker_id",
        "pitch_shift",
        "f0_method",
        "index_rate",
        "rms_mix_rate",
        "sample_rate",
        "block_ms",
        "crossfade_ms",
        "context_ms",
        "frame_ms",
        "inference_batch_frames",
        "queue_capacity_frames",
        "resident_capacity_frames",
        "formant_shift",
        "threshold_dbfs",
    }
    assert value.configuration_hash.startswith("sha256:")
    assert replace(value, index_rate=0.5).configuration_hash != value.configuration_hash
    changed_runtime = replace(
        value.adapter_runtime,
        worker_module_sha256="3" * 64,
    )
    assert (
        replace(value, adapter_runtime=changed_runtime).configuration_hash
        != value.configuration_hash
    )

    hubert = value.source_root / "assets/hubert_base/pytorch_model.bin"
    hubert.write_bytes(b"changed-hubert")
    assert (
        value.configuration_hash != configuration(tmp_path / "other").configuration_hash
    )


def test_unsupported_protect_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVECONV_RVC_V2_PROTECT", "0.33")
    with pytest.raises(ValueError, match="does not support"):
        RvcConfiguration.from_environment()


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
