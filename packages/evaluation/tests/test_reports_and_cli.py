from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from liveconv_evaluation.cli import main
from liveconv_evaluation.report import (
    SttEvidence,
    aggregate_render_reports,
    build_render_report,
)
from liveconv_evaluation.transcript import NORMALIZATION_REVISION

from ._support import write_pcm16

ROOT = Path(__file__).resolve().parents[1]

PASS_THRESHOLD_VALUES = {
    "min_aligned_nrmse_for_waveform_difference": 0.01,
    "min_log_spectral_distance_for_waveform_difference": 0.01,
    "max_output_clipped_fraction": 0.01,
    "max_output_silence_fraction": 0.95,
    "max_duration_ratio_delta": 0.1,
    "max_output_nonfinite_samples": 0,
    "max_output_adjacent_sample_delta": 2.0,
    "max_output_interior_silence_run_frames": 5,
    "max_output_adjacent_repeated_segment_frames": 0,
    "max_reference_cer": 0.1,
    "max_cer_degradation": 0.05,
    "min_exact_entity_match_rate": 1.0,
}


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _schema_pass_report(tmp_path, sine, sample_rate):
    # This fixture exercises report structure; evaluator tests cover metric arithmetic.
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)
    evidence = SttEvidence(
        provider="test-provider",
        model_revision="test-model@abc123",
        decode_config={"temperature": 0},
        language="ja-JP",
        transcribed_at="2026-08-09T12:00:00Z",
    )
    report = build_render_report(
        source,
        output,
        reference_transcript="おんせいです",
        source_transcript="おんせいです",
        output_transcript="おんせいです",
        exact_entities=["おんせい"],
        source_stt_evidence=evidence,
        output_stt_evidence=evidence,
    )
    report["threshold_policy"] = {
        "label": "approved schema fixture",
        "status": "approved",
        "values": dict(PASS_THRESHOLD_VALUES),
    }
    report["verdict"]["overall"] = "pass"
    evidence_counts = {
        "transformation_evidence": 2,
        "content_preservation": 3,
        "speaker_change": 1,
        "audio_integrity": 7,
        "streaming_operations": 1,
    }
    for lane_name, lane in report["verdict"]["lanes"].items():
        lane["status"] = "pass"
        lane["evidence"] = [
            f"fixture={lane_name}:{index}"
            for index in range(evidence_counts[lane_name])
        ]
    return report


def test_render_and_aggregate_reports_match_schemas(tmp_path, sine, sample_rate):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)
    evidence = SttEvidence(
        provider="test-provider",
        model_revision="test-model@abc123",
        decode_config={"temperature": 0, "beam_size": 1},
        language="ja",
        transcribed_at="2026-08-09T12:00:00Z",
    )
    report = build_render_report(
        source,
        output,
        reference_transcript="電話番号は09012345678です",
        source_transcript="電話番号は09012345678です",
        output_transcript="電話番号は09012345678です",
        exact_entities=["09012345678"],
        source_stt_evidence=evidence,
        output_stt_evidence=evidence,
    )

    jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
        report
    )
    aggregate = aggregate_render_reports([report], run_id="run-test", variant_id="gain")
    jsonschema.Draft202012Validator(_schema("aggregate-report.schema.json")).validate(
        aggregate
    )
    assert aggregate["render_count"] == 1
    assert aggregate["decision"] == "unassessed"
    assert (
        aggregate["metric_summaries"]["output_max_adjacent_sample_delta"]["count"] == 1
    )
    assert (
        aggregate["metric_summaries"]["output_max_interior_silence_run_frames"]["count"]
        == 1
    )
    assert (
        aggregate["metric_summaries"]["output_max_adjacent_repeated_segment_frames"][
            "count"
        ]
        == 1
    )
    assert report["measurements"]["stt_evidence"]["output"]["model_revision"] == (
        "test-model@abc123"
    )
    assert report["artifacts"]["source"]["locator"].startswith("artifact:sha256:")
    assert str(source) not in report["artifacts"]["source"]["locator"]

    invalid_pass = deepcopy(report)
    invalid_pass["threshold_policy"] = {
        "label": "still only proposed",
        "status": "proposed",
        "values": {},
    }
    invalid_pass["verdict"]["overall"] = "pass"
    for lane in invalid_pass["verdict"]["lanes"].values():
        lane["status"] = "pass"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
            invalid_pass
        )


def test_pass_report_requires_transcripts_stt_and_external_lane_evidence(
    tmp_path, sine, sample_rate
):
    valid_pass = _schema_pass_report(tmp_path, sine, sample_rate)

    validator = jsonschema.Draft202012Validator(_schema("render-report.schema.json"))
    validator.validate(valid_pass)

    invalid_reports = []
    null_stt = deepcopy(valid_pass)
    null_stt["measurements"]["stt_evidence"]["output"] = None
    invalid_reports.append(null_stt)
    empty_transcript = deepcopy(valid_pass)
    empty_transcript["measurements"]["transcripts"]["reference_to_output"][
        "normalized_hypothesis"
    ] = ""
    invalid_reports.append(empty_transcript)
    empty_speaker_evidence = deepcopy(valid_pass)
    empty_speaker_evidence["verdict"]["lanes"]["speaker_change"]["evidence"] = []
    invalid_reports.append(empty_speaker_evidence)
    blank_streaming_evidence = deepcopy(valid_pass)
    blank_streaming_evidence["verdict"]["lanes"]["streaming_operations"]["evidence"] = [
        " "
    ]
    invalid_reports.append(blank_streaming_evidence)

    for invalid_report in invalid_reports:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid_report)


@pytest.mark.parametrize("missing_threshold", sorted(PASS_THRESHOLD_VALUES))
def test_pass_report_requires_every_executable_lane_threshold(
    tmp_path, sine, sample_rate, missing_threshold
):
    report = _schema_pass_report(tmp_path, sine, sample_rate)
    del report["threshold_policy"]["values"][missing_threshold]

    validator = jsonschema.Draft202012Validator(_schema("render-report.schema.json"))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(report)


def test_fixture_can_only_freeze_with_immutable_generation_revisions():
    manifest = json.loads(
        (ROOT / "fixtures" / "router-speech-v1.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(_schema("fixture-manifest.schema.json"))

    validator.validate(manifest)
    assert manifest["normalization_revision"] == NORMALIZATION_REVISION

    incomplete_frozen = deepcopy(manifest)
    incomplete_frozen["status"] = "frozen"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(incomplete_frozen)

    complete_frozen = deepcopy(incomplete_frozen)
    complete_frozen["source_generation"].update(
        {
            "engine": "test-engine",
            "model_revision": "test-model@abc123",
            "voice_revisions": ["voice-a@abc123"],
        }
    )
    for index, condition in enumerate(complete_frozen["render_conditions"]):
        condition["voice_revision"] = f"voice-{index}@abc123"
    validator.validate(complete_frozen)


def test_stt_evidence_rejects_a_different_normalization_revision():
    with pytest.raises(ValueError, match="normalization_revision"):
        SttEvidence(
            provider="test-provider",
            model_revision="test-model@abc123",
            decode_config={},
            language="ja-JP",
            transcribed_at="2026-08-09T12:00:00Z",
            normalization_revision="different-normalizer-v1",
        )


def test_cli_emits_deterministic_unassessed_report(tmp_path, sine, sample_rate, capsys):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine, sample_rate)

    assert main(["compare", str(source), str(output)]) == 0
    first = capsys.readouterr().out
    assert main(["compare", str(source), str(output)]) == 0
    second = capsys.readouterr().out

    assert first == second
    report = json.loads(first)
    assert report["verdict"]["overall"] == "unassessed"
    assert report["verdict"]["lanes"]["speaker_change"]["status"] == "unassessed"
    assert report["verdict"]["lanes"]["streaming_operations"]["status"] == "unassessed"
