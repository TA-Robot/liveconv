from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest


@pytest.fixture
def sample_rate() -> int:
    return 16_000


@pytest.fixture
def sine(sample_rate: int) -> npt.NDArray[np.float64]:
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    return 0.5 * np.sin(2.0 * np.pi * 440.0 * time)
