from __future__ import annotations

import asyncio

import pytest

from workers.runtime import ArtifactSpec
from workers.runtime.errors import WorkerRuntimeError

from ._support import FIXTURE, make_frame, make_profile, run_async


def assert_runtime_error(
    raised: pytest.ExceptionInfo[WorkerRuntimeError], code: str
) -> None:
    assert raised.value.code == code


def test_hello_readiness_health_and_clean_close() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("passthrough")
        with pytest.raises(WorkerRuntimeError) as before_ready:
            await supervisor.push_audio(make_frame())
        assert_runtime_error(before_ready, "INVALID_STATE")

        ready = await supervisor.start()
        assert ready.profile_id == FIXTURE["profile"]["profile_id"]
        assert ready.pipeline_id == FIXTURE["profile"]["pipeline_id"]
        assert ready.implementation_revision == "fake-worker-v1"
        assert ready.weight_revision is None
        assert ready.configuration_hash == FIXTURE["profile"]["configuration_hash"]

        health = await supervisor.health()
        assert health.ready is True
        assert health.active_generation_id is None
        assert health.queue_depth_frames == 0
        assert health.capacity_frames == 25
        assert supervisor.available is True
        assert supervisor.pid is not None

        await supervisor.close()
        assert supervisor.available is False
        assert supervisor.pid is None
        await supervisor.close()

    run_async(scenario())


def test_close_serializes_with_start_before_process_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile(
            "passthrough",
            artifacts=(
                ArtifactSpec(
                    env_var="LIVECONV_TEST_ARTIFACT_PATH",
                    sha256="0" * 64,
                ),
            ),
            environment={"LIVECONV_TEST_ARTIFACT_PATH": "/delayed/test"},
        )
        verification_entered = asyncio.Event()
        release_verification = asyncio.Event()

        async def delayed_verification() -> dict[str, str]:
            verification_entered.set()
            await release_verification.wait()
            return {}

        monkeypatch.setattr(supervisor, "_verify_artifacts", delayed_verification)
        start_task = asyncio.create_task(supervisor.start())
        await verification_entered.wait()
        close_task = asyncio.create_task(supervisor.close())
        await asyncio.sleep(0)
        assert not close_task.done()

        release_verification.set()
        await start_task
        await close_task

        assert supervisor.available is False
        assert supervisor.pid is None
        assert supervisor.process_group_id is None
        with pytest.raises(WorkerRuntimeError) as after_close:
            await supervisor.start()
        assert_runtime_error(after_close, "INVALID_STATE")

    run_async(scenario())


@pytest.mark.parametrize(
    ("mode", "gain"),
    [("passthrough", None), ("gain", FIXTURE["gain"])],
)
def test_passthrough_and_gain_round_trip(mode: str, gain: float | None) -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile(mode, gain=gain)
        source = make_frame()
        try:
            await supervisor.start()
            await supervisor.start_generation(source.generation_id)
            await supervisor.push_audio(source)
            output = await supervisor.next_output()

            assert output.generation_id == source.generation_id
            assert output.sequence == source.sequence
            assert output.sample_rate == source.sample_rate
            assert output.channels == source.channels
            assert output.samples_per_channel == source.samples_per_channel
            assert output.source_monotonic_ns == source.source_monotonic_ns
            if gain is None:
                assert output.pcm_f32le == source.pcm_f32le
            else:
                assert output.unpack_samples() == pytest.approx(
                    tuple(sample * gain for sample in source.unpack_samples())
                )

            completed = await supervisor.end_generation(source.generation_id)
            assert completed.generation_id == source.generation_id
        finally:
            await supervisor.close()

    run_async(scenario())


def test_generation_end_drains_all_accepted_input_asynchronously() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("delayed")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(sequence=0))
            await supervisor.push_audio(make_frame(sequence=1))

            end_task = asyncio.create_task(supervisor.end_generation(generation_id))
            completed = await end_task
            outputs = [await supervisor.next_output(), await supervisor.next_output()]

            assert completed.generation_id == generation_id
            assert [output.sequence for output in outputs] == [0, 1]
            assert supervisor.queued_input_frames == 0
        finally:
            await supervisor.close()

    run_async(scenario())


def test_worker_output_must_follow_accepted_sequence_order() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("reverse-order", restart_limit=0)
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(sequence=0))
            await supervisor.push_audio(make_frame(sequence=1))

            with pytest.raises(WorkerRuntimeError) as raised:
                await supervisor.next_output()
            assert raised.value.code == "WORKER_PROTOCOL"
            assert supervisor.take_output_nowait() is None
            assert supervisor.available is False
        finally:
            await supervisor.close()

    run_async(scenario())


def test_cancel_is_immediate_and_suppresses_output_emitted_after_ack() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("cancellation-race")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame())

            canceled = await supervisor.cancel_generation(generation_id)
            assert canceled.generation_id == generation_id

            # Health is a protocol FIFO barrier after the fake worker's late output.
            health = await supervisor.health()
            assert health.active_generation_id is None
            assert supervisor.take_output_nowait() is None
            assert supervisor.queued_input_frames == 0
        finally:
            await supervisor.close()

    run_async(scenario())


def test_cancel_discards_output_already_queued_before_ack() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("passthrough")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(sequence=0))
            await supervisor.push_audio(make_frame(sequence=1))
            await supervisor.health()

            await supervisor.cancel_generation(generation_id)
            assert supervisor.take_output_nowait() is None

            next_generation_id = generation_id + 1
            await supervisor.start_generation(next_generation_id)
            source = make_frame(generation_id=next_generation_id)
            await supervisor.push_audio(source)
            output = await supervisor.next_output()
            assert output.generation_id == next_generation_id
            assert output.pcm_f32le == source.pcm_f32le
        finally:
            await supervisor.close()

    run_async(scenario())


def test_canceling_output_waiter_cannot_steal_next_generation_output() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("stalled-until-cancel")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(generation_id=generation_id))

            pending_output = asyncio.create_task(supervisor.next_output())
            await asyncio.sleep(0)
            pending_output.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending_output

            await supervisor.cancel_generation(generation_id)
            next_generation_id = generation_id + 1
            await supervisor.start_generation(next_generation_id)
            source = make_frame(generation_id=next_generation_id)
            await supervisor.push_audio(source)

            output = await supervisor.next_output()
            assert output.generation_id == next_generation_id
            assert output.sequence == source.sequence
            assert output.pcm_f32le == source.pcm_f32le
        finally:
            await supervisor.close()

    run_async(scenario())


def test_worker_input_queue_is_bounded_to_500_ms_without_frame_eviction() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("stalled")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            assert supervisor.input_capacity_frames == 25

            for sequence in range(supervisor.input_capacity_frames):
                await supervisor.push_audio(make_frame(sequence=sequence))
            assert supervisor.queued_input_frames == 25

            with pytest.raises(WorkerRuntimeError) as overflow:
                await supervisor.push_audio(make_frame(sequence=25))
            assert_runtime_error(overflow, "QUEUE_OVERFLOW")
            assert overflow.value.recoverable is True
            assert supervisor.take_output_nowait() is None
        finally:
            await supervisor.close()

    run_async(scenario())
