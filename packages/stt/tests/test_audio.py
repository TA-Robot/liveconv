from __future__ import annotations

import hashlib

import pytest

from liveconv_stt import AudioValidationError, InputLimits, read_pcm_wav

from .conftest import write_wav


def test_reads_bounded_mono_pcm16_and_hashes_encoded_wav(pcm_wav):
    audio = read_pcm_wav(pcm_wav)

    assert audio.artifact.sha256 == hashlib.sha256(pcm_wav.read_bytes()).hexdigest()
    assert audio.artifact.channels == 1
    assert audio.artifact.sample_width_bytes == 2
    assert audio.artifact.sample_rate_hz == 16_000
    assert len(audio.pcm_s16le) == audio.artifact.frame_count * 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"channels": 2}, "mono"),
        ({"sample_width": 1}, "16-bit"),
        ({"sample_rate": 4_000}, "sample rate"),
    ],
)
def test_rejects_unsupported_pcm_shapes(tmp_path, kwargs, message):
    path = write_wav(tmp_path / "invalid.wav", **kwargs)
    with pytest.raises(AudioValidationError, match=message):
        read_pcm_wav(path)


def test_enforces_byte_and_duration_limits(tmp_path):
    path = write_wav(tmp_path / "bounded.wav", frame_count=1_600)

    with pytest.raises(AudioValidationError, match="byte limit"):
        read_pcm_wav(path, limits=InputLimits(max_input_bytes=50))
    with pytest.raises(AudioValidationError, match="duration limit"):
        read_pcm_wav(path, limits=InputLimits(max_duration_seconds=0.05))


def test_rejects_symlink_input(tmp_path, pcm_wav):
    link = tmp_path / "linked.wav"
    link.symlink_to(pcm_wav)
    with pytest.raises(AudioValidationError, match="non-symlink"):
        read_pcm_wav(link)


def test_hard_limits_cannot_be_raised_without_code_change():
    with pytest.raises(AudioValidationError, match="safe range"):
        InputLimits(max_input_bytes=64 * 1024 * 1024 + 1)
    with pytest.raises(AudioValidationError, match="safe range"):
        InputLimits(max_duration_seconds=601)
