from __future__ import annotations

import json
from importlib.resources import files

import pytest
from jsonschema import Draft202012Validator
from liveconv_protocol import ErrorCode

from liveconv_router_experiment.client import ProtocolSession
from liveconv_router_experiment.errors import ExperimentFailure
from liveconv_router_experiment.suite import (
    RunnerConfig,
    run_experiment,
    synthetic_frame,
)
from liveconv_router_experiment.trace import SteppingClock, TraceRecorder
from liveconv_router_experiment.transport import (
    GatewayApi,
    parse_session_descriptor,
    validate_gateway_url,
)

from .fakes import PASSTHROUGH, FakeConnector, FakeGatewayState, FakeHttpAdapter


async def _run_fake() -> tuple[object, TraceRecorder]:
    state = FakeGatewayState()
    trace = TraceRecorder(
        "fake-client-clock",
        clock=SteppingClock(current_ns=1_000_000_000, step_ns=1_000_000),
    )
    result = await run_experiment(
        RunnerConfig(
            gateway_url="http://127.0.0.1:8765",
            token=state.token,
            origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        ),
        trace=trace,
        http=FakeHttpAdapter(state),
        websocket_connector=FakeConnector(state),
    )
    return result, trace


@pytest.mark.asyncio
async def test_complete_suite_is_deterministic_and_schema_valid() -> None:
    first_result, first_trace = await _run_fake()
    second_result, second_trace = await _run_fake()

    assert first_result.route_smoke_passed
    assert second_result.route_smoke_passed
    assert [case.case_id for case in first_result.cases] == [
        "smoke.passthrough",
        "smoke.gain",
        "fault.bad_auth",
        "fault.ticket_replay",
        "fault.sequence_gap",
        "fault.stale_cancel",
        "fault.illegal_model_switch",
        "fault.delete",
    ]
    assert first_trace.to_json() == second_trace.to_json()
    document = first_trace.document()
    schema_path = files("liveconv_router_experiment").joinpath("trace.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)

    encoded = first_trace.to_json()
    assert "fake-ticket" not in encoded
    assert "test-token" not in encoded
    assert document["client_clock_id"] == "fake-client-clock"
    assert document["server_clock_ids"] == ["fake-server-clock"]
    assert document["run_scope"] == "route_smoke_v1"
    assert document["decision_status"] == "inconclusive"
    assert document["coverage"]["full_experiment_eligible"] is False
    assert document["coverage"]["missing_required_lanes"]
    assert document["environment"]["git_commit"] == "unrecorded"

    evidence = {case.case_id: case.evidence for case in first_result.cases}
    assert evidence["smoke.passthrough"]["classification"] == "identical"
    assert evidence["smoke.passthrough"]["payloads_identical"] is True
    assert evidence["smoke.gain"]["classification"] == "gain_only_nuisance"
    assert evidence["smoke.gain"]["payloads_identical"] is False
    assert evidence["fault.sequence_gap"]["required_action"] == "fallback"
    assert evidence["fault.stale_cancel"]["accepted_stale_frames"] == 0


@pytest.mark.asyncio
async def test_client_rejects_wrong_generation_pipeline() -> None:
    state = FakeGatewayState(wrong_generation_pipeline=True)
    trace = TraceRecorder("client-clock", clock=SteppingClock())
    api = GatewayApi(
        "http://127.0.0.1:8765",
        state.token,
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        trace,
        http=FakeHttpAdapter(state),
        websocket_connector=FakeConnector(state),
    )
    session = None
    try:
        descriptor = await api.require_session("pipeline", PASSTHROUGH)
        session = await ProtocolSession.attach(api, descriptor, "pipeline")
        with pytest.raises(ExperimentFailure, match="wrong pipeline"):
            await session.start_generation(1)
    finally:
        if session is not None:
            await session.abort()
        await api.close()


@pytest.mark.asyncio
async def test_client_rejects_discontinuous_output_sequence() -> None:
    state = FakeGatewayState(output_sequence_offset=1)
    trace = TraceRecorder("client-clock", clock=SteppingClock())
    api = GatewayApi(
        "http://127.0.0.1:8765",
        state.token,
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        trace,
        http=FakeHttpAdapter(state),
        websocket_connector=FakeConnector(state),
    )
    session = None
    try:
        descriptor = await api.require_session("sequence", PASSTHROUGH)
        session = await ProtocolSession.attach(api, descriptor, "sequence")
        await session.start_generation(1)
        await session.send_frame(synthetic_frame(1, 0, 1_000_000))
        with pytest.raises(ExperimentFailure, match="duplicate or discontinuous"):
            await session.receive_output()
    finally:
        if session is not None:
            await session.abort()
        await api.close()


def test_trace_rejects_sensitive_or_cross_clock_partial_data() -> None:
    trace = TraceRecorder("client-clock", clock=SteppingClock())
    with pytest.raises(ExperimentFailure, match="sensitive trace key"):
        trace.record("case", "local", "unsafe", {"ticket": "must-not-land"})
    with pytest.raises(ExperimentFailure, match="recorded together"):
        trace.record(
            "case",
            "local",
            "unsafe-clock",
            {},
            server_clock_id="server-clock",
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://audio.example.test",
        "https://user:password@audio.example.test",
        "https://audio.example.test/api",
        "wss://audio.example.test",
    ],
)
def test_gateway_url_rejects_insecure_or_ambiguous_origins(url: str) -> None:
    with pytest.raises(ValueError):
        validate_gateway_url(url)


def test_gateway_url_accepts_loopback_http_and_remote_https() -> None:
    assert validate_gateway_url("http://127.0.0.1:8765/") == ("http://127.0.0.1:8765")
    assert validate_gateway_url("https://audio.example.test") == (
        "https://audio.example.test"
    )


def test_session_descriptor_rejects_cross_origin_websocket_path() -> None:
    body = {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "pipeline_id": "00000000-0000-0000-0000-000000000002",
        "profile_id": PASSTHROUGH,
        "profile_hash": f"sha256:{'a' * 64}",
        "configuration_hash": f"sha256:{'b' * 64}",
        "websocket_path": "wss://attacker.invalid/v1/ws",
        "ticket": "secret-ticket",
    }
    with pytest.raises(ExperimentFailure, match="safe path"):
        parse_session_descriptor(body, PASSTHROUGH)


def test_synthetic_pcm_is_canonical_and_reproducible() -> None:
    first = synthetic_frame(7, 2, 123_000)
    second = synthetic_frame(7, 2, 123_000)
    assert first.encode() == second.encode()
    assert first.header.sample_rate == 48_000
    assert first.header.channels == 1
    assert first.header.samples_per_channel == 960
    assert max(abs(sample) for sample in first.unpack_samples()) <= 0.75
    assert ErrorCode.SEQUENCE_GAP.value == "SEQUENCE_GAP"


def test_credentials_are_excluded_from_configuration_repr() -> None:
    config = RunnerConfig(
        gateway_url="https://audio.example.test",
        token="credential-must-not-appear",
        origin="chrome-extension://abcdefghijklmnopabcdefghijklmnop",
    )
    assert "credential-must-not-appear" not in repr(config)
