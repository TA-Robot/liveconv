from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_cross_corpus_unpaired_curriculum as cross  # noqa: E402


def test_hadou_selection_spreads_fixed_remainder() -> None:
    selected = cross.selected_hadou_indices()

    assert len(selected) == 34
    assert len(set(selected)) == 34
    assert selected[0] == 0
    assert selected[-1] >= 165


def test_native_rate_window_keeps_2_point_4_seconds_without_stretch() -> None:
    sample_rate = 16_000
    silence = np.zeros(sample_rate, dtype=np.int16)
    speech = np.full(sample_rate * 3, 2_000, dtype=np.int16)
    source = np.concatenate((silence, speech, silence))
    wav = io.BytesIO()
    with wave.open(wav, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(source.astype("<i2").tobytes())

    selected = cross.active_window_wav_bytes(wav.getvalue(), label="fixture")

    with wave.open(io.BytesIO(selected), "rb") as handle:
        assert handle.getframerate() == sample_rate
        assert handle.getnframes() == int(sample_rate * 2.4)
        output = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    assert np.mean(np.abs(output)) == 2_000


def test_schedule_is_deterministic_and_preserves_composition() -> None:
    records = []
    for domain, count in cross.EXPECTED_COMPOSITION.items():
        records.extend(
            {"domain": domain, "teacher_id": f"{domain}-{index:03d}"}
            for index in range(count)
        )

    first = cross.scheduled_sources(records)
    second = cross.scheduled_sources(list(reversed(records)))

    assert [item["teacher_id"] for item in first] == [
        item["teacher_id"] for item in second
    ]
    assert len(first) == cross.EXPECTED_ROWS
    assert len({item["teacher_id"] for item in first}) == cross.EXPECTED_ROWS
