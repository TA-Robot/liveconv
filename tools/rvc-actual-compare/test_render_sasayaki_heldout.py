"""CPU-only tests for the bounded RVC Sasayaki heldout comparison."""

from __future__ import annotations

import importlib.util
import struct
import sys
import wave
from pathlib import Path

RUNNER = Path(__file__).parent / "render_sasayaki_heldout.py"
SPEC = importlib.util.spec_from_file_location("rvc_sasayaki_heldout", RUNNER)
assert SPEC and SPEC.loader
run = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run
SPEC.loader.exec_module(run)


def test_comparison_is_bounded_to_two_sasayaki_profiles() -> None:
    assert run.PROFILE_IDS == (
        "vc.rvc-v2.amitaro-sasayaki.v1",
        "vc.rvc-v2.amitaro-sasayaki-clean-bright.v1",
    )
    assert [item["source_id"] for item in run.SOURCES] == [
        "EMOTION100_002",
        "EMOTION100_004",
        "EMOTION100_017",
    ]


def test_wav_to_f32le_preserves_pcm16_scale(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    output = tmp_path / "source.f32le"
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48_000)
        stream.writeframes(struct.pack("<hhh", -32768, 0, 32767))

    assert run.wav_to_f32le(source, output) == 3
    assert struct.unpack("<fff", output.read_bytes()) == (
        -1.0,
        0.0,
        32767 / 32768,
    )


def test_selected_records_rejects_incomplete_profile_set() -> None:
    complete = {
        "variants": [{"profile_id": profile_id} for profile_id in run.PROFILE_IDS]
    }
    assert len(run._selected_records(complete, "variants")) == 2

    incomplete = {"variants": complete["variants"][:1]}
    try:
        run._selected_records(incomplete, "variants")
    except run.HeldoutRenderError as error:
        assert "profile set" in str(error)
    else:
        raise AssertionError("incomplete profile set was accepted")
