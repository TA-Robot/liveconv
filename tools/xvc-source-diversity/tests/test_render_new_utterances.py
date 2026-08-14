from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_new_utterances.py"
SPEC = importlib.util.spec_from_file_location("xvc_render_new_utterances", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
NEW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NEW
SPEC.loader.exec_module(NEW)


def _manifest() -> dict[str, object]:
    clients = [f"{index + 101:064x}" for index in range(6)]
    return {
        "kind": NEW.KIND,
        "source": {"license": "CC0-1.0"},
        "items": [
            {
                "id": f"row-{index}",
                "filename": f"row-{index}.mp3",
                "sha256": f"{index + 1:064x}",
                "client_id_sha256": clients[index % 6],
                "text": f"full sentence {index}",
                "source_transcript": "七文字以上です",
                "source_normalized_characters": 7,
                "duration_seconds": 3.0,
                "window_policy": "first-2.4s-right-pad-if-short",
                "group": "same-speaker-second-utterance",
            }
            for index in range(12)
        ],
    }


def test_manifest_requires_twelve_rows_from_six_speakers(tmp_path: Path) -> None:
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(_manifest()), encoding="utf-8")

    loaded = NEW.load_evaluation(path)

    assert len(loaded["items"]) == 12
    assert len({item["client_id_sha256"] for item in loaded["items"]}) == 6


def test_manifest_rejects_a_short_source_transcript(tmp_path: Path) -> None:
    value = _manifest()
    value["items"][0]["source_transcript"] = "短い"
    value["items"][0]["source_normalized_characters"] = 2
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(NEW.NewUtteranceError, match="identity"):
        NEW.load_evaluation(path)


def test_reconstruction_candidate_is_exp041() -> None:
    policy = NEW.candidate_policy("reconstruction20")

    assert policy["experiment_id"] == "EXP-041"
    assert policy["variant_id"] == "cv12-reconstruction20"


def test_aligned_condition_candidate_is_exp045() -> None:
    policy = NEW.candidate_policy("aligned-conditions")

    assert policy["experiment_id"] == "EXP-045"
    assert policy["variant_id"] == "cv12-aligned-conditions"


def test_authentic_anchor_candidate_is_exp047() -> None:
    policy = NEW.candidate_policy("authentic-anchor")

    assert policy["experiment_id"] == "EXP-047"
    assert policy["variant_id"] == "cv11-authentic1"


def test_semantic2x_candidate_is_exp050() -> None:
    policy = NEW.candidate_policy("semantic2x")

    assert policy["experiment_id"] == "EXP-050"
    assert policy["variant_id"] == "cv12-semantic2x"


def test_source36_candidate_is_exp053() -> None:
    policy = NEW.candidate_policy("source36")

    assert policy["experiment_id"] == "EXP-053"
    assert policy["variant_id"] == "cv12-source36"


def test_target275_candidate_policies_cover_changed_and_expanded_sets() -> None:
    changed = NEW.candidate_policy("target275")
    expanded = NEW.candidate_policy("target275-expanded")

    assert changed["experiment_id"] == "EXP-056"
    assert expanded["experiment_id"] == "EXP-058"
    assert changed["variant_id"] == expanded["variant_id"] == "cv12-target275"


def test_content_filtered_candidate_is_exp061() -> None:
    policy = NEW.candidate_policy("content-filtered6x2")

    assert policy["experiment_id"] == "EXP-061"
    assert policy["variant_id"] == "cv12-content-filtered6x2"


def test_content_filtered_hadou_candidate_is_exp063() -> None:
    policy = NEW.candidate_policy("content-filtered6x2-hadou")

    assert policy["experiment_id"] == "EXP-063"
    assert policy["variant_id"] == "cv12-content-filtered6x2"


def test_wave_adversarial_policies_cover_changed_and_hadou_sets() -> None:
    changed = NEW.candidate_policy("wave-adversarial")
    hadou = NEW.candidate_policy("wave-adversarial-hadou")

    assert changed["experiment_id"] == "EXP-065"
    assert hadou["experiment_id"] == "EXP-067"
    assert changed["variant_id"] == hadou["variant_id"] == (
        "cv12-wave-adversarial"
    )
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "wave-adversarial" in choices
    assert "wave-adversarial-hadou" in choices


def test_wave_adversarial_expanded_policy_uses_exp076() -> None:
    policy = NEW.candidate_policy("wave-adversarial-expanded")

    assert policy["experiment_id"] == "EXP-076"
    assert policy["variant_id"] == "cv12-wave-adversarial"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "wave-adversarial-expanded" in choices


def test_wave_adversarial_fresh48_policy_uses_exp113() -> None:
    policy = NEW.candidate_policy("wave-adversarial-fresh48")

    assert policy["experiment_id"] == "EXP-113"
    assert policy["variant_id"] == "cv12-wave-adversarial"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "wave-adversarial-fresh48" in choices


def test_output2_policies_cover_changed_and_hadou_sets() -> None:
    changed = NEW.candidate_policy("output2")
    hadou = NEW.candidate_policy("output2-hadou")

    assert changed["experiment_id"] == "EXP-069"
    assert hadou["experiment_id"] == "EXP-071"
    assert changed["variant_id"] == hadou["variant_id"] == "cv12-output2"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "output2" in choices
    assert "output2-hadou" in choices


def test_real_rehearsal_policies_cover_changed_and_hadou_sets() -> None:
    changed = NEW.candidate_policy("real-reconstruction20")
    hadou = NEW.candidate_policy("real-reconstruction20-hadou")

    assert changed["experiment_id"] == "EXP-073"
    assert hadou["experiment_id"] == "EXP-075"
    assert changed["variant_id"] == hadou["variant_id"] == (
        "cv12-real-reconstruction20"
    )
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-reconstruction20" in choices
    assert "real-reconstruction20-hadou" in choices


def test_decoder_final_policies_cover_changed_and_hadou_sets() -> None:
    changed = NEW.candidate_policy("decoder-final")
    hadou = NEW.candidate_policy("decoder-final-hadou")
    assert changed["experiment_id"] == "EXP-078"
    assert hadou["experiment_id"] == "EXP-080"
    assert changed["variant_id"] == hadou["variant_id"] == "cv12-decoder-final"


def test_source_semantic_policies_cover_changed_hadou_and_expanded() -> None:
    changed = NEW.candidate_policy("source-semantic")
    hadou = NEW.candidate_policy("source-semantic-hadou")
    expanded = NEW.candidate_policy("source-semantic-expanded")

    assert (
        changed["experiment_id"],
        hadou["experiment_id"],
        expanded["experiment_id"],
    ) == ("EXP-082", "EXP-084", "EXP-085")
    assert {
        changed["variant_id"],
        hadou["variant_id"],
        expanded["variant_id"],
    } == {"cv12-source-semantic"}


def test_source_semantic_stress_policy_is_exp086() -> None:
    policy = NEW.candidate_policy("source-semantic-stress")

    assert policy["experiment_id"] == "EXP-086"
    assert policy["variant_id"] == "cv12-source-semantic"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "source-semantic-stress" in choices


def test_denoise_semantic_policies_cover_all_followup_sets() -> None:
    kinds = (
        "denoise-semantic",
        "denoise-semantic-hadou",
        "denoise-semantic-expanded",
        "denoise-semantic-stress",
    )
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-088",
        "EXP-090",
        "EXP-091",
        "EXP-092",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-denoise-semantic"
    }


def test_cross_target_condition_policies_cover_all_followup_sets() -> None:
    kinds = (
        "cross-target-condition",
        "cross-target-condition-hadou",
        "cross-target-condition-expanded",
        "cross-target-condition-stress",
    )
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-095",
        "EXP-097",
        "EXP-098",
        "EXP-099",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-cross-target-condition"
    }
    assert all(policy["conditioned_inference"] for policy in policies)


def test_clean_post_rehearsal_policies_cover_fresh_and_hadou() -> None:
    policies = [
        NEW.candidate_policy("clean-post-rehearsal-fresh48"),
        NEW.candidate_policy("clean-post-rehearsal-hadou"),
    ]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-142",
        "EXP-143",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-clean-post-rehearsal170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "clean-post-rehearsal-fresh48" in choices
    assert "clean-post-rehearsal-hadou" in choices


def test_semantic_token_hold_policies_cover_all_followup_sets() -> None:
    kinds = (
        "semantic-token-hold",
        "semantic-token-hold-hadou",
        "semantic-token-hold-expanded",
        "semantic-token-hold-stress",
    )
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-101",
        "EXP-103",
        "EXP-104",
        "EXP-105",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-semantic-token-hold"
    }


def test_real_teacher_semantic_policies_cover_all_followup_sets() -> None:
    kinds = (
        "real-teacher-semantic20",
        "real-teacher-semantic20-hadou",
        "real-teacher-semantic20-expanded",
        "real-teacher-semantic20-stress",
    )
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-107",
        "EXP-109",
        "EXP-110",
        "EXP-111",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-real-teacher-semantic20"
    }


def test_real_teacher_fresh48_policy_is_exp112() -> None:
    policy = NEW.candidate_policy("real-teacher-semantic20-fresh48")

    assert policy["experiment_id"] == "EXP-112"
    assert policy["variant_id"] == "cv12-real-teacher-semantic20"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-semantic20-fresh48" in choices


def test_real_teacher_breadth48_fresh_policy_is_exp115() -> None:
    policy = NEW.candidate_policy("real-teacher-breadth48-fresh48")

    assert policy["experiment_id"] == "EXP-115"
    assert policy["variant_id"] == "cv12-real-teacher-breadth48"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-breadth48-fresh48" in choices


def test_real_teacher_output48_fresh_policy_is_exp117() -> None:
    policy = NEW.candidate_policy("real-teacher-output48-fresh48")

    assert policy["experiment_id"] == "EXP-117"
    assert policy["variant_id"] == "cv12-real-teacher-output48"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output48-fresh48" in choices


def test_real_teacher_output48_ffn22_fresh_policy_is_exp119() -> None:
    policy = NEW.candidate_policy("real-teacher-output48-ffn22-fresh48")

    assert policy["experiment_id"] == "EXP-119"
    assert policy["variant_id"] == "cv12-real-teacher-output48-ffn22"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output48-ffn22-fresh48" in choices


def test_real_teacher_output48_dora_fresh_policy_is_exp121() -> None:
    policy = NEW.candidate_policy("real-teacher-output48-dora-fresh48")

    assert policy["experiment_id"] == "EXP-121"
    assert policy["variant_id"] == "cv12-real-teacher-output48-dora"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output48-dora-fresh48" in choices


def test_real_teacher_output48_temporal_fresh_policy_is_exp123() -> None:
    policy = NEW.candidate_policy("real-teacher-output48-temporal-fresh48")

    assert policy["experiment_id"] == "EXP-123"
    assert policy["variant_id"] == "cv12-real-teacher-output48-temporal"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output48-temporal-fresh48" in choices


def test_real_teacher_multidomain48_fresh_policy_is_exp125() -> None:
    policy = NEW.candidate_policy("real-teacher-output-multidomain48-fresh48")

    assert policy["experiment_id"] == "EXP-125"
    assert policy["variant_id"] == "cv12-real-teacher-output-multidomain48"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-multidomain48-fresh48" in choices


def test_real_teacher_multidomain48_hadou_policy_is_exp127() -> None:
    policy = NEW.candidate_policy("real-teacher-output-multidomain48-hadou")

    assert policy["experiment_id"] == "EXP-127"
    assert policy["variant_id"] == "cv12-real-teacher-output-multidomain48"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-multidomain48-hadou" in choices


def test_real_teacher_multidomain48_stress_policy_is_exp128() -> None:
    policy = NEW.candidate_policy("real-teacher-output-multidomain48-stress")

    assert policy["experiment_id"] == "EXP-128"
    assert policy["variant_id"] == "cv12-real-teacher-output-multidomain48"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-multidomain48-stress" in choices


def test_real_teacher_phonetic48_policies_are_exp131_and_exp132() -> None:
    fresh = NEW.candidate_policy("real-teacher-output-phonetic48-fresh48")
    hadou = NEW.candidate_policy("real-teacher-output-phonetic48-hadou")

    assert fresh["experiment_id"] == "EXP-131"
    assert hadou["experiment_id"] == "EXP-132"
    assert fresh["variant_id"] == hadou["variant_id"]
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-phonetic48-fresh48" in choices
    assert "real-teacher-output-phonetic48-hadou" in choices


def test_real_teacher_window48_policies_are_exp135_and_exp136() -> None:
    fresh = NEW.candidate_policy("real-teacher-output-window48-fresh48")
    hadou = NEW.candidate_policy("real-teacher-output-window48-hadou")

    assert fresh["experiment_id"] == "EXP-135"
    assert hadou["experiment_id"] == "EXP-136"
    assert fresh["variant_id"] == hadou["variant_id"]
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-window48-fresh48" in choices
    assert "real-teacher-output-window48-hadou" in choices


def test_real_teacher_window201_policies_are_exp139_and_exp140() -> None:
    fresh = NEW.candidate_policy("real-teacher-output-window201-fresh48")
    hadou = NEW.candidate_policy("real-teacher-output-window201-hadou")

    assert fresh["experiment_id"] == "EXP-139"
    assert hadou["experiment_id"] == "EXP-140"
    assert fresh["variant_id"] == hadou["variant_id"]
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-teacher-output-window201-fresh48" in choices
    assert "real-teacher-output-window201-hadou" in choices


def test_clean_post_rehearsal_jsut_policy_is_exp144() -> None:
    policy = NEW.candidate_policy("clean-post-rehearsal-jsut")

    assert policy["experiment_id"] == "EXP-144"
    assert policy["variant_id"] == "cv12-clean-post-rehearsal170"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "clean-post-rehearsal-jsut" in choices


def test_hard_negative_curriculum_policies_cover_three_frozen_sets() -> None:
    fresh = NEW.candidate_policy("hard-negative-curriculum-fresh48")
    hadou = NEW.candidate_policy("hard-negative-curriculum-hadou")
    jsut = NEW.candidate_policy("hard-negative-curriculum-jsut")

    assert [fresh["experiment_id"], hadou["experiment_id"], jsut["experiment_id"]] == [
        "EXP-147",
        "EXP-148",
        "EXP-149",
    ]
    assert fresh["variant_id"] == hadou["variant_id"] == jsut["variant_id"]


def test_selective_retention_policies_cover_three_frozen_sets() -> None:
    fresh = NEW.candidate_policy("selective-retention-fresh48")
    hadou = NEW.candidate_policy("selective-retention-hadou")
    jsut = NEW.candidate_policy("selective-retention-jsut")

    assert [fresh["experiment_id"], hadou["experiment_id"], jsut["experiment_id"]] == [
        "EXP-151",
        "EXP-152",
        "EXP-153",
    ]
    assert fresh["variant_id"] == hadou["variant_id"] == jsut["variant_id"]


def test_full_converter_retention_policies_cover_three_frozen_sets() -> None:
    fresh = NEW.candidate_policy("full-converter-retention-fresh48")
    hadou = NEW.candidate_policy("full-converter-retention-hadou")
    jsut = NEW.candidate_policy("full-converter-retention-jsut")

    assert [fresh["experiment_id"], hadou["experiment_id"], jsut["experiment_id"]] == [
        "EXP-155",
        "EXP-156",
        "EXP-157",
    ]
    assert fresh["variant_id"] == hadou["variant_id"] == jsut["variant_id"]
    assert fresh["candidate_format"] == "merged-control69-converter"
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "full-converter-retention-jsut" in choices


def test_real_reference_adversarial_policies_include_stress_gate() -> None:
    kinds = [
        "real-reference-adversarial-fresh48",
        "real-reference-adversarial-hadou",
        "real-reference-adversarial-stress",
        "real-reference-adversarial-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-159",
        "EXP-160",
        "EXP-161",
        "EXP-162",
    ]
    assert len({policy["variant_id"] for policy in policies}) == 1
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-reference-adversarial-stress" in choices


def test_real_adversarial_ema_policies_include_stress_gate() -> None:
    kinds = [
        "real-adversarial-ema-fresh48",
        "real-adversarial-ema-hadou",
        "real-adversarial-ema-stress",
        "real-adversarial-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-164",
        "EXP-165",
        "EXP-166",
        "EXP-167",
    ]
    assert len({policy["variant_id"] for policy in policies}) == 1
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-adversarial-ema-stress" in choices


def test_real_adversarial_ema_expanded_policy_is_posthoc_exp168() -> None:
    policy = NEW.candidate_policy("real-adversarial-ema-expanded")

    assert policy["experiment_id"] == "EXP-168"
    assert policy["variant_id"] == "cv12-selective-real-adversarial-ema170"
    assert "33 additional" in policy["question"]


def test_paired_pcgrad_policies_follow_reserved_jsut_ids() -> None:
    kinds = [
        "paired-pcgrad-fresh48",
        "paired-pcgrad-hadou",
        "paired-pcgrad-stress",
        "paired-pcgrad-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-177",
        "EXP-178",
        "EXP-179",
        "EXP-180",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-selective-pcgrad85"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "paired-pcgrad-stress" in choices


def test_jsut_retention_ema_policy_has_distinct_gate_identity() -> None:
    kinds = [
        "jsut-retention-ema-fresh48",
        "jsut-retention-ema-hadou",
        "jsut-retention-ema-stress",
        "jsut-retention-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-172",
        "EXP-173",
        "EXP-174",
        "EXP-175",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-jsut-retention-real-adversarial-ema170"
    }


def test_parameter_anchor_ema_policy_has_distinct_gate_identity() -> None:
    kinds = [
        "parameter-anchor-ema-fresh48",
        "parameter-anchor-ema-hadou",
        "parameter-anchor-ema-stress",
        "parameter-anchor-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-182",
        "EXP-183",
        "EXP-184",
        "EXP-185",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-selective-real-adversarial-anchor-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "parameter-anchor-ema-stress" in choices


def test_commonvoice48_retention_policy_has_distinct_gate_identity() -> None:
    kinds = [
        "commonvoice48-retention-ema-fresh48",
        "commonvoice48-retention-ema-hadou",
        "commonvoice48-retention-ema-stress",
        "commonvoice48-retention-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-187",
        "EXP-188",
        "EXP-189",
        "EXP-190",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-commonvoice48-retention-real-adversarial-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "commonvoice48-retention-ema-stress" in choices


def test_conditioned_retention_policy_has_distinct_gate_identity() -> None:
    kinds = [
        "conditioned-retention-ema-fresh48",
        "conditioned-retention-ema-stress",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-192",
        "EXP-193",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-conditioned-retention-real-adversarial-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "conditioned-retention-ema-fresh48" in choices
    assert "conditioned-retention-ema-stress" in choices


def test_source36_retention_stress_policy_is_prebound() -> None:
    policy = NEW.candidate_policy("source36-retention-ema-stress")

    assert policy["experiment_id"] == "EXP-195"
    assert policy["variant_id"] == (
        "cv12-commonvoice48-source36-real-adversarial-ema170"
    )
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "source36-retention-ema-stress" in choices


def test_source_envelope_retention_stress_policy_is_prebound() -> None:
    policy = NEW.candidate_policy("source-envelope-retention-ema-stress")

    assert policy["experiment_id"] == "EXP-197"
    assert policy["variant_id"] == (
        "cv12-commonvoice48-source-envelope-real-adversarial-ema170"
    )
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "source-envelope-retention-ema-stress" in choices


def test_acoustic_encoder_policy_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "acoustic-encoder-ema-fresh48",
        "acoustic-encoder-ema-hadou",
        "acoustic-encoder-ema-stress",
        "acoustic-encoder-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-199",
        "EXP-200",
        "EXP-201",
        "EXP-202",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cv12-selective-acoustic-encoder-real-adversarial-ema170"
    }
    assert {policy["candidate_format"] for policy in policies} == {
        "merged-control69-acoustic-encoder"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_unpaired_human_policy_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "unpaired-human-ema-fresh48",
        "unpaired-human-ema-hadou",
        "unpaired-human-ema-stress",
        "unpaired-human-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-204",
        "EXP-205",
        "EXP-206",
        "EXP-207",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "human170-factorized-unpaired-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_unpaired_output_cycle_policy_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "unpaired-output-cycle-ema-fresh48",
        "unpaired-output-cycle-ema-hadou",
        "unpaired-output-cycle-ema-stress",
        "unpaired-output-cycle-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-209",
        "EXP-210",
        "EXP-211",
        "EXP-212",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "human170-unpaired-output-cycle-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_cross_corpus_output_cycle_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "cross-corpus-output-cycle-ema-fresh48",
        "cross-corpus-output-cycle-ema-hadou",
        "cross-corpus-output-cycle-ema-stress",
        "cross-corpus-output-cycle-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-214",
        "EXP-215",
        "EXP-216",
        "EXP-217",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cross-corpus170-unpaired-output-cycle-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_contrastive_output_cycle_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "contrastive-output-cycle-ema-fresh48",
        "contrastive-output-cycle-ema-hadou",
        "contrastive-output-cycle-ema-stress",
        "contrastive-output-cycle-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-219",
        "EXP-220",
        "EXP-221",
        "EXP-222",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cross-corpus170-contrastive-output-cycle-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_discrete_output_cycle_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "discrete-output-cycle-ema-fresh48",
        "discrete-output-cycle-ema-hadou",
        "discrete-output-cycle-ema-stress",
        "discrete-output-cycle-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-224",
        "EXP-225",
        "EXP-226",
        "EXP-227",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cross-corpus170-discrete-output-cycle-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_content_voice_pcgrad_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "content-voice-pcgrad-ema-fresh48",
        "content-voice-pcgrad-ema-hadou",
        "content-voice-pcgrad-ema-stress",
        "content-voice-pcgrad-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-229",
        "EXP-230",
        "EXP-231",
        "EXP-232",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cross-corpus170-content-voice-pcgrad-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_speaker7_voice_overlay_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "speaker7-voice-overlay-ema-fresh48",
        "speaker7-voice-overlay-ema-hadou",
        "speaker7-voice-overlay-ema-stress",
        "speaker7-voice-overlay-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-234",
        "EXP-235",
        "EXP-236",
        "EXP-237",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "control69-speaker7-real-voice-ema170"
    }
    assert {policy["candidate_format"] for policy in policies} == {
        "merged-control69-plus-adapter"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_pseudoparallel_prebinds_complete_five_surface_contract() -> None:
    kinds = [
        "pseudoparallel-real-adv-ema-fresh48",
        "pseudoparallel-real-adv-ema-hadou",
        "pseudoparallel-real-adv-ema-stress",
        "pseudoparallel-real-adv-ema-jsut",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-239",
        "EXP-240",
        "EXP-241",
        "EXP-242",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "cross-corpus170-pseudoparallel-real-adv-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_pseudoparallel_expanded_stress_policy_is_exp243() -> None:
    policy = NEW.candidate_policy(
        "pseudoparallel-real-adv-ema-expanded-stress"
    )

    assert policy["experiment_id"] == "EXP-243"
    assert policy["variant_id"] == (
        "cross-corpus170-pseudoparallel-real-adv-ema170"
    )
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "pseudoparallel-real-adv-ema-expanded-stress" in choices


def test_src4vc_pseudoparallel_prebinds_broad_evaluation_contract() -> None:
    kinds = [
        "src4vc-pseudoparallel-ema-fresh48",
        "src4vc-pseudoparallel-ema-hadou",
        "src4vc-pseudoparallel-ema-stress",
        "src4vc-pseudoparallel-ema-jsut",
        "src4vc-pseudoparallel-ema-expanded-stress",
    ]
    policies = [NEW.candidate_policy(kind) for kind in kinds]

    assert [policy["experiment_id"] for policy in policies] == [
        "EXP-245",
        "EXP-246",
        "EXP-247",
        "EXP-248",
        "EXP-249",
    ]
    assert {policy["variant_id"] for policy in policies} == {
        "src4vc85-pseudoparallel-real-adv-ema170"
    }
    choices = next(
        action.choices
        for action in NEW._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert all(kind in choices for kind in kinds)


def test_materialized_hadou_manifest_is_admitted() -> None:
    path = Path(
        "artifacts/xvc-source-diversity/exp060-hadou31-inputs-v1/evaluation.json"
    )

    value = NEW.load_evaluation(path)

    assert value["kind"] == NEW.HADOU_KIND
    assert len(value["items"]) == 31


def test_expanded_manifest_uses_all_33_unique_local_files() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "experiments"
        / "EXP-055-xvc-target-text-breadth"
        / "expanded-evaluation.json"
    )

    value = NEW.load_evaluation(path)

    assert value["kind"] == NEW.EXPANDED_KIND
    assert len(value["items"]) == 33
    assert len({item["client_id_sha256"] for item in value["items"]}) == 33
