from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).with_name("render_rvc_silence_prime.py")
SPEC = importlib.util.spec_from_file_location("render_rvc_silence_prime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Torch:
    def __init__(self) -> None:
        self.seeds: list[int] = []

    def manual_seed(self, seed: int) -> None:
        self.seeds.append(seed)


class Engine:
    def __init__(self) -> None:
        self.torch = Torch()


class Backend:
    def __init__(self) -> None:
        self._engine = Engine()
        self.reset_count = 0
        self.input_sizes: list[int] = []

    def reset(self) -> None:
        self.reset_count += 1

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        assert sample_rate == MODULE.SAMPLE_RATE
        self.input_sizes.append(len(samples))
        return samples


def test_silence_prime_resets_then_reseeds_before_second_turn() -> None:
    backend = Backend()
    second = np.asarray([0.1, 0.2], dtype=np.float32)

    output = MODULE.convert_with_silence_prime(backend, second, seed=0)

    assert backend.reset_count == 1
    assert backend.input_sizes == [MODULE.PRIME_SAMPLES, 2]
    assert backend._engine.torch.seeds == [0]
    assert output.tolist() == second.tolist()
