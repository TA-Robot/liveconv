from __future__ import annotations

import asyncio
import hashlib
import os
import signal
import time
from pathlib import Path

import pytest

from workers.runtime import ArtifactSpec
from workers.runtime.errors import WorkerRuntimeError

from ._support import ARTIFACT_PATH, FIXTURE, make_frame, make_profile, run_async


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def test_artifact_digest_is_verified_before_process_spawn() -> None:
    async def scenario() -> None:
        env_var = "LIVECONV_TEST_ARTIFACT_PATH"
        artifact = ArtifactSpec(env_var=env_var, sha256="0" * 64)
        supervisor, _ = make_profile(
            "passthrough",
            artifacts=(artifact,),
            environment={env_var: str(ARTIFACT_PATH)},
        )

        with pytest.raises(WorkerRuntimeError) as mismatch:
            await supervisor.start()
        assert mismatch.value.code == "MODEL_UNAVAILABLE"
        assert env_var in str(mismatch.value)
        assert str(ARTIFACT_PATH) not in str(mismatch.value)
        assert supervisor.pid is None
        await supervisor.close()

    run_async(scenario())


def test_matching_artifact_digest_allows_spawn() -> None:
    async def scenario() -> None:
        env_var = "LIVECONV_TEST_ARTIFACT_PATH"
        digest = hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest()
        artifact = ArtifactSpec(env_var=env_var, sha256=digest)
        supervisor, _ = make_profile(
            "passthrough",
            artifacts=(artifact,),
            environment={env_var: str(ARTIFACT_PATH)},
        )
        try:
            ready = await supervisor.start()
            assert ready.profile_id == FIXTURE["profile"]["profile_id"]
        finally:
            await supervisor.close()

    run_async(scenario())


def test_artifact_metadata_is_not_resolved_on_supervisor_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        env_var = "LIVECONV_TEST_ARTIFACT_PATH"
        digest = hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest()
        artifact = ArtifactSpec(env_var=env_var, sha256=digest)
        supervisor, _ = make_profile(
            "passthrough",
            artifacts=(artifact,),
            environment={env_var: str(ARTIFACT_PATH)},
        )
        original_resolve = Path.resolve

        def stalled_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            time.sleep(1)
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", stalled_resolve)
        started = time.monotonic()
        try:
            await supervisor.start()
            assert time.monotonic() - started < 0.8
        finally:
            await supervisor.close()

    run_async(scenario())


def test_relative_artifact_path_cannot_resolve_differently_across_cwds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        gateway_cwd = tmp_path / "gateway"
        worker_cwd = tmp_path / "worker"
        gateway_cwd.mkdir()
        worker_cwd.mkdir()
        (gateway_cwd / "artifact.bin").write_bytes(b"approved")
        (worker_cwd / "artifact.bin").write_bytes(b"different")
        monkeypatch.chdir(gateway_cwd)

        env_var = "LIVECONV_TEST_ARTIFACT_PATH"
        artifact = ArtifactSpec(
            env_var=env_var,
            sha256=hashlib.sha256(b"approved").hexdigest(),
        )
        supervisor, _ = make_profile(
            "passthrough",
            artifacts=(artifact,),
            environment={env_var: "artifact.bin"},
            cwd=worker_cwd,
        )

        with pytest.raises(WorkerRuntimeError, match="absolute path") as rejected:
            await supervisor.start()
        assert rejected.value.code == "MODEL_UNAVAILABLE"
        assert supervisor.pid is None
        await supervisor.close()

    run_async(scenario())


def test_crash_discards_generation_and_automatically_restarts() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("crashed")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            original_process_group = supervisor.process_group_id
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame())

            with pytest.raises(WorkerRuntimeError) as crash:
                await supervisor.next_output()
            assert crash.value.code == "WORKER_CRASH"
            assert crash.value.recoverable is True
            assert supervisor.take_output_nowait() is None

            ready = await supervisor.wait_until_ready()
            assert ready.profile_id == FIXTURE["profile"]["profile_id"]
            assert supervisor.restart_count == 1
            assert supervisor.process_group_id != original_process_group
        finally:
            await supervisor.close()

    run_async(scenario())


def test_public_start_coalesces_with_scheduled_restart() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("crashed")
        generation_id = FIXTURE["audio"]["generation_id"]
        spawned_groups: list[int] = []
        original_spawn = supervisor._spawn_and_handshake

        async def tracked_spawn():
            ready = await original_spawn()
            assert supervisor.process_group_id is not None
            spawned_groups.append(supervisor.process_group_id)
            return ready

        supervisor._spawn_and_handshake = tracked_spawn  # type: ignore[method-assign]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame())
            with pytest.raises(WorkerRuntimeError, match="exited unexpectedly"):
                await supervisor.next_output()

            ready = await supervisor.start()
            assert ready.profile_id == FIXTURE["profile"]["profile_id"]
            await asyncio.sleep(0)
            assert len(spawned_groups) == 2
            assert supervisor.process_group_id == spawned_groups[-1]
        finally:
            await supervisor.close()
        assert all(not process_group_exists(group) for group in spawned_groups)

    run_async(scenario())


def test_idle_crash_restart_accepts_the_next_generation_without_stale_error() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("passthrough")
        try:
            await supervisor.start()
            original_group = supervisor.process_group_id
            assert original_group is not None
            os.killpg(original_group, signal.SIGKILL)

            for _ in range(100):
                if supervisor.restart_count == 1:
                    break
                await asyncio.sleep(0.01)
            assert supervisor.restart_count == 1
            ready = await supervisor.wait_until_ready()
            assert ready.profile_id == FIXTURE["profile"]["profile_id"]
            assert supervisor.process_group_id != original_group
            assert supervisor.take_output_nowait() is None

            generation_id = FIXTURE["audio"]["generation_id"]
            await supervisor.start_generation(generation_id)
            source = make_frame(generation_id=generation_id)
            await supervisor.push_audio(source)
            output = await supervisor.next_output()
            assert output.generation_id == generation_id
            assert output.pcm_f32le == source.pcm_f32le
        finally:
            await supervisor.close()

    run_async(scenario())


def test_fourth_crash_in_sixty_seconds_exhausts_three_restarts() -> None:
    async def scenario() -> None:
        supervisor, _ = make_profile("crashed", restart_limit=3)
        first_generation = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            for crash_index in range(4):
                generation_id = first_generation + crash_index
                await supervisor.start_generation(generation_id)
                await supervisor.push_audio(make_frame(generation_id=generation_id))
                with pytest.raises(WorkerRuntimeError) as crash:
                    await supervisor.next_output()
                assert crash.value.code == "WORKER_CRASH"

                if crash_index < 3:
                    await supervisor.wait_until_ready()

            assert supervisor.restart_count == 3
            assert supervisor.available is False
            with pytest.raises(WorkerRuntimeError) as exhausted:
                await supervisor.wait_until_ready()
            assert exhausted.value.code == "MODEL_UNAVAILABLE"
        finally:
            await supervisor.close()

    run_async(scenario())
