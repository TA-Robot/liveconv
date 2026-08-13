from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).with_name("render_stable_rvc_turn_split.py")
SPEC = importlib.util.spec_from_file_location(
    "render_stable_rvc_turn_split", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def frames(value: float = 0.0) -> list[bytes]:
    return [
        np.full(960, value, dtype="<f4").tobytes()
        for _index in range(MODULE.EXPECTED_FRAMES)
    ]


def test_split_turns_uses_fixed_frame_boundary() -> None:
    source = frames()

    first, second, quiet_rms = MODULE.split_turns(source)

    assert len(first) == MODULE.SPLIT_FRAME
    assert len(second) == MODULE.EXPECTED_FRAMES - MODULE.SPLIT_FRAME
    assert first + second == source
    assert quiet_rms == 0.0


def test_split_turns_rejects_nonquiet_boundary() -> None:
    source = frames()
    for index in range(MODULE.QUIET_START_FRAME, MODULE.QUIET_END_FRAME):
        source[index] = np.full(960, 0.01, dtype="<f4").tobytes()

    with pytest.raises(MODULE.StableTurnSplitError, match="no longer quiet"):
        MODULE.split_turns(source)


def test_split_turns_rejects_wrong_source_length() -> None:
    with pytest.raises(MODULE.StableTurnSplitError, match="409-frame"):
        MODULE.split_turns(frames()[:-1])


def test_listener_staging_is_sibling() -> None:
    listener = Path("/listener/comparison")

    assert MODULE.listener_staging_path(listener) == Path(
        "/listener/.comparison.staging"
    )
