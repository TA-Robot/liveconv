from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from liveconv_audio import Settings, create_app

API_TOKEN = "0123456789abcdefghijklmnopqrstuvwxyz-TEST"
ALLOWED_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}
ORIGIN_HEADERS = {"Origin": ALLOWED_ORIGIN}


@pytest.fixture
def settings() -> Settings:
    root = Path(__file__).resolve().parents[3]
    return Settings(
        api_token=API_TOKEN,
        allowed_origins=frozenset({ALLOWED_ORIGIN}),
        profile_config=root / "config" / "model-profiles.json",
        ticket_ttl_seconds=30,
        attach_timeout_seconds=0.5,
        ingress_budget_ms=500,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def create_session(client: TestClient):
    def create(profile_id: str = "test.passthrough.v1") -> dict[str, object]:
        response = client.post(
            "/v1/sessions",
            headers=AUTH_HEADERS,
            json={
                "protocol_version": 1,
                "profile_id": profile_id,
                "input": {
                    "sample_rate": 48_000,
                    "channels": 1,
                    "sample_format": "f32le",
                    "frame_ms": 20,
                },
                "voice_id": None,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create
