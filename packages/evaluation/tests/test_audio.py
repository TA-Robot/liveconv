from __future__ import annotations

import numpy as np
from liveconv_evaluation.audio import (
    AnalysisParameters,
    AudioSignal,
    compare_signals,
    read_wav,
)

from ._support import write_pcm16


def test_identity_is_exact_and_has_zero_normalized_error(tmp_path, sine, sample_rate):
    path = write_pcm16(tmp_path / "identity.wav", sine, sample_rate)
    signal = read_wav(path)

    metrics = compare_signals(signal, signal)

    assert metrics["comparison"]["exact_sample_match"] is True
    assert metrics["comparison"]["alignment_lag_samples_at_source_rate"] == 0
    assert metrics["comparison"]["aligned_gain_normalized_nrmse"] == 0.0
    assert metrics["comparison"]["aligned_gain_normalized_correlation"] == 1.0


def test_gain_only_change_is_not_meaningful_after_gain_normalization(
    tmp_path, sine, sample_rate
):
    source = read_wav(write_pcm16(tmp_path / "source.wav", sine, sample_rate))
    quieter = read_wav(write_pcm16(tmp_path / "quieter.wav", sine * 0.5, sample_rate))

    metrics = compare_signals(source, quieter)

    assert metrics["comparison"]["exact_sample_match"] is False
    assert metrics["comparison"]["aligned_gain_normalized_nrmse"] < 0.001
    assert metrics["comparison"]["mean_absolute_log_spectral_distance"] < 0.01


def test_frequency_change_has_signal_and_spectral_distance(tmp_path, sine, sample_rate):
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    changed = 0.5 * np.sin(2.0 * np.pi * 880.0 * time)
    source = read_wav(write_pcm16(tmp_path / "source.wav", sine, sample_rate))
    output = read_wav(write_pcm16(tmp_path / "output.wav", changed, sample_rate))

    metrics = compare_signals(source, output)

    assert metrics["comparison"]["aligned_gain_normalized_nrmse"] > 1.0
    assert metrics["comparison"]["mean_absolute_log_spectral_distance"] > 0.1


def test_clipping_and_silence_are_measured(tmp_path, sine, sample_rate):
    clipped = read_wav(write_pcm16(tmp_path / "clipped.wav", sine * 4.0, sample_rate))
    silence = AudioSignal(np.zeros(sample_rate), sample_rate)

    clipped_metrics = compare_signals(clipped, clipped)
    silence_metrics = compare_signals(silence, silence)

    assert clipped_metrics["output"]["clipped_sample_fraction"] > 0.0
    assert silence_metrics["output"]["silence_frame_fraction"] == 1.0
    assert silence_metrics["output"]["rms_dbfs"] is None


def test_nonfinite_samples_are_counted_without_emitting_nonfinite_metrics(sample_rate):
    source = AudioSignal(np.array([0.0, 0.25, -0.25, 0.0]), sample_rate)
    output = AudioSignal(np.array([0.0, np.nan, np.inf, 0.0]), sample_rate)

    metrics = compare_signals(
        source,
        output,
        AnalysisParameters(max_alignment_ms=0, spectral_fft_size=16),
    )

    assert metrics["output"]["nonfinite_sample_count"] == 2


def test_interior_silence_runs_are_counted_in_analysis_frames(sample_rate):
    frame_size = round(sample_rate * AnalysisParameters().frame_ms / 1000.0)
    lead = np.linspace(0.1, 0.2, frame_size)
    tail = np.linspace(-0.2, -0.1, frame_size)
    signal = AudioSignal(
        np.concatenate((lead, np.zeros(frame_size * 2), tail)), sample_rate
    )

    metrics = compare_signals(signal, signal)

    assert metrics["output"]["interior_silence_run_count"] == 1
    assert metrics["output"]["max_interior_silence_run_frames"] == 2


def test_exact_adjacent_replayed_segments_are_measured(sample_rate):
    frame_size = round(sample_rate * AnalysisParameters().frame_ms / 1000.0)
    first = np.linspace(0.1, 0.2, frame_size)
    second = np.linspace(-0.1, -0.2, frame_size)
    replayed = AudioSignal(np.concatenate((first, second, first, second)), sample_rate)

    metrics = compare_signals(replayed, replayed)

    assert metrics["output"]["adjacent_repeated_segment_count"] >= 1
    assert metrics["output"]["max_adjacent_repeated_segment_frames"] == 2
