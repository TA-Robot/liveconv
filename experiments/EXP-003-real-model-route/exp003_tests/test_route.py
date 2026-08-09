from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from liveconv_real_model_route.config import RunConfiguration
from liveconv_real_model_route.registry import ProfileRegistry
from liveconv_real_model_route.suite import run_route_suite
from liveconv_real_model_route.trace import SteppingClock

from .fakes import BadOutput, FakeConnector, FakeHttp, FakeWebSocket, VirtualPacer

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "exp003_tests" / "fixtures" / "profile-registry.json"


def configuration() -> RunConfiguration:
    return RunConfiguration(
        gateway_url="http://127.0.0.1:8765",
        origin="chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        registry_path=REGISTRY_PATH,
        profile_ids=("vc.fake.alpha.v1", "vc.fake.beta.v1"),
        trace_path=ROOT / "unused-test-trace.json",
        api_token="deterministic-test-token",
        timeout_seconds=1.0,
        batch_frames=3,
        partial_frames=2,
        cancel_frames=2,
    )


@pytest.mark.asyncio
async def test_batched_route_credit_partial_cancel_stale_and_switch() -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        configuration().profile_ids, voice_id_present=False
    )
    http = FakeHttp(profiles)
    pacer = VirtualPacer()
    websocket = FakeWebSocket(
        profiles,
        batch_frames=3,
        send_clock=pacer,
        full_batch_delay_seconds=0.1,
    )
    trace = await run_route_suite(
        configuration(),
        registry,
        http=http,
        websockets=FakeConnector(websocket),
        pacer=pacer,
        trace_clock=SteppingClock(),
    )

    document = trace.document()
    assert document["technical_outcome"] == "passed"
    assert document["decision_status"] == "inconclusive"
    assert all(value is False for value in document["claims"].values())
    serialized = trace.to_json()
    assert "must-never-enter-trace" not in serialized
    assert "deterministic-test-token" not in serialized
    assert "/private/" not in serialized
    assert websocket.max_unreturned_frames <= 3
    assert http.closed and websocket.closed
    assert any(method == "DELETE" for method, _ in http.requests)

    results = {item["case_id"]: item for item in document["results"]}
    assert results["session.cleanup"]["evidence"]["session_invalidated"] is True
    assert results["session.cleanup"]["evidence"]["http_status_code"] == 404
    for profile_id in configuration().profile_ids:
        evidence = results[f"route.{profile_id}.partial_flush"]["evidence"]
        assert evidence["input_frames"] == 5
        assert evidence["accepted_output_frames"] == 5
        assert evidence["partial_end_frames"] == 2
        assert evidence["credit_high_water"] <= evidence["advertised_credit_limit"]
        assert evidence["output_changed"] is True
    assert results["stale_exclusion"]["evidence"] == {
        "locally_invalidated_generations": 1,
        "stale_output_frames_excluded": 1,
        "stale_output_frames_accepted": 0,
        "gate_remained_generation_bound": True,
    }
    assert (
        results["switch.vc.fake.alpha.v1.to.vc.fake.beta.v1"]["evidence"][
            "pipeline_changed"
        ]
        is True
    )

    for headers in websocket.observed_inputs.values():
        timestamps = [header.source_monotonic_ns for header in headers]
        assert all(
            later - earlier == 20_000_000
            for earlier, later in zip(timestamps, timestamps[1:])
        )
    for send_times in websocket.observed_send_times.values():
        assert all(
            later - earlier >= 20_000_000
            for earlier, later in zip(send_times, send_times[1:])
        )

    schema = json.loads(
        (ROOT / "src/liveconv_real_model_route/trace.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(document)


@pytest.mark.asyncio
async def test_closed_session_must_be_absent_from_http_api() -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        configuration().profile_ids, voice_id_present=False
    )
    trace = await run_route_suite(
        configuration(),
        registry,
        http=FakeHttp(profiles, closed_session_status=204),
        websockets=FakeConnector(FakeWebSocket(profiles, batch_frames=3)),
        pacer=VirtualPacer(),
        trace_clock=SteppingClock(),
    )

    assert trace.document()["technical_outcome"] == "failed"
    results = {item["case_id"]: item for item in trace.document()["results"]}
    assert results["harness.failure"]["evidence"]["failure_type"] == (
        "RouteValidationError"
    )


@pytest.mark.parametrize(
    "bad_output",
    ["sequence", "timestamp", "nonfinite", "unnormalized", "unchanged"],
)
@pytest.mark.asyncio
async def test_output_integrity_failures_are_technical_failures(
    bad_output: BadOutput,
) -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        configuration().profile_ids, voice_id_present=False
    )
    trace = await run_route_suite(
        configuration(),
        registry,
        http=FakeHttp(profiles),
        websockets=FakeConnector(
            FakeWebSocket(profiles, batch_frames=3, bad_output=bad_output)
        ),
        pacer=VirtualPacer(),
        trace_clock=SteppingClock(),
    )
    document = trace.document()
    assert document["technical_outcome"] == "failed"
    assert document["decision_status"] == "inconclusive"
    failure = next(
        item for item in document["results"] if item["case_id"] == "harness.failure"
    )
    assert failure["evidence"]["sensitive_failure_message_recorded"] is False


@pytest.mark.asyncio
async def test_advertised_credit_smaller_than_batch_fails_closed() -> None:
    registry = ProfileRegistry.load(REGISTRY_PATH)
    profiles = registry.require_route_profiles(
        configuration().profile_ids, voice_id_present=False
    )
    websocket = FakeWebSocket(profiles, batch_frames=3, credit_frames=2)
    trace = await run_route_suite(
        configuration(),
        registry,
        http=FakeHttp(profiles),
        websockets=FakeConnector(websocket),
        pacer=VirtualPacer(),
        trace_clock=SteppingClock(),
    )
    assert trace.document()["technical_outcome"] == "failed"
    assert websocket.observed_inputs == {}
    assert websocket.closed is True
