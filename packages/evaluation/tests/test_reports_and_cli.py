from __future__ import annotations

import hashlib
import json
import wave
from copy import deepcopy
from dataclasses import replace
from importlib import resources
from pathlib import Path

import jsonschema
import liveconv_evaluation.cli as evaluation_cli
import liveconv_evaluation.external as evaluation_external
import liveconv_speaker.authorization as speaker_authorization
import numpy as np
import pytest
from liveconv_evaluation.audio import sha256_file
from liveconv_evaluation.cli import main
from liveconv_evaluation.report import (
    SttEvidence,
    aggregate_render_reports,
    build_render_report,
)
from liveconv_evaluation.transcript import NORMALIZATION_REVISION
from liveconv_evaluation.verdict import (
    EvaluationVerdict,
    LaneVerdict,
    ThresholdPolicy,
    VerdictStatus,
)

from ._support import write_pcm16

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
SYNTHETIC_TARGET_SHA256 = (
    "a92aaa78a600be0afa2425e55a8adb57dc0630789ce9a50284bf467345631ff7"
)
SYNTHETIC_AUTHORIZATION_SHA256 = (
    "6ccedfbd58e2d0ab6e2b463c91c1c38d92654857dd4cb63e2d2e8075d9e3284c"
)

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

PERMISSIVE_PASS_THRESHOLD_VALUES = {
    "min_aligned_nrmse_for_waveform_difference": 0.0,
    "min_log_spectral_distance_for_waveform_difference": 0.0,
    "max_output_clipped_fraction": 1.0,
    "max_output_silence_fraction": 1.0,
    "max_duration_ratio_delta": 10.0,
    "max_output_nonfinite_samples": 0,
    "max_output_adjacent_sample_delta": 2.0,
    "max_output_interior_silence_run_frames": 1_000_000,
    "max_output_adjacent_repeated_segment_frames": 1_000_000,
    "max_reference_cer": 1.0,
    "max_cer_degradation": 1.0,
    "min_exact_entity_match_rate": 0.0,
}


def _schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _audio_artifact(path: Path) -> dict:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        sample_rate = audio.getframerate()
        channels = audio.getnchannels()
    return {
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "duration_seconds": round(frames / sample_rate, 9),
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": 2,
    }


def _speaker_envelope(source: Path, output: Path, *, status="fail", policy="approved"):
    model_digest = "a" * 64
    target = {
        "sha256": SYNTHETIC_TARGET_SHA256,
        "bytes": 686_466,
        "duration_seconds": 14.300458333,
        "sample_rate_hz": 24_000,
        "channels": 1,
        "sample_width_bytes": 2,
    }
    evidence = [
        "target_to_output=0.9 >= 0.8",
        "target_similarity_gain=0.1 >= 0.1",
        "target_advantage=0.2 >= 0.2",
    ]
    metrics = (
        {
            "source_to_target": 0.1,
            "source_to_output": 0.2,
            "target_to_output": 0.9,
            "target_similarity_gain": 0.8,
            "target_advantage": 0.7,
        }
        if status == "pass"
        else {
            "source_to_target": 0.5,
            "source_to_output": 0.6,
            "target_to_output": 0.5,
            "target_similarity_gain": 0.0,
            "target_advantage": -0.1,
        }
    )
    return {
        "schema_version": 1,
        "report_type": "speaker-change-evidence",
        "evaluator": {
            "implementation": "liveconv-speaker-ecapa-v1",
            "model_revision": f"fixture-ecapa@sha256:{model_digest}",
            "model_sha256": model_digest,
            "runtime_lock": {
                "revision": "liveconv-speaker-hash-locked-runtime-v1",
                "sha256": (
                    "036443cefaffc07492b31078f861d7bd5c816b96007819c63323968089760fd3"
                ),
                "packages": {
                    "requests": "2.32.5",
                    "speechbrain": "1.0.3",
                    "torch": "2.6.0",
                    "torchaudio": "2.6.0",
                },
            },
            "device": "cpu",
            "embedding_dimensions": 192,
            "embeddings_persisted": False,
        },
        "artifacts": {
            "source": _audio_artifact(source),
            "target": target,
            "output": _audio_artifact(output),
        },
        "target_authorization": {
            "type": "synthetic-corpus-manifest",
            "authorization_id": "liveconv-project-authored-synthetic-ja-v1",
            "record_sha256": SYNTHETIC_AUTHORIZATION_SHA256,
            "target_artifact_sha256": target["sha256"],
            "status": "approved",
        },
        "policy": {
            "label": "fixture speaker policy",
            "status": policy,
            "min_target_similarity": 0.8,
            "min_target_gain": 0.1,
            "min_target_advantage": 0.2,
        },
        "speaker_change": {
            **metrics,
            "status": status,
            "evidence": evidence,
        },
        "evaluation_lane": {
            "status": status,
            "summary": "Bound speaker evidence was evaluated.",
            "evidence": evidence,
        },
        "limitations": ["Fixture evidence only."],
    }


def _streaming_envelope(source: Path, output: Path, *, status="pass"):
    checks = {
        "bounded_queues": True,
        "stale_generation_discard": True,
        "interruption_cancel": True,
    }
    return {
        "schema_version": 1,
        "report_type": "streaming-operations-evidence",
        "evaluator": {
            "implementation": "fixture-streaming-evaluator",
            "revision": "fixture-streaming==1.0.0",
            "runtime_lock": {
                "revision": "fixture-streaming-lock-v1",
                "sha256": "d" * 64,
                "packages": {"fixture-runner": "1.0.0"},
            },
        },
        "artifacts": {
            "source_sha256": sha256_file(source),
            "output_sha256": sha256_file(output),
        },
        "policy": {"label": "approved streaming policy", "status": "approved"},
        "streaming_operations": {
            "trace_sha256": "e" * 64,
            "checks": checks,
        },
        "evaluation_lane": {
            "status": status,
            "summary": "Bound streaming checks were evaluated.",
            "evidence": ["stale_generation_frames=0"],
        },
        "limitations": ["Fixture trace only."],
    }


def _load_pass_lanes(tmp_path: Path, prefix: str, source: Path, output: Path):
    source_sha256 = sha256_file(source)
    output_sha256 = sha256_file(output)
    speaker_path = tmp_path / f"{prefix}-speaker.json"
    streaming_path = tmp_path / f"{prefix}-streaming.json"
    speaker_path.write_text(
        json.dumps(_speaker_envelope(source, output, status="pass")),
        encoding="utf-8",
    )
    streaming_path.write_text(
        json.dumps(_streaming_envelope(source, output, status="pass")),
        encoding="utf-8",
    )
    speaker = evaluation_external.load_speaker_lane(
        speaker_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    streaming = evaluation_external.load_streaming_lane(
        streaming_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    assert speaker is not None
    assert streaming is not None
    return speaker, streaming


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
    source_sha256 = report["artifacts"]["source"]["sha256"]
    output_sha256 = report["artifacts"]["output"]["sha256"]
    report["verdict"]["lanes"]["speaker_change"]["provenance"] = {
        "schema_version": 1,
        "report_type": "speaker-change-evidence",
        "binding": {
            "verified": True,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
        },
        "evaluator": {"implementation": "fixture"},
        "artifacts": {"source": source_sha256, "output": output_sha256},
        "policy": {"label": "fixture", "status": "approved"},
        "target_authorization": {"status": "approved"},
    }
    report["verdict"]["lanes"]["streaming_operations"]["provenance"] = {
        "schema_version": 1,
        "report_type": "streaming-operations-evidence",
        "binding": {
            "verified": True,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
        },
        "evaluator": {"implementation": "fixture"},
        "artifacts": {"source": source_sha256, "output": output_sha256},
        "policy": {"label": "fixture", "status": "approved"},
        "streaming_operations": {"trace_sha256": "e" * 64},
    }
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


def test_cli_attaches_independent_speaker_and_streaming_lanes(
    tmp_path, sine, sample_rate, capsys
):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine, sample_rate)
    speaker = tmp_path / "speaker.json"
    streaming = tmp_path / "streaming.json"
    speaker.write_text(json.dumps(_speaker_envelope(source, output)), encoding="utf-8")
    streaming.write_text(
        json.dumps(_streaming_envelope(source, output)), encoding="utf-8"
    )

    assert (
        main(
            [
                "compare",
                str(source),
                str(output),
                "--speaker-lane",
                str(speaker),
                "--streaming-lane",
                str(streaming),
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["verdict"]["overall"] == "fail"
    assert report["verdict"]["lanes"]["speaker_change"]["status"] == "fail"
    assert report["verdict"]["lanes"]["streaming_operations"]["status"] == "pass"
    assert (
        report["verdict"]["lanes"]["speaker_change"]["provenance"]["evaluator"][
            "runtime_lock"
        ]["packages"]["torch"]
        == "2.6.0"
    )


def test_cli_rejects_passing_lane_without_evidence(tmp_path, sine, sample_rate):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine, sample_rate)
    lane = tmp_path / "lane.json"
    lane.write_text(
        json.dumps({"status": "pass", "summary": "unsupported", "evidence": []}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(["compare", str(source), str(output), "--speaker-lane", str(lane)])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(report_type="unrelated-report"),
        lambda value: value["artifacts"]["output"].update(sha256="f" * 64),
        lambda value: value["evaluator"].update(runtime_lock={}),
        lambda value: value["evaluator"]["runtime_lock"]["packages"].pop("requests"),
        lambda value: value["policy"].update(status="proposed"),
        lambda value: value["target_authorization"].update(status="proposed"),
        lambda value: value["target_authorization"].update(
            authorization_id="caller-says-approved", record_sha256="c" * 64
        ),
    ],
)
def test_cli_rejects_forged_stale_or_unapproved_speaker_pass(
    tmp_path, sine, sample_rate, mutation
):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)
    envelope = _speaker_envelope(source, output, status="pass")
    mutation(envelope)
    lane = tmp_path / "speaker.json"
    lane.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(SystemExit):
        main(["compare", str(source), str(output), "--speaker-lane", str(lane)])


def test_lane_envelopes_match_their_packaged_schemas(tmp_path, sine, sample_rate):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)

    jsonschema.Draft202012Validator(_schema("speaker-lane.schema.json")).validate(
        _speaker_envelope(source, output)
    )
    jsonschema.Draft202012Validator(_schema("streaming-lane.schema.json")).validate(
        _streaming_envelope(source, output)
    )


def test_report_publication_failure_preserves_previous_report(
    tmp_path, sine, sample_rate, monkeypatch
):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine, sample_rate)
    report = tmp_path / "report.json"
    report.write_text("previous-good-report\n", encoding="utf-8")

    def fail_replace(source_path, destination_path):
        raise OSError("simulated atomic replacement failure")

    monkeypatch.setattr("liveconv_evaluation.cli.os.replace", fail_replace)

    with pytest.raises(SystemExit):
        main(["compare", str(source), str(output), "--report", str(report)])

    assert report.read_text(encoding="utf-8") == "previous-good-report\n"
    assert list(tmp_path.glob(".report.json.*.tmp")) == []


def test_report_publish_replace_failure_restores_previous_report(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    report.write_text("previous-good-report\n", encoding="utf-8")
    real_replace = evaluation_cli.os.replace

    def fail_new_report_publish(source, destination):
        source_path = Path(source)
        if source_path.suffix == ".tmp" and Path(destination) == report:
            raise OSError("injected report replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(evaluation_cli.os, "replace", fail_new_report_publish)

    with pytest.raises(OSError, match="replace failure"):
        evaluation_cli._write_atomic(report, "new-report\n")

    assert report.read_text(encoding="utf-8") == "previous-good-report\n"
    assert list(tmp_path.glob(".report.json.*")) == []


def test_report_directory_fsync_failure_restores_previous_report(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    report.write_text("previous-good-report\n", encoding="utf-8")
    real_fsync = evaluation_cli.os.fsync
    calls = 0

    def fail_directory_fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(evaluation_cli.os, "fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="directory fsync failure"):
        evaluation_cli._write_atomic(report, "new-report\n")

    assert report.read_text(encoding="utf-8") == "previous-good-report\n"
    assert list(tmp_path.glob(".report.json.*")) == []


def test_report_rollback_failure_retains_old_and_new_recovery_artifacts(
    tmp_path, monkeypatch
):
    report = tmp_path / "report.json"
    report.write_text("previous-good-report\n", encoding="utf-8")
    real_replace = evaluation_cli.os.replace
    real_fsync = evaluation_cli.os.fsync
    fsync_calls = 0

    def fail_restore(source, destination):
        source_path = Path(source)
        if source_path.suffix == ".backup" and Path(destination) == report:
            raise OSError("injected restore failure")
        return real_replace(source, destination)

    def fail_directory_fsync(descriptor):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError("injected directory fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr(evaluation_cli.os, "replace", fail_restore)
    monkeypatch.setattr(evaluation_cli.os, "fsync", fail_directory_fsync)

    with pytest.raises(RuntimeError, match="recovery artifacts were retained"):
        evaluation_cli._write_atomic(report, "new-report\n")

    backups = list(tmp_path.glob(".report.json.*.backup"))
    temporaries = list(tmp_path.glob(".report.json.*.tmp"))
    assert not report.exists()
    assert len(backups) == len(temporaries) == 1
    assert backups[0].read_text(encoding="utf-8") == "previous-good-report\n"
    assert temporaries[0].read_text(encoding="utf-8") == "new-report\n"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["artifacts"]["source"].update(bytes=1),
        lambda value: value["evaluator"]["runtime_lock"]["packages"].update(
            requests="latest"
        ),
        lambda value: value["speaker_change"].update(target_to_output=1.01),
    ],
)
def test_producer_schema_invalid_speaker_evidence_cannot_publish_or_pass(
    tmp_path, sine, sample_rate, mutation
):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)
    envelope = _speaker_envelope(source, output, status="pass")
    mutation(envelope)
    producer_schema = json.loads(
        (
            REPOSITORY_ROOT
            / "packages/speaker/src/liveconv_speaker/schemas"
            / "speaker-evidence.schema.json"
        ).read_text(encoding="utf-8")
    )
    producer_errors = list(
        jsonschema.Draft202012Validator(producer_schema).iter_errors(envelope)
    )
    assert producer_errors
    lane = tmp_path / "speaker.json"
    lane.write_text(json.dumps(envelope), encoding="utf-8")
    report = tmp_path / "render.json"

    with pytest.raises(SystemExit):
        main(
            [
                "compare",
                str(source),
                str(output),
                "--speaker-lane",
                str(lane),
                "--report",
                str(report),
            ]
        )

    assert not report.exists()


@pytest.mark.parametrize(
    ("lane_name", "schema_name", "mutation"),
    [
        (
            "speaker_change",
            "speaker-lane.schema.json",
            lambda value: value["policy"].pop("min_target_gain"),
        ),
        (
            "streaming_operations",
            "streaming-lane.schema.json",
            lambda value: value["streaming_operations"]["checks"].pop(
                "interruption_cancel"
            ),
        ),
    ],
)
def test_direct_library_unvalidated_external_lane_cannot_return_schema_invalid_pass(
    tmp_path, lane_name, schema_name, mutation
):
    sample_rate = 16_000
    samples = np.arange(sample_rate, dtype=np.float64) / sample_rate
    source = write_pcm16(
        tmp_path / "source.wav", 0.25 * np.sin(2 * np.pi * 440 * samples), sample_rate
    )
    output = write_pcm16(
        tmp_path / "output.wav", 0.25 * np.sin(2 * np.pi * 880 * samples), sample_rate
    )
    envelope = (
        _speaker_envelope(source, output, status="pass")
        if lane_name == "speaker_change"
        else _streaming_envelope(source, output, status="pass")
    )
    mutation(envelope)
    assert list(
        jsonschema.Draft202012Validator(_schema(schema_name)).iter_errors(envelope)
    )

    source_sha256 = sha256_file(source)
    output_sha256 = sha256_file(output)
    speaker = LaneVerdict(
        VerdictStatus.PASS,
        "Caller claims a speaker pass.",
        ("speaker=pass",),
        {
            "report_type": "speaker-change-evidence",
            "binding": {"verified": True},
            "policy": {"status": "approved"},
        },
    )
    streaming = LaneVerdict(
        VerdictStatus.PASS,
        "Caller claims a streaming pass.",
        ("streaming=pass",),
        {
            "report_type": "streaming-operations-evidence",
            "binding": {"verified": True},
            "policy": {"status": "approved"},
        },
    )
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
        reference_transcript="注文番号123",
        source_transcript="注文番号123",
        output_transcript="注文番号123",
        exact_entities=["123"],
        source_stt_evidence=evidence,
        output_stt_evidence=evidence,
        threshold_policy=ThresholdPolicy(
            "complete approved policy", "approved", PASS_THRESHOLD_VALUES
        ),
        speaker_change=speaker,
        streaming_operations=streaming,
    )

    assert source_sha256 == report["artifacts"]["source"]["sha256"]
    assert output_sha256 == report["artifacts"]["output"]["sha256"]
    assert report["verdict"]["overall"] != "pass"
    assert report["verdict"]["lanes"][lane_name]["status"] == "unassessed"
    assert "provenance" not in report["verdict"]["lanes"][lane_name]
    jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
        report
    )


def test_direct_verdict_requires_complete_approved_policy_with_loaded_evidence(
    tmp_path, sine, sample_rate
):
    source = write_pcm16(tmp_path / "source.wav", sine, sample_rate)
    output = write_pcm16(tmp_path / "output.wav", sine * 0.8, sample_rate)
    source_sha256 = sha256_file(source)
    output_sha256 = sha256_file(output)
    speaker_path = tmp_path / "speaker.json"
    streaming_path = tmp_path / "streaming.json"
    speaker_path.write_text(
        json.dumps(_speaker_envelope(source, output, status="pass")),
        encoding="utf-8",
    )
    streaming_path.write_text(
        json.dumps(_streaming_envelope(source, output, status="pass")),
        encoding="utf-8",
    )
    speaker = evaluation_external.load_speaker_lane(
        speaker_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    streaming = evaluation_external.load_streaming_lane(
        streaming_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    assert speaker is not None
    assert streaming is not None
    internal = LaneVerdict(VerdictStatus.PASS, "Internal lane passed.", ("ok",))

    def verdict(policy: ThresholdPolicy) -> EvaluationVerdict:
        return EvaluationVerdict(
            transformation_evidence=internal,
            content_preservation=internal,
            speaker_change=speaker,
            audio_integrity=internal,
            streaming_operations=streaming,
            policy_status=policy.status,
            content_evidence_complete=True,
            threshold_policy=policy,
            source_sha256=source_sha256,
            output_sha256=output_sha256,
        )

    assert (
        verdict(
            ThresholdPolicy("complete approved", "approved", PASS_THRESHOLD_VALUES)
        ).overall
        is VerdictStatus.PASS
    )
    assert (
        verdict(ThresholdPolicy("incomplete approved", "approved", {})).overall
        is VerdictStatus.UNASSESSED
    )
    assert (
        verdict(
            ThresholdPolicy("complete proposed", "proposed", PASS_THRESHOLD_VALUES)
        ).overall
        is VerdictStatus.UNASSESSED
    )


def test_external_lanes_pass_same_render_and_reject_cross_render_replay(tmp_path):
    sample_rate = 16_000
    timeline = np.arange(sample_rate, dtype=np.float64) / sample_rate
    source_a = write_pcm16(
        tmp_path / "source-a.wav",
        0.25 * np.sin(2 * np.pi * 440 * timeline),
        sample_rate,
    )
    output_a = write_pcm16(
        tmp_path / "output-a.wav",
        0.25 * np.sin(2 * np.pi * 880 * timeline),
        sample_rate,
    )
    source_b = write_pcm16(
        tmp_path / "source-b.wav",
        0.25 * np.sin(2 * np.pi * 330 * timeline),
        sample_rate,
    )
    output_b = write_pcm16(
        tmp_path / "output-b.wav",
        0.25 * np.sin(2 * np.pi * 660 * timeline),
        sample_rate,
    )
    speaker_a, streaming_a = _load_pass_lanes(tmp_path, "render-a", source_a, output_a)
    speaker_b, streaming_b = _load_pass_lanes(tmp_path, "render-b", source_b, output_b)
    evidence = SttEvidence(
        provider="test-provider",
        model_revision="test-model@abc123",
        decode_config={"temperature": 0},
        language="ja-JP",
        transcribed_at="2026-08-09T12:00:00Z",
    )
    policy = ThresholdPolicy(
        "complete permissive policy",
        "approved",
        PERMISSIVE_PASS_THRESHOLD_VALUES,
    )

    def report(source, output, speaker, streaming):
        return build_render_report(
            source,
            output,
            reference_transcript="注文番号123",
            source_transcript="注文番号123",
            output_transcript="注文番号123",
            exact_entities=["123"],
            source_stt_evidence=evidence,
            output_stt_evidence=evidence,
            threshold_policy=policy,
            speaker_change=speaker,
            streaming_operations=streaming,
        )

    same_render = report(source_a, output_a, speaker_a, streaming_a)
    assert same_render["verdict"]["overall"] == "pass"
    for lane_name in ("speaker_change", "streaming_operations"):
        binding = same_render["verdict"]["lanes"][lane_name]["provenance"]["binding"]
        assert binding["source_sha256"] == same_render["artifacts"]["source"]["sha256"]
        assert binding["output_sha256"] == same_render["artifacts"]["output"]["sha256"]
    jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
        same_render
    )

    replay_inputs = {
        "speaker_change": (speaker_a, streaming_b),
        "streaming_operations": (speaker_b, streaming_a),
    }
    for replayed_lane_name, (speaker, streaming) in replay_inputs.items():
        replayed = report(source_b, output_b, speaker, streaming)

        assert replayed["verdict"]["overall"] == "unassessed"
        assert (
            replayed["verdict"]["lanes"][replayed_lane_name]["status"] == "unassessed"
        )
        assert "provenance" not in replayed["verdict"]["lanes"][replayed_lane_name]
        other_lane_name = (
            "streaming_operations"
            if replayed_lane_name == "speaker_change"
            else "speaker_change"
        )
        assert replayed["verdict"]["lanes"][other_lane_name]["status"] == "pass"
        jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
            replayed
        )


@pytest.mark.parametrize("forged_lane_name", ["speaker_change", "streaming_operations"])
def test_dataclass_replace_cannot_clone_or_forge_loader_validated_lane(
    tmp_path, forged_lane_name
):
    sample_rate = 16_000
    samples = np.arange(sample_rate, dtype=np.float64) / sample_rate
    source = write_pcm16(
        tmp_path / "source.wav", 0.25 * np.sin(2 * np.pi * 440 * samples), sample_rate
    )
    output = write_pcm16(
        tmp_path / "output.wav", 0.25 * np.sin(2 * np.pi * 880 * samples), sample_rate
    )
    source_sha256 = sha256_file(source)
    output_sha256 = sha256_file(output)

    speaker_value = _speaker_envelope(
        source,
        output,
        status="fail" if forged_lane_name == "speaker_change" else "pass",
    )
    streaming_value = _streaming_envelope(
        source,
        output,
        status="fail" if forged_lane_name == "streaming_operations" else "pass",
    )
    if forged_lane_name == "streaming_operations":
        streaming_value["streaming_operations"]["checks"]["interruption_cancel"] = False
    speaker_path = tmp_path / "speaker.json"
    streaming_path = tmp_path / "streaming.json"
    speaker_path.write_text(json.dumps(speaker_value), encoding="utf-8")
    streaming_path.write_text(json.dumps(streaming_value), encoding="utf-8")
    speaker = evaluation_external.load_speaker_lane(
        speaker_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    streaming = evaluation_external.load_streaming_lane(
        streaming_path, source_sha256=source_sha256, output_sha256=output_sha256
    )
    assert speaker is not None
    assert streaming is not None

    seed = speaker if forged_lane_name == "speaker_change" else streaming
    cloned = replace(seed)
    forged_provenance = deepcopy(seed.to_dict()["provenance"])
    forged_evidence = (
        ("forged_similarity=1", "forged_gain=1", "forged_advantage=1")
        if forged_lane_name == "speaker_change"
        else ("forged_streaming_checks=pass",)
    )
    forged = replace(
        seed,
        status=VerdictStatus.PASS,
        summary="Caller-forged passing evidence.",
        evidence=forged_evidence,
        provenance=forged_provenance,
    )
    assert cloned is not seed
    assert isinstance(forged.provenance, dict)

    internal = LaneVerdict(VerdictStatus.PASS, "Internal lane passed.", ("ok",))
    complete_policy = ThresholdPolicy(
        "complete approved policy", "approved", PASS_THRESHOLD_VALUES
    )
    verdict_arguments = {
        "transformation_evidence": internal,
        "content_preservation": internal,
        "speaker_change": speaker,
        "audio_integrity": internal,
        "streaming_operations": streaming,
        "policy_status": "approved",
        "content_evidence_complete": True,
        "threshold_policy": complete_policy,
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
    }
    verdict_arguments[forged_lane_name] = forged
    verdict = EvaluationVerdict(**verdict_arguments)

    assert verdict.overall is VerdictStatus.UNASSESSED
    normalized_lane = getattr(verdict, forged_lane_name)
    assert normalized_lane.status is VerdictStatus.UNASSESSED
    assert normalized_lane.provenance is None

    clone_arguments = dict(verdict_arguments)
    clone_arguments[forged_lane_name] = cloned
    clone_verdict = EvaluationVerdict(**clone_arguments)
    assert getattr(clone_verdict, forged_lane_name).status is VerdictStatus.UNASSESSED

    evidence = SttEvidence(
        provider="test-provider",
        model_revision="test-model@abc123",
        decode_config={"temperature": 0},
        language="ja-JP",
        transcribed_at="2026-08-09T12:00:00Z",
    )
    report_arguments = {
        "reference_transcript": "注文番号123",
        "source_transcript": "注文番号123",
        "output_transcript": "注文番号123",
        "exact_entities": ["123"],
        "source_stt_evidence": evidence,
        "output_stt_evidence": evidence,
        "threshold_policy": complete_policy,
        "speaker_change": speaker,
        "streaming_operations": streaming,
    }
    report_arguments[forged_lane_name] = forged
    report = build_render_report(source, output, **report_arguments)

    assert report["verdict"]["overall"] != "pass"
    assert report["verdict"]["lanes"][forged_lane_name]["status"] == "unassessed"
    assert "provenance" not in report["verdict"]["lanes"][forged_lane_name]
    jsonschema.Draft202012Validator(_schema("render-report.schema.json")).validate(
        report
    )


def test_evaluation_registry_rejects_tamper_with_recomputed_self_digest(
    tmp_path, monkeypatch
):
    registry = json.loads(
        resources.files("liveconv_evaluation")
        .joinpath("authorizations/reviewed-targets.json")
        .read_text(encoding="utf-8")
    )
    registry["records"][0]["owner"] = "tampered owner"
    unsigned = {key: value for key, value in registry.items() if key != "integrity"}
    registry["integrity"]["sha256"] = evaluation_external._canonical_digest(unsigned)
    registry_dir = tmp_path / "authorizations"
    registry_dir.mkdir()
    (registry_dir / "reviewed-targets.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        evaluation_external.importlib.resources, "files", lambda package: tmp_path
    )
    evaluation_external._reviewed_authorizations.cache_clear()
    try:
        with pytest.raises(ValueError, match="code-bound digest"):
            evaluation_external._reviewed_authorizations()
    finally:
        evaluation_external._reviewed_authorizations.cache_clear()


def test_packaged_schemas_and_reviewed_registry_cannot_drift_from_source_paths():
    for name in (
        "aggregate-report.schema.json",
        "fixture-manifest.schema.json",
        "render-report.schema.json",
        "speaker-lane.schema.json",
        "streaming-lane.schema.json",
    ):
        assert (
            resources.files("liveconv_evaluation")
            .joinpath("schemas", name)
            .read_bytes()
            == (ROOT / "schemas" / name).read_bytes()
        )

    assert (ROOT / "schemas/speaker-lane.schema.json").read_bytes() == (
        REPOSITORY_ROOT
        / "packages/speaker/src/liveconv_speaker/schemas/speaker-evidence.schema.json"
    ).read_bytes()
    assert (
        resources.files("liveconv_evaluation")
        .joinpath("authorizations/reviewed-targets.json")
        .read_bytes()
        == (
            REPOSITORY_ROOT
            / "packages/speaker/src/liveconv_speaker/authorizations"
            / "reviewed-targets.json"
        ).read_bytes()
    )
    evaluation_registry = resources.files("liveconv_evaluation").joinpath(
        "authorizations/reviewed-targets.json"
    )
    assert evaluation_external.REVIEWED_TARGET_REGISTRY_SHA256 == (
        speaker_authorization.REVIEWED_TARGET_REGISTRY_SHA256
    )
    assert hashlib.sha256(evaluation_registry.read_bytes()).hexdigest() == (
        evaluation_external.REVIEWED_TARGET_REGISTRY_SHA256
    )
    evaluation_external._reviewed_authorizations.cache_clear()
    try:
        assert len(evaluation_external._reviewed_authorizations()) == 1
    finally:
        evaluation_external._reviewed_authorizations.cache_clear()
