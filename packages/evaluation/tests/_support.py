from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import numpy.typing as npt


def write_pcm16(path: Path, samples: npt.ArrayLike, sample_rate: int) -> Path:
    array = np.asarray(samples, dtype=np.float64)
    if array.ndim == 1:
        array = array[:, np.newaxis]
    encoded = np.round(np.clip(array, -1.0, 32767.0 / 32768.0) * 32768.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(array.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(encoded.tobytes())
    return path
