"""Explicit five-lane verdicts driven only by caller-supplied thresholds."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .transcript import NORMALIZATION_REVISION


class VerdictStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNASSESSED = "unassessed"


@dataclass(frozen=True)
class LaneVerdict:
    status: VerdictStatus
    summary: str
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "summary": self.summary,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class EvaluationVerdict:
    transformation_evidence: LaneVerdict
    content_preservation: LaneVerdict
    speaker_change: LaneVerdict
    audio_integrity: LaneVerdict
    streaming_operations: LaneVerdict
    policy_status: str | None = None
    content_evidence_complete: bool = False
    overall: VerdictStatus = field(init=False)

    def __post_init__(self) -> None:
        statuses = (
            self.transformation_evidence.status,
            self.content_preservation.status,
            self.speaker_change.status,
            self.audio_integrity.status,
            self.streaming_operations.status,
        )
        external_evidence_complete = all(
            _has_nonempty_evidence(lane)
            for lane in (self.speaker_change, self.streaming_operations)
        )
        if VerdictStatus.FAIL in statuses:
            overall = VerdictStatus.FAIL
        elif (
            all(status is VerdictStatus.PASS for status in statuses)
            and self.policy_status == "approved"
            and self.content_evidence_complete
            and external_evidence_complete
        ):
            overall = VerdictStatus.PASS
        else:
            overall = VerdictStatus.UNASSESSED
        object.__setattr__(self, "overall", overall)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "lanes": {
                "transformation_evidence": self.transformation_evidence.to_dict(),
                "content_preservation": self.content_preservation.to_dict(),
                "speaker_change": self.speaker_change.to_dict(),
                "audio_integrity": self.audio_integrity.to_dict(),
                "streaming_operations": self.streaming_operations.to_dict(),
            },
        }


_THRESHOLD_NAMES = {
    "min_aligned_nrmse_for_waveform_difference",
    "min_log_spectral_distance_for_waveform_difference",
    "max_output_clipped_fraction",
    "max_output_silence_fraction",
    "max_duration_ratio_delta",
    "max_output_nonfinite_samples",
    "max_output_adjacent_sample_delta",
    "max_output_interior_silence_run_frames",
    "max_output_adjacent_repeated_segment_frames",
    "max_reference_cer",
    "max_cer_degradation",
    "min_exact_entity_match_rate",
}

_FRACTION_THRESHOLDS = {
    "max_output_clipped_fraction",
    "max_output_silence_fraction",
    "min_exact_entity_match_rate",
}

_REQUIRED_INTEGRITY_THRESHOLDS = {
    "max_output_clipped_fraction",
    "max_output_silence_fraction",
    "max_duration_ratio_delta",
    "max_output_nonfinite_samples",
    "max_output_adjacent_sample_delta",
    "max_output_interior_silence_run_frames",
    "max_output_adjacent_repeated_segment_frames",
}

_REQUIRED_STT_FIELDS = {
    "provider",
    "model_revision",
    "decode_config",
    "language",
    "transcribed_at",
    "normalization_revision",
}


def _has_nonempty_evidence(lane: LaneVerdict) -> bool:
    return lane.status is not VerdictStatus.PASS or any(
        isinstance(item, str) and item.strip() for item in lane.evidence
    )


def _valid_stt_evidence(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != _REQUIRED_STT_FIELDS:
        return False
    if not isinstance(value.get("decode_config"), Mapping):
        return False
    string_fields = _REQUIRED_STT_FIELDS - {"decode_config"}
    if any(
        not isinstance(value.get(name), str) or not value[name].strip()
        for name in string_fields
    ):
        return False
    return value["normalization_revision"] == NORMALIZATION_REVISION


def _content_evidence_issues(
    transcripts: Mapping[str, Any], stt_evidence: Mapping[str, Any] | None
) -> list[str]:
    issues: list[str] = []
    for name in ("reference_to_source", "reference_to_output"):
        metrics = transcripts.get(name)
        if not isinstance(metrics, Mapping):
            issues.append(f"{name}_transcript_metrics_missing")
            continue
        for field_name in ("normalized_reference", "normalized_hypothesis"):
            value = metrics.get(field_name)
            if not isinstance(value, str) or not value:
                issues.append(f"{name}_{field_name}_empty")

    evidence = stt_evidence if isinstance(stt_evidence, Mapping) else {}
    for name in ("source", "output"):
        if not _valid_stt_evidence(evidence.get(name)):
            issues.append(f"{name}_stt_provenance_missing_or_invalid")
    return issues


@dataclass(frozen=True)
class ThresholdPolicy:
    label: str
    status: str
    values: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("threshold policy label must not be empty")
        if self.status not in {"proposed", "approved"}:
            raise ValueError("threshold policy status must be proposed or approved")
        unknown = set(self.values) - _THRESHOLD_NAMES
        if unknown:
            raise ValueError(f"unknown threshold names: {', '.join(sorted(unknown))}")
        for name, value in self.values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"threshold {name} must be numeric")
            if not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"threshold {name} must be finite and non-negative")
            if name in _FRACTION_THRESHOLDS and value > 1:
                raise ValueError(f"threshold {name} must not exceed 1")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ThresholdPolicy:
        if set(value) != {"label", "status", "values"}:
            raise ValueError(
                "threshold policy requires exactly label, status, and values"
            )
        raw_values = value["values"]
        if not isinstance(raw_values, Mapping):
            raise ValueError("threshold policy values must be an object")
        return cls(str(value["label"]), str(value["status"]), dict(raw_values))

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "status": self.status, "values": dict(self.values)}


def _condition(
    name: str,
    actual: float | int | None,
    threshold: float,
    relation: str,
) -> tuple[bool, str]:
    if actual is None:
        return False, f"{name} unavailable"
    passed = actual >= threshold if relation == "min" else actual <= threshold
    operator = ">=" if relation == "min" else "<="
    return passed, f"{name}={actual:.8g} {operator} {threshold:.8g}"


def _lane_from_conditions(
    conditions: list[tuple[bool, str]], unassessed_summary: str, assessed_summary: str
) -> LaneVerdict:
    if not conditions:
        return LaneVerdict(VerdictStatus.UNASSESSED, unassessed_summary)
    passed = all(item[0] for item in conditions)
    return LaneVerdict(
        VerdictStatus.PASS if passed else VerdictStatus.FAIL,
        assessed_summary,
        tuple(item[1] for item in conditions),
    )


def _integrity_lane(
    conditions: list[tuple[bool, str]], supplied_thresholds: set[str]
) -> LaneVerdict:
    evidence = [condition[1] for condition in conditions]
    if any(not condition[0] for condition in conditions):
        return LaneVerdict(
            VerdictStatus.FAIL,
            "At least one supplied audio-integrity guardrail failed.",
            tuple(evidence),
        )

    missing = sorted(_REQUIRED_INTEGRITY_THRESHOLDS - supplied_thresholds)
    if missing:
        evidence.append(f"missing_guardrails={','.join(missing)}")
        return LaneVerdict(
            VerdictStatus.UNASSESSED,
            "All required audio-integrity guardrails must be supplied before pass.",
            tuple(evidence),
        )

    return LaneVerdict(
        VerdictStatus.PASS,
        "All required audio-integrity guardrails passed.",
        tuple(evidence),
    )


def evaluate_measurements(
    audio: Mapping[str, Any],
    transcripts: Mapping[str, Any],
    policy: ThresholdPolicy | None,
    *,
    speaker_change: LaneVerdict | None = None,
    operations: LaneVerdict | None = None,
    stt_evidence: Mapping[str, Any] | None = None,
) -> EvaluationVerdict:
    """Build five independent lanes; no policy means no implicit verdict."""

    unavailable = LaneVerdict(
        VerdictStatus.UNASSESSED, "No caller-supplied threshold policy."
    )
    speaker_change = speaker_change or LaneVerdict(
        VerdictStatus.UNASSESSED,
        "A two-file comparison has no calibrated speaker-change evidence.",
    )
    operations = operations or LaneVerdict(
        VerdictStatus.UNASSESSED,
        "A two-file comparison has no streaming trace or interruption evidence.",
    )
    if policy is None:
        return EvaluationVerdict(
            transformation_evidence=unavailable,
            content_preservation=unavailable,
            speaker_change=speaker_change,
            audio_integrity=unavailable,
            streaming_operations=operations,
            policy_status=None,
            content_evidence_complete=False,
        )

    values = policy.values
    comparison = audio["comparison"]
    output = audio["output"]

    transformation_conditions: list[tuple[bool, str]] = []
    if "min_aligned_nrmse_for_waveform_difference" in values:
        transformation_conditions.append(
            _condition(
                "aligned_gain_normalized_nrmse",
                comparison.get("aligned_gain_normalized_nrmse"),
                values["min_aligned_nrmse_for_waveform_difference"],
                "min",
            )
        )
    if "min_log_spectral_distance_for_waveform_difference" in values:
        transformation_conditions.append(
            _condition(
                "mean_absolute_log_spectral_distance",
                comparison.get("mean_absolute_log_spectral_distance"),
                values["min_log_spectral_distance_for_waveform_difference"],
                "min",
            )
        )
    transformation = _lane_from_conditions(
        transformation_conditions,
        "No meaningful waveform-difference threshold was supplied.",
        "Signal-difference thresholds only; this is not proof of voice conversion.",
    )

    content_conditions: list[tuple[bool, str]] = []
    reference_to_output = transcripts.get("reference_to_output")
    if "max_reference_cer" in values:
        content_conditions.append(
            _condition(
                "reference_to_output_cer",
                reference_to_output.get("character_error_rate")
                if reference_to_output
                else None,
                values["max_reference_cer"],
                "max",
            )
        )
    if "max_cer_degradation" in values:
        reference_to_source = transcripts.get("reference_to_source")
        output_cer = (
            reference_to_output.get("character_error_rate")
            if reference_to_output
            else None
        )
        source_cer = (
            reference_to_source.get("character_error_rate")
            if reference_to_source
            else None
        )
        degradation = (
            output_cer - source_cer
            if output_cer is not None and source_cer is not None
            else None
        )
        content_conditions.append(
            _condition(
                "reference_cer_degradation",
                degradation,
                values["max_cer_degradation"],
                "max",
            )
        )
    if "min_exact_entity_match_rate" in values:
        entity_metrics = transcripts.get("exact_entities")
        content_conditions.append(
            _condition(
                "exact_entity_match_rate",
                entity_metrics.get("exact_match_rate") if entity_metrics else None,
                values["min_exact_entity_match_rate"],
                "min",
            )
        )
    content = _lane_from_conditions(
        content_conditions,
        "No transcript-preservation threshold was supplied.",
        "Transcript preservation evaluated with deterministic normalization.",
    )
    content_evidence_issues = _content_evidence_issues(transcripts, stt_evidence)
    if content.status is VerdictStatus.PASS and content_evidence_issues:
        content = LaneVerdict(
            VerdictStatus.UNASSESSED,
            "Complete non-empty transcripts and STT provenance are required "
            "before pass.",
            content.evidence
            + tuple(f"evidence_gap={issue}" for issue in content_evidence_issues),
        )

    integrity_conditions: list[tuple[bool, str]] = []
    if "max_output_clipped_fraction" in values:
        integrity_conditions.append(
            _condition(
                "output_clipped_sample_fraction",
                output.get("clipped_sample_fraction"),
                values["max_output_clipped_fraction"],
                "max",
            )
        )
    if "max_output_silence_fraction" in values:
        integrity_conditions.append(
            _condition(
                "output_silence_frame_fraction",
                output.get("silence_frame_fraction"),
                values["max_output_silence_fraction"],
                "max",
            )
        )
    if "max_duration_ratio_delta" in values:
        ratio = comparison.get("duration_ratio")
        delta = abs(ratio - 1.0) if ratio is not None else None
        integrity_conditions.append(
            _condition(
                "duration_ratio_delta",
                delta,
                values["max_duration_ratio_delta"],
                "max",
            )
        )
    if "max_output_nonfinite_samples" in values:
        integrity_conditions.append(
            _condition(
                "output_nonfinite_sample_count",
                output.get("nonfinite_sample_count"),
                values["max_output_nonfinite_samples"],
                "max",
            )
        )
    if "max_output_adjacent_sample_delta" in values:
        integrity_conditions.append(
            _condition(
                "output_max_adjacent_sample_delta",
                output.get("max_adjacent_sample_delta"),
                values["max_output_adjacent_sample_delta"],
                "max",
            )
        )
    if "max_output_interior_silence_run_frames" in values:
        integrity_conditions.append(
            _condition(
                "output_max_interior_silence_run_frames",
                output.get("max_interior_silence_run_frames"),
                values["max_output_interior_silence_run_frames"],
                "max",
            )
        )
    if "max_output_adjacent_repeated_segment_frames" in values:
        integrity_conditions.append(
            _condition(
                "output_max_adjacent_repeated_segment_frames",
                output.get("max_adjacent_repeated_segment_frames"),
                values["max_output_adjacent_repeated_segment_frames"],
                "max",
            )
        )
    integrity = _integrity_lane(
        integrity_conditions,
        set(values) & _REQUIRED_INTEGRITY_THRESHOLDS,
    )
    return EvaluationVerdict(
        transformation_evidence=transformation,
        content_preservation=content,
        speaker_change=speaker_change,
        audio_integrity=integrity,
        streaming_operations=operations,
        policy_status=policy.status,
        content_evidence_complete=not content_evidence_issues,
    )
