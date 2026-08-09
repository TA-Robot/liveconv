from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import liveconv_audio._adapter_registry as adapter_registry
import pytest
from fastapi.testclient import TestClient
from liveconv_audio import Settings, create_app
from liveconv_audio import __main__ as audio_main
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


def rvc_configuration() -> dict[str, object]:
    return {
        "worker_module": "workers.adapters.rvc_v2.worker",
        "adapter_revision": "liveconv-rvc-v2-worker-v1.4",
        "source_revision": "a" * 40,
        "artifacts": {
            "checkpoint_sha256": "b" * 64,
            "index_sha256": None,
            "hubert_config_sha256": "c" * 64,
            "hubert_preprocessor_sha256": "d" * 64,
            "hubert_weights_sha256": "e" * 64,
            "rmvpe_sha256": "f" * 64,
            "worker_wheel_sha256": "1" * 64,
            "worker_wheel_record_sha256": "2" * 64,
            "worker_module_sha256": "3" * 64,
            "backend_module_sha256": "4" * 64,
            "network_isolation_module_sha256": "5" * 64,
            "requirements_lock_sha256": "6" * 64,
        },
        "settings": {
            "speaker_id": 0,
            "pitch_shift": 0,
            "f0_method": "rmvpe",
            "index_rate": 0.0,
            "rms_mix_rate": 1.0,
            "sample_rate": 48_000,
            "block_ms": 500,
            "crossfade_ms": 50,
            "context_ms": 2_500,
            "frame_ms": 20,
            "inference_batch_frames": 25,
            "queue_capacity_frames": 25,
            "resident_capacity_frames": 50,
            "formant_shift": 0.0,
            "threshold_dbfs": -60.0,
        },
    }


def write_promotion_pack(
    directory: Path,
    *,
    pack_id: str = "rvc-v2",
    status: str = "technical_validation",
    evidence_sha256: str = f"sha256:{'c' * 64}",
    ready_for_runtime: bool = False,
) -> Path:
    directory.mkdir(exist_ok=True)
    pack = directory / f"{pack_id}.json"
    pack.write_text(
        json.dumps(
            {
                "pack_id": pack_id,
                "ready_for_runtime": ready_for_runtime,
                "promotion_evidence": {
                    "status": status,
                    "evidence_sha256": evidence_sha256,
                },
            }
        )
    )
    return pack


async def invoke_chunked_session_request(
    app,
    *,
    authorization: bytes | None,
    chunks: tuple[bytes, ...],
) -> tuple[list[dict[str, object]], int]:
    headers = [(b"content-type", b"application/json")]
    if authorization is not None:
        headers.append((b"authorization", authorization))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/sessions",
        "raw_path": b"/v1/sessions",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    calls = 0

    async def receive() -> dict[str, object]:
        nonlocal calls
        index = calls
        calls += 1
        return {
            "type": "http.request",
            "body": chunks[index],
            "more_body": index + 1 < len(chunks),
        }

    sent: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await app(scope, receive, send)
    return sent, calls


def test_liveness_is_public_and_every_other_api_requires_bearer(
    client: TestClient,
    settings: Settings,
) -> None:
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").status_code == 401
    assert client.get("/v1/runtime-boundary").status_code == 401
    assert client.get("/v1/models").status_code == 401
    assert client.get("/v1/model-roster").status_code == 401
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
    assert client.get("/v1/runtime-boundary", headers=AUTH_HEADERS).json() == {
        "protocol_version": 1,
        "transport_scope": "loopback",
        "max_sessions": 64,
        "ticket_one_use": True,
    }
    with TestClient(create_app(replace(settings, bind_host="0.0.0.0"))) as network:
        assert (
            network.get("/v1/runtime-boundary", headers=AUTH_HEADERS).json()[
                "transport_scope"
            ]
            == "network"
        )


def test_module_entrypoint_imports_and_selects_the_websockets_backend(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    __import__("websockets")
    captured: dict[str, object] = {}
    sentinel_app = object()

    monkeypatch.setattr(
        audio_main,
        "Settings",
        SimpleNamespace(from_env=lambda: settings),
    )
    monkeypatch.setattr(audio_main, "create_app", lambda value: sentinel_app)
    monkeypatch.setattr(
        audio_main.uvicorn,
        "run",
        lambda app, **kwargs: captured.update(app=app, **kwargs),
    )

    audio_main.main()

    assert captured["app"] is sentinel_app
    assert captured["ws"] == "websockets"
    assert captured["ws_max_size"] == 16 * 1024


@pytest.mark.asyncio
async def test_unauthenticated_v1_request_body_is_not_consumed(
    settings: Settings,
) -> None:
    sent, calls = await invoke_chunked_session_request(
        create_app(settings),
        authorization=None,
        chunks=(b"x" * 1_000_000, b"y" * 1_000_000, b"z" * 1_000_000),
    )
    assert calls == 0
    assert sent[0]["status"] == 401


@pytest.mark.asyncio
async def test_authenticated_chunked_v1_body_stops_at_16_kib(
    settings: Settings,
) -> None:
    sent, calls = await invoke_chunked_session_request(
        create_app(settings),
        authorization=f"Bearer {API_TOKEN}".encode(),
        chunks=(b"x" * 8_192, b"y" * 8_193, b"z" * 1_000_000),
    )
    assert calls == 2
    assert sent[0]["status"] == 413


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


def test_model_roster_exposes_all_prepared_models_without_private_runtime(
    client: TestClient,
) -> None:
    response = client.get("/v1/model-roster", headers=AUTH_HEADERS)
    assert response.status_code == 200
    document = response.json()
    assert document["schema_version"] == 1
    assert document["roster_hash"].startswith("sha256:")
    assert [model["model_id"] for model in document["models"]] == [
        "rvc-v2",
        "beatrice-2",
        "x-vc",
        "openvoice-v2",
    ]
    assert {model["execution_state"] for model in document["models"]} == {"unavailable"}
    assert all(model["profile"] is None for model in document["models"])
    serialized = json.dumps(document)
    for forbidden in ("worker_endpoint", "runtime", "license_record", "/workspace"):
        assert forbidden not in serialized


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


def test_technical_profile_opt_in_is_exact_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVECONV_ALLOW_TECHNICAL_PROFILES", "1")
    assert Settings.from_env().allow_technical_profiles is True
    monkeypatch.setenv("LIVECONV_ALLOW_TECHNICAL_PROFILES", "true")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        Settings.from_env()


def test_technical_profiles_cannot_be_enabled_on_a_non_loopback_bind(
    settings: Settings,
) -> None:
    exposed = replace(
        settings,
        allow_technical_profiles=True,
        bind_host="0.0.0.0",
    )
    assert "technical profiles require a loopback bind host" in (
        exposed.configuration_errors
    )
    concurrent = replace(settings, allow_technical_profiles=True, max_sessions=2)
    assert "technical profiles require max_sessions=1" in (
        concurrent.configuration_errors
    )


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


def test_ready_external_worker_profile_is_explicit_and_publicly_redacted(
    settings: Settings,
    tmp_path: Path,
) -> None:
    source = json.loads(settings.profile_config.read_text())
    profile = deepcopy(source["profiles"][0])
    profile.update(
        {
            "profile_id": "vc.rvc.synthetic-ja.v1",
            "kind": "voice_conversion",
            "implementation_revision": "liveconv-rvc-v2-worker-v1.4+rvc." + "a" * 40,
            "weight_revision": f"sha256:{'b' * 64}",
            "minimum_context_ms": 500,
            "voice_requirement": "pretrained_voice",
            "resource_class": "gpu",
        }
    )
    profile["runtime"] = {
        "adapter": "worker",
        "configuration": rvc_configuration(),
        "worker_endpoint": str(tmp_path / "python"),
        "max_vram_mb": 2_048,
    }
    worker_endpoint = tmp_path / "python"
    worker_endpoint.write_text("#!/bin/sh\nexit 0\n")
    worker_endpoint.chmod(0o700)
    pack_directory = tmp_path / "packs"
    pack = write_promotion_pack(pack_directory)
    profile["promotion"] = {
        "status": "technical_validation",
        "pack_id": "rvc-v2",
        "pack_sha256": f"sha256:{hashlib.sha256(pack.read_bytes()).hexdigest()}",
        "evidence_sha256": f"sha256:{'c' * 64}",
        "endpoint_sha256": (
            f"sha256:{hashlib.sha256(worker_endpoint.read_bytes()).hexdigest()}"
        ),
    }
    document = {"schema_version": 1, "profiles": [profile]}
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(document))

    loaded = ProfileRegistry.load(path, model_pack_directory=pack_directory)
    assert loaded.get_selectable(profile["profile_id"]) is None
    assert loaded.public_profiles() == []

    technical = ProfileRegistry.load(
        path,
        allow_technical_profiles=True,
        model_pack_directory=pack_directory,
    )
    selected = technical.get_selectable(profile["profile_id"])
    assert selected is not None
    public = technical.public_profiles()[0]
    assert public["profile_id"] == profile["profile_id"]
    assert "runtime" not in public

    document["profiles"][0]["promotion"]["evidence_sha256"] = f"sha256:{'0' * 64}"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="promotion evidence digest differs"):
        ProfileRegistry.load(path, model_pack_directory=pack_directory)
    document["profiles"][0]["promotion"]["evidence_sha256"] = f"sha256:{'c' * 64}"

    document["profiles"][0]["promotion"]["status"] = "approved"
    path.write_text(json.dumps(document))
    with pytest.raises(
        ValueError,
        match="promotion evidence does not authorize profile",
    ):
        ProfileRegistry.load(path, model_pack_directory=pack_directory)

    pack = write_promotion_pack(
        pack_directory,
        status="approved",
        ready_for_runtime=False,
    )
    document["profiles"][0]["promotion"]["pack_sha256"] = (
        f"sha256:{hashlib.sha256(pack.read_bytes()).hexdigest()}"
    )
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="model pack is not approved"):
        ProfileRegistry.load(path, model_pack_directory=pack_directory)
    document["profiles"][0]["promotion"]["status"] = "technical_validation"
    path.write_text(json.dumps(document))
    assert (
        ProfileRegistry.load(
            path,
            allow_technical_profiles=True,
            model_pack_directory=pack_directory,
        ).get_selectable(profile["profile_id"])
        is not None
    )

    document["profiles"][0]["runtime"]["worker_endpoint"] = "relative/python"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="worker_endpoint must be an absolute path"):
        ProfileRegistry.load(path, model_pack_directory=pack_directory)


def test_worker_registration_rejects_cross_bound_model_pack(
    settings: Settings,
    tmp_path: Path,
) -> None:
    source = json.loads(settings.profile_config.read_text())
    profile = deepcopy(source["profiles"][0])
    profile.update(
        {
            "profile_id": "vc.rvc.synthetic-ja.v1",
            "kind": "voice_conversion",
            "implementation_revision": "liveconv-rvc-v2-worker-v1.4+rvc." + "a" * 40,
            "weight_revision": f"sha256:{'b' * 64}",
            "minimum_context_ms": 500,
            "voice_requirement": "pretrained_voice",
            "resource_class": "gpu",
        }
    )
    worker_endpoint = tmp_path / "python"
    worker_endpoint.write_text("#!/bin/sh\nexit 0\n")
    worker_endpoint.chmod(0o700)
    profile["runtime"] = {
        "adapter": "worker",
        "configuration": rvc_configuration(),
        "worker_endpoint": str(worker_endpoint),
        "max_vram_mb": 2_048,
    }
    pack_directory = tmp_path / "packs"
    pack = write_promotion_pack(pack_directory, pack_id="beatrice-2")
    profile["promotion"] = {
        "status": "technical_validation",
        "pack_id": "beatrice-2",
        "pack_sha256": f"sha256:{hashlib.sha256(pack.read_bytes()).hexdigest()}",
        "evidence_sha256": f"sha256:{'c' * 64}",
        "endpoint_sha256": (
            f"sha256:{hashlib.sha256(worker_endpoint.read_bytes()).hexdigest()}"
        ),
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"schema_version": 1, "profiles": [profile]}))

    with pytest.raises(ValueError, match="worker registration requires pack rvc-v2"):
        ProfileRegistry.load(
            path,
            allow_technical_profiles=True,
            model_pack_directory=pack_directory,
        )


def test_worker_profile_rejects_registration_capacity_drift(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = ProfileRegistry.load(settings.profile_config).get_selectable(
        "test.passthrough.v1"
    )
    assert profile is not None
    registration = adapter_registry._BUILTIN_REGISTRATIONS["passthrough"]
    monkeypatch.setitem(
        adapter_registry._BUILTIN_REGISTRATIONS,
        "passthrough",
        replace(registration, queue_capacity_frames=lambda _profile, _budget: 2),
    )

    with pytest.raises(
        ValueError,
        match="worker profile differs from adapter registration",
    ):
        adapter_registry.worker_profile_for(profile, "pipeline-1", 500)
