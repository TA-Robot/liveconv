from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).with_name("render_rvc_turn_state.py")
SPEC = importlib.util.spec_from_file_location("render_rvc_turn_state", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Backend:
    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        assert sample_rate == MODULE.SAMPLE_RATE
        return samples


def test_convert_turns_resets_each_generation() -> None:
    backend = Backend()
    first = np.asarray([0.1, 0.2], dtype=np.float32)
    second = np.asarray([0.3], dtype=np.float32)

    outputs = MODULE.convert_turns(backend, first, second, preserve_state=False)

    assert backend.reset_count == 2
    assert outputs[0].tolist() == first.tolist()
    assert outputs[1].tolist() == second.tolist()


def test_convert_turns_can_preserve_second_generation_state() -> None:
    backend = Backend()
    first = np.asarray([0.1], dtype=np.float32)
    second = np.asarray([0.2], dtype=np.float32)

    MODULE.convert_turns(backend, first, second, preserve_state=True)

    assert backend.reset_count == 1
