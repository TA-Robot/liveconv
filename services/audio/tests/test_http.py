from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from liveconv_audio import Settings, create_app
from liveconv_audio.profiles import ProfileRegistry

from .conftest import ALLOWED_ORIGIN, API_TOKEN, AUTH_HEADERS


def session_request() -> dict[str, object]:
    return {
        "protocol_version": 1,
        "profile_id": "test.passthrough.v1",
        "input": {
            "sample_rate": 48_000,
            "channels": 1,
            "sample_format": "f32le",
            "frame_ms": 20,
        },
        "voice_id": None,
    }


def test_liveness_is_public_and_every_other_api_requires_bearer(
    client: TestClient,
) -> None:
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").status_code == 401
    assert client.get("/v1/models").status_code == 401
    assert client.post("/v1/sessions", json={}).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404

    response = client.get(
        "/health/ready",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert client.get("/health/ready", headers=AUTH_HEADERS).json() == {
        "status": "ready"
    }


def test_model_catalog_exposes_only_ready_builtin_capabilities(
    client: TestClient,
    settings: Settings,
) -> None:
    response = client.get("/v1/models", headers=AUTH_HEADERS)
    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert {profile["profile_id"] for profile in profiles} == {
        "test.passthrough.v1",
        "test.gain.v1",
    }
    for profile in profiles:
        assert profile["readiness"] == "ready"
        assert profile["profile_hash"].startswith("sha256:")
        assert profile["configuration_hash"].startswith("sha256:")
        assert "runtime" not in profile
        assert "worker_endpoint" not in profile
        assert "license_record" not in profile

    document = json.loads(settings.profile_config.read_text())
    source = next(
        profile
        for profile in document["profiles"]
        if profile["profile_id"] == "test.gain.v1"
    )
    source["runtime"].pop("worker_endpoint", None)
    canonical_profile = json.dumps(
        source,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    canonical_configuration = json.dumps(
        source["runtime"]["configuration"],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    public_gain = next(
        profile for profile in profiles if profile["profile_id"] == "test.gain.v1"
    )
    assert public_gain["profile_hash"] == (
        f"sha256:{hashlib.sha256(canonical_profile).hexdigest()}"
    )
    assert public_gain["configuration_hash"] == (
        f"sha256:{hashlib.sha256(canonical_configuration).hexdigest()}"
    )


def test_session_stores_only_ticket_digest_and_public_state_has_no_ticket(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    ticket = created["ticket"]
    assert isinstance(ticket, str)
    assert created["websocket_path"] == "/v1/ws"
    assert created["limits"] == {
        "ingress_budget_ms": 500,
        "max_ingress_frames": 25,
    }

    session = client.app.state.gateway.store.get(created["session_id"])
    assert session is not None
    assert session.ticket_digest == hashlib.sha256(ticket.encode()).digest()
    assert ticket.encode() != session.ticket_digest
    assert not hasattr(session, "ticket")

    response = client.get(
        f"/v1/sessions/{created['session_id']}",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    public = response.json()
    assert "ticket" not in public
    assert "ticket_digest" not in public
    assert public["profile_hash"] == created["profile_hash"]
    assert public["configuration_hash"] == created["configuration_hash"]


def test_delete_invalidates_session(client: TestClient, create_session) -> None:
    created = create_session()
    path = f"/v1/sessions/{created['session_id']}"
    assert client.delete(path, headers=AUTH_HEADERS).status_code == 204
    assert client.get(path, headers=AUTH_HEADERS).status_code == 404
    assert client.delete(path, headers=AUTH_HEADERS).status_code == 404


def test_session_creation_rejects_unknown_profile_and_audio_shape(
    client: TestClient,
) -> None:
    base = {
        "protocol_version": 1,
        "profile_id": "test.unknown.v1",
        "input": {
            "sample_rate": 48_000,
            "channels": 1,
            "sample_format": "f32le",
            "frame_ms": 20,
        },
        "voice_id": None,
    }
    assert (
        client.post("/v1/sessions", headers=AUTH_HEADERS, json=base).status_code == 404
    )

    base["profile_id"] = "test.passthrough.v1"
    base["input"]["sample_rate"] = 24_000
    assert (
        client.post("/v1/sessions", headers=AUTH_HEADERS, json=base).status_code == 422
    )


def test_builtin_profile_rejects_voice_id(client: TestClient) -> None:
    response = client.post(
        "/v1/sessions",
        headers=AUTH_HEADERS,
        json={
            "protocol_version": 1,
            "profile_id": "test.gain.v1",
            "input": {
                "sample_rate": 48_000,
                "channels": 1,
                "sample_format": "f32le",
                "frame_ms": 20,
            },
            "voice_id": "not-used-by-test-profile",
        },
    )
    assert response.status_code == 422


def test_max_sessions_is_a_hard_bound(settings: Settings) -> None:
    bounded = replace(settings, max_sessions=1)
    with TestClient(create_app(bounded)) as client:
        first = client.post(
            "/v1/sessions", headers=AUTH_HEADERS, json=session_request()
        )
        assert first.status_code == 201
        assert (
            client.post(
                "/v1/sessions", headers=AUTH_HEADERS, json=session_request()
            ).status_code
            == 503
        )
        assert (
            client.delete(
                f"/v1/sessions/{first.json()['session_id']}",
                headers=AUTH_HEADERS,
            ).status_code
            == 204
        )
        assert (
            client.post(
                "/v1/sessions", headers=AUTH_HEADERS, json=session_request()
            ).status_code
            == 201
        )


@pytest.mark.parametrize(
    ("api_token", "origins"),
    [
        ("short-token", frozenset({ALLOWED_ORIGIN})),
        (
            "日本語トークン壱弐参四伍六七八九0123456789abcdef",
            frozenset({ALLOWED_ORIGIN}),
        ),
        (API_TOKEN, frozenset({"chrome-extension://*"})),
    ],
)
def test_unsafe_credentials_or_origins_block_readiness_and_creation(
    settings: Settings,
    api_token: str,
    origins: frozenset[str],
) -> None:
    unsafe = replace(settings, api_token=api_token, allowed_origins=origins)
    headers = AUTH_HEADERS
    with TestClient(create_app(unsafe)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready", headers=headers).status_code == 503
        assert (
            client.post(
                "/v1/sessions", headers=headers, json=session_request()
            ).status_code
            == 503
        )


@pytest.mark.parametrize(
    "name",
    [
        "LIVECONV_TICKET_TTL_SECONDS",
        "LIVECONV_ATTACH_TIMEOUT_SECONDS",
        "LIVECONV_SESSION_LIFETIME_SECONDS",
        "LIVECONV_SEND_TIMEOUT_SECONDS",
    ],
)
@pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
def test_nonfinite_duration_settings_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    raw: str,
) -> None:
    monkeypatch.setenv("LIVECONV_API_TOKEN", API_TOKEN)
    monkeypatch.setenv("LIVECONV_ALLOWED_ORIGINS", ALLOWED_ORIGIN)
    monkeypatch.setenv(name, raw)
    with pytest.raises(ValueError, match="must be greater than zero"):
        Settings.from_env()


def test_packaged_default_profile_registry_matches_repository_config(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    monkeypatch.delenv("LIVECONV_PROFILE_CONFIG", raising=False)
    packaged = Settings.from_env().profile_config
    assert packaged.is_file()
    assert json.loads(packaged.read_text()) == json.loads(
        settings.profile_config.read_text()
    )


def test_profile_hash_excludes_worker_endpoint_and_rejects_private_config(
    settings: Settings,
    tmp_path: Path,
) -> None:
    source = json.loads(settings.profile_config.read_text())
    first_document = deepcopy(source)
    second_document = deepcopy(source)
    first_document["profiles"][0]["runtime"]["worker_endpoint"] = "/private/a.sock"
    second_document["profiles"][0]["runtime"]["worker_endpoint"] = "/private/b.sock"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text(json.dumps(first_document))
    second_path.write_text(json.dumps(second_document))

    first = ProfileRegistry.load(first_path).get_selectable("test.passthrough.v1")
    second = ProfileRegistry.load(second_path).get_selectable("test.passthrough.v1")
    assert first is not None and second is not None
    assert first.profile_hash == second.profile_hash

    unsafe_document = deepcopy(source)
    unsafe_document["profiles"][1]["runtime"]["configuration"] = {
        "gain": 0.5,
        "nested": {"api_token": "must-not-load"},
    }
    unsafe_path = tmp_path / "unsafe.json"
    unsafe_path.write_text(json.dumps(unsafe_document))
    with pytest.raises(ValueError, match="private key names are forbidden"):
        ProfileRegistry.load(unsafe_path)
