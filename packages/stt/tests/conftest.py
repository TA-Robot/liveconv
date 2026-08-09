from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest


@pytest.fixture
def pcm_wav(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.wav"
    sample_rate = 16_000
    samples = [
        int(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        for index in range(sample_rate // 20)
    ]
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def write_wav(
    path: Path,
    *,
    channels: int = 1,
    sample_width: int = 2,
    sample_rate: int = 16_000,
    frame_count: int = 160,
) -> Path:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frame_count * channels * sample_width))
    return path
