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
        self.input_wav = Buffer([1.0, 2.0])
        self.input_wav_res = Buffer([3.0])
        self.rvc = Rvc()


class Buffer:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def clone(self) -> Buffer:
        return Buffer(self.values.copy())

    def copy_(self, other: Buffer) -> None:
        self.values = other.values.copy()


class Rvc:
    def __init__(self) -> None:
        self.cache_pitch = Buffer([4.0])
        self.cache_pitchf = Buffer([5.0])


class Backend:
    def __init__(self) -> None:
        self._engine = Engine()
        self.reset_count = 0
        self.input_sizes: list[int] = []
        self.full_reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def convert(self, samples: list[float], sample_rate: int) -> list[float]:
        assert sample_rate == MODULE.SAMPLE_RATE
        self.input_sizes.append(len(samples))
        return samples

    def _reset_state(self) -> None:
        self.full_reset_count += 1
        self._engine.input_wav.values = [0.0, 0.0]
        self._engine.input_wav_res.values = [0.0]
        self._engine.rvc.cache_pitch.values = [0.0]
        self._engine.rvc.cache_pitchf.values = [0.0]


def test_silence_prime_resets_then_reseeds_before_second_turn() -> None:
    backend = Backend()
    second = np.asarray([0.1, 0.2], dtype=np.float32)

    output = MODULE.convert_with_silence_prime(backend, second, seed=0)

    assert backend.reset_count == 1
    assert backend.input_sizes == [MODULE.PRIME_SAMPLES, 2]
    assert backend._engine.torch.seeds == [0]
    assert output.tolist() == second.tolist()


def test_input_context_control_restores_only_input_buffers() -> None:
    backend = Backend()
    first = np.asarray([0.1], dtype=np.float32)
    second = np.asarray([0.2], dtype=np.float32)

    output = MODULE.convert_with_input_context(backend, first, second)

    assert backend.reset_count == 1
    assert backend.full_reset_count == 1
    assert backend.input_sizes == [1, 1]
    assert backend._engine.input_wav.values == [1.0, 2.0]
    assert backend._engine.input_wav_res.values == [3.0]
    assert backend._engine.rvc.cache_pitch.values == [0.0]
    assert backend._engine.rvc.cache_pitchf.values == [0.0]
    assert output.tolist() == second.tolist()


def test_pitch_cache_control_restores_only_pitch_buffers() -> None:
    backend = Backend()
    first = np.asarray([0.1], dtype=np.float32)
    second = np.asarray([0.2], dtype=np.float32)

    output = MODULE.convert_with_pitch_cache(backend, first, second)

    assert backend.reset_count == 1
    assert backend.full_reset_count == 1
    assert backend._engine.input_wav.values == [0.0, 0.0]
    assert backend._engine.input_wav_res.values == [0.0]
    assert backend._engine.rvc.cache_pitch.values == [4.0]
    assert backend._engine.rvc.cache_pitchf.values == [5.0]
    assert output.tolist() == second.tolist()
