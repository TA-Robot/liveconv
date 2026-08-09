from __future__ import annotations

import numpy as np
from liveconv_evaluation.audio import AudioSignal, compare_signals
from liveconv_evaluation.transcript import (
    NORMALIZATION_REVISION,
    compare_exact_entities,
    compare_transcripts,
)
from liveconv_evaluation.verdict import (
    LaneVerdict,
    ThresholdPolicy,
    VerdictStatus,
    evaluate_measurements,
)


def _transcripts() -> dict:
    return {
        "reference_to_source": compare_transcripts(
            "注文番号123", "注文番号123"
        ).to_dict(),
        "reference_to_output": compare_transcripts(
            "注文番号123", "注文番号123"
        ).to_dict(),
        "exact_entities": compare_exact_entities(["123"], "注文番号123"),
    }


def _stt_evidence() -> dict:
    record = {
        "provider": "test-provider",
        "model_revision": "test-model@abc123",
        "decode_config": {"temperature": 0},
        "language": "ja-JP",
        "transcribed_at": "2026-08-09T12:00:00Z",
        "normalization_revision": NORMALIZATION_REVISION,
    }
    return {"source": dict(record), "output": dict(record)}


def _complete_policy(status: str = "approved") -> ThresholdPolicy:
    return ThresholdPolicy(
        f"{status} complete test policy",
        status,
        {
            "min_aligned_nrmse_for_waveform_difference": 0.01,
            "min_log_spectral_distance_for_waveform_difference": 0.01,
            "max_reference_cer": 0.0,
            "max_output_clipped_fraction": 0.0,
            "max_output_silence_fraction": 0.0,
            "max_duration_ratio_delta": 0.0,
            "max_output_nonfinite_samples": 0.0,
            "max_output_adjacent_sample_delta": 2.0,
            "max_output_interior_silence_run_frames": 0.0,
            "max_output_adjacent_repeated_segment_frames": 1_000.0,
            "max_cer_degradation": 0.0,
            "min_exact_entity_match_rate": 1.0,
        },
    )


def _changed_audio() -> dict:
    time = np.arange(16_000, dtype=np.float64) / 16_000
    source = AudioSignal(0.25 * np.sin(2 * np.pi * 440 * time), 16_000)
    output = AudioSignal(0.25 * np.sin(2 * np.pi * 880 * time), 16_000)
    return compare_signals(source, output)


def test_no_thresholds_means_no_implicit_pass():
    signal = AudioSignal(np.sin(np.linspace(0, 20, 4096)), 16_000)
    verdict = evaluate_measurements(
        compare_signals(signal, signal), _transcripts(), None
    )

    assert verdict.overall is VerdictStatus.UNASSESSED
    assert verdict.transformation_evidence.status is VerdictStatus.UNASSESSED
    assert verdict.content_preservation.status is VerdictStatus.UNASSESSED
    assert verdict.speaker_change.status is VerdictStatus.UNASSESSED
    assert verdict.audio_integrity.status is VerdictStatus.UNASSESSED
    assert verdict.streaming_operations.status is VerdictStatus.UNASSESSED


def test_gain_only_does_not_pass_meaningful_transformation_thresholds():
    samples = 0.25 * np.sin(np.linspace(0, 100, 16_000))
    source = AudioSignal(samples, 16_000)
    output = AudioSignal(samples * 0.5, 16_000)
    policy = ThresholdPolicy(
        "test policy",
        "proposed",
        {
            "min_aligned_nrmse_for_waveform_difference": 0.01,
            "min_log_spectral_distance_for_waveform_difference": 0.01,
        },
    )

    verdict = evaluate_measurements(compare_signals(source, output), {}, policy)

    assert verdict.transformation_evidence.status is VerdictStatus.FAIL
    assert "not proof of voice conversion" in verdict.transformation_evidence.summary


def test_partial_integrity_policy_cannot_pass_lane():
    samples = 0.25 * np.sin(np.linspace(0, 100, 16_000))
    source = AudioSignal(samples, 16_000)
    output = AudioSignal(samples, 16_000)
    policy = ThresholdPolicy(
        "test policy",
        "proposed",
        {
            "max_reference_cer": 0.0,
            "max_cer_degradation": 0.0,
            "max_output_clipped_fraction": 0.0,
            "max_output_nonfinite_samples": 0.0,
        },
    )

    verdict = evaluate_measurements(
        compare_signals(source, output),
        _transcripts(),
        policy,
        stt_evidence=_stt_evidence(),
    )

    assert verdict.content_preservation.status is VerdictStatus.PASS
    assert verdict.audio_integrity.status is VerdictStatus.UNASSESSED
    assert "missing_guardrails=" in verdict.audio_integrity.evidence[-1]
    assert verdict.transformation_evidence.status is VerdictStatus.UNASSESSED
    assert verdict.overall is VerdictStatus.UNASSESSED


def test_missing_speaker_evidence_prevents_overall_pass():
    policy = _complete_policy()
    operations = LaneVerdict(
        VerdictStatus.PASS, "Caller-authored streaming pass.", ("trace=run-test",)
    )

    verdict = evaluate_measurements(
        _changed_audio(),
        _transcripts(),
        policy,
        operations=operations,
        stt_evidence=_stt_evidence(),
    )

    assert verdict.transformation_evidence.status is VerdictStatus.PASS
    assert verdict.content_preservation.status is VerdictStatus.PASS
    assert verdict.speaker_change.status is VerdictStatus.UNASSESSED
    assert verdict.audio_integrity.status is VerdictStatus.PASS
    assert verdict.streaming_operations.status is VerdictStatus.UNASSESSED
    assert verdict.overall is VerdictStatus.UNASSESSED


def test_proposed_policy_cannot_produce_overall_pass():
    policy = _complete_policy("proposed")
    speaker_lane = LaneVerdict(
        VerdictStatus.PASS, "Caller-authored speaker pass.", ("speaker=test",)
    )
    operations_lane = LaneVerdict(
        VerdictStatus.PASS, "Caller-authored streaming pass.", ("trace=test",)
    )

    verdict = evaluate_measurements(
        _changed_audio(),
        _transcripts(),
        policy,
        speaker_change=speaker_lane,
        operations=operations_lane,
        stt_evidence=_stt_evidence(),
    )

    assert verdict.transformation_evidence.status is VerdictStatus.PASS
    assert verdict.content_preservation.status is VerdictStatus.PASS
    assert verdict.audio_integrity.status is VerdictStatus.PASS
    assert verdict.speaker_change.status is VerdictStatus.UNASSESSED
    assert verdict.streaming_operations.status is VerdictStatus.UNASSESSED
    assert verdict.overall is VerdictStatus.UNASSESSED


def test_one_character_exact_entity_corruption_fails_content_lane():
    samples = 0.25 * np.sin(np.linspace(0, 100, 16_000))
    signal = AudioSignal(samples, 16_000)
    transcripts = _transcripts()
    transcripts["exact_entities"] = compare_exact_entities(
        ["090-1234-5678"], "電話番号は090-1234-5679です"
    )
    policy = ThresholdPolicy(
        "identifier guardrail",
        "approved",
        {
            "max_reference_cer": 1.0,
            "min_exact_entity_match_rate": 1.0,
        },
    )

    verdict = evaluate_measurements(
        compare_signals(signal, signal), transcripts, policy
    )

    assert verdict.content_preservation.status is VerdictStatus.FAIL
    assert any(
        "exact_entity_match_rate=0" in item
        for item in verdict.content_preservation.evidence
    )


def test_supplied_integrity_failure_fails_even_when_policy_is_partial():
    source = AudioSignal(np.full(4096, 0.25), 16_000)
    clipped = AudioSignal(np.ones(4096), 16_000)
    policy = ThresholdPolicy(
        "partial integrity failure",
        "approved",
        {"max_output_clipped_fraction": 0.0},
    )

    verdict = evaluate_measurements(compare_signals(source, clipped), {}, policy)

    assert verdict.audio_integrity.status is VerdictStatus.FAIL


def test_caller_authored_speaker_verdict_is_unassessed_without_contract():
    samples = 0.25 * np.sin(np.linspace(0, 100, 16_000))
    signal = AudioSignal(samples, 16_000)
    speaker = LaneVerdict(
        VerdictStatus.PASS,
        "Caller-supplied calibrated speaker evidence passed.",
        ("calibration=EXP-test",),
    )

    verdict = evaluate_measurements(
        compare_signals(signal, signal),
        _transcripts(),
        None,
        speaker_change=speaker,
    )

    assert verdict.speaker_change.status is VerdictStatus.UNASSESSED
    assert verdict.speaker_change.provenance is None
    assert verdict.overall is VerdictStatus.UNASSESSED


def test_empty_transcripts_cannot_produce_overall_pass():
    empty_transcripts = {
        "reference_to_source": compare_transcripts("", "").to_dict(),
        "reference_to_output": compare_transcripts("", "").to_dict(),
    }
    external = LaneVerdict(
        VerdictStatus.PASS, "External evidence passed.", ("trace=test",)
    )

    verdict = evaluate_measurements(
        _changed_audio(),
        empty_transcripts,
        _complete_policy(),
        speaker_change=external,
        operations=external,
        stt_evidence=_stt_evidence(),
    )

    assert verdict.content_preservation.status is VerdictStatus.FAIL
    assert verdict.overall is VerdictStatus.FAIL
    assert any(
        "exact_entity_match_rate unavailable" in item
        for item in verdict.content_preservation.evidence
    )


def test_null_stt_provenance_cannot_produce_overall_pass():
    external = LaneVerdict(
        VerdictStatus.PASS, "External evidence passed.", ("trace=test",)
    )
    stt_evidence = _stt_evidence()
    stt_evidence["output"] = None

    verdict = evaluate_measurements(
        _changed_audio(),
        _transcripts(),
        _complete_policy(),
        speaker_change=external,
        operations=external,
        stt_evidence=stt_evidence,
    )

    assert verdict.content_preservation.status is VerdictStatus.UNASSESSED
    assert verdict.overall is VerdictStatus.UNASSESSED
    assert any(
        "output_stt_provenance" in item
        for item in verdict.content_preservation.evidence
    )


def test_pass_external_lanes_without_evidence_cannot_produce_overall_pass():
    evidenced = LaneVerdict(
        VerdictStatus.PASS, "External evidence passed.", ("trace=test",)
    )
    empty = LaneVerdict(VerdictStatus.PASS, "Unsupported pass.")

    for speaker, operations in ((empty, evidenced), (evidenced, empty)):
        verdict = evaluate_measurements(
            _changed_audio(),
            _transcripts(),
            _complete_policy(),
            speaker_change=speaker,
            operations=operations,
            stt_evidence=_stt_evidence(),
        )
        assert verdict.overall is VerdictStatus.UNASSESSED


def test_unbound_external_lane_objects_cannot_produce_overall_pass():
    unbound = LaneVerdict(
        VerdictStatus.PASS, "Unbound external pass.", ("caller-claim=true",)
    )
    unbound_operations = LaneVerdict(
        VerdictStatus.PASS, "Unbound operations pass.", ("caller-claim=true",)
    )

    verdict = evaluate_measurements(
        _changed_audio(),
        _transcripts(),
        _complete_policy(),
        speaker_change=unbound,
        operations=unbound_operations,
        stt_evidence=_stt_evidence(),
    )

    assert verdict.speaker_change.status is VerdictStatus.UNASSESSED
    assert verdict.overall is VerdictStatus.UNASSESSED


def test_integrity_discontinuity_threshold_consumes_adjacent_delta():
    source = AudioSignal(np.zeros(64), 16_000)
    output = AudioSignal(np.concatenate((np.zeros(32), np.ones(32))), 16_000)
    policy = ThresholdPolicy(
        "discontinuity regression",
        "approved",
        {"max_output_adjacent_sample_delta": 0.5},
    )

    verdict = evaluate_measurements(compare_signals(source, output), {}, policy)

    assert verdict.audio_integrity.status is VerdictStatus.FAIL
    assert any(
        "output_max_adjacent_sample_delta=1" in item
        for item in verdict.audio_integrity.evidence
    )


def test_unknown_or_unlabelled_threshold_policy_is_rejected():
    try:
        ThresholdPolicy("", "proposed", {})
    except ValueError as error:
        assert "label" in str(error)
    else:
        raise AssertionError("empty threshold label should fail")

    try:
        ThresholdPolicy("test", "proposed", {"secret_product_fact": 1.0})
    except ValueError as error:
        assert "unknown threshold" in str(error)
    else:
        raise AssertionError("unknown threshold should fail")
