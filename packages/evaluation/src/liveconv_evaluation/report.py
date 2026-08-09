"""Render-level and aggregate report construction."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .audio import AnalysisParameters, compare_signals, read_wav, sha256_file
from .transcript import (
    NORMALIZATION_REVISION,
    compare_exact_entities,
    compare_transcripts,
)
from .verdict import LaneVerdict, ThresholdPolicy, evaluate_measurements


@dataclass(frozen=True)
class SttEvidence:
    provider: str
    model_revision: str
    decode_config: Mapping[str, Any]
    language: str
    transcribed_at: str
    normalization_revision: str = NORMALIZATION_REVISION

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "model_revision",
            "language",
            "transcribed_at",
            "normalization_revision",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"STT evidence {name} must not be empty")
        if not isinstance(self.decode_config, Mapping):
            raise ValueError("STT evidence decode_config must be an object")
        if self.normalization_revision != NORMALIZATION_REVISION:
            raise ValueError(
                "STT evidence normalization_revision must match the executable "
                f"revision {NORMALIZATION_REVISION}"
            )
        parsed = datetime.fromisoformat(self.transcribed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("STT evidence transcribed_at must include a timezone")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SttEvidence:
        required = {
            "provider",
            "model_revision",
            "decode_config",
            "language",
            "transcribed_at",
            "normalization_revision",
        }
        if set(value) != required:
            raise ValueError("STT evidence has missing or unknown fields")
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["decode_config"] = dict(self.decode_config)
        return result


def _artifact(
    path: str | Path,
    signal: Mapping[str, Any],
    locator: str | None,
) -> dict[str, Any]:
    artifact_path = Path(path)
    digest = sha256_file(artifact_path)
    return {
        "locator": locator or f"artifact:sha256:{digest}",
        "sha256": digest,
        "bytes": artifact_path.stat().st_size,
        "audio": dict(signal),
    }


def _transcript_metrics(
    reference: str | None,
    source: str | None,
    output: str | None,
    exact_entities: Iterable[str] | None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if reference is not None and source is not None:
        metrics["reference_to_source"] = compare_transcripts(
            reference, source
        ).to_dict()
    if reference is not None and output is not None:
        metrics["reference_to_output"] = compare_transcripts(
            reference, output
        ).to_dict()
    if source is not None and output is not None:
        metrics["source_to_output"] = compare_transcripts(source, output).to_dict()
    if exact_entities is not None:
        if output is None:
            raise ValueError(
                "output_transcript is required when exact_entities are supplied"
            )
        metrics["exact_entities"] = compare_exact_entities(exact_entities, output)
    return metrics


def build_render_report(
    source_path: str | Path,
    output_path: str | Path,
    *,
    reference_transcript: str | None = None,
    source_transcript: str | None = None,
    output_transcript: str | None = None,
    exact_entities: Iterable[str] | None = None,
    source_stt_evidence: SttEvidence | None = None,
    output_stt_evidence: SttEvidence | None = None,
    threshold_policy: ThresholdPolicy | None = None,
    analysis_parameters: AnalysisParameters | None = None,
    speaker_change: LaneVerdict | None = None,
    streaming_operations: LaneVerdict | None = None,
    source_locator: str | None = None,
    output_locator: str | None = None,
    render_id: str | None = None,
) -> dict[str, Any]:
    source_signal = read_wav(source_path)
    output_signal = read_wav(output_path)
    audio = compare_signals(source_signal, output_signal, analysis_parameters)
    source_artifact = _artifact(source_path, audio["source"], source_locator)
    output_artifact = _artifact(output_path, audio["output"], output_locator)
    source_hash = source_artifact["sha256"]
    output_hash = output_artifact["sha256"]
    transcripts = _transcript_metrics(
        reference_transcript,
        source_transcript,
        output_transcript,
        exact_entities,
    )
    stt_evidence = {
        "source": source_stt_evidence.to_dict() if source_stt_evidence else None,
        "output": output_stt_evidence.to_dict() if output_stt_evidence else None,
    }
    verdict = evaluate_measurements(
        audio,
        transcripts,
        threshold_policy,
        speaker_change=speaker_change,
        operations=streaming_operations,
        stt_evidence=stt_evidence,
        source_sha256=source_hash,
        output_sha256=output_hash,
    )
    limitations = ["Waveform difference alone does not prove voice conversion."]
    if speaker_change is None:
        limitations.append(
            "This report contains no calibrated speaker-change evidence."
        )
    if streaming_operations is None:
        limitations.append(
            "A two-file comparison contains no streaming interruption evidence."
        )
    if source_transcript is not None and source_stt_evidence is None:
        limitations.append("The source transcript has no attached STT provenance.")
    if output_transcript is not None and output_stt_evidence is None:
        limitations.append("The output transcript has no attached STT provenance.")

    return {
        "schema_version": 1,
        "report_type": "render-comparison",
        "render_id": render_id or f"render-{source_hash[:12]}-{output_hash[:12]}",
        "artifacts": {
            "source": source_artifact,
            "output": output_artifact,
        },
        "measurements": {
            "analysis_parameters": audio["analysis_parameters"],
            "waveform": audio["comparison"],
            "transcripts": transcripts,
            "stt_evidence": stt_evidence,
        },
        "threshold_policy": threshold_policy.to_dict() if threshold_policy else None,
        "verdict": verdict.to_dict(),
        "limitations": limitations,
    }


def _number_at(report: Mapping[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = report
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _summary(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
        "mean": float(np.mean(array)),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
    }


_AGGREGATE_METRICS = {
    "aligned_gain_normalized_nrmse": (
        "measurements",
        "waveform",
        "aligned_gain_normalized_nrmse",
    ),
    "mean_absolute_log_spectral_distance": (
        "measurements",
        "waveform",
        "mean_absolute_log_spectral_distance",
    ),
    "duration_ratio": ("measurements", "waveform", "duration_ratio"),
    "output_clipped_sample_fraction": (
        "artifacts",
        "output",
        "audio",
        "clipped_sample_fraction",
    ),
    "output_silence_frame_fraction": (
        "artifacts",
        "output",
        "audio",
        "silence_frame_fraction",
    ),
    "output_max_adjacent_sample_delta": (
        "artifacts",
        "output",
        "audio",
        "max_adjacent_sample_delta",
    ),
    "output_interior_silence_run_count": (
        "artifacts",
        "output",
        "audio",
        "interior_silence_run_count",
    ),
    "output_max_interior_silence_run_frames": (
        "artifacts",
        "output",
        "audio",
        "max_interior_silence_run_frames",
    ),
    "output_adjacent_repeated_segment_count": (
        "artifacts",
        "output",
        "audio",
        "adjacent_repeated_segment_count",
    ),
    "output_max_adjacent_repeated_segment_frames": (
        "artifacts",
        "output",
        "audio",
        "max_adjacent_repeated_segment_frames",
    ),
    "reference_to_output_cer": (
        "measurements",
        "transcripts",
        "reference_to_output",
        "character_error_rate",
    ),
}


def aggregate_render_reports(
    reports: Iterable[Mapping[str, Any]], *, run_id: str, variant_id: str
) -> dict[str, Any]:
    report_list = list(reports)
    summaries: dict[str, Any] = {}
    for name, path in _AGGREGATE_METRICS.items():
        values = [
            value
            for report in report_list
            if (value := _number_at(report, path)) is not None
        ]
        if values:
            summaries[name] = _summary(values)

    verdict_counts: dict[str, dict[str, int]] = {}
    for lane in (
        "transformation_evidence",
        "content_preservation",
        "speaker_change",
        "audio_integrity",
        "streaming_operations",
    ):
        statuses = Counter(
            report.get("verdict", {})
            .get("lanes", {})
            .get(lane, {})
            .get("status", "unassessed")
            for report in report_list
        )
        verdict_counts[lane] = dict(sorted(statuses.items()))

    return {
        "schema_version": 1,
        "report_type": "aggregate-report",
        "run_id": run_id,
        "variant_id": variant_id,
        "render_count": len(report_list),
        "eligible_render_count": len(report_list),
        "exclusions": [],
        "metric_summaries": summaries,
        "verdict_counts": verdict_counts,
        "decision": "unassessed",
        "uncertainty": "No confidence interval method was supplied.",
    }
