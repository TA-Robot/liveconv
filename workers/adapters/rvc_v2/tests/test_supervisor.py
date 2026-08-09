from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from workers.adapters.rvc_v2.backend import TEST_CONFIGURATION_HASH
from workers.runtime import AudioFrame, WorkerProfile, WorkerSupervisor
from workers.runtime.errors import WorkerRuntimeError

ROOT = Path(__file__).resolve().parents[4]


def profile(*, configuration_hash: str = TEST_CONFIGURATION_HASH) -> WorkerProfile:
    return WorkerProfile(
        profile_id="rvc-v2.conformance",
        pipeline_id="00000000-0000-0000-0000-000000000002",
        configuration_hash=configuration_hash,
        command=(
            sys.executable,
            "-m",
            "workers.adapters.rvc_v2.worker",
            "--test-backend",
        ),
        cwd=ROOT,
        environment={
            "LIVECONV_ENABLE_TEST_BACKEND": "1",
            "PATH": os.environ["PATH"],
        },
        implementation_revision="rvc-v2-test-backend",
        weight_revision="sha256:" + "0" * 64,
        frame_ms=20,
        queue_budget_ms=500,
        startup_timeout_ms=5_000,
        first_output_timeout_ms=5_000,
        stall_timeout_ms=5_000,
        cancel_timeout_ms=1_000,
        close_grace_ms=1_000,
        terminate_grace_ms=500,
    )


def audio_frame(sequence: int = 0, generation_id: int = 1) -> AudioFrame:
    return AudioFrame.from_samples(
        generation_id=generation_id,
        sequence=sequence,
        sample_rate=16_000,
        channels=1,
        samples_per_channel=320,
        source_monotonic_ns=sequence * 20_000_000,
        samples=[0.25] * 320,
    )


def run(coroutine: object) -> object:
    async def bounded() -> object:
        return await asyncio.wait_for(coroutine, 10)  # type: ignore[arg-type]

    return asyncio.run(bounded())


def test_supervisor_round_trip_health_and_close() -> None:
    async def scenario() -> None:
        supervisor = WorkerSupervisor(profile())
        try:
            ready = await supervisor.start()
            assert ready.implementation_revision == "rvc-v2-test-backend"
            health = await supervisor.health()
            assert health.ready is True
            assert health.capacity_frames == 50

            source = audio_frame()
            await supervisor.start_generation(source.generation_id)
            await supervisor.push_audio(source)
            end = asyncio.create_task(supervisor.end_generation(source.generation_id))
            output = await supervisor.next_output()
            await end
            assert output.unpack_samples() == pytest.approx((-0.125,) * 320)
            assert output.sequence == source.sequence
            assert output.source_monotonic_ns == source.source_monotonic_ns
        finally:
            await supervisor.close()

    run(scenario())


def test_supervisor_cancel_clears_pending_audio() -> None:
    async def scenario() -> None:
        supervisor = WorkerSupervisor(profile())
        try:
            await supervisor.start()
            await supervisor.start_generation(3)
            await supervisor.push_audio(audio_frame(generation_id=3))
            result = await supervisor.cancel_generation(3)
            assert result.generation_id == 3
            assert supervisor.queued_input_frames == 0
            assert supervisor.take_output_nowait() is None
        finally:
            await supervisor.close()

    run(scenario())


def test_supervisor_rejects_unbound_configuration_hash() -> None:
    async def scenario() -> None:
        supervisor = WorkerSupervisor(profile(configuration_hash="sha256:" + "1" * 64))
        try:
            with pytest.raises(WorkerRuntimeError) as mismatch:
                await supervisor.start()
            assert mismatch.value.code == "MODEL_UNAVAILABLE"
        finally:
            await supervisor.close()

    run(scenario())
