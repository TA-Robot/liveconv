from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

from workers.runtime import AudioFrame, WorkerProfile, WorkerSupervisor

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "workers" / "conformance" / "fixtures" / "worker-v1.json"
ARTIFACT_PATH = ROOT / "workers" / "conformance" / "fixtures" / "synthetic-artifact.txt"


def load_fixture() -> dict[str, Any]:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


FIXTURE = load_fixture()


class ManualClock:
    """A monotonic clock whose waiters move only when the test advances it."""

    def __init__(self) -> None:
        self._now_ns = 0
        self._waiters: list[tuple[int, asyncio.Future[None]]] = []

    def now_ns(self) -> int:
        return self._now_ns

    async def wait_until_ns(self, deadline_ns: int) -> None:
        if deadline_ns <= self._now_ns:
            return
        future = asyncio.get_running_loop().create_future()
        self._waiters.append((deadline_ns, future))
        try:
            await future
        finally:
            self._waiters = [item for item in self._waiters if item[1] is not future]

    @property
    def waiter_count(self) -> int:
        return sum(not future.done() for _, future in self._waiters)

    def advance_ms(self, milliseconds: int) -> None:
        assert milliseconds >= 0
        self._now_ns += milliseconds * 1_000_000
        for deadline_ns, future in tuple(self._waiters):
            if deadline_ns <= self._now_ns and not future.done():
                future.set_result(None)

    async def wait_for_waiters(self, minimum: int = 1) -> None:
        for _ in range(100):
            if self.waiter_count >= minimum:
                return
            await asyncio.sleep(0)
        raise AssertionError(f"expected at least {minimum} clock waiter(s)")


async def _bounded[T](awaitable: Awaitable[T]) -> T:
    return await asyncio.wait_for(awaitable, timeout=5.0)


def run_async[T](awaitable: Awaitable[T]) -> T:
    return asyncio.run(_bounded(awaitable))


def fake_worker_command(mode: str, *, gain: float | None = None) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "workers.conformance.fake_worker",
        "--mode",
        mode,
    ]
    if gain is not None:
        command.extend(("--gain", str(gain)))
    return tuple(command)


def make_profile(
    mode: str,
    *,
    clock: ManualClock | None = None,
    gain: float | None = None,
    command: tuple[str, ...] | None = None,
    artifacts: tuple[object, ...] = (),
    environment: dict[str, str] | None = None,
    restart_limit: int | None = None,
    cwd: Path | None = None,
) -> tuple[WorkerSupervisor, ManualClock]:
    config = FIXTURE["profile"]
    selected_clock = clock or ManualClock()
    profile = WorkerProfile(
        profile_id=config["profile_id"],
        pipeline_id=config["pipeline_id"],
        configuration_hash=config["configuration_hash"],
        command=(fake_worker_command(mode, gain=gain) if command is None else command),
        cwd=cwd or ROOT,
        environment=environment or {},
        implementation_revision=config["implementation_revision"],
        weight_revision=config["weight_revision"],
        frame_ms=config["frame_ms"],
        queue_budget_ms=config["queue_budget_ms"],
        startup_timeout_ms=config["startup_timeout_ms"],
        first_output_timeout_ms=config["first_output_timeout_ms"],
        stall_timeout_ms=config["stall_timeout_ms"],
        cancel_timeout_ms=config["cancel_timeout_ms"],
        close_grace_ms=config["close_grace_ms"],
        terminate_grace_ms=config["terminate_grace_ms"],
        restart_limit=(
            config["restart_limit"] if restart_limit is None else restart_limit
        ),
        restart_window_ms=config["restart_window_ms"],
        artifacts=artifacts,
    )
    return WorkerSupervisor(profile, clock=selected_clock), selected_clock


def make_frame(*, sequence: int = 0, generation_id: int | None = None) -> AudioFrame:
    audio = FIXTURE["audio"]
    samples = tuple(audio["sample_pattern"] * audio["pattern_repetitions"])
    return AudioFrame.from_samples(
        generation_id=(
            audio["generation_id"] if generation_id is None else generation_id
        ),
        sequence=sequence,
        sample_rate=audio["sample_rate"],
        channels=audio["channels"],
        samples_per_channel=audio["samples_per_channel"],
        source_monotonic_ns=audio["source_monotonic_ns"] + sequence * 20_000_000,
        samples=samples,
    )
