"""Deterministic PCM WAV loading and signal-comparison metrics."""

from __future__ import annotations

import hashlib
import math
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class AnalysisParameters:
    """Metric definitions, not product pass/fail thresholds."""

    silence_floor_dbfs: float = -60.0
    clipping_amplitude: float = 0.999
    frame_ms: float = 20.0
    alignment_hop_ms: float = 10.0
    max_alignment_ms: float = 500.0
    spectral_fft_size: int = 512

    def __post_init__(self) -> None:
        if not -200.0 <= self.silence_floor_dbfs <= 0.0:
            raise ValueError("silence_floor_dbfs must be between -200 and 0")
        if not 0.0 < self.clipping_amplitude <= 1.0:
            raise ValueError("clipping_amplitude must be in (0, 1]")
        if self.frame_ms <= 0 or self.alignment_hop_ms <= 0:
            raise ValueError("frame durations must be positive")
        if self.max_alignment_ms < 0:
            raise ValueError("max_alignment_ms must be non-negative")
        if self.spectral_fft_size < 16:
            raise ValueError("spectral_fft_size must be at least 16")


@dataclass(frozen=True)
class AudioSignal:
    """Floating point audio in frames-by-channels layout."""

    samples: npt.NDArray[np.float64]
    sample_rate: int
    sample_width: int | None = None

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float64)
        if samples.ndim == 1:
            samples = samples[:, np.newaxis]
        if samples.ndim != 2:
            raise ValueError("samples must have shape (frames,) or (frames, channels)")
        if samples.shape[1] < 1:
            raise ValueError("audio must have at least one channel")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        object.__setattr__(self, "samples", samples)

    @property
    def frames(self) -> int:
        return int(self.samples.shape[0])

    @property
    def channels(self) -> int:
        return int(self.samples.shape[1])

    @property
    def duration_seconds(self) -> float:
        return self.frames / self.sample_rate

    def mono(self) -> npt.NDArray[np.float64]:
        return np.mean(self.samples, axis=1)


def _decode_pcm(raw: bytes, sample_width: int) -> npt.NDArray[np.float64]:
    if sample_width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if sample_width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8)
        if octets.size % 3:
            raise ValueError("24-bit PCM payload is not sample aligned")
        triplets = octets.reshape(-1, 3).astype(np.int32)
        values = triplets[:, 0] | (triplets[:, 1] << 8) | (triplets[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float64) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"unsupported PCM sample width: {sample_width}")


def read_wav(path: str | Path) -> AudioSignal:
    """Read an uncompressed integer PCM WAV file."""

    wav_path = Path(path)
    with wave.open(str(wav_path), "rb") as handle:
        if handle.getcomptype() != "NONE":
            raise ValueError(f"compressed WAV is unsupported: {handle.getcomptype()}")
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        frame_count = handle.getnframes()
        raw = handle.readframes(frame_count)

    decoded = _decode_pcm(raw, sample_width)
    expected_samples = frame_count * channels
    if decoded.size != expected_samples:
        raise ValueError(
            f"WAV payload has {decoded.size} samples; expected {expected_samples}"
        )
    return AudioSignal(
        decoded.reshape(frame_count, channels), sample_rate, sample_width
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(value: float | np.floating[Any]) -> float | None:
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _dbfs(value: float) -> float | None:
    if value <= 0 or not math.isfinite(value):
        return None
    return 20.0 * math.log10(value)


def _frame_rms(
    samples: npt.NDArray[np.float64], frame_size: int
) -> npt.NDArray[np.float64]:
    frames = _frames(samples, frame_size)
    if not frames.size:
        return np.empty(0, dtype=np.float64)
    return np.sqrt(np.mean(np.square(frames), axis=1))


def _frames(
    samples: npt.NDArray[np.float64], frame_size: int
) -> npt.NDArray[np.float64]:
    frame_size = max(1, frame_size)
    if samples.size == 0:
        return np.empty((0, frame_size), dtype=np.float64)
    frame_count = math.ceil(samples.size / frame_size)
    padded = np.pad(samples, (0, frame_count * frame_size - samples.size))
    return padded.reshape(frame_count, frame_size)


def _interior_silence_runs(silent_frames: npt.NDArray[np.bool_]) -> tuple[int, int]:
    non_silent = np.flatnonzero(~silent_frames)
    if non_silent.size < 2:
        return 0, 0

    interior = silent_frames[non_silent[0] + 1 : non_silent[-1]]
    run_count = 0
    longest = 0
    current = 0
    for silent in interior:
        if silent:
            current += 1
            longest = max(longest, current)
        elif current:
            run_count += 1
            current = 0
    if current:
        run_count += 1
    return run_count, longest


def _adjacent_repeated_segments(
    frames: npt.NDArray[np.float64], silent_frames: npt.NDArray[np.bool_]
) -> tuple[int, int]:
    """Find exact, immediately replayed non-silent frame sequences."""

    signatures = [frame.tobytes() for frame in frames]
    frame_count = len(signatures)
    non_silent_prefix = np.concatenate(([0], np.cumsum(~silent_frames, dtype=np.int64)))
    repeated_boundaries: set[int] = set()
    longest = 0
    next_lcp = [0] * (frame_count + 1)
    for first_start in range(frame_count - 1, -1, -1):
        current_lcp = [0] * (frame_count + 1)
        for second_start in range(frame_count - 1, first_start, -1):
            if signatures[first_start] == signatures[second_start]:
                current_lcp[second_start] = 1 + next_lcp[second_start + 1]
            length = second_start - first_start
            non_silent_count = (
                non_silent_prefix[second_start] - non_silent_prefix[first_start]
            )
            if current_lcp[second_start] >= length and non_silent_count:
                repeated_boundaries.add(second_start)
                longest = max(longest, length)
        next_lcp = current_lcp
    return len(repeated_boundaries), longest


def _signal_stats(
    signal: AudioSignal, parameters: AnalysisParameters
) -> dict[str, Any]:
    samples = signal.samples
    finite = np.isfinite(samples)
    finite_samples = samples[finite]
    nonfinite_count = int(samples.size - finite_samples.size)
    if finite_samples.size:
        peak = float(np.max(np.abs(finite_samples)))
        rms = float(np.sqrt(np.mean(np.square(finite_samples))))
        dc_offset = float(np.mean(finite_samples))
        clipped_fraction = float(
            np.count_nonzero(np.abs(finite_samples) >= parameters.clipping_amplitude)
            / finite_samples.size
        )
    else:
        peak = rms = dc_offset = 0.0
        clipped_fraction = 0.0

    frame_size = max(1, round(signal.sample_rate * parameters.frame_ms / 1000.0))
    sanitized_mono = np.nan_to_num(signal.mono(), nan=0.0, posinf=0.0, neginf=0.0)
    frames = _frames(sanitized_mono, frame_size)
    frame_rms = (
        np.sqrt(np.mean(np.square(frames), axis=1))
        if frames.size
        else np.empty(0, dtype=np.float64)
    )
    silence_amplitude = 10.0 ** (parameters.silence_floor_dbfs / 20.0)
    silent_frames = frame_rms <= silence_amplitude
    silence_fraction = (
        float(np.count_nonzero(silent_frames) / frame_rms.size)
        if frame_rms.size
        else 1.0
    )
    gap_count, longest_gap = _interior_silence_runs(silent_frames)
    repeated_count, longest_repetition = _adjacent_repeated_segments(
        frames, silent_frames
    )
    adjacent = np.diff(sanitized_mono)

    return {
        "frames": signal.frames,
        "channels": signal.channels,
        "sample_rate_hz": signal.sample_rate,
        "sample_width_bytes": signal.sample_width,
        "duration_seconds": signal.duration_seconds,
        "peak_amplitude": peak,
        "rms_amplitude": rms,
        "rms_dbfs": _dbfs(rms),
        "dc_offset": dc_offset,
        "clipped_sample_fraction": clipped_fraction,
        "silence_frame_fraction": silence_fraction,
        "nonfinite_sample_count": nonfinite_count,
        "max_adjacent_sample_delta": (
            float(np.max(np.abs(adjacent))) if adjacent.size else 0.0
        ),
        "interior_silence_run_count": gap_count,
        "max_interior_silence_run_frames": longest_gap,
        "adjacent_repeated_segment_count": repeated_count,
        "max_adjacent_repeated_segment_frames": longest_repetition,
    }


def _resample_linear(
    samples: npt.NDArray[np.float64], source_rate: int, target_rate: int
) -> npt.NDArray[np.float64]:
    if source_rate == target_rate or samples.size == 0:
        return samples.copy()
    output_size = max(1, round(samples.size * target_rate / source_rate))
    old_positions = np.arange(samples.size, dtype=np.float64) / source_rate
    new_positions = np.arange(output_size, dtype=np.float64) / target_rate
    return np.interp(new_positions, old_positions, samples)


def _alignment_lag(
    reference: npt.NDArray[np.float64],
    candidate: npt.NDArray[np.float64],
    sample_rate: int,
    parameters: AnalysisParameters,
) -> int:
    hop = max(1, round(sample_rate * parameters.alignment_hop_ms / 1000.0))
    reference_envelope = _frame_rms(reference, hop)
    candidate_envelope = _frame_rms(candidate, hop)
    max_lag = round(parameters.max_alignment_ms / parameters.alignment_hop_ms)
    best_score = -math.inf
    best_lag = 0

    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            ref_part = reference_envelope[: candidate_envelope.size - lag]
            cand_part = candidate_envelope[lag : lag + ref_part.size]
        else:
            ref_part = reference_envelope[-lag:]
            cand_part = candidate_envelope[: ref_part.size]
        length = min(ref_part.size, cand_part.size)
        if length < 2:
            continue
        ref_part = ref_part[:length]
        cand_part = cand_part[:length]
        denominator = float(np.linalg.norm(ref_part) * np.linalg.norm(cand_part))
        score = float(np.dot(ref_part, cand_part) / denominator) if denominator else 0.0
        if score > best_score + 1e-12 or (
            math.isclose(score, best_score, abs_tol=1e-12) and abs(lag) < abs(best_lag)
        ):
            best_score = score
            best_lag = lag
    return best_lag * hop


def _aligned_overlap(
    reference: npt.NDArray[np.float64],
    candidate: npt.NDArray[np.float64],
    lag: int,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    if lag >= 0:
        candidate = candidate[lag:]
    else:
        reference = reference[-lag:]
    length = min(reference.size, candidate.size)
    return reference[:length], candidate[:length]


def _log_spectra(
    samples: npt.NDArray[np.float64], fft_size: int
) -> npt.NDArray[np.float64]:
    hop = max(1, fft_size // 2)
    if samples.size < fft_size:
        samples = np.pad(samples, (0, fft_size - samples.size))
    frame_count = 1 + (samples.size - fft_size) // hop
    starts = np.arange(frame_count) * hop
    frames = np.stack([samples[start : start + fft_size] for start in starts])
    spectra = np.abs(np.fft.rfft(frames * np.hanning(fft_size), axis=1))
    # log1p prevents quantization noise in near-empty bins from dominating a
    # gain-normalized comparison while retaining deterministic spectral changes.
    return np.log1p(spectra)


def compare_signals(
    source: AudioSignal,
    output: AudioSignal,
    parameters: AnalysisParameters | None = None,
) -> dict[str, Any]:
    """Measure signal difference and integrity without assigning product meaning."""

    parameters = parameters or AnalysisParameters()
    source_mono = np.nan_to_num(source.mono(), nan=0.0, posinf=0.0, neginf=0.0)
    output_mono = _resample_linear(
        np.nan_to_num(output.mono(), nan=0.0, posinf=0.0, neginf=0.0),
        output.sample_rate,
        source.sample_rate,
    )
    lag = _alignment_lag(source_mono, output_mono, source.sample_rate, parameters)
    aligned_source, aligned_output = _aligned_overlap(source_mono, output_mono, lag)

    source_rms = (
        float(np.sqrt(np.mean(np.square(aligned_source))))
        if aligned_source.size
        else 0.0
    )
    output_rms = (
        float(np.sqrt(np.mean(np.square(aligned_output))))
        if aligned_output.size
        else 0.0
    )
    gain = source_rms / output_rms if source_rms > 0 and output_rms > 0 else 1.0
    normalized_output = aligned_output * gain

    if source_rms > 0 and aligned_source.size:
        delta_rms = float(
            np.sqrt(np.mean(np.square(aligned_source - normalized_output)))
        )
        aligned_nrmse = delta_rms / source_rms
    else:
        aligned_nrmse = None

    if (
        aligned_source.size > 1
        and np.std(aligned_source) > 0
        and np.std(normalized_output) > 0
    ):
        correlation = float(np.corrcoef(aligned_source, normalized_output)[0, 1])
    elif np.array_equal(aligned_source, normalized_output):
        correlation = 1.0
    else:
        correlation = None

    if aligned_source.size:
        source_spectra = _log_spectra(aligned_source, parameters.spectral_fft_size)
        output_spectra = _log_spectra(normalized_output, parameters.spectral_fft_size)
        frame_count = min(source_spectra.shape[0], output_spectra.shape[0])
        spectral_distance = float(
            np.mean(np.abs(source_spectra[:frame_count] - output_spectra[:frame_count]))
        )
    else:
        spectral_distance = None

    exact_match = (
        source.sample_rate == output.sample_rate
        and source.channels == output.channels
        and source.samples.shape == output.samples.shape
        and np.array_equal(source.samples, output.samples)
    )
    duration_ratio = (
        output.duration_seconds / source.duration_seconds
        if source.duration_seconds > 0
        else None
    )

    return {
        "analysis_parameters": asdict(parameters),
        "source": _signal_stats(source, parameters),
        "output": _signal_stats(output, parameters),
        "comparison": {
            "exact_sample_match": exact_match,
            "alignment_lag_samples_at_source_rate": lag,
            "aligned_overlap_frames": int(aligned_source.size),
            "gain_applied_for_comparison": _finite_float(gain),
            "aligned_gain_normalized_nrmse": _finite_float(aligned_nrmse)
            if aligned_nrmse is not None
            else None,
            "aligned_gain_normalized_correlation": _finite_float(correlation)
            if correlation is not None
            else None,
            "mean_absolute_log_spectral_distance": _finite_float(spectral_distance)
            if spectral_distance is not None
            else None,
            "duration_ratio": _finite_float(duration_ratio)
            if duration_ratio is not None
            else None,
        },
    }
