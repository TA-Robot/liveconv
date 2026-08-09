from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from workers.adapters.openvoice_v2.engine import (
    _IMPLEMENTATION_SOURCE_FILES,
    EngineConfiguration,
    RuntimeIdentity,
)
from workers.adapters.openvoice_v2.worker import CAPACITY_FRAMES, MINIMUM_FRAMES

ADAPTER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ADAPTER_ROOT.parents[2]
MATERIAL_PATH = ADAPTER_ROOT / "canonical-profile.json"
PACK_PATH = REPOSITORY_ROOT / "workers/packs/openvoice-v2.json"
PROVENANCE_EVIDENCE_SHA256 = (
    "sha256:bff2066e3ef311dc123f1b8d85d5f98a14610a71cc6f4ecf71d34670fc85e057"
)


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_canonical_profile_binds_the_retained_repaired_worker_evidence() -> None:
    material = _load(MATERIAL_PATH)
    pack = _load(PACK_PATH)
    retained = material["retained_repaired_worker"]
    assert isinstance(retained, dict)

    assert material["profile_id"] == "vc.openvoice-v2.technical.v1"
    assert material["pack"] == {
        "pack_id": "openvoice-v2",
        "status": "research",
        "ready_for_runtime": False,
        "promotion_status": "technical_validation",
        "promotion_evidence_sha256": PROVENANCE_EVIDENCE_SHA256,
    }
    assert pack["promotion_evidence"] == {
        "status": "technical_validation",
        "evidence_sha256": PROVENANCE_EVIDENCE_SHA256,
    }
    assert retained["provenance_evidence_sha256"] == PROVENANCE_EVIDENCE_SHA256
    assert retained["configuration_hash"] == (
        "sha256:cb28dfe641651e20b073f568c8eaf76d68caa4fbc8582c3ccee9406232be9170"
    )
    assert retained["weight_revision"] == (
        "sha256:29e76b818c6677c3c79666b83a2e9d05799258d51e05edc2337a8940a0dc9e69"
    )


def test_canonical_profile_binds_engine_artifact_digests_and_private_names() -> None:
    material = _load(MATERIAL_PATH)
    engine = material["canonical_engine_configuration"]
    environment = material["private_environment"]
    assert isinstance(engine, dict)
    assert isinstance(environment, dict)

    for name, digest in engine.items():
        if name.endswith("_sha256"):
            assert isinstance(digest, str)
            assert len(digest) == 64
            assert set(digest) <= set("0123456789abcdef")
    required_names = environment["required_names"]
    optional_names = environment["optional_names"]
    assert isinstance(required_names, list)
    assert isinstance(optional_names, list)
    assert set(required_names).isdisjoint(optional_names)
    assert all(name.startswith("LIVECONV_OPENVOICE_V2_") for name in required_names)
    assert all(name.startswith("LIVECONV_OPENVOICE_V2_") for name in optional_names)
    serialized = MATERIAL_PATH.read_text(encoding="utf-8")
    assert "/workspace/" not in serialized
    assert "secret" not in serialized.lower()


def test_canonical_profile_reproduces_the_retained_engine_identity() -> None:
    material = _load(MATERIAL_PATH)
    canonical = material["canonical_engine_configuration"]
    revisions = material["revisions"]
    trusted_worker = material["trusted_worker"]
    assert isinstance(canonical, dict)
    assert isinstance(revisions, dict)
    assert isinstance(trusted_worker, dict)

    runtime = RuntimeIdentity(
        prefix=Path("private-runtime-prefix"),
        pyvenv_sha256=str(canonical["pyvenv_sha256"]),
        worker_wheel_path=Path("private-worker-wheel"),
        worker_wheel_sha256=str(canonical["worker_wheel_sha256"]),
        wheel_record_sha256=str(canonical["wheel_record_sha256"]),
        installed_record_sha256=str(canonical["installed_record_sha256"]),
        distribution_manifest_sha256=str(canonical["distribution_manifest_sha256"]),
        implementation_sha256=str(canonical["implementation_sha256"]),
        distribution_version="0.1.0",
    )
    configuration = EngineConfiguration(
        source_root=Path("private-source-root"),
        source_tree_sha256=str(canonical["source_tree_sha256"]),
        config_path=Path("private-config"),
        config_sha256=str(canonical["config_sha256"]),
        checkpoint_path=Path("private-checkpoint"),
        checkpoint_sha256=str(canonical["checkpoint_sha256"]),
        target_reference_path=Path("private-target-reference"),
        target_reference_sha256=str(canonical["target_reference_sha256"]),
        runtime_identity=runtime,
        runtime_lock_sha256=str(canonical["runtime_lock_sha256"]),
        device=str(canonical["device"]),
        tau=float(canonical["tau"]),
        seed=int(canonical["seed"]),
    )
    assert configuration.configuration_hash == material["configuration_hash"]
    assert configuration.weight_revision == revisions["weight_revision"]
    assert (
        trusted_worker["retained_implementation_sha256"]
        == canonical["implementation_sha256"]
    )
    source_files = trusted_worker["implementation_manifest_files"]
    assert isinstance(source_files, list)
    source_manifest = hashlib.sha256()
    for relative in sorted(source_files):
        assert isinstance(relative, str)
        encoded_relative = relative.encode("utf-8")
        encoded = (REPOSITORY_ROOT / relative).read_bytes()
        source_manifest.update(len(encoded_relative).to_bytes(4, "big"))
        source_manifest.update(encoded_relative)
        source_manifest.update(len(encoded).to_bytes(8, "big"))
        source_manifest.update(encoded)
    assert trusted_worker["current_source_implementation_sha256"] == (
        source_manifest.hexdigest()
    )
    assert trusted_worker["current_source_runtime_rebuild_required"] is False
    assert trusted_worker["historical_stale_identity"] == {
        "source_tree_sha256": (
            "d75090a60578d5d368284f292c8116611998e3ed23861a12a6eabcf8d26791a6"
        ),
        "classification": "stale_historical_identity",
        "continuity_claimed": False,
    }


def test_canonical_profile_matches_the_bounded_end_buffered_contract() -> None:
    material = _load(MATERIAL_PATH)
    delivery = material["delivery"]
    limits = material["registration_limits"]
    assert isinstance(delivery, dict)
    assert isinstance(limits, dict)

    assert delivery == {
        "mode": "end_buffered",
        "streaming": False,
        "frame_ms": 20,
        "minimum_input_frames": MINIMUM_FRAMES,
        "maximum_input_frames": CAPACITY_FRAMES,
        "minimum_context_ms": MINIMUM_FRAMES * 20,
        "maximum_context_ms": CAPACITY_FRAMES * 20,
        "cancellation": "cooperative",
    }
    assert limits == {
        "technical_opt_in_required": True,
        "native_fallback_required": True,
        "non_live_only": True,
        "no_latency_claim": True,
        "no_runtime_approval": True,
    }

    retained = material["retained_repaired_worker"]
    assert isinstance(retained, dict)
    trusted_worker = material["trusted_worker"]
    assert isinstance(trusted_worker, dict)
    assert trusted_worker["entrypoint_args"] == [
        "-I",
        "-m",
        "workers.adapters.openvoice_v2",
    ]
    smoke = retained["real_worker_smoke"]
    assert isinstance(smoke, dict)
    assert smoke == {
        "status": "technical_smoke_pass",
        "worker_supervisor_smoke_count": 1,
        "frames_per_generation": 25,
        "frame_duration_ms": 20,
        "output_ordered": True,
        "output_finite": True,
        "output_changed": True,
        "output_before_end": False,
        "cancel_inflight_generation": True,
        "stale_output_after_cancel": False,
        "worker_close_exit_code": 0,
        "quality_assessment": "not_assessed",
        "latency_assessment": "not_assessed",
        "live_streaming_assessment": "not_assessed",
        "raw_audio_retained": False,
    }


def test_trusted_entrypoint_installs_socket_isolation_before_worker_import() -> None:
    module = ast.parse((ADAPTER_ROOT / "__main__.py").read_text(encoding="utf-8"))
    statements = module.body
    network_import = next(
        index
        for index, statement in enumerate(statements)
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "network_isolation"
        and any(alias.name == "deny_non_unix_sockets" for alias in statement.names)
    )
    isolation_call = next(
        index
        for index, statement in enumerate(statements)
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "deny_non_unix_sockets"
    )
    worker_import = next(
        index
        for index, statement in enumerate(statements)
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "worker"
        and any(alias.name == "main" for alias in statement.names)
    )
    assert network_import < isolation_call < worker_import
    assert "workers/adapters/openvoice_v2/__main__.py" in _IMPLEMENTATION_SOURCE_FILES
    assert "workers/adapters/openvoice_v2/network_isolation.py" in (
        _IMPLEMENTATION_SOURCE_FILES
    )

    engine_module = ast.parse((ADAPTER_ROOT / "engine.py").read_text(encoding="utf-8"))
    load_openvoice = next(
        statement
        for statement in engine_module.body
        if isinstance(statement, ast.FunctionDef)
        and statement.name == "_load_openvoice"
    )
    isolation_guard = next(
        index
        for index, statement in enumerate(load_openvoice.body)
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "require_non_unix_socket_denial"
    )
    upstream_import = next(
        index
        for index, statement in enumerate(load_openvoice.body)
        if isinstance(statement, ast.Assign)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and isinstance(statement.value.func.value, ast.Name)
        and statement.value.func.value.id == "importlib"
        and statement.value.func.attr == "import_module"
    )
    assert isolation_guard < upstream_import


def test_socket_isolation_is_idempotent_and_denies_inet_domains() -> None:
    script = "\n".join(
        (
            "import socket",
            "from workers.adapters.openvoice_v2.network_isolation import (",
            "    deny_non_unix_sockets,",
            ")",
            "deny_non_unix_sockets()",
            "deny_non_unix_sockets()",
            "for domain in (socket.AF_INET, socket.AF_INET6):",
            "    try:",
            "        socket.socket(domain, socket.SOCK_DGRAM)",
            "    except PermissionError:",
            "        continue",
            "    raise SystemExit(1)",
        )
    )
    environment = {"PYTHONPATH": str(REPOSITORY_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
