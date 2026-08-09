from __future__ import annotations

import asyncio
import math
import os
import signal
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from liveconv_audio import create_app
from liveconv_protocol import (
    ErrorCode,
    FrameHeader,
    FrameKind,
    PcmFrame,
    ProtocolValidationError,
)
from starlette.websockets import WebSocketDisconnect

from workers.runtime import AudioFrame, WorkerProfile, WorkerSupervisor

from .conftest import AUTH_HEADERS, ORIGIN_HEADERS

ROOT = Path(__file__).resolve().parents[3]


def attach_message(
    created: dict[str, object], request_id: str = "attach-1"
) -> dict[str, object]:
    return {
        "type": "session.attach",
        "protocol_version": 1,
        "request_id": request_id,
        "session_id": created["session_id"],
        "ticket": created["ticket"],
    }


def control(
    message_type: str,
    created: dict[str, object],
    request_id: str,
    **fields: object,
) -> dict[str, object]:
    return {
        "type": message_type,
        "protocol_version": 1,
        "request_id": request_id,
        "session_id": created["session_id"],
        **fields,
    }


def create_http_session(
    client: TestClient,
    profile_id: str = "test.passthrough.v1",
) -> dict[str, object]:
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


def input_frame(
    generation_id: int,
    sequence: int,
    value: float = 0.5,
    source_monotonic_ns: int | None = None,
) -> PcmFrame:
    return PcmFrame.from_samples(
        FrameHeader(
            kind=FrameKind.INPUT,
            generation_id=generation_id,
            sequence=sequence,
            source_monotonic_ns=(
                1_000_000 + sequence
                if source_monotonic_ns is None
                else source_monotonic_ns
            ),
        ),
        [value] * 960,
    )


def connect_and_attach(client: TestClient, created: dict[str, object]):
    websocket = client.websocket_connect("/v1/ws", headers=ORIGIN_HEADERS)
    websocket.__enter__()
    websocket.send_json(attach_message(created))
    ready = websocket.receive_json()
    assert ready["type"] == "session.ready"
    return websocket, ready


def close_websocket(websocket) -> None:
    websocket.__exit__(None, None, None)


def wait_for_ingress(client: TestClient, connection) -> None:
    assert client.portal is not None
    client.portal.call(connection.ingress.join)


def fake_worker_factory(
    mode: str,
    supervisors: list[WorkerSupervisor],
):
    def create(profile, pipeline_id: str, queue_budget_ms: int) -> WorkerSupervisor:
        command = [
            sys.executable,
            "-m",
            "workers.conformance.fake_worker",
            "--mode",
            mode,
        ]
        if mode == "gain":
            command.extend(("--gain", str(profile.runtime.configuration["gain"])))
        bounded_queue_ms = max(
            profile.frame_ms,
            (queue_budget_ms // profile.frame_ms) * profile.frame_ms,
        )
        supervisor = WorkerSupervisor(
            WorkerProfile(
                profile_id=profile.profile_id,
                pipeline_id=pipeline_id,
                configuration_hash=profile.configuration_hash,
                command=tuple(command),
                cwd=ROOT,
                environment={},
                implementation_revision="fake-worker-v1",
                weight_revision=None,
                frame_ms=profile.frame_ms,
                queue_budget_ms=bounded_queue_ms,
                startup_timeout_ms=1_000,
                first_output_timeout_ms=profile.timeouts.first_output_ms,
                stall_timeout_ms=profile.timeouts.stall_ms,
                cancel_timeout_ms=100,
                close_grace_ms=50,
                terminate_grace_ms=50,
                restart_limit=0,
                restart_window_ms=60_000,
            )
        )
        supervisors.append(supervisor)
        return supervisor

    return create


def install_fake_worker(
    client: TestClient,
    mode: str,
) -> list[WorkerSupervisor]:
    supervisors: list[WorkerSupervisor] = []
    client.app.state.gateway.worker_supervisor_factory = fake_worker_factory(
        mode,
        supervisors,
    )
    return supervisors


class DelayedBatch25Supervisor:
    """Minimal worker double that withholds a full private batch on demand."""

    input_capacity_frames = 25

    def __init__(self) -> None:
        self._active_generation_id: int | None = None
        self._inputs: list[AudioFrame] = []
        self._outputs: asyncio.Queue[AudioFrame] = asyncio.Queue()
        self._release_first_batch = asyncio.Event()
        self.maximum_queued_input_frames = 0

    @property
    def queued_input_frames(self) -> int:
        return len(self._inputs)

    async def start(self) -> None:
        return None

    async def start_generation(self, generation_id: int) -> None:
        self._active_generation_id = generation_id
        self._inputs.clear()
        self._outputs = asyncio.Queue()
        self._release_first_batch = asyncio.Event()

    async def push_audio(self, frame: AudioFrame) -> None:
        if frame.generation_id != self._active_generation_id:
            raise RuntimeError("inactive generation")
        if len(self._inputs) >= self.input_capacity_frames:
            raise RuntimeError("private worker queue overflow")
        self._inputs.append(frame)
        self.maximum_queued_input_frames = max(
            self.maximum_queued_input_frames,
            len(self._inputs),
        )
        if len(self._inputs) == self.input_capacity_frames:
            await self._release_first_batch.wait()
            await self._flush_inputs()

    async def next_output(self) -> AudioFrame:
        return await self._outputs.get()

    async def end_generation(self, generation_id: int) -> None:
        if generation_id != self._active_generation_id:
            raise RuntimeError("inactive generation")
        self._release_first_batch.set()
        await self._flush_inputs()
        self._active_generation_id = None

    async def cancel_generation(self, generation_id: int) -> None:
        if generation_id == self._active_generation_id:
            self._active_generation_id = None
        self._inputs.clear()
        self._outputs = asyncio.Queue()
        self._release_first_batch.set()

    async def close(self) -> None:
        self._active_generation_id = None
        self._inputs.clear()
        self._outputs = asyncio.Queue()
        self._release_first_batch.set()

    def release_first_batch(self) -> None:
        self._release_first_batch.set()

    async def _flush_inputs(self) -> None:
        while self._inputs:
            await self._outputs.put(self._inputs.pop(0))


def install_delayed_batch_worker(client: TestClient) -> list[DelayedBatch25Supervisor]:
    supervisors: list[DelayedBatch25Supervisor] = []

    def create(*_args: object) -> DelayedBatch25Supervisor:
        supervisor = DelayedBatch25Supervisor()
        supervisors.append(supervisor)
        return supervisor

    client.app.state.gateway.worker_supervisor_factory = create
    return supervisors


def wait_for_worker_queue(
    supervisors: list[WorkerSupervisor],
    minimum: int = 1,
) -> WorkerSupervisor:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if supervisors and supervisors[-1].queued_input_frames >= minimum:
            return supervisors[-1]
        time.sleep(0.005)
    raise AssertionError(f"worker did not retain {minimum} input frame(s)")


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_process_group_exit(process_group_id: int) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if not process_group_exists(process_group_id):
            return
        time.sleep(0.005)
    raise AssertionError(f"process group {process_group_id} survived cleanup")


def test_rejects_unlisted_origin(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as raised:
        with client.websocket_connect(
            "/v1/ws",
            headers={"Origin": "chrome-extension://not-allowed"},
        ):
            pass
    assert raised.value.code == 4403


def test_ticket_is_one_use(client: TestClient, create_session) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    close_websocket(websocket)
    assert created["session_id"] not in client.app.state.gateway.connections
    assert client.app.state.gateway.store.get(created["session_id"]) is None

    with client.websocket_connect("/v1/ws", headers=ORIGIN_HEADERS) as replay:
        replay.send_json(attach_message(created, "attach-replay"))
        error = replay.receive_json()
        assert error["code"] == "AUTH_FAILED"
        with pytest.raises(WebSocketDisconnect) as raised:
            replay.receive_json()
        assert raised.value.code == 4401


def test_expired_ticket_is_rejected(client: TestClient, create_session) -> None:
    created = create_session()
    session = client.app.state.gateway.store.get(created["session_id"])
    assert session is not None
    session.ticket_expires_monotonic = 0

    with client.websocket_connect("/v1/ws", headers=ORIGIN_HEADERS) as websocket:
        websocket.send_json(attach_message(created))
        assert websocket.receive_json()["code"] == "AUTH_FAILED"


def test_wrong_ticket_is_rejected_without_consuming_real_ticket(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    bad = {**attach_message(created), "ticket": "wrong-ticket"}
    with client.websocket_connect("/v1/ws", headers=ORIGIN_HEADERS) as websocket:
        websocket.send_json(bad)
        assert websocket.receive_json()["code"] == "AUTH_FAILED"

    websocket, ready = connect_and_attach(client, created)
    assert ready["profile_id"] == "test.passthrough.v1"
    close_websocket(websocket)


def test_passthrough_preserves_payload_and_frame_identity(
    client: TestClient,
    create_session,
) -> None:
    created = create_session("test.passthrough.v1")
    websocket, ready = connect_and_attach(client, created)
    try:
        assert ready["profile_hash"] == created["profile_hash"]
        websocket.send_json(
            control("generation.start", created, "start-0", generation_id=0)
        )
        started = websocket.receive_json()
        assert started["type"] == "generation.ready"
        assert started["pipeline_id"] == ready["pipeline_id"]

        source = input_frame(0, 0, 0.375)
        websocket.send_bytes(source.encode())
        output = PcmFrame.decode(websocket.receive_bytes())
        assert output.header.kind is FrameKind.OUTPUT
        assert output.header.generation_id == source.header.generation_id
        assert output.header.sequence == source.header.sequence
        assert output.header.source_monotonic_ns == source.header.source_monotonic_ns
        assert output.payload == source.payload

        websocket.send_json(
            control("generation.end", created, "end-0", generation_id=0)
        )
        completed = websocket.receive_json()
        assert completed["type"] == "generation.completed"
        websocket.send_json(
            control("generation.end", created, "end-0", generation_id=0)
        )
        assert websocket.receive_json() == completed
    finally:
        close_websocket(websocket)


def test_gain_profile_applies_canonical_configuration(
    client: TestClient,
    create_session,
) -> None:
    created = create_session("test.gain.v1")
    websocket, ready = connect_and_attach(client, created)
    try:
        assert ready["configuration_hash"] == created["configuration_hash"]
        websocket.send_json(
            control("generation.start", created, "start-1", generation_id=1)
        )
        websocket.receive_json()
        source = input_frame(1, 0, 0.8)
        websocket.send_bytes(source.encode())
        output = PcmFrame.decode(websocket.receive_bytes())
        assert output.unpack_samples() == pytest.approx([0.4] * 960)
    finally:
        close_websocket(websocket)


def test_gateway_conversion_never_uses_the_shared_thread_executor(
    client: TestClient,
    create_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_to_thread(*args, **kwargs):
        raise AssertionError(f"unexpected asyncio.to_thread call: {args!r} {kwargs!r}")

    monkeypatch.setattr(asyncio, "to_thread", forbidden_to_thread)
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-process", generation_id=1)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        source = input_frame(1, 0, 0.25)
        websocket.send_bytes(source.encode())
        assert PcmFrame.decode(websocket.receive_bytes()).payload == source.payload
    finally:
        close_websocket(websocket)


def test_gateway_pumps_a_full_worker_batch_before_waiting_for_output(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "batch-25")
    profile = client.app.state.gateway.registry.get_selectable("test.passthrough.v1")
    assert profile is not None
    profile.timeouts.first_output_ms = 2_000
    profile.timeouts.stall_ms = 2_000
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-batch", generation_id=4)
        )
        assert websocket.receive_json()["type"] == "generation.ready"

        for sequence in range(25):
            websocket.send_bytes(input_frame(4, sequence, sequence / 100).encode())
        outputs = [PcmFrame.decode(websocket.receive_bytes()) for _ in range(25)]
        assert [frame.header.sequence for frame in outputs] == list(range(25))
        assert supervisors[-1].queued_input_frames == 0

        websocket.send_json(
            control("generation.end", created, "end-batch", generation_id=4)
        )
        assert websocket.receive_json()["type"] == "generation.completed"
    finally:
        close_websocket(websocket)


def test_gateway_holds_a_50_frame_ingress_tail_outside_a_delayed_worker_batch(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_delayed_batch_worker(client)
    profile = client.app.state.gateway.registry.get_selectable("test.passthrough.v1")
    assert profile is not None
    profile.minimum_context_ms = 500
    profile.timeouts.first_output_ms = 2_000
    profile.timeouts.stall_ms = 2_000
    created = create_session()
    assert created["limits"] == {"ingress_budget_ms": 1_000, "max_ingress_frames": 50}
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-delayed", generation_id=8)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(28):
            websocket.send_bytes(input_frame(8, sequence, 0.1).encode())

        supervisor = wait_for_worker_queue(supervisors, minimum=25)
        connection = client.app.state.gateway.connections[created["session_id"]]
        assert supervisor.maximum_queued_input_frames == 25
        assert client.portal is not None
        assert client.portal.call(connection.ingress.qsize) == 3
        assert client.portal.call(lambda: connection.pending_ingress_frames) == 28

        client.portal.call(supervisor.release_first_batch)
        websocket.send_json(
            control("generation.end", created, "end-delayed", generation_id=8)
        )
        outputs = [PcmFrame.decode(websocket.receive_bytes()) for _ in range(28)]
        assert [frame.header.sequence for frame in outputs] == list(range(28))
        assert supervisor.maximum_queued_input_frames == 25
        assert websocket.receive_json()["type"] == "generation.completed"
    finally:
        close_websocket(websocket)


def test_cancel_unblocks_a_worker_capacity_wait_and_next_generation_is_healthy(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_delayed_batch_worker(client)
    profile = client.app.state.gateway.registry.get_selectable("test.passthrough.v1")
    assert profile is not None
    profile.minimum_context_ms = 500
    profile.timeouts.first_output_ms = 2_000
    profile.timeouts.stall_ms = 2_000
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-wait", generation_id=9)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(28):
            websocket.send_bytes(input_frame(9, sequence, 0.1).encode())
        supervisor = wait_for_worker_queue(supervisors, minimum=25)

        started = time.monotonic()
        websocket.send_json(
            control("generation.cancel", created, "cancel-wait", generation_id=9)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"
        assert time.monotonic() - started < 1

        websocket.send_json(
            control("generation.start", created, "start-after-wait", generation_id=10)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(25):
            websocket.send_bytes(input_frame(10, sequence, 0.2).encode())
        wait_for_worker_queue([supervisor], minimum=25)
        assert client.portal is not None
        client.portal.call(supervisor.release_first_batch)
        websocket.send_json(
            control("generation.end", created, "end-after-wait", generation_id=10)
        )
        outputs = [PcmFrame.decode(websocket.receive_bytes()) for _ in range(25)]
        assert {frame.header.generation_id for frame in outputs} == {10}
        assert [frame.header.sequence for frame in outputs] == list(range(25))
        assert websocket.receive_json()["type"] == "generation.completed"
    finally:
        close_websocket(websocket)


def test_generation_end_flushes_a_partial_worker_batch_before_completion(
    client: TestClient,
    create_session,
) -> None:
    install_fake_worker(client, "batch-25")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-partial", generation_id=5)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(4):
            websocket.send_bytes(input_frame(5, sequence, 0.1 * sequence).encode())
        websocket.send_json(
            control("generation.end", created, "end-partial", generation_id=5)
        )

        outputs = [PcmFrame.decode(websocket.receive_bytes()) for _ in range(4)]
        assert [frame.header.sequence for frame in outputs] == [0, 1, 2, 3]
        assert websocket.receive_json()["type"] == "generation.completed"
    finally:
        close_websocket(websocket)


def test_cancel_discards_a_partial_worker_batch_before_the_next_generation(
    client: TestClient,
    create_session,
) -> None:
    install_fake_worker(client, "batch-25")
    profile = client.app.state.gateway.registry.get_selectable("test.passthrough.v1")
    assert profile is not None
    profile.timeouts.first_output_ms = 2_000
    profile.timeouts.stall_ms = 2_000
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-cancel", generation_id=6)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(5):
            websocket.send_bytes(input_frame(6, sequence, 0.6).encode())
        websocket.send_json(
            control("generation.cancel", created, "cancel-batch", generation_id=6)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"

        websocket.send_json(
            control("generation.start", created, "start-next", generation_id=7)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        for sequence in range(25):
            websocket.send_bytes(input_frame(7, sequence, 0.7).encode())
        outputs = [PcmFrame.decode(websocket.receive_bytes()) for _ in range(25)]
        assert {frame.header.generation_id for frame in outputs} == {7}
        assert [frame.header.sequence for frame in outputs] == list(range(25))
    finally:
        close_websocket(websocket)


def test_model_switch_is_generation_bound_and_idempotent(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, ready = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-2", generation_id=2)
        )
        websocket.receive_json()
        select = control(
            "model.select",
            created,
            "select-gain",
            profile_id="test.gain.v1",
        )
        websocket.send_json(select)
        error = websocket.receive_json()
        assert error["code"] == "INVALID_STATE"

        websocket.send_json(
            control("generation.cancel", created, "cancel-2", generation_id=2)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"
        websocket.send_json(select)
        assert websocket.receive_json() == error

        select = control(
            "model.select",
            created,
            "select-gain-after-cancel",
            profile_id="test.gain.v1",
        )
        websocket.send_json(select)
        selected = websocket.receive_json()
        assert selected["type"] == "model.selected"
        assert selected["pipeline_id"] != ready["pipeline_id"]
        assert selected["configuration_hash"] != ready["configuration_hash"]

        websocket.send_json(select)
        assert websocket.receive_json() == selected

        websocket.send_json(
            control(
                "model.select",
                created,
                "select-gain-after-cancel",
                profile_id="test.passthrough.v1",
            )
        )
        assert websocket.receive_json()["code"] == "INVALID_STATE"
    finally:
        close_websocket(websocket)


def test_failed_request_id_replays_first_outcome_after_state_changes(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    failed_start = control(
        "generation.start",
        created,
        "start-51-while-active",
        generation_id=51,
    )
    try:
        websocket.send_json(
            control("generation.start", created, "start-50", generation_id=50)
        )
        websocket.receive_json()
        websocket.send_json(failed_start)
        first_error = websocket.receive_json()
        assert first_error["code"] == "INVALID_STATE"

        websocket.send_json(
            control("generation.cancel", created, "cancel-50", generation_id=50)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"
        websocket.send_json(failed_start)
        assert websocket.receive_json() == first_error

        websocket.send_json(
            control("generation.start", created, "start-52", generation_id=52)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
    finally:
        close_websocket(websocket)


def test_gap_stale_and_cancel_never_emit_late_audio(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-3", generation_id=3)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(3, 0).encode())
        assert PcmFrame.decode(websocket.receive_bytes()).header.sequence == 0

        websocket.send_bytes(input_frame(3, 2).encode())
        error = websocket.receive_json()
        fallback = websocket.receive_json()
        assert error["code"] == "SEQUENCE_GAP"
        assert fallback["type"] == "fallback.required"
        assert fallback["generation_id"] == 3

        websocket.send_json(
            control("generation.start", created, "start-4", generation_id=4)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        websocket.send_bytes(input_frame(3, 1).encode())
        assert websocket.receive_json()["code"] == "STALE_GENERATION"
        websocket.send_json(
            control(
                "ping",
                created,
                "ping-after-stale",
                client_monotonic_ns=10,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"

        websocket.send_json(
            control("generation.cancel", created, "cancel-4", generation_id=4)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"
        websocket.send_bytes(input_frame(4, 0).encode())
        assert websocket.receive_json()["code"] == "STALE_GENERATION"
        websocket.send_json(
            control(
                "ping",
                created,
                "ping-after-cancel",
                client_monotonic_ns=11,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
    finally:
        close_websocket(websocket)


@pytest.mark.parametrize("sample", [math.nan, math.inf, -math.inf, 1.01, -1.01])
def test_invalid_pcm_requires_fallback(
    client: TestClient,
    create_session,
    sample: float,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-5", generation_id=5)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(5, 0, sample).encode())
        error = websocket.receive_json()
        fallback = websocket.receive_json()
        assert error["code"] == "UNSUPPORTED_AUDIO"
        assert error["required_action"] == "fallback"
        assert fallback["type"] == "fallback.required"
    finally:
        close_websocket(websocket)


def test_session_close_invalidates_http_session(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    session = client.app.state.gateway.store.get(created["session_id"])
    assert session is not None
    websocket.send_json(control("session.close", created, "close-1"))
    assert websocket.receive_json()["type"] == "session.closed"
    with pytest.raises(WebSocketDisconnect):
        websocket.receive_json()
    close_websocket(websocket)
    assert created["session_id"] not in client.app.state.gateway.connections
    assert client.app.state.gateway.store.get(created["session_id"]) is None
    assert session.deleted
    assert session.ticket_digest == b""
    assert session.request_cache == {}


def test_session_close_cancels_drain_before_generation_invalidation(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    connection = client.app.state.gateway.connections[created["session_id"]]
    entered = asyncio.Event()
    release = asyncio.Event()
    original_abort = connection.abort_generation

    async def gated_end(generation_id: int) -> None:
        del generation_id
        entered.set()
        await release.wait()

    async def releasing_abort(generation_id: int) -> None:
        release.set()
        await original_abort(generation_id)

    connection.worker_bridge.end_generation = gated_end  # type: ignore[method-assign]
    connection.abort_generation = releasing_abort  # type: ignore[method-assign]
    websocket.send_json(
        control("generation.start", created, "start-close-race", generation_id=19)
    )
    assert websocket.receive_json()["type"] == "generation.ready"
    websocket.send_json(
        control("generation.end", created, "end-close-race", generation_id=19)
    )
    assert client.portal is not None
    client.portal.call(entered.wait)
    websocket.send_json(control("session.close", created, "close-race"))
    assert websocket.receive_json()["type"] == "session.closed"
    with pytest.raises(WebSocketDisconnect):
        websocket.receive_json()
    close_websocket(websocket)
    assert created["session_id"] not in client.app.state.gateway.connections
    assert client.app.state.gateway.store.get(created["session_id"]) is None


def test_end_drain_can_be_canceled_and_end_replay_is_terminal(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "stalled")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    connection = client.app.state.gateway.connections[created["session_id"]]
    end = control("generation.end", created, "end-cancel", generation_id=20)
    try:
        websocket.send_json(
            control("generation.start", created, "start-20", generation_id=20)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(20, 0).encode())
        wait_for_worker_queue(supervisors)
        websocket.send_json(end)
        websocket.send_json(
            control("generation.cancel", created, "cancel-20", generation_id=20)
        )
        canceled = websocket.receive_json()
        assert canceled["type"] == "generation.canceled"
        assert canceled["request_id"] == "cancel-20"
        wait_for_ingress(client, connection)

        websocket.send_json(end)
        replay = websocket.receive_json()
        assert replay["type"] == "generation.canceled"
        assert replay["request_id"] == "end-cancel"

        websocket.send_json(
            control(
                "ping",
                created,
                "ping-after-drain-cancel",
                client_monotonic_ns=20,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
    finally:
        close_websocket(websocket)


def test_late_worker_failure_after_cancel_is_suppressed(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "cancellation-race")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    connection = client.app.state.gateway.connections[created["session_id"]]
    try:
        websocket.send_json(
            control("generation.start", created, "start-23", generation_id=23)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(23, 0).encode())
        supervisor = wait_for_worker_queue(supervisors)
        websocket.send_json(
            control("generation.end", created, "end-23", generation_id=23)
        )
        cancel = control(
            "generation.cancel",
            created,
            "cancel-23",
            generation_id=23,
        )
        websocket.send_json(cancel)
        canceled = websocket.receive_json()
        assert canceled["type"] == "generation.canceled"
        websocket.send_json(cancel)
        assert websocket.receive_json() == canceled

        wait_for_ingress(client, connection)
        assert client.portal is not None
        client.portal.call(supervisor.health)
        assert supervisor.take_output_nowait() is None
        assert connection.generation_failures == {}
        websocket.send_json(
            control(
                "ping",
                created,
                "late-failure-barrier",
                client_monotonic_ns=23,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
    finally:
        close_websocket(websocket)


def test_canceled_output_waiter_cannot_steal_the_next_generation(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "one-output-then-stall")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-60", generation_id=60)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        websocket.send_bytes(input_frame(60, 0, 0.2).encode())
        assert PcmFrame.decode(websocket.receive_bytes()).header.sequence == 0

        websocket.send_bytes(input_frame(60, 1, 0.3).encode())
        wait_for_worker_queue(supervisors)
        websocket.send_json(
            control("generation.cancel", created, "cancel-60", generation_id=60)
        )
        assert websocket.receive_json()["type"] == "generation.canceled"

        websocket.send_json(
            control("generation.start", created, "start-61", generation_id=61)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        source = input_frame(61, 0, 0.4)
        websocket.send_bytes(source.encode())
        output = PcmFrame.decode(websocket.receive_bytes())
        assert output.header.generation_id == 61
        assert output.header.sequence == 0
        assert output.payload == source.payload
    finally:
        close_websocket(websocket)


def test_worker_failure_during_drain_is_correlated_and_never_completes(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "stalled")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    end = control("generation.end", created, "end-failed", generation_id=21)
    try:
        websocket.send_json(
            control("generation.start", created, "start-21", generation_id=21)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(21, 0).encode())
        supervisor = wait_for_worker_queue(supervisors)
        websocket.send_json(end)
        websocket.send_json(
            control(
                "ping",
                created,
                "end-failure-barrier",
                client_monotonic_ns=21,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
        process_group_id = supervisor.process_group_id
        assert process_group_id is not None
        os.killpg(process_group_id, signal.SIGKILL)

        failure = websocket.receive_json()
        fallback = websocket.receive_json()
        websocket.send_json(
            control("generation.start", created, "start-22", generation_id=22)
        )
        correlated = websocket.receive_json()
        restarted = websocket.receive_json()
        assert failure["code"] == "WORKER_CRASH"
        assert failure["required_action"] == "fallback"
        assert fallback["type"] == "fallback.required"
        assert correlated["code"] == "WORKER_CRASH"
        assert correlated["request_id"] == "end-failed"
        assert correlated["required_action"] == "fallback"
        assert restarted["type"] == "generation.ready", restarted
        assert restarted["generation_id"] == 22

        websocket.send_json(end)
        assert websocket.receive_json() == correlated
    finally:
        close_websocket(websocket)


def test_worker_error_details_are_not_exposed_to_remote_client(
    client: TestClient,
    create_session,
) -> None:
    install_fake_worker(client, "sensitive-start-error")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-sensitive", generation_id=24)
        )
        error = websocket.receive_json()
        encoded = str(error)
        assert error["code"] == "WORKER_CRASH"
        assert error["message"] == "profile worker failed"
        assert "/private/cache" not in encoded
        assert "credential=secret" not in encoded
    finally:
        close_websocket(websocket)


class _BlockedOutboundWebSocket:
    async def send_text(self, data: str) -> None:
        del data
        await asyncio.Event().wait()

    async def send_bytes(self, data: bytes) -> None:
        del data
        await asyncio.Event().wait()

    async def close(self, code: int = 1000) -> None:
        del code


class _DisconnectedOutboundWebSocket:
    async def send_text(self, data: str) -> None:
        del data
        raise RuntimeError("client disconnected")

    async def send_bytes(self, data: bytes) -> None:
        del data
        raise RuntimeError("client disconnected")

    async def close(self, code: int = 1000) -> None:
        del code


class _PendingAttachmentWebSocket:
    def __init__(self) -> None:
        self.headers = {"origin": ORIGIN_HEADERS["Origin"]}
        self.accepted = asyncio.Event()
        self.release = asyncio.Event()
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted.set()

    async def receive(self) -> dict[str, object]:
        await self.release.wait()
        return {"type": "websocket.disconnect"}

    async def send_text(self, data: str) -> None:
        del data

    async def close(self, code: int = 1000, reason: str = "") -> None:
        del reason
        self.close_code = code


@pytest.mark.asyncio
async def test_pending_attachment_capacity_is_bounded_before_accept(
    settings,
) -> None:
    bounded = replace(settings, max_pending_attachments=1)
    gateway = create_app(bounded).state.gateway
    first = _PendingAttachmentWebSocket()
    first_task = asyncio.create_task(gateway.websocket(first))  # type: ignore[arg-type]
    await asyncio.wait_for(first.accepted.wait(), timeout=1)
    assert gateway.pending_attachments == 1

    second = _PendingAttachmentWebSocket()
    await gateway.websocket(second)  # type: ignore[arg-type]
    assert not second.accepted.is_set()
    assert second.close_code == 4429
    assert gateway.pending_attachments == 1

    first.release.set()
    await asyncio.wait_for(first_task, timeout=1)
    assert gateway.pending_attachments == 0


def test_output_disconnect_retrieves_pump_and_releases_session(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    connection = client.app.state.gateway.connections[created["session_id"]]
    try:
        websocket.send_json(
            control("generation.start", created, "start-disconnect", generation_id=25)
        )
        assert websocket.receive_json()["type"] == "generation.ready"
        output_task = connection.output_task
        assert output_task is not None
        connection.websocket = _DisconnectedOutboundWebSocket()  # type: ignore[assignment]

        websocket.send_bytes(input_frame(25, 0).encode())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not output_task.done():
            time.sleep(0.005)
        assert output_task.done()
        assert output_task.exception() is None

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if created["session_id"] not in client.app.state.gateway.connections:
                break
            time.sleep(0.005)
        assert created["session_id"] not in client.app.state.gateway.connections
        assert client.app.state.gateway.store.get(created["session_id"]) is None
    finally:
        close_websocket(websocket)


def test_outbound_send_timeout_wakes_route_and_releases_session(
    settings,
) -> None:
    bounded = replace(settings, send_timeout_seconds=0.02)
    with TestClient(create_app(bounded)) as client:
        created = create_http_session(client)
        websocket, _ = connect_and_attach(client, created)
        connection = client.app.state.gateway.connections[created["session_id"]]
        connection.websocket = _BlockedOutboundWebSocket()  # type: ignore[assignment]
        event = connection.error_event(
            ProtocolValidationError(ErrorCode.WORKER_CRASH, "internal test detail")
        )
        assert client.portal is not None
        with pytest.raises(ProtocolValidationError, match="send deadline expired"):
            client.portal.call(connection.send_event, event)

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if created["session_id"] not in client.app.state.gateway.connections:
                break
            time.sleep(0.005)
        assert created["session_id"] not in client.app.state.gateway.connections
        assert client.app.state.gateway.store.get(created["session_id"]) is None
        close_websocket(websocket)


def test_worker_timeout_requires_fallback(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "stalled")
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-22", generation_id=22)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(22, 0).encode())
        supervisor = wait_for_worker_queue(supervisors)
        process_group_id = supervisor.process_group_id
        assert process_group_id is not None
        error = websocket.receive_json()
        fallback = websocket.receive_json()
        assert error["code"] == "MODEL_TIMEOUT"
        assert error["required_action"] == "fallback"
        assert fallback["type"] == "fallback.required"
        wait_for_process_group_exit(process_group_id)
    finally:
        close_websocket(websocket)


def test_http_delete_active_connection_is_silent_and_terminal(
    client: TestClient,
    create_session,
) -> None:
    supervisors = install_fake_worker(client, "stalled")
    profile = client.app.state.gateway.registry.get_selectable("test.passthrough.v1")
    assert profile is not None
    profile.timeouts.first_output_ms = 2_000
    profile.timeouts.stall_ms = 2_000
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    connection = client.app.state.gateway.connections[created["session_id"]]
    try:
        websocket.send_json(
            control("generation.start", created, "start-delete", generation_id=30)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(30, 0).encode())
        supervisor = wait_for_worker_queue(supervisors)
        process_group_id = supervisor.process_group_id
        assert process_group_id is not None
        websocket.send_bytes(input_frame(30, 1).encode())
        websocket.send_bytes(input_frame(30, 2).encode())
        websocket.send_json(
            control(
                "ping",
                created,
                "delete-barrier",
                client_monotonic_ns=30,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
        assert connection.pending_ingress_frames == 3

        path = f"/v1/sessions/{created['session_id']}"
        assert client.delete(path, headers=AUTH_HEADERS).status_code == 204
        assert client.delete(path, headers=AUTH_HEADERS).status_code == 404
        assert connection.worker_task is not None and connection.worker_task.done()
        assert connection.pending_ingress_frames == 0
        assert connection.ingress.empty()
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()
        assert created["session_id"] not in client.app.state.gateway.connections
        assert client.app.state.gateway.store.get(created["session_id"]) is None
        wait_for_process_group_exit(process_group_id)
    finally:
        close_websocket(websocket)


def test_ingress_capacity_counts_inflight_frames_and_clears_rejected_generation(
    settings,
) -> None:
    bounded = replace(settings, ingress_budget_ms=40)
    supervisors: list[WorkerSupervisor] = []
    factory = fake_worker_factory("one-output-then-stall", supervisors)
    with TestClient(create_app(bounded, worker_supervisor_factory=factory)) as client:
        profile = client.app.state.gateway.registry.get_selectable(
            "test.passthrough.v1"
        )
        assert profile is not None
        profile.timeouts.first_output_ms = 2_000
        profile.timeouts.stall_ms = 2_000
        created = create_http_session(client)
        assert created["limits"]["max_ingress_frames"] == 2
        websocket, _ = connect_and_attach(client, created)
        connection = client.app.state.gateway.connections[created["session_id"]]
        try:
            websocket.send_json(
                control("generation.start", created, "start-31", generation_id=31)
            )
            websocket.receive_json()
            websocket.send_bytes(input_frame(31, 0).encode())
            assert PcmFrame.decode(websocket.receive_bytes()).header.sequence == 0
            websocket.send_bytes(input_frame(31, 1).encode())
            wait_for_worker_queue(supervisors)
            websocket.send_bytes(input_frame(31, 2).encode())
            websocket.send_json(
                control(
                    "ping",
                    created,
                    "capacity-barrier",
                    client_monotonic_ns=31,
                    clock_id="test-clock",
                )
            )
            assert websocket.receive_json()["type"] == "pong"
            assert connection.pending_ingress_frames == 2

            websocket.send_bytes(input_frame(31, 3).encode())
            error = websocket.receive_json()
            fallback = websocket.receive_json()
            assert error["code"] == "QUEUE_OVERFLOW"
            assert fallback["type"] == "fallback.required"
            assert connection.pending_ingress_frames == 0

            wait_for_ingress(client, connection)
            assert connection.pending_ingress_frames == 0
            assert connection.ingress.empty()
            websocket.send_json(
                control(
                    "ping",
                    created,
                    "capacity-release-barrier",
                    client_monotonic_ns=32,
                    clock_id="test-clock",
                )
            )
            assert websocket.receive_json()["type"] == "pong"
        finally:
            close_websocket(websocket)


def test_request_cache_hard_cap_closes_connection(settings) -> None:
    bounded = replace(settings, request_cache_max=1)
    with TestClient(create_app(bounded)) as client:
        created = create_http_session(client)
        websocket, _ = connect_and_attach(client, created)
        session = client.app.state.gateway.store.get(created["session_id"])
        assert session is not None
        websocket.send_json(
            control(
                "ping",
                created,
                "ping-one",
                client_monotonic_ns=1,
                clock_id="test-clock",
            )
        )
        assert websocket.receive_json()["type"] == "pong"
        websocket.send_json(
            control(
                "ping",
                created,
                "ping-two",
                client_monotonic_ns=2,
                clock_id="test-clock",
            )
        )
        error = websocket.receive_json()
        assert error["required_action"] == "close_session"
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()
        close_websocket(websocket)
        assert created["session_id"] not in client.app.state.gateway.connections
        assert client.app.state.gateway.store.get(created["session_id"]) is None
        assert session.request_cache == {}


def test_oversize_and_decreasing_timestamp_require_fallback(
    client: TestClient,
    create_session,
) -> None:
    created = create_session()
    websocket, _ = connect_and_attach(client, created)
    try:
        websocket.send_json(
            control("generation.start", created, "start-40", generation_id=40)
        )
        websocket.receive_json()
        websocket.send_bytes(b"x" * (16 * 1024 + 1))
        assert websocket.receive_json()["required_action"] == "fallback"
        assert websocket.receive_json()["type"] == "fallback.required"

        websocket.send_json(
            control("generation.start", created, "start-41", generation_id=41)
        )
        websocket.receive_json()
        websocket.send_bytes(input_frame(41, 0, source_monotonic_ns=2_000_000).encode())
        websocket.receive_bytes()
        websocket.send_bytes(input_frame(41, 1, source_monotonic_ns=2_000_000).encode())
        assert PcmFrame.decode(websocket.receive_bytes()).header.sequence == 1
        websocket.send_bytes(input_frame(41, 2, source_monotonic_ns=1_999_999).encode())
        error = websocket.receive_json()
        fallback = websocket.receive_json()
        assert error["field"] == "source_monotonic_ns"
        assert error["required_action"] == "fallback"
        assert fallback["type"] == "fallback.required"
    finally:
        close_websocket(websocket)
