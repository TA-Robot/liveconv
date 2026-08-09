from __future__ import annotations

import asyncio
import math
import os
import struct
import sys
import wave
from pathlib import Path

import pytest

from workers.adapters.beatrice_2.backend import BeatriceConfiguration
from workers.runtime import ArtifactSpec, AudioFrame, WorkerProfile, WorkerSupervisor

ROOT = Path(__file__).resolve().parents[4]
RUN_REAL = os.environ.get("LIVECONV_RUN_BEATRICE_REAL") == "1"


def _profile(configuration: BeatriceConfiguration) -> WorkerProfile:
    names = (
        "LIVECONV_BEATRICE_SOURCE_ROOT",
        "LIVECONV_BEATRICE_SOURCE_REVISION",
        "LIVECONV_BEATRICE_SOURCE_MODULE",
        "LIVECONV_BEATRICE_SOURCE_SHA256",
        "LIVECONV_BEATRICE_SOURCE_TREE_SHA256",
        "LIVECONV_BEATRICE_PHONE_CHECKPOINT",
        "LIVECONV_BEATRICE_PHONE_SHA256",
        "LIVECONV_BEATRICE_PITCH_CHECKPOINT",
        "LIVECONV_BEATRICE_PITCH_SHA256",
        "LIVECONV_BEATRICE_CONVERTER_CHECKPOINT",
        "LIVECONV_BEATRICE_CONVERTER_SHA256",
        "LIVECONV_BEATRICE_RUNTIME_LOCK_SHA256",
        "LIVECONV_BEATRICE_WORKER_WHEEL",
        "LIVECONV_BEATRICE_WORKER_WHEEL_SHA256",
        "LIVECONV_BEATRICE_TARGET_SPEAKER_ID",
        "LIVECONV_BEATRICE_SAMPLE_RATE",
        "LIVECONV_BEATRICE_BATCH_MS",
        "LIVECONV_BEATRICE_DEVICE",
    )
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment["PATH"] = os.environ["PATH"]
    return WorkerProfile(
        profile_id="beatrice-2.official-smoke",
        pipeline_id="00000000-0000-0000-0000-000000000004",
        configuration_hash=configuration.configuration_hash,
        command=(
            os.environ.get("LIVECONV_BEATRICE_PYTHON", sys.executable),
            "-m",
            "workers.adapters.beatrice_2.worker",
        ),
        cwd=Path(os.environ.get("LIVECONV_BEATRICE_WORKER_CWD", ROOT)),
        environment=environment,
        implementation_revision=configuration.source_revision,
        weight_revision=f"sha256:{configuration.converter_sha256}",
        frame_ms=20,
        queue_budget_ms=500,
        startup_timeout_ms=60_000,
        first_output_timeout_ms=30_000,
        stall_timeout_ms=30_000,
        cancel_timeout_ms=2_000,
        close_grace_ms=5_000,
        terminate_grace_ms=1_000,
        artifacts=(
            ArtifactSpec(
                env_var="LIVECONV_BEATRICE_SOURCE_MODULE",
                sha256=configuration.source_sha256,
            ),
            ArtifactSpec(
                env_var="LIVECONV_BEATRICE_PHONE_CHECKPOINT",
                sha256=configuration.phone_sha256,
            ),
            ArtifactSpec(
                env_var="LIVECONV_BEATRICE_PITCH_CHECKPOINT",
                sha256=configuration.pitch_sha256,
            ),
            ArtifactSpec(
                env_var="LIVECONV_BEATRICE_CONVERTER_CHECKPOINT",
                sha256=configuration.converter_sha256,
            ),
            ArtifactSpec(
                env_var="LIVECONV_BEATRICE_WORKER_WHEEL",
                sha256=configuration.worker_runtime.worker_wheel_sha256,
            ),
        ),
    )


def _japanese_samples() -> list[float]:
    path = ROOT / "artifacts/shared/synthetic-ja-v1/source/LV001-JA-001.wav"
    with wave.open(str(path), "rb") as stream:
        assert stream.getnchannels() == 1
        assert stream.getsampwidth() == 2
        sample_rate = stream.getframerate()
        count = stream.getnframes()
        pcm = stream.readframes(count)
    values = [value / 32768 for value in struct.unpack(f"<{count}h", pcm)]
    if sample_rate == 48_000:
        samples = values
    elif sample_rate == 24_000:
        samples = []
        for index, value in enumerate(values):
            following = values[min(index + 1, len(values) - 1)]
            samples.extend((value, (value + following) * 0.5))
    else:
        raise AssertionError("real smoke fixture must be 24 or 48 kHz")
    remainder = len(samples) % 960
    if remainder:
        samples.extend([0.0] * (960 - remainder))
    return samples


@pytest.mark.skipif(not RUN_REAL, reason="real Beatrice artifacts are opt-in")
def test_official_checkpoint_converts_japanese_through_supervisor() -> None:
    async def scenario() -> None:
        configuration = BeatriceConfiguration.from_environment(
            require_installed_record=False
        )
        supervisor = WorkerSupervisor(_profile(configuration))
        source = _japanese_samples()
        converted: list[float] = []
        try:
            ready = await supervisor.start()
            assert ready.implementation_revision == configuration.source_revision
            await supervisor.start_generation(1)
            sequence = 0
            for batch_offset in range(0, len(source), 25 * 960):
                batch = source[batch_offset : batch_offset + 25 * 960]
                frame_count = len(batch) // 960
                for offset in range(0, len(batch), 960):
                    frame_samples = batch[offset : offset + 960]
                    await supervisor.push_audio(
                        AudioFrame.from_samples(
                            generation_id=1,
                            sequence=sequence,
                            sample_rate=48_000,
                            channels=1,
                            samples_per_channel=960,
                            source_monotonic_ns=sequence * 20_000_000,
                            samples=frame_samples,
                        )
                    )
                    sequence += 1
                if frame_count == 25:
                    for _ in range(frame_count):
                        converted.extend(
                            (await supervisor.next_output()).unpack_samples()
                        )

            remainder_frames = (len(source) // 960) % 25
            end_task = asyncio.create_task(supervisor.end_generation(1))
            for _ in range(remainder_frames):
                converted.extend((await supervisor.next_output()).unpack_samples())
            await end_task

            assert len(converted) == len(source)
            assert all(math.isfinite(value) and abs(value) <= 1 for value in converted)
            assert any(
                abs(output - original) > 1e-5
                for output, original in zip(converted, source)
            )

            await supervisor.start_generation(2)
            for frame_sequence in range(25):
                offset = frame_sequence * 960
                await supervisor.push_audio(
                    AudioFrame.from_samples(
                        generation_id=2,
                        sequence=frame_sequence,
                        sample_rate=48_000,
                        channels=1,
                        samples_per_channel=960,
                        source_monotonic_ns=frame_sequence * 20_000_000,
                        samples=source[offset : offset + 960],
                    )
                )
            await supervisor.cancel_generation(2)
            assert supervisor.take_output_nowait() is None

            # This output cannot arrive until the canceled real inference returns.
            await supervisor.start_generation(3)
            await supervisor.push_audio(
                AudioFrame.from_samples(
                    generation_id=3,
                    sequence=0,
                    sample_rate=48_000,
                    channels=1,
                    samples_per_channel=960,
                    source_monotonic_ns=0,
                    samples=source[:960],
                )
            )
            next_end = asyncio.create_task(supervisor.end_generation(3))
            next_output = await supervisor.next_output()
            await next_end
            assert next_output.generation_id == 3
            assert len(next_output.unpack_samples()) == 960
            assert supervisor.take_output_nowait() is None

            await supervisor.start_generation(4)
            for sequence in range(2):
                offset = sequence * 960
                await supervisor.push_audio(
                    AudioFrame.from_samples(
                        generation_id=4,
                        sequence=sequence,
                        sample_rate=48_000,
                        channels=1,
                        samples_per_channel=960,
                        source_monotonic_ns=sequence * 20_000_000,
                        samples=source[offset : offset + 960],
                    )
                )
            short_end = asyncio.create_task(supervisor.end_generation(4))
            short_outputs = [
                await supervisor.next_output(),
                await supervisor.next_output(),
            ]
            await short_end
            assert [output.sequence for output in short_outputs] == [0, 1]
            assert all(len(output.unpack_samples()) == 960 for output in short_outputs)
        finally:
            await supervisor.close()

    asyncio.run(asyncio.wait_for(scenario(), 120))
