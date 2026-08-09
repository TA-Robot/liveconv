from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from liveconv_exp004_rvc_gateway_smoke.config import RunConfiguration
from liveconv_exp004_rvc_gateway_smoke.suite import run_smoke

from .fakes import (
    BadOutput,
    FakeConnector,
    FakeHttp,
    FakeProfileIdentity,
    FakeWebSocket,
    VirtualPacer,
)
from .profile_fixture import PROFILE_ID, write_retained_rvc_profile

ROOT = Path(__file__).resolve().parents[1]


def configuration(tmp_path: Path) -> RunConfiguration:
    profile = write_retained_rvc_profile(tmp_path / "retained-rvc-profile.json")
    return RunConfiguration(
        gateway_url="http://127.0.0.1:8766",
        profile_id=PROFILE_ID,
        origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        trace_path=ROOT / "unused-test-trace.json",
        git_commit="a" * 40,
        api_token="deterministic-test-token",
        profile_config=profile.path,
        expected_profile_hash=profile.profile_hash,
        expected_configuration_hash=profile.configuration_hash,
        timeout_seconds=1.0,
        stale_grace_seconds=0.001,
    )


def fake_identity(configuration: RunConfiguration) -> FakeProfileIdentity:
    return FakeProfileIdentity(
        profile_id=configuration.profile_id,
        profile_hash=configuration.expected_profile_hash,
        configuration_hash=configuration.expected_configuration_hash,
    )


@pytest.mark.asyncio
async def test_one_profile_rvc_route_batch_tail_cancel_and_teardown(
    tmp_path: Path,
) -> None:
    config = configuration(tmp_path)
    identity = fake_identity(config)
    http = FakeHttp(identity)
    websocket = FakeWebSocket(identity)
    connector = FakeConnector(websocket)
    pacer = VirtualPacer()

    trace = await run_smoke(config, http=http, websockets=connector, pacer=pacer)

    document = trace.document()
    assert document["technical_outcome"] == "passed"
    assert document["decision_status"] == "inconclusive"
    assert all(value is False for value in document["claims"].values())
    assert http.closed is True
    assert http.deleted is True
    assert websocket.closed is True
    assert connector.calls == [
        (
            "ws://127.0.0.1:8766/v1/ws/00000000-0000-4000-8000-000000000001",
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            1.0,
        )
    ]
    assert all(
        request.authorization == "Bearer deterministic-test-token"
        for request in http.requests
    )
    assert [(request.method, request.path) for request in http.requests] == [
        ("GET", "/v1/models"),
        ("POST", "/v1/sessions"),
        ("DELETE", "/v1/sessions/00000000-0000-4000-8000-000000000001"),
        ("GET", "/v1/sessions/00000000-0000-4000-8000-000000000001"),
    ]
    assert len(pacer.sleeps) == 27

    results = {item["case_id"]: item for item in document["results"]}
    assert (
        results["catalog_session_attach"]["evidence"][
            "required_gateway_credit_available"
        ]
        is True
    )
    assert (
        results["catalog_session_attach"]["evidence"]["effective_ingress_credit_frames"]
        == 50
    )
    assert results["generation_1_batch_tail_flush"]["evidence"]["input_frames"] == 28
    assert (
        results["generation_1_batch_tail_flush"]["evidence"]["accepted_output_frames"]
        == 28
    )
    assert results["generation_1_batch_tail_flush"]["evidence"]["tail_frames"] == 3
    assert (
        results["generation_1_batch_tail_flush"]["evidence"][
            "advertised_ingress_credit_frames"
        ]
        == 50
    )
    assert (
        results["generation_1_batch_tail_flush"]["evidence"]["credit_high_water"] <= 50
    )
    assert (
        results["generation_1_batch_tail_flush"]["evidence"]["paced_frame_interval_ms"]
        == 20
    )
    assert (
        results["generation_1_batch_tail_flush"]["evidence"][
            "overflow_or_fallback_observed"
        ]
        is False
    )
    assert results["generation_2_cancel"]["evidence"] == {
        "generation_id": 2,
        "sent_frames_before_cancel": 1,
        "local_output_gate_closed_before_cancel_send": True,
        "server_acknowledged_cancel": True,
        "accepted_output_after_cancel": 0,
        "stale_output_frames_excluded": 1,
        "stale_output_frames_accepted": 0,
    }
    assert results["session_close_delete_404"]["evidence"] == {
        "session_close_acknowledged": True,
        "delete_http_status": 204,
        "get_after_delete_http_status": 404,
        "session_invalidated": True,
    }
    schema = json.loads(
        (ROOT / "src/liveconv_exp004_rvc_gateway_smoke/trace.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(document)


@pytest.mark.asyncio
async def test_generation_ready_uses_bounded_cold_start_timeout(
    tmp_path: Path,
) -> None:
    ready = asyncio.Event()
    delayed_configuration = replace(configuration(tmp_path), timeout_seconds=0.01)
    identity = fake_identity(delayed_configuration)
    run = asyncio.create_task(
        run_smoke(
            delayed_configuration,
            http=FakeHttp(identity),
            websockets=FakeConnector(
                FakeWebSocket(identity, generation_ready_gate=ready)
            ),
            pacer=VirtualPacer(),
        )
    )

    await asyncio.sleep(0.03)
    assert run.done() is False
    ready.set()

    document = (await run).document()
    assert document["technical_outcome"] == "passed"


@pytest.mark.parametrize(
    "bad_output", ["sequence", "timestamp", "nonfinite", "unnormalized", "unchanged"]
)
@pytest.mark.asyncio
async def test_invalid_or_unchanged_output_is_not_a_technical_pass(
    bad_output: BadOutput,
    tmp_path: Path,
) -> None:
    config = configuration(tmp_path)
    identity = fake_identity(config)
    trace = await run_smoke(
        config,
        http=FakeHttp(identity),
        websockets=FakeConnector(FakeWebSocket(identity, bad_output=bad_output)),
        pacer=VirtualPacer(),
    )
    document = trace.document()
    assert document["technical_outcome"] == "failed"
    failure = next(
        item for item in document["results"] if item["case_id"] == "harness_failure"
    )
    assert failure["evidence"] == {
        "failure_type": "RouteValidationError",
        "free_form_error_recorded": False,
    }


@pytest.mark.parametrize(
    ("http_options", "websocket_options"),
    [
        ({"extra_catalog_profile": True}, {}),
        ({"session_protocol_version": 2}, {}),
        ({}, {"ingress_budget_ms": 1_000, "max_ingress_frames": 51}),
        ({}, {"ingress_budget_ms": 1_000, "max_ingress_frames": 49}),
        ({}, {"ingress_budget_ms": 500, "max_ingress_frames": 50}),
    ],
)
@pytest.mark.asyncio
async def test_catalog_session_and_credit_envelope_must_be_exact(
    tmp_path: Path,
    http_options: dict[str, object],
    websocket_options: dict[str, object],
) -> None:
    config = configuration(tmp_path)
    identity = fake_identity(config)
    trace = await run_smoke(
        config,
        http=FakeHttp(identity, **http_options),
        websockets=FakeConnector(FakeWebSocket(identity, **websocket_options)),
        pacer=VirtualPacer(),
    )
    document = trace.document()
    assert document["technical_outcome"] == "failed"
    assert any(result["case_id"] == "harness_failure" for result in document["results"])


@pytest.mark.asyncio
async def test_catalog_hashes_must_match_the_validated_retained_profile(
    tmp_path: Path,
) -> None:
    config = configuration(tmp_path)
    mismatched = FakeProfileIdentity(
        profile_id=config.profile_id,
        profile_hash=f"sha256:{'c' * 64}",
        configuration_hash=config.expected_configuration_hash,
    )
    http = FakeHttp(mismatched)
    trace = await run_smoke(
        config,
        http=http,
        websockets=FakeConnector(FakeWebSocket(mismatched)),
        pacer=VirtualPacer(),
    )
    document = trace.document()
    assert document["technical_outcome"] == "failed"
    assert [(request.method, request.path) for request in http.requests] == [
        ("GET", "/v1/models"),
    ]
