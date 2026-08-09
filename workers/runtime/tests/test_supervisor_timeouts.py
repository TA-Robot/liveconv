from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from workers.runtime import ArtifactSpec
from workers.runtime.errors import WorkerRuntimeError

from ._support import FIXTURE, make_frame, make_profile, run_async


async def assert_failure_code(task: asyncio.Task[object], code: str) -> None:
    with pytest.raises(WorkerRuntimeError) as raised:
        await task
    assert raised.value.code == code


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def test_startup_timeout_uses_injected_monotonic_clock() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("delayed-ready")
        start_task = asyncio.create_task(supervisor.start())
        await clock.wait_for_waiters()
        clock.advance_ms(FIXTURE["profile"]["startup_timeout_ms"] + 1)

        await assert_failure_code(start_task, "MODEL_TIMEOUT")
        assert supervisor.available is False
        await supervisor.close()

    run_async(scenario())


def test_artifact_verification_timeout_is_bounded_and_cancellable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        artifact_path = tmp_path / "artifact.bin"
        artifact_path.write_bytes(b"approved")
        env_var = "LIVECONV_TEST_ARTIFACT_PATH"
        artifact = ArtifactSpec(
            env_var=env_var,
            sha256=hashlib.sha256(b"approved").hexdigest(),
        )
        supervisor, clock = make_profile(
            "passthrough",
            artifacts=(artifact,),
            environment={env_var: str(artifact_path)},
        )

        async def stalled_inspection(path: Path) -> tuple[Path, str]:
            await asyncio.Event().wait()
            raise AssertionError(f"unreachable inspection for {path}")

        monkeypatch.setattr(supervisor, "_inspect_artifact", stalled_inspection)
        start_task = asyncio.create_task(supervisor.start())
        await clock.wait_for_waiters()
        clock.advance_ms(FIXTURE["profile"]["startup_timeout_ms"] + 1)

        await assert_failure_code(start_task, "MODEL_TIMEOUT")
        assert supervisor.pid is None
        await supervisor.close()

    run_async(scenario())


def test_process_spawn_timeout_is_bounded_and_cancellable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("passthrough")

        async def stalled_spawn(*args: object, **kwargs: object) -> None:
            del args, kwargs
            await asyncio.Event().wait()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", stalled_spawn)
        start_task = asyncio.create_task(supervisor.start())
        await clock.wait_for_waiters()
        clock.advance_ms(FIXTURE["profile"]["startup_timeout_ms"] + 1)

        await assert_failure_code(start_task, "MODEL_TIMEOUT")
        assert supervisor.pid is None
        await supervisor.close()

    run_async(scenario())


def test_first_output_timeout_starts_with_first_accepted_frame() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("stalled")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame())

            output_task = asyncio.create_task(supervisor.next_output())
            await clock.wait_for_waiters()
            clock.advance_ms(FIXTURE["profile"]["first_output_timeout_ms"] + 1)
            await assert_failure_code(output_task, "MODEL_TIMEOUT")
            assert supervisor.take_output_nowait() is None
        finally:
            await supervisor.close()

    run_async(scenario())


def test_stall_timeout_is_rearmed_after_each_output() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("one-output-then-stall")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(sequence=0))
            first = await supervisor.next_output()
            assert first.sequence == 0

            await supervisor.push_audio(make_frame(sequence=1))
            second_task = asyncio.create_task(supervisor.next_output())
            await clock.wait_for_waiters()
            clock.advance_ms(FIXTURE["profile"]["stall_timeout_ms"] + 1)
            await assert_failure_code(second_task, "MODEL_TIMEOUT")
        finally:
            await supervisor.close()

    run_async(scenario())


def test_new_input_after_idle_gets_a_fresh_stall_budget() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("one-output-then-stall")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            await supervisor.push_audio(make_frame(sequence=0))
            assert (await supervisor.next_output()).sequence == 0

            clock.advance_ms(FIXTURE["profile"]["stall_timeout_ms"] + 1)
            await supervisor.push_audio(make_frame(sequence=1))
            pending = asyncio.create_task(supervisor.next_output())
            await clock.wait_for_waiters()
            assert not pending.done()

            clock.advance_ms(FIXTURE["profile"]["stall_timeout_ms"] + 1)
            await assert_failure_code(pending, "MODEL_TIMEOUT")
        finally:
            await supervisor.close()

    run_async(scenario())


def test_cancel_acknowledgement_timeout_terminates_the_generation() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("ignore-cancel")
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            await supervisor.start_generation(generation_id)
            cancel_task = asyncio.create_task(
                supervisor.cancel_generation(generation_id)
            )
            await clock.wait_for_waiters()
            clock.advance_ms(FIXTURE["profile"]["cancel_timeout_ms"] + 1)
            await assert_failure_code(cancel_task, "MODEL_TIMEOUT")
            assert supervisor.take_output_nowait() is None
        finally:
            await supervisor.close()

    run_async(scenario())


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        ("ignore-start", "start"),
        ("ignore-end", "end"),
    ],
)
def test_generation_control_timeout_is_mapped_and_kills_worker(
    mode: str,
    operation: str,
) -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile(mode, restart_limit=0)
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            process_group_id = supervisor.process_group_id
            assert process_group_id is not None
            if operation == "start":
                operation_task = asyncio.create_task(
                    supervisor.start_generation(generation_id)
                )
                timeout_ms = FIXTURE["profile"]["startup_timeout_ms"]
            else:
                await supervisor.start_generation(generation_id)
                operation_task = asyncio.create_task(
                    supervisor.end_generation(generation_id)
                )
                timeout_ms = max(
                    FIXTURE["profile"]["first_output_timeout_ms"],
                    FIXTURE["profile"]["stall_timeout_ms"],
                )
            await clock.wait_for_waiters()
            clock.advance_ms(timeout_ms + 1)

            await assert_failure_code(operation_task, "MODEL_TIMEOUT")
            assert supervisor.available is False
            assert supervisor.pid is None
            assert not process_group_exists(process_group_id)
        finally:
            await supervisor.close()

    run_async(scenario())


def test_blocked_worker_stdin_has_a_bounded_write_deadline() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("blocked-input", restart_limit=0)
        generation_id = FIXTURE["audio"]["generation_id"]
        try:
            await supervisor.start()
            process_group_id = supervisor.process_group_id
            assert process_group_id is not None
            await supervisor.start_generation(generation_id)

            blocked_task: asyncio.Task[None] | None = None
            for sequence in range(supervisor.input_capacity_frames):
                candidate = asyncio.create_task(
                    supervisor.push_audio(make_frame(sequence=sequence))
                )
                for _ in range(20):
                    if candidate.done():
                        break
                    await asyncio.sleep(0)
                if candidate.done():
                    await candidate
                    continue
                blocked_task = candidate
                break

            assert blocked_task is not None
            await clock.wait_for_waiters()
            clock.advance_ms(FIXTURE["profile"]["stall_timeout_ms"] + 1)
            await assert_failure_code(blocked_task, "MODEL_TIMEOUT")
            assert supervisor.available is False
            assert supervisor.pid is None
            assert not process_group_exists(process_group_id)
        finally:
            await supervisor.close()

    run_async(scenario())


def test_bounded_close_kills_the_process_group_and_leaves_no_orphan() -> None:
    async def scenario() -> None:
        supervisor, clock = make_profile("orphan-child")
        await supervisor.start()
        process_group_id = supervisor.process_group_id
        assert process_group_id is not None
        assert process_group_exists(process_group_id)

        close_task = asyncio.create_task(supervisor.close())
        await clock.wait_for_waiters()
        clock.advance_ms(FIXTURE["profile"]["close_grace_ms"] + 1)
        await clock.wait_for_waiters()
        clock.advance_ms(FIXTURE["profile"]["terminate_grace_ms"] + 1)
        await close_task

        assert supervisor.pid is None
        assert supervisor.process_group_id is None
        assert not process_group_exists(process_group_id)

    run_async(scenario())
