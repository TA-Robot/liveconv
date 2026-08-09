from __future__ import annotations

import pytest
from liveconv_protocol import (
    ErrorCode,
    FrameOrderGuard,
    FrameOrderResult,
    ProtocolValidationError,
)


def raised_code(function: object, *args: object) -> ErrorCode:
    with pytest.raises(ProtocolValidationError) as raised:
        function(*args)  # type: ignore[operator]
    return raised.value.code


def test_accepts_contiguous_frames_and_increasing_generations() -> None:
    guard = FrameOrderGuard()
    guard.start_generation(0)
    assert guard.observe(0, 0) is FrameOrderResult.ACCEPTED
    assert guard.observe(0, 1) is FrameOrderResult.ACCEPTED
    guard.finish_generation(0)

    guard.start_generation(9)
    assert guard.observe(9, 0) is FrameOrderResult.ACCEPTED
    guard.cancel_generation(9)


def test_rejects_stale_generation_start_and_frame() -> None:
    guard = FrameOrderGuard()
    guard.start_generation(7)
    guard.finish_generation(7)

    assert raised_code(guard.start_generation, 7) is ErrorCode.STALE_GENERATION
    assert raised_code(guard.observe, 7, 0) is ErrorCode.STALE_GENERATION

    guard.start_generation(8)
    assert raised_code(guard.observe, 7, 0) is ErrorCode.STALE_GENERATION


def test_gap_invalidates_active_generation() -> None:
    guard = FrameOrderGuard()
    guard.start_generation(10)
    guard.observe(10, 0)

    assert raised_code(guard.observe, 10, 2) is ErrorCode.SEQUENCE_GAP
    assert guard.active_generation_id is None
    assert raised_code(guard.observe, 10, 1) is ErrorCode.STALE_GENERATION


def test_duplicate_invalidates_active_generation() -> None:
    guard = FrameOrderGuard()
    guard.start_generation(3)
    guard.observe(3, 0)

    assert raised_code(guard.observe, 3, 0) is ErrorCode.SEQUENCE_GAP
    assert raised_code(guard.observe, 3, 1) is ErrorCode.STALE_GENERATION


def test_rejects_future_frame_without_start() -> None:
    guard = FrameOrderGuard()
    assert raised_code(guard.observe, 1, 0) is ErrorCode.INVALID_STATE


def test_rejects_second_active_generation() -> None:
    guard = FrameOrderGuard()
    guard.start_generation(1)
    assert raised_code(guard.start_generation, 2) is ErrorCode.INVALID_STATE
