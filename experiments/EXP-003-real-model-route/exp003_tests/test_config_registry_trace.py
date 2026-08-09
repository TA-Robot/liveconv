from __future__ import annotations

import json
from pathlib import Path

import pytest
from liveconv_audio.profiles import ModelProfile

import liveconv_real_model_route.config as config_module
from liveconv_real_model_route.config import RunConfiguration
from liveconv_real_model_route.errors import ConfigurationError, RouteValidationError
from liveconv_real_model_route.registry import ProfileRegistry
from liveconv_real_model_route.trace import SteppingClock, TraceRecorder

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "exp003_tests" / "fixtures" / "profile-registry.json"


def test_environment_is_direct_only_and_secret_fields_are_repr_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified: list[str] = []
    monkeypatch.setattr(config_module, "_verify_git_state", verified.append)
    config = RunConfiguration.from_environment(
        {
            "LIVECONV_EXP003_GATEWAY_URL": "https://gateway.example.test",
            "LIVECONV_EXP003_ORIGIN": (
                "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
            "LIVECONV_EXP003_PROFILE_REGISTRY": str(REGISTRY_PATH),
            "LIVECONV_EXP003_PROFILE_IDS": "vc.fake.alpha.v1,vc.fake.beta.v1",
            "LIVECONV_EXP003_TRACE": "trace.json",
            "LIVECONV_API_TOKEN": "not-visible-in-repr",
            "LIVECONV_EXP003_VOICE_ID": "not-visible-either",
            "LIVECONV_EXP003_BATCH_FRAMES": "3",
            "LIVECONV_EXP003_PARTIAL_FRAMES": "2",
            "LIVECONV_EXP003_CANCEL_FRAMES": "1",
            "LIVECONV_EXP003_GIT_COMMIT": "a" * 40,
            "LIVECONV_EXP003_WORKTREE_CLEAN": "true",
        }
    )
    rendered = repr(config)
    assert "not-visible" not in rendered
    assert config.profile_ids == ("vc.fake.alpha.v1", "vc.fake.beta.v1")
    assert config.git_commit == "a" * 40
    assert config.worktree_clean is True
    assert verified == ["a" * 40]


def test_persisted_environment_requires_commit_and_clean_worktree() -> None:
    base = {
        "LIVECONV_EXP003_GATEWAY_URL": "https://gateway.example.test",
        "LIVECONV_EXP003_ORIGIN": (
            "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "LIVECONV_EXP003_PROFILE_REGISTRY": str(REGISTRY_PATH),
        "LIVECONV_EXP003_PROFILE_IDS": "vc.fake.alpha.v1,vc.fake.beta.v1",
        "LIVECONV_API_TOKEN": "redacted-test-value",
    }
    with pytest.raises(ConfigurationError, match="WORKTREE_CLEAN"):
        RunConfiguration.from_environment(base)
    with pytest.raises(ConfigurationError, match="clean worktree"):
        RunConfiguration.from_environment(
            {**base, "LIVECONV_EXP003_WORKTREE_CLEAN": "false"}
        )
    with pytest.raises(ConfigurationError, match="GIT_COMMIT"):
        RunConfiguration.from_environment(
            {**base, "LIVECONV_EXP003_WORKTREE_CLEAN": "true"}
        )
    with pytest.raises(ConfigurationError, match="TRACE"):
        RunConfiguration.from_environment(
            {
                **base,
                "LIVECONV_EXP003_WORKTREE_CLEAN": "true",
                "LIVECONV_EXP003_GIT_COMMIT": "a" * 40,
            }
        )


def test_non_loopback_plain_http_and_single_profile_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="loopback"):
        RunConfiguration(
            gateway_url="http://gateway.example.test",
            origin="chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            registry_path=REGISTRY_PATH,
            profile_ids=("vc.fake.alpha.v1", "vc.fake.beta.v1"),
            trace_path=Path("trace.json"),
            api_token="x",
            batch_frames=3,
            partial_frames=1,
            cancel_frames=1,
        )
    with pytest.raises(ConfigurationError, match="at least two"):
        RunConfiguration.from_environment(
            {
                "LIVECONV_EXP003_GATEWAY_URL": "https://gateway.example.test",
                "LIVECONV_EXP003_ORIGIN": (
                    "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ),
                "LIVECONV_EXP003_PROFILE_REGISTRY": str(REGISTRY_PATH),
                "LIVECONV_EXP003_PROFILE_IDS": "vc.fake.alpha.v1",
                "LIVECONV_API_TOKEN": "x",
                "LIVECONV_EXP003_GIT_COMMIT": "a" * 40,
                "LIVECONV_EXP003_WORKTREE_CLEAN": "true",
                "LIVECONV_EXP003_TRACE": "trace.json",
            }
        )


def test_registry_metadata_excludes_private_runtime_material() -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        ("vc.fake.alpha.v1", "vc.fake.beta.v1"), voice_id_present=False
    )
    encoded = json.dumps([profile.safe_metadata() for profile in profiles])
    assert "worker_endpoint" not in encoded
    assert "/private/" not in encoded
    assert "fixture_mode" not in encoded
    assert "license_record" not in encoded
    assert registry.document_hash.startswith("sha256:")


def test_trace_rejects_sensitive_keys_and_nonfinite_values() -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        ("vc.fake.alpha.v1", "vc.fake.beta.v1"), voice_id_present=False
    )
    trace = TraceRecorder(profiles, registry.document_hash, clock=SteppingClock())
    with pytest.raises(RouteValidationError, match="sensitive"):
        trace.record("bad", "bad", {"nested": {"api_token": "secret"}})
    with pytest.raises(RouteValidationError, match="non-finite"):
        trace.record("bad", "bad", {"metric": float("nan")})


def test_registry_rejects_duplicate_fields(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text('{"schema_version":1,"schema_version":1,"profiles":[]}')
    with pytest.raises(ConfigurationError, match="duplicate"):
        ProfileRegistry.load(path)


def test_registry_rejects_overflowed_json_float(tmp_path: Path) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    encoded = json.dumps(document).replace(
        '"max_vram_mb": 1024', '"max_vram_mb": 1e999'
    )
    path = tmp_path / "registry.json"
    path.write_text(encoded)
    with pytest.raises(ConfigurationError, match="non-finite"):
        ProfileRegistry.load(path)


def test_registry_rejects_private_runtime_configuration_key(tmp_path: Path) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    document["profiles"][0]["runtime"]["configuration"]["api_token"] = "bad"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ConfigurationError, match="private configuration key"):
        ProfileRegistry.load(path)


@pytest.mark.parametrize(
    "worker_module",
    (
        "workers.adapters.beatrice_2.worker",
        "workers.adapters.x_vc.worker",
        "workers.adapters.openvoice_v2",
    ),
)
def test_registry_worker_module_matches_service_profile_hash(
    tmp_path: Path, worker_module: str
) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    runtime = document["profiles"][0]["runtime"]
    runtime["worker_module"] = worker_module
    runtime["configuration"].pop("worker_module")
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    experiment_profile = ProfileRegistry.load(path).require_route_profiles(
        ("vc.fake.alpha.v1",), voice_id_present=False
    )[0]
    service_profile = ModelProfile.model_validate(document["profiles"][0])

    assert experiment_profile.profile_hash == service_profile.profile_hash
    assert experiment_profile.configuration_hash == service_profile.configuration_hash


def test_registry_promotion_matches_service_profile_hash(tmp_path: Path) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    profile = document["profiles"][0]
    profile["promotion"] = {
        "status": "technical_validation",
        "pack_id": "example-pack",
        "pack_sha256": f"sha256:{'1' * 64}",
        "evidence_sha256": f"sha256:{'2' * 64}",
        "endpoint_sha256": f"sha256:{'3' * 64}",
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    experiment_profile = ProfileRegistry.load(path).require_route_profiles(
        ("vc.fake.alpha.v1",), voice_id_present=False
    )[0]
    service_profile = ModelProfile.model_validate(profile)

    assert experiment_profile.profile_hash == service_profile.profile_hash
    assert experiment_profile.configuration_hash == service_profile.configuration_hash


def test_registry_rejects_invalid_promotion_digest(tmp_path: Path) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    document["profiles"][0]["promotion"] = {
        "status": "technical_validation",
        "pack_id": "example-pack",
        "pack_sha256": "sha256:not-a-digest",
        "evidence_sha256": f"sha256:{'2' * 64}",
        "endpoint_sha256": f"sha256:{'3' * 64}",
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    with pytest.raises(ConfigurationError, match="promotion pack_sha256 is invalid"):
        ProfileRegistry.load(path)


@pytest.mark.parametrize("worker_module", (pytest.param(None), pytest.param("absent")))
def test_registry_legacy_worker_module_forms_match_service_profile_hash(
    tmp_path: Path, worker_module: str | None
) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    runtime = document["profiles"][0]["runtime"]
    if worker_module == "absent":
        runtime.pop("worker_module", None)
    else:
        runtime["worker_module"] = worker_module
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    experiment_profile = ProfileRegistry.load(path).require_route_profiles(
        ("vc.fake.alpha.v1",), voice_id_present=False
    )[0]
    service_profile = ModelProfile.model_validate(document["profiles"][0])

    assert experiment_profile.profile_hash == service_profile.profile_hash
    assert experiment_profile.configuration_hash == service_profile.configuration_hash


@pytest.mark.parametrize(
    "worker_module",
    ("", 1, "/private/worker", "workers.adapters.x-vc.worker"),
)
def test_registry_rejects_invalid_runtime_worker_module(
    tmp_path: Path, worker_module: object
) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    document["profiles"][0]["runtime"]["worker_module"] = worker_module
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    with pytest.raises(ConfigurationError, match="runtime.worker_module is invalid"):
        ProfileRegistry.load(path)


def test_registry_rejects_extra_runtime_worker_module_fields(tmp_path: Path) -> None:
    document = json.loads(REGISTRY_PATH.read_text())
    document["profiles"][0]["runtime"]["unreviewed_module"] = "unexpected"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document))

    with pytest.raises(ConfigurationError, match="runtime shape is invalid"):
        ProfileRegistry.load(path)


def test_trace_cannot_overwrite_registry() -> None:
    with pytest.raises(ConfigurationError, match="differ from registry"):
        RunConfiguration(
            gateway_url="https://gateway.example.test",
            origin="chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            registry_path=REGISTRY_PATH,
            profile_ids=("vc.fake.alpha.v1", "vc.fake.beta.v1"),
            trace_path=REGISTRY_PATH,
            api_token="x",
            batch_frames=3,
            partial_frames=1,
            cancel_frames=1,
        )
