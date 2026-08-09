from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import liveconv_exp004_rvc_gateway_smoke.config as config_module
from liveconv_exp004_rvc_gateway_smoke.config import RunConfiguration
from liveconv_exp004_rvc_gateway_smoke.errors import (
    ConfigurationError,
    RouteValidationError,
)
from liveconv_exp004_rvc_gateway_smoke.launcher import DisposableGateway
from liveconv_exp004_rvc_gateway_smoke.trace import TraceRecorder

from .profile_fixture import PROFILE_ID, write_retained_rvc_profile

ROOT = Path(__file__).resolve().parents[1]


def test_persisted_environment_requires_exact_clean_commit_outside_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = write_retained_rvc_profile(
        tmp_path / "retained-rvc-profile.json", first_output_ms=240_000
    )
    verified: list[str] = []
    monkeypatch.setattr(
        config_module,
        "_verify_clean_commit",
        lambda commit: verified.append(commit) or ROOT.parent.parent,
    )
    environment = {
        "LIVECONV_EXP004_GATEWAY_URL": "http://127.0.0.1:8766",
        "LIVECONV_EXP004_PROFILE_ID": PROFILE_ID,
        "LIVECONV_EXP004_TRACE": str(tmp_path / "trace.json"),
        "LIVECONV_EXP004_GIT_COMMIT": "a" * 40,
        "LIVECONV_API_TOKEN": "not-visible-in-repr",
        "LIVECONV_EXP004_PROFILE_CONFIG": str(profile.path),
    }
    config = RunConfiguration.from_environment(environment)

    assert verified == ["a" * 40]
    assert config.auto_launch is False
    assert config.generation_ready_timeout_seconds == 240.0
    assert "not-visible" not in repr(config)
    assert str(profile.path) not in repr(config)

    with pytest.raises(ConfigurationError, match="GIT_COMMIT"):
        RunConfiguration.from_environment(
            {
                key: value
                for key, value in environment.items()
                if key != "LIVECONV_EXP004_GIT_COMMIT"
            }
        )


def test_auto_launch_requires_safe_profile_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config_module, "_verify_clean_commit", lambda _: tmp_path)
    base = {
        "LIVECONV_EXP004_TRACE": str(tmp_path.parent / "trace.json"),
        "LIVECONV_EXP004_GIT_COMMIT": "a" * 40,
    }
    with pytest.raises(ConfigurationError, match="PROFILE_CONFIG"):
        RunConfiguration.from_environment(base)

    profile = write_retained_rvc_profile(tmp_path / "retained-rvc-profile.json")
    automatic = RunConfiguration.from_environment(
        {**base, "LIVECONV_EXP004_PROFILE_CONFIG": str(profile.path)}
    )
    assert automatic.auto_launch is True
    assert automatic.generation_ready_timeout_seconds == 180.0

    extra_profile = write_retained_rvc_profile(
        tmp_path / "multi-rvc-profile.json", extra_profile=True
    )
    with pytest.raises(ConfigurationError, match="exactly the selected"):
        RunConfiguration.from_environment(
            {**base, "LIVECONV_EXP004_PROFILE_CONFIG": str(extra_profile.path)}
        )

    sensitive = tmp_path / "token-profile.json"
    sensitive.write_text("not a secret")
    with pytest.raises(ConfigurationError, match="filename"):
        RunConfiguration.from_environment(
            {**base, "LIVECONV_EXP004_PROFILE_CONFIG": str(sensitive)}
        )


def test_configuration_rejects_non_rvc_profile_and_external_token_omission(
    tmp_path: Path,
) -> None:
    profile = write_retained_rvc_profile(tmp_path / "retained-rvc-profile.json")
    with pytest.raises(ConfigurationError, match="retained RVC"):
        RunConfiguration(
            gateway_url="http://127.0.0.1:8766",
            profile_id="test.gain.v1",
            origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            trace_path=tmp_path / "trace.json",
            git_commit="a" * 40,
            api_token="x",
            profile_config=profile.path,
            expected_profile_hash=profile.profile_hash,
            expected_configuration_hash=profile.configuration_hash,
        )


def test_auto_launch_pins_the_base_ingress_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = write_retained_rvc_profile(tmp_path / "retained-rvc-profile.json")
    configuration = RunConfiguration(
        gateway_url=None,
        profile_id=PROFILE_ID,
        origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        trace_path=tmp_path / "trace.json",
        git_commit="a" * 40,
        api_token="",
        profile_config=profile.path,
        expected_profile_hash=profile.profile_hash,
        expected_configuration_hash=profile.configuration_hash,
    )
    monkeypatch.setenv("LIVECONV_INGRESS_BUDGET_MS", "9_999")
    assert (
        DisposableGateway(configuration)._launch_environment()[
            "LIVECONV_INGRESS_BUDGET_MS"
        ]
        == "500"
    )
    with pytest.raises(ConfigurationError, match="loopback"):
        RunConfiguration(
            gateway_url="https://gateway.example.test",
            profile_id="vc.rvc.synthetic-ja.v1",
            origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            trace_path=tmp_path / "trace.json",
            git_commit="a" * 40,
            api_token="x",
            profile_config=profile.path,
            expected_profile_hash=profile.profile_hash,
            expected_configuration_hash=profile.configuration_hash,
        )
    configuration = RunConfiguration(
        gateway_url="https://127.0.0.1:8766",
        profile_id="vc.rvc.synthetic-ja.v1",
        origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        trace_path=tmp_path / "trace.json",
        git_commit="a" * 40,
        api_token="x",
        profile_config=profile.path,
        expected_profile_hash=profile.profile_hash,
        expected_configuration_hash=profile.configuration_hash,
    )
    assert configuration.generation_ready_timeout_seconds == 180.0
    with pytest.raises(ConfigurationError, match="API_TOKEN"):
        RunConfiguration(
            gateway_url="http://127.0.0.1:8766",
            profile_id="vc.rvc.synthetic-ja.v1",
            origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            trace_path=tmp_path / "trace.json",
            git_commit="a" * 40,
            api_token="",
            profile_config=profile.path,
            expected_profile_hash=profile.profile_hash,
            expected_configuration_hash=profile.configuration_hash,
        )


def test_trace_rejects_sensitive_pcm_and_path_keys() -> None:
    trace = TraceRecorder("a" * 40, "vc.rvc.synthetic-ja.v1")
    with pytest.raises(RouteValidationError, match="forbidden"):
        trace.add_result(
            "bad",
            passed=False,
            evidence={"nested": {"raw_pcm": "not-permitted"}},
        )
    with pytest.raises(RouteValidationError, match="forbidden"):
        trace.add_result(
            "bad_path",
            passed=False,
            evidence={"artifact_path": "/private/not-permitted"},
        )
    with pytest.raises(RouteValidationError, match="non-finite"):
        trace.add_result("bad_number", passed=False, evidence={"metric": float("nan")})


def test_trace_schema_is_metadata_only_and_claims_remain_false() -> None:
    trace = TraceRecorder("a" * 40, "vc.rvc.synthetic-ja.v1")
    trace.set_profile_identity(
        profile_hash=f"sha256:{'a' * 64}",
        configuration_hash=f"sha256:{'b' * 64}",
    )
    trace.add_result("catalog_session_attach", passed=True, evidence={"matched": True})
    trace.finish(True)
    document = trace.document()
    schema = json.loads(
        (ROOT / "src/liveconv_exp004_rvc_gateway_smoke/trace.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(document)
    encoded = trace.to_json()
    assert "raw_pcm" not in encoded
    assert all(value is False for value in document["claims"].values())


def test_trace_write_requires_clean_commit_verification(tmp_path: Path) -> None:
    trace = TraceRecorder("a" * 40, "vc.rvc.synthetic-ja.v1")
    with pytest.raises(RouteValidationError, match="clean Git commit"):
        trace.write(tmp_path / "trace.json")
