from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_role_mix.py"
SPEC = importlib.util.spec_from_file_location("xvc_run_role_mix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ROLE_MIX = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ROLE_MIX
SPEC.loader.exec_module(ROLE_MIX)


def test_role_schedule_is_interleaved_exact_official_ratio() -> None:
    schedule = ROLE_MIX.role_schedule()

    assert schedule[:10] == list(ROLE_MIX.ROLE_CYCLE) * 2
    assert len(schedule) == 1_044
    assert Counter(schedule) == ROLE_MIX.ROLE_COUNTS


def test_role_schedule_rejects_another_update_count() -> None:
    with pytest.raises(ROLE_MIX.RoleMixError, match="update count"):
        ROLE_MIX.role_schedule(1_043)


def test_assigned_tensors_follow_waveform_roles() -> None:
    target = {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    generated = {
        "source_wav": "donor-wave",
        "semantic_tokens": "donor-token",
        "target_wav": "donor-wave",
        "ssl_feat": "donor-ssl",
    }

    assert ROLE_MIX.assigned_tensors(target, generated, "standard") == {
        "source_wav": "donor-wave",
        "semantic_tokens": "donor-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    assert ROLE_MIX.assigned_tensors(target, generated, "reconstruction") == {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    assert ROLE_MIX.assigned_tensors(target, generated, "reversed") == {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "donor-wave",
        "ssl_feat": "donor-ssl",
    }


def test_real_donor_rehearsal_uses_real_waveform_and_features() -> None:
    target = {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    generated = {
        "source_wav": "generated-wave",
        "semantic_tokens": "generated-token",
        "target_wav": "generated-wave",
        "ssl_feat": "generated-ssl",
    }
    real = {
        "source_wav": "real-wave",
        "semantic_tokens": "real-token",
        "target_wav": "real-wave",
        "ssl_feat": "real-ssl",
    }

    assert ROLE_MIX.assigned_tensors(
        target, generated, "real-donor-reconstruction", real_donor=real
    ) == {
        "source_wav": "real-wave",
        "semantic_tokens": "real-token",
        "target_wav": "real-wave",
        "ssl_feat": "real-ssl",
    }


def test_predecessor_receipt_rejects_drift(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"kind": "wrong"}), encoding="utf-8")

    with pytest.raises(ROLE_MIX.RoleMixError, match="identity"):
        ROLE_MIX._load_predecessor(path)


def test_speaker7_scope_contains_only_global_speaker_modulators() -> None:
    inventory = (
        ROLE_MIX.REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json"
    )

    scope = ROLE_MIX.training_scope(inventory, "speaker7")

    assert tuple(scope["target_modules"]) == ROLE_MIX.SPEAKER7_TARGETS
    assert scope["trainable_parameter_count"] == 166_400


def test_speaker7_policy_is_all_standard_and_exp038() -> None:
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="all-standard", lora_scope="speaker7")
    )

    assert policy["experiment_id"] == "EXP-038"
    assert Counter(ROLE_MIX.training_modes("all-standard")) == {"standard": 1_044}


def test_target_preserving_reconstruction_has_no_reversed_updates() -> None:
    schedule = ROLE_MIX.training_modes("standard-reconstruction")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(
            training_policy="standard-reconstruction", lora_scope="control69"
        )
    )

    assert schedule[:10] == list(ROLE_MIX.RECONSTRUCTION_CYCLE) * 2
    assert Counter(schedule) == ROLE_MIX.RECONSTRUCTION_COUNTS
    assert "reversed" not in schedule
    assert policy["experiment_id"] == "EXP-040"


def test_real_reconstruction_rehearsal_is_exact_and_exp072() -> None:
    schedule = ROLE_MIX.training_modes("real-reconstruction20")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(
            training_policy="real-reconstruction20", lora_scope="control69"
        )
    )

    assert Counter(schedule) == {
        "standard": 835,
        "real-donor-reconstruction": 209,
    }
    assert policy["experiment_id"] == "EXP-072"
    choices = next(
        action.choices
        for action in ROLE_MIX._parser()._actions
        if action.dest == "training_policy"
    )
    assert "real-reconstruction20" in choices


def test_real_teacher_semantic_rehearsal_is_exact_and_keeps_target_voice() -> None:
    schedule = ROLE_MIX.training_modes("real-teacher-semantic20")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(
            training_policy="real-teacher-semantic20", lora_scope="control69"
        )
    )
    target = {
        "source_wav": "target-source",
        "semantic_tokens": "target-token",
        "target_wav": "amitaro-wave",
        "ssl_feat": "target-hidden",
    }
    generated = {
        "source_wav": "generated-wave",
        "semantic_tokens": "generated-token",
        "target_wav": "generated-wave",
        "ssl_feat": "generated-hidden",
    }
    real = {
        "source_wav": "real-commonvoice-wave",
        "semantic_tokens": "real-commonvoice-token",
        "target_wav": "real-commonvoice-wave",
        "ssl_feat": "real-commonvoice-hidden",
    }

    assert Counter(schedule) == {
        "standard": 835,
        "real-donor-teacher-semantic": 209,
    }
    assert ROLE_MIX.assigned_tensors(
        target,
        generated,
        "real-donor-teacher-semantic",
        real_donor=real,
    ) == {
        "source_wav": "real-commonvoice-wave",
        "semantic_tokens": "real-commonvoice-token",
        "target_wav": "amitaro-wave",
        "ssl_feat": "target-hidden",
    }
    assert policy["experiment_id"] == "EXP-106"
    assert ROLE_MIX.training_loss_weights("real-teacher-semantic20") == (
        ROLE_MIX.STANDARD_LOSS_WEIGHTS
    )
    choices = next(
        action.choices
        for action in ROLE_MIX._parser()._actions
        if action.dest == "training_policy"
    )
    assert "real-teacher-semantic20" in choices


def test_source_augmentation_is_exact_and_keeps_standard_roles() -> None:
    conditions = ROLE_MIX.source_condition_schedule("source-augmentation")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="source-augmentation", lora_scope="control69")
    )

    assert len(conditions) == 1_044
    assert Counter(row["kind"] for row in conditions) == (
        ROLE_MIX.SOURCE_CONDITION_COUNTS
    )
    assert Counter(ROLE_MIX.training_modes("source-augmentation")) == {
        "standard": 1_044
    }
    assert policy["experiment_id"] == "EXP-043"


def test_paired_augmentation_preserves_time_condition_alignment() -> None:
    conditions = ROLE_MIX.source_condition_schedule("paired-augmentation")
    target_conditions = Counter(
        ROLE_MIX.target_condition_kind("paired-augmentation", str(row["kind"]))
        for row in conditions
    )
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="paired-augmentation", lora_scope="control69")
    )

    assert target_conditions == {
        "clean": 731,
        "tempo": 105,
        "pitch": 104,
        "leading-silence": 104,
    }
    assert policy["experiment_id"] == "EXP-044"


def test_authentic_anchor_replaces_exactly_one_donor_per_target() -> None:
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="authentic-anchor", lora_scope="control69")
    )
    anchors = [
        ROLE_MIX.uses_authentic_anchor("authentic-anchor", donor_index)
        for _target_index in range(87)
        for donor_index in range(12)
    ]

    assert sum(anchors) == 87
    assert Counter(ROLE_MIX.training_modes("authentic-anchor")) == {
        "standard": 1_044
    }
    assert policy["experiment_id"] == "EXP-046"


def test_semantic2x_changes_only_ssl_reconstruction_weight() -> None:
    weights = ROLE_MIX.training_loss_weights("semantic2x")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="semantic2x", lora_scope="control69")
    )

    assert weights == {
        "mse_loss": 2000.0,
        "vq_loss": 1.0,
        "mel_loss": 15.0,
        "sim_mse_loss": 10.0,
    }
    assert policy["experiment_id"] == "EXP-049"


def test_source_semantic_changes_learning_target_without_changing_schedule() -> None:
    target = {
        "source_wav": "target-wave",
        "semantic_tokens": "target-token",
        "target_wav": "target-wave",
        "ssl_feat": "target-ssl",
    }
    generated = {
        "source_wav": "source-wave",
        "semantic_tokens": "source-token",
        "target_wav": "source-wave",
        "ssl_feat": "source-ssl",
    }
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="source-semantic", lora_scope="control69")
    )

    assert ROLE_MIX.assigned_tensors(
        target, generated, "standard", semantic_target="source"
    ) == {
        "source_wav": "source-wave",
        "semantic_tokens": "source-token",
        "target_wav": "target-wave",
        "ssl_feat": "source-ssl",
    }
    assert Counter(ROLE_MIX.training_modes("source-semantic")) == {
        "standard": 1_044
    }
    assert ROLE_MIX.training_loss_weights("source-semantic") == (
        ROLE_MIX.STANDARD_LOSS_WEIGHTS
    )
    assert policy["experiment_id"] == "EXP-081"
    choices = next(
        action.choices
        for action in ROLE_MIX._parser()._actions
        if action.dest == "training_policy"
    )
    assert "source-semantic" in choices


def test_denoise_semantic_alternates_clean_and_noise_with_fixed_objective() -> None:
    schedule = ROLE_MIX.source_condition_schedule("denoise-semantic")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="denoise-semantic", lora_scope="control69")
    )

    assert schedule[:4] == [
        {"kind": "clean"},
        {"kind": "noise", "snr_db": 20.0},
        {"kind": "clean"},
        {"kind": "noise", "snr_db": 20.0},
    ]
    assert Counter(row["kind"] for row in schedule) == {"clean": 522, "noise": 522}
    assert Counter(ROLE_MIX.training_modes("denoise-semantic")) == {
        "standard": 1_044
    }
    assert ROLE_MIX.training_loss_weights("denoise-semantic") == (
        ROLE_MIX.STANDARD_LOSS_WEIGHTS
    )
    assert policy["experiment_id"] == "EXP-087"


def test_cross_target_condition_rotates_without_self_conditioning() -> None:
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(
            training_policy="cross-target-condition", lora_scope="control69"
        )
    )
    indices = [
        ROLE_MIX.frame_condition_target_index("cross-target-condition", index, 87)
        for index in range(87)
    ]

    assert indices == list(range(1, 87)) + [0]
    assert all(index != condition for index, condition in enumerate(indices))
    assert Counter(ROLE_MIX.training_modes("cross-target-condition")) == {
        "standard": 1_044
    }
    assert ROLE_MIX.source_condition_schedule("cross-target-condition") == [
        {"kind": "clean"}
    ] * 1_044
    assert ROLE_MIX.training_loss_weights("cross-target-condition") == (
        ROLE_MIX.STANDARD_LOSS_WEIGHTS
    )
    assert policy["experiment_id"] == "EXP-094"
    assert policy["conditioned_inference"] is True
    choices = next(
        action.choices
        for action in ROLE_MIX._parser()._actions
        if action.dest == "training_policy"
    )
    assert "cross-target-condition" in choices


def test_semantic_token_hold_alternates_fixed_five_frame_blocks() -> None:
    schedule = ROLE_MIX.semantic_token_schedule("semantic-token-hold")
    held = ROLE_MIX.held_token_values(list(range(ROLE_MIX.base.SEMANTIC_FRAMES)))
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="semantic-token-hold", lora_scope="control69")
    )

    assert schedule[:4] == ["clean", "hold5", "clean", "hold5"]
    assert Counter(schedule) == {"clean": 522, "hold5": 522}
    assert held == [value for start in range(0, 30, 5) for value in [start] * 5]
    assert Counter(ROLE_MIX.training_modes("semantic-token-hold")) == {
        "standard": 1_044
    }
    assert ROLE_MIX.source_condition_schedule("semantic-token-hold") == [
        {"kind": "clean"}
    ] * 1_044
    assert policy["experiment_id"] == "EXP-100"


def test_source36_excludes_frame_condition_and_speaker_modulators() -> None:
    inventory = (
        ROLE_MIX.REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json"
    )
    scope = ROLE_MIX.training_scope(inventory, "source36")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="all-standard", lora_scope="source36")
    )

    assert len(scope["target_modules"]) == 36
    assert scope["trainable_parameter_count"] == 442_368
    assert all(".to_q_c" not in name for name in scope["target_modules"])
    assert all(".to_k_c" not in name for name in scope["target_modules"])
    assert all(".to_v_c" not in name for name in scope["target_modules"])
    assert all(".to_out_c" not in name for name in scope["target_modules"])
    assert all(".ff_c." not in name for name in scope["target_modules"])
    assert all("norm" not in name for name in scope["target_modules"])
    assert policy["experiment_id"] == "EXP-052"


def test_output2_is_exact_decoder_interface_scope_and_exp068() -> None:
    inventory = (
        ROLE_MIX.REPO_ROOT
        / "artifacts"
        / "exp007"
        / "phase0-inputs-v1"
        / "inventory.json"
    )

    scope = ROLE_MIX.training_scope(inventory, "output2")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="all-standard", lora_scope="output2")
    )

    assert tuple(scope["target_modules"]) == ROLE_MIX.OUTPUT2_TARGETS
    assert scope["trainable_parameter_count"] == 22_016
    assert policy["experiment_id"] == "EXP-068"
    choices = next(
        action.choices
        for action in ROLE_MIX._parser()._actions
        if action.dest == "lora_scope"
    )
    assert "output2" in choices


def test_decoder_final_scope_is_exact_and_exp077() -> None:
    inventory = ROLE_MIX.REPO_ROOT / "artifacts/exp007/phase0-inputs-v1/inventory.json"
    scope = ROLE_MIX.training_scope(inventory, "decoder-final")
    policy = ROLE_MIX.experiment_policy(
        SimpleNamespace(training_policy="all-standard", lora_scope="decoder-final")
    )

    assert tuple(scope["modules_to_save"]) == ROLE_MIX.DECODER_FINAL_MODULES
    assert scope["trainable_parameter_count"] == 297_890
    assert policy["experiment_id"] == "EXP-077"
