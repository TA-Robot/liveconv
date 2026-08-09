from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

import numpy as np
from liveconv_evaluation import AudioSignal, compare_signals
from liveconv_protocol import (
    V1_SAMPLE_RATE,
    V1_SAMPLES_PER_CHANNEL,
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    RequiredAction,
)

from .client import ProtocolSession, attempt_ticket_replay
from .errors import ExperimentFailure
from .trace import TraceRecorder
from .transport import (
    GatewayApi,
    HttpAdapter,
    SessionDescriptor,
    WebSocketConnector,
)

PASSTHROUGH_PROFILE = "test.passthrough.v1"
GAIN_PROFILE = "test.gain.v1"
FRAME_INTERVAL_NS = 20_000_000


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    gateway_url: str
    token: str = field(repr=False)
    origin: str
    timeout_seconds: float = 3.0


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    passed: bool
    evidence: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    route_smoke_passed: bool
    cases: tuple[CaseResult, ...]
    trace: TraceRecorder


def synthetic_frame(
    generation_id: int,
    sequence: int,
    source_monotonic_ns: int,
) -> PcmFrame:
    """Create redistributable, deterministic f32le PCM without speech content."""

    phase = sequence * 11
    samples = (
        (((index + phase) % 64) - 32) / 64.0 * 0.75
        for index in range(V1_SAMPLES_PER_CHANNEL)
    )
    return PcmFrame.from_samples(
        FrameHeader(
            kind=FrameKind.INPUT,
            generation_id=generation_id,
            sequence=sequence,
            source_monotonic_ns=source_monotonic_ns,
        ),
        samples,
    )


async def _cleanup(
    api: GatewayApi,
    case_id: str,
    descriptor: SessionDescriptor | None,
    session: ProtocolSession | None,
) -> None:
    if descriptor is None:
        return
    if session is not None and not session.closed:
        try:
            await session.close()
            return
        except Exception:
            with contextlib.suppress(Exception):
                await session.abort()
    with contextlib.suppress(Exception):
        await api.delete_session(case_id, descriptor.session_id)


def _signal_evidence(
    inputs: list[PcmFrame], outputs: list[PcmFrame]
) -> dict[str, object]:
    source = np.asarray(
        [sample for frame in inputs for sample in frame.unpack_samples()],
        dtype=np.float64,
    )
    output = np.asarray(
        [sample for frame in outputs for sample in frame.unpack_samples()],
        dtype=np.float64,
    )
    metrics = compare_signals(
        AudioSignal(source, V1_SAMPLE_RATE),
        AudioSignal(output, V1_SAMPLE_RATE),
    )["comparison"]
    return {
        "exact_sample_match": metrics["exact_sample_match"],
        "aligned_gain_normalized_nrmse": metrics["aligned_gain_normalized_nrmse"],
        "aligned_gain_normalized_correlation": metrics[
            "aligned_gain_normalized_correlation"
        ],
        "gain_applied_for_comparison": metrics["gain_applied_for_comparison"],
        "duration_ratio": metrics["duration_ratio"],
    }


async def _smoke_profile(
    api: GatewayApi,
    case_id: str,
    profile_id: str,
    *,
    expected_gain: float,
) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, profile_id)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        await session.ping()
        await session.start_generation(1)
        base_ns = api.trace.clock.monotonic_ns()
        inputs: list[PcmFrame] = []
        outputs: list[PcmFrame] = []
        for sequence in range(3):
            frame = synthetic_frame(
                generation_id=1,
                sequence=sequence,
                source_monotonic_ns=base_ns + sequence * FRAME_INTERVAL_NS,
            )
            inputs.append(frame)
            await session.send_frame(frame)
            outputs.append(await session.receive_output())
        await session.end_generation()
        await session.close()

        source_samples = np.asarray(
            [sample for frame in inputs for sample in frame.unpack_samples()],
            dtype=np.float32,
        )
        output_samples = np.asarray(
            [sample for frame in outputs for sample in frame.unpack_samples()],
            dtype=np.float32,
        )
        expected_samples = source_samples * np.float32(expected_gain)
        expected_transform = bool(np.array_equal(output_samples, expected_samples))
        payloads_identical = all(
            source.payload == output.payload
            for source, output in zip(inputs, outputs, strict=True)
        )
        if not expected_transform:
            raise ExperimentFailure(
                f"{profile_id} output does not match its deterministic transform"
            )
        if expected_gain == 1.0 and not payloads_identical:
            raise ExperimentFailure("passthrough did not preserve payload bytes")
        if expected_gain != 1.0 and payloads_identical:
            raise ExperimentFailure("gain profile did not change PCM samples")
        signal = _signal_evidence(inputs, outputs)
        normalized_error = signal["aligned_gain_normalized_nrmse"]
        if normalized_error is None or float(normalized_error) > 1e-6:
            raise ExperimentFailure("deterministic gain was not gain-normalized")
        classification = "identical" if expected_gain == 1.0 else "gain_only_nuisance"
        return {
            "profile_id": profile_id,
            "frames": len(inputs),
            "canonical_audio": "48000Hz-mono-f32le-20ms",
            "payloads_identical": payloads_identical,
            "expected_transform_match": expected_transform,
            "classification": classification,
            "signal": signal,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


async def _bad_auth(api: GatewayApi, case_id: str) -> dict[str, object]:
    response, descriptor = await api.create_session(
        case_id,
        PASSTHROUGH_PROFILE,
        token_override="EXP002-invalid-credential-not-a-secret",
    )
    if descriptor is not None or response.status_code != 401:
        raise ExperimentFailure("bad bearer authentication did not return HTTP 401")
    return {"status_code": response.status_code, "session_created": False}


async def _ticket_replay(api: GatewayApi, case_id: str) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, PASSTHROUGH_PROFILE)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        event = await attempt_ticket_replay(api, descriptor, case_id)
        await session.close()
        return {
            "error_code": event.code,
            "recoverable": event.recoverable,
            "required_action": event.required_action,
            "ticket_rejected": True,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


async def _sequence_gap(api: GatewayApi, case_id: str) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, PASSTHROUGH_PROFILE)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        await session.start_generation(20)
        base_ns = api.trace.clock.monotonic_ns()
        first = synthetic_frame(20, 0, base_ns)
        await session.send_frame(first)
        await session.receive_output()
        await session.inject_frame(
            synthetic_frame(20, 2, base_ns + 2 * FRAME_INTERVAL_NS)
        )
        error = await session.expect_error(ErrorCode.SEQUENCE_GAP, generation_id=20)
        if error.required_action is not RequiredAction.FALLBACK:
            raise ExperimentFailure("sequence gap did not require fallback")
        await session.expect_fallback(ErrorCode.SEQUENCE_GAP, 20)
        await session.close()
        return {
            "error_code": error.code,
            "required_action": error.required_action,
            "fallback_observed": True,
            "accepted_stale_frames": 0,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


async def _stale_after_cancel(api: GatewayApi, case_id: str) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, PASSTHROUGH_PROFILE)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        base_ns = api.trace.clock.monotonic_ns()
        await session.start_generation(30)
        await session.cancel_generation()
        await session.inject_frame(synthetic_frame(30, 0, base_ns))
        first_error = await session.expect_error(
            ErrorCode.STALE_GENERATION, generation_id=30
        )

        await session.start_generation(31)
        await session.inject_frame(synthetic_frame(30, 0, base_ns + FRAME_INTERVAL_NS))
        second_error = await session.expect_error(
            ErrorCode.STALE_GENERATION, generation_id=30
        )
        current = synthetic_frame(31, 0, base_ns + 2 * FRAME_INTERVAL_NS)
        await session.send_frame(current)
        output = await session.receive_output()
        if output.payload != current.payload:
            raise ExperimentFailure("stale rejection damaged the current generation")
        await session.cancel_generation()
        await session.close()
        return {
            "post_cancel_error": first_error.code,
            "during_new_generation_error": second_error.code,
            "current_generation_survived": True,
            "accepted_stale_frames": 0,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


async def _illegal_model_switch(api: GatewayApi, case_id: str) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, PASSTHROUGH_PROFILE)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        initial_pipeline = session.pipeline_id
        await session.start_generation(40)
        request_id = await session.inject_model_select(GAIN_PROFILE)
        error = await session.expect_error(
            ErrorCode.INVALID_STATE, request_id=request_id
        )
        if session.pipeline_id != initial_pipeline:
            raise ExperimentFailure("illegal model switch changed the client pipeline")
        frame = synthetic_frame(40, 0, api.trace.clock.monotonic_ns())
        await session.send_frame(frame)
        output = await session.receive_output()
        if output.payload != frame.payload:
            raise ExperimentFailure("illegal switch changed active generation output")
        await session.cancel_generation()
        await session.close()
        return {
            "error_code": error.code,
            "pipeline_unchanged": True,
            "active_generation_survived": True,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


async def _delete_attached_session(api: GatewayApi, case_id: str) -> dict[str, object]:
    descriptor: SessionDescriptor | None = None
    session: ProtocolSession | None = None
    try:
        descriptor = await api.require_session(case_id, PASSTHROUGH_PROFILE)
        session = await ProtocolSession.attach(api, descriptor, case_id)
        deleted = await api.delete_session(case_id, descriptor.session_id)
        if deleted.status_code != 204:
            raise ExperimentFailure(
                f"session DELETE returned HTTP {deleted.status_code}"
            )
        await session.expect_transport_closed()
        fetched = await api.get_session(case_id, descriptor.session_id)
        if fetched.status_code != 404:
            raise ExperimentFailure("deleted session remained visible over HTTP")
        return {
            "delete_status_code": deleted.status_code,
            "get_after_delete_status_code": fetched.status_code,
            "websocket_closed": True,
        }
    finally:
        await _cleanup(api, case_id, descriptor, session)


CaseFunction = Callable[[GatewayApi, str], Awaitable[dict[str, object]]]

_CASES: tuple[tuple[str, CaseFunction], ...] = (
    (
        "smoke.passthrough",
        lambda api, case_id: _smoke_profile(
            api, case_id, PASSTHROUGH_PROFILE, expected_gain=1.0
        ),
    ),
    (
        "smoke.gain",
        lambda api, case_id: _smoke_profile(
            api, case_id, GAIN_PROFILE, expected_gain=0.5
        ),
    ),
    ("fault.bad_auth", _bad_auth),
    ("fault.ticket_replay", _ticket_replay),
    ("fault.sequence_gap", _sequence_gap),
    ("fault.stale_cancel", _stale_after_cancel),
    ("fault.illegal_model_switch", _illegal_model_switch),
    ("fault.delete", _delete_attached_session),
)


async def run_experiment(
    config: RunnerConfig,
    *,
    trace: TraceRecorder,
    http: HttpAdapter | None = None,
    websocket_connector: WebSocketConnector | None = None,
) -> ExperimentResult:
    api = GatewayApi(
        config.gateway_url,
        config.token,
        config.origin,
        trace,
        timeout_seconds=config.timeout_seconds,
        http=http,
        websocket_connector=websocket_connector,
    )
    results: list[CaseResult] = []
    try:
        for case_id, case_function in _CASES:
            try:
                evidence = await case_function(api, case_id)
            except ExperimentFailure as exc:
                evidence = {"failure_type": type(exc).__name__}
                passed = False
            else:
                passed = True
            trace.add_result(case_id, passed=passed, evidence=evidence)
            trace.record(
                case_id,
                "local",
                "case.completed",
                {"passed": passed},
            )
            results.append(CaseResult(case_id, passed, evidence))
    finally:
        await api.close()
    return ExperimentResult(
        route_smoke_passed=all(result.passed for result in results),
        cases=tuple(results),
        trace=trace,
    )
