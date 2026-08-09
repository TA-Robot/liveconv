from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from collections.abc import Mapping
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "build-ms2-profile-registry.py"
REPOSITORY_ROOT = SCRIPT.parents[1]


def load_builder() -> object:
    spec = importlib.util.spec_from_file_location("build_ms2_profile_registry", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def endpoint_map(tmp_path: Path) -> dict[str, Path]:
    endpoints: dict[str, Path] = {}
    for model_id in ("rvc-v2", "beatrice-2", "x-vc", "openvoice-v2"):
        endpoint = tmp_path / f"{model_id}-python"
        endpoint.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        endpoint.chmod(0o700)
        endpoints[model_id] = endpoint
    return endpoints


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def profiles_by_id(document: Mapping[str, object]) -> dict[str, dict[str, object]]:
    profiles = document["profiles"]
    assert isinstance(profiles, list)
    return {
        str(profile["profile_id"]): profile
        for profile in profiles
        if isinstance(profile, dict)
    }


def material(path: str) -> dict[str, object]:
    value = json.loads((REPOSITORY_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_builds_the_frozen_roster_with_current_digests_and_material_configuration(
    tmp_path: Path,
) -> None:
    builder = load_builder()
    endpoints = endpoint_map(tmp_path)

    document = builder.build_registry(endpoints)

    profiles = document["profiles"]
    assert isinstance(profiles, list)
    assert [profile["profile_id"] for profile in profiles] == [
        "vc.rvc.synthetic-ja.v1",
        "vc.beatrice.synthetic-ja.v1",
        "vc.x-vc.synthetic-ja.v1",
        "vc.openvoice-v2.synthetic-ja.v1",
    ]
    by_id = profiles_by_id(document)
    expected_configurations = {
        "vc.rvc.synthetic-ja.v1": material(
            "workers/adapters/rvc_v2/ms2-profile-material.json"
        )["canonical_configuration"],
        "vc.beatrice.synthetic-ja.v1": material(
            "workers/adapters/beatrice_2/profile-material.json"
        )["worker"]["configuration_payload"],
        "vc.x-vc.synthetic-ja.v1": material(
            "workers/adapters/x_vc/technical-profile.json"
        )["runtime"]["configuration"],
        "vc.openvoice-v2.synthetic-ja.v1": material(
            "workers/adapters/openvoice_v2/canonical-profile.json"
        )["canonical_engine_configuration"],
    }

    for model_id, profile_id in builder.ROSTER_PROFILE_IDS.items():
        profile = by_id[profile_id]
        runtime = profile["runtime"]
        promotion = profile["promotion"]
        assert runtime["worker_endpoint"] == str(endpoints[model_id])
        assert runtime["configuration"] == expected_configurations[profile_id]
        assert promotion["pack_id"] == model_id
        assert promotion["pack_sha256"] == sha256(
            REPOSITORY_ROOT / "workers" / "packs" / f"{model_id}.json"
        )
        assert promotion["endpoint_sha256"] == sha256(endpoints[model_id])
        assert promotion["status"] == "technical_validation"

    rvc_runtime = by_id["vc.rvc.synthetic-ja.v1"]["runtime"]
    assert rvc_runtime["configuration"]["worker_module"] == (
        "workers.adapters.rvc_v2.worker"
    )
    assert "worker_module" not in rvc_runtime
    assert by_id["vc.beatrice.synthetic-ja.v1"]["runtime"]["worker_module"] == (
        "workers.adapters.beatrice_2.worker"
    )
    assert by_id["vc.x-vc.synthetic-ja.v1"]["runtime"]["worker_module"] == (
        "workers.adapters.x_vc.worker"
    )
    openvoice = by_id["vc.openvoice-v2.synthetic-ja.v1"]
    assert openvoice["runtime"]["worker_module"] == "workers.adapters.openvoice_v2"
    assert openvoice["streaming"] is False
    assert openvoice["cancellation"] == "cooperative"
    assert openvoice["voice_requirement"] == "pretrained_voice"


def test_stages_validation_before_atomic_replacement(tmp_path: Path) -> None:
    builder = load_builder()
    document = builder.build_registry(endpoint_map(tmp_path))
    destination = tmp_path / "registry.json"
    destination.write_text('{"previous": true}\n', encoding="ascii")
    observed: dict[str, object] = {}

    def validate(candidate: Path) -> None:
        observed["candidate"] = candidate
        observed["document"] = json.loads(candidate.read_text(encoding="utf-8"))

    builder.write_registry_atomically(destination, document, validator=validate)

    candidate = observed["candidate"]
    assert isinstance(candidate, Path)
    assert candidate.parent == destination.parent
    assert candidate != destination
    assert json.loads(destination.read_text(encoding="utf-8")) == observed["document"]


def test_gateway_loader_receives_technical_opt_in_and_local_packs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = load_builder()
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        '{"schema_version": 1, "profiles": []}\n', encoding="ascii"
    )
    captured: dict[str, object] = {}

    class ProfileRegistry:
        @staticmethod
        def load(path: Path, **kwargs: object) -> None:
            captured["path"] = path
            captured.update(kwargs)

    package = types.ModuleType("liveconv_audio")
    profiles = types.ModuleType("liveconv_audio.profiles")
    profiles.ProfileRegistry = ProfileRegistry
    monkeypatch.setitem(sys.modules, "liveconv_audio", package)
    monkeypatch.setitem(sys.modules, "liveconv_audio.profiles", profiles)

    builder.validate_with_profile_registry(
        registry_path, repository_root=REPOSITORY_ROOT
    )

    assert captured == {
        "path": registry_path,
        "allow_technical_profiles": True,
        "model_pack_directory": REPOSITORY_ROOT / "workers" / "packs",
    }


def test_rejects_relative_endpoint_and_secret_like_output(tmp_path: Path) -> None:
    builder = load_builder()
    endpoints = endpoint_map(tmp_path)
    endpoints["rvc-v2"] = Path("relative-python")

    with pytest.raises(builder.RegistryBuildError, match="absolute path"):
        builder.build_registry(endpoints)

    document = builder.build_registry(endpoint_map(tmp_path))
    profiles = document["profiles"]
    assert isinstance(profiles, list)
    runtime = profiles[1]["runtime"]
    assert isinstance(runtime, dict)
    configuration = runtime["configuration"]
    assert isinstance(configuration, dict)
    configuration["access_token"] = "must-not-serialize"

    with pytest.raises(builder.RegistryBuildError, match="secret-like key"):
        builder.write_registry_atomically(tmp_path / "registry.json", document)


def test_validation_failure_preserves_existing_registry(tmp_path: Path) -> None:
    builder = load_builder()
    destination = tmp_path / "registry.json"
    destination.write_text('{"previous": true}\n', encoding="ascii")

    def reject(_candidate: Path) -> None:
        raise builder.RegistryBuildError("synthetic registry rejection")

    with pytest.raises(
        builder.RegistryBuildError, match="synthetic registry rejection"
    ):
        builder.write_registry_atomically(
            destination,
            builder.build_registry(endpoint_map(tmp_path)),
            validator=reject,
        )

    assert destination.read_text(encoding="ascii") == '{"previous": true}\n'
