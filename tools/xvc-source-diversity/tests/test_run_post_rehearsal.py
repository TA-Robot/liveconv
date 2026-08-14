from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import run_post_rehearsal as post  # noqa: E402
import run_role_mix as role_mix  # noqa: E402


def test_exp317_policy_keeps_ordinary_exp238_170_update_contract() -> None:
    policy = post.listening_policy(
        post.CV32_REPLACEMENT_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert post.expected_training_rows(post.CV32_REPLACEMENT_OUTPUT_KIND) == 170
    assert policy["slug"] == "exp317"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-cv32-replacement-real-adv-ema170"
    )
    assert policy["result_kind"] == (
        "liveconv-exp317-xvc-pseudoparallel-cv32-replacement-"
        "real-adv-ema/v1"
    )
    assert "external7" in policy["run_kind"]


def test_exp317_manifest_gate_replaces_only_first_32_cv_positions() -> None:
    reference = json.loads(
        (
            post.REPO_ROOT
            / "artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1"
            / "curriculum.json"
        ).read_text(encoding="utf-8")
    )
    items = [dict(item) for item in reference["items"]]
    for replacement_index, position in enumerate(post.CV32_REPLACEMENT_POSITIONS):
        original = items[position]
        source_id = f"cv32-replacement-{replacement_index:02d}"
        source_text = f"CV32 replacement sentence {replacement_index}"
        items[position] = {
            **original,
            "id": f"cv32-{replacement_index:02d}",
            "teacher_id": f"commonvoice-cv32-{replacement_index:02d}",
            "source_manifest_id": f"EXP055:{source_id}",
            "source_file": f"new-sources/{replacement_index:02d}.wav",
            "source_sha256": hashlib.sha256(source_id.encode()).hexdigest(),
            "source_text": source_text,
            "target_text": source_text,
            "target_file": f"control-outputs/cv32-{replacement_index:02d}.wav",
            "target_sha256": hashlib.sha256(
                f"teacher-{source_id}".encode()
            ).hexdigest(),
            "source_client_id_sha256": hashlib.sha256(
                f"client-{source_id}".encode()
            ).hexdigest(),
        }
    manifest = {
        "kind": post.CV32_REPLACEMENT_OUTPUT_KIND,
        "composition": post.CV32_REPLACEMENT_COMPOSITION,
        "items": items,
    }

    receipt = post.validate_cv32_replacement_manifest(
        manifest, reference_manifest=reference
    )

    assert receipt["replacement_row_count"] == 32
    assert receipt["unchanged_row_count"] == 138
    assert receipt["remaining_commonvoice_rows"] == 16
    assert receipt["position_specific_real_targets"] is True


def test_cv26_policies_bind_ordinary_170_update_contract() -> None:
    expected = {
        post.CV26_CURRENT_WINDOW_OUTPUT_KIND: (
            "exp318",
            "cross-corpus170-pseudoparallel-cv26-current-window-real-adv-ema170",
            "liveconv-exp318-xvc-pseudoparallel-cv26-current-window-real-adv-ema/v1",
        ),
        post.CV26_ACTIVE_WINDOW_OUTPUT_KIND: (
            "exp319",
            "cross-corpus170-pseudoparallel-cv26-active-window-real-adv-ema170",
            "liveconv-exp319-xvc-pseudoparallel-cv26-active-window-real-adv-ema/v1",
        ),
    }
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE in choices
    for kind, (slug, candidate_id, result_kind) in expected.items():
        policy = post.listening_policy(
            kind,
            post.LORA69_TARGET,
            post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
            True,
        )
        assert post.expected_training_rows(kind) == 170
        assert policy["slug"] == slug
        assert policy["candidate_id"] == candidate_id
        assert policy["result_kind"] == result_kind
        assert "external7" in policy["run_kind"]


def test_cv26_manifest_gate_replaces_fixed_rows_and_requires_active_metadata() -> None:
    reference = json.loads(
        (
            post.REPO_ROOT
            / "artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1"
            / "curriculum.json"
        ).read_text(encoding="utf-8")
    )
    base = reference["items"]

    def build(kind: str, *, active: bool) -> dict[str, object]:
        items = [dict(item) for item in base]
        for index, position in enumerate(post.CV26_REPLACEMENT_POSITIONS):
            source_id = f"cv26-source-{index:02d}"
            source_text = f"CV26 replacement sentence {index}"
            items[position] = {
                **items[position],
                "id": f"cv26-row-{index:02d}",
                "teacher_id": f"commonvoice-cv26-{index:02d}",
                "source_manifest_id": f"EXP055:{source_id}",
                "source_file": (
                    f"active-sources/{index:02d}.wav"
                    if active
                    else f"current-sources/{index:02d}.wav"
                ),
                "source_sha256": hashlib.sha256(
                    (f"active-{source_id}" if active else source_id).encode()
                ).hexdigest(),
                "source_text": source_text,
                "target_text": source_text,
                "source_client_id_sha256": hashlib.sha256(
                    f"client-{source_id}".encode()
                ).hexdigest(),
            }
            if active:
                items[position]["source_window"] = {
                    "active_sample_fraction": 0.25,
                    "window_start_sample": 1_600,
                }
                items[position]["source_window_policy"] = "speech-active"
        return {
            "kind": kind,
            "composition": post.CV26_COMPOSITION,
            "items": items,
        }

    current = build(post.CV26_CURRENT_WINDOW_OUTPUT_KIND, active=False)
    active = build(post.CV26_ACTIVE_WINDOW_OUTPUT_KIND, active=True)
    current_receipt = post.validate_cv26_manifest(
        current, reference_manifest=reference
    )
    active_receipt = post.validate_cv26_manifest(
        active, reference_manifest=reference, current_manifest=current
    )
    assert current_receipt["replacement_row_count"] == 26
    assert current_receipt["unchanged_row_count"] == 144
    assert current_receipt["remaining_commonvoice_rows"] == 16
    assert active_receipt["active_window_metadata"] is True
    assert active_receipt["source_identity_distinct_from_current_window"] is True


def test_cv32_policies_bind_202_update_external7_candidates() -> None:
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE in choices
    assert post.expected_training_rows(post.CV32_REPEAT_OUTPUT_KIND) == 202
    assert post.expected_training_rows(post.CV32_BREADTH_OUTPUT_KIND) == 202
    assert post.expected_training_rows(post.PSEUDOPARALLEL_OUTPUT_KIND) == 170

    repeat = post.listening_policy(
        post.CV32_REPEAT_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )
    breadth = post.listening_policy(
        post.CV32_BREADTH_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert repeat["slug"] == "exp305"
    assert repeat["candidate_id"] == (
        "cross-corpus202-pseudoparallel-repeat32-control-real-adv-ema202"
    )
    assert breadth["slug"] == "exp306"
    assert breadth["candidate_id"] == (
        "cross-corpus202-pseudoparallel-cv32-breadth-real-adv-ema202"
    )
    assert "external7" in repeat["run_kind"]
    assert "external7" in breadth["run_kind"]


def test_cv32_manifest_gate_preserves_exp238_and_distinguishes_policies() -> None:
    reference = json.loads(
        (
            post.REPO_ROOT
            / "artifacts/xvc-source-diversity/exp238-cross-corpus-control69-targets-v1"
            / "curriculum.json"
        ).read_text(encoding="utf-8")
    )
    base = reference["items"]
    commonvoice = [
        item for item in base if item["domain"] == "commonvoice-unpaired"
    ]
    repeats = [
        {**item, "id": f"{item['id']}-repeat32-{index:02d}"}
        for index, item in enumerate(commonvoice[:32])
    ]
    repeat_manifest = {
        "kind": post.CV32_REPEAT_OUTPUT_KIND,
        "composition": post.CV32_EXPECTED_COMPOSITION,
        "items": [*base, *repeats],
    }
    repeat_receipt = post.validate_cv32_manifest(
        repeat_manifest, reference_manifest=reference
    )
    assert repeat_receipt["addition_policy"] == (
        "repeat-first-32-commonvoice-tuples"
    )

    breadth_rows = []
    for index, item in enumerate(commonvoice[:32]):
        breadth_rows.append(
            {
                **item,
                "id": f"cv32-new-{index:02d}",
                "teacher_id": f"commonvoice-unpaired-cv32-new-{index:02d}",
                "source_manifest_id": f"EXP055:cv32-new-{index:02d}",
                "source_file": f"sources/cv32-new-{index:02d}.wav",
                "source_sha256": f"{index + 1:064x}",
                "source_text": f"新しい発話 {index}",
                "target_text": f"新しい発話 {index}",
                "client_id_sha256": f"{index + 100:064x}",
            }
        )
    breadth_manifest = {
        "kind": post.CV32_BREADTH_OUTPUT_KIND,
        "composition": post.CV32_EXPECTED_COMPOSITION,
        "items": [*base, *breadth_rows],
    }
    breadth_receipt = post.validate_cv32_manifest(
        breadth_manifest, reference_manifest=reference
    )
    assert breadth_receipt["addition_policy"] == (
        "genuine-new-commonvoice-32-speaker-tuples"
    )


def test_listening_policy_satisfies_shared_index_contract() -> None:
    policy = post.listening_policy()
    item = {
        "age": "",
        "gender": "",
        "text": "評価文",
    }
    hashes = {
        "base": "a" * 64,
        "cv12-standard": "b" * 64,
        post.CANDIDATE_ID: "c" * 64,
    }

    index = role_mix.listening_index(item, hashes=hashes, policy=policy)

    assert index["run_kind"] == policy["run_kind"]
    assert index["variants"][2]["profile_id"] == (
        f"xvc.exp141.{post.CANDIDATE_ID}.listen-now"
    )


def test_hard_curriculum_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(post.HARD_OUTPUT_KIND)

    assert policy["slug"] == "exp146"
    assert policy["candidate_id"] == "cv12-hard-negative-curriculum170"
    assert policy["result_kind"].startswith("liveconv-exp146-")


def test_selective_retention_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(post.SELECTIVE_OUTPUT_KIND)

    assert policy["slug"] == "exp150"
    assert policy["candidate_id"] == "cv12-selective-retention170"
    assert policy["result_kind"].startswith("liveconv-exp150-")


def test_full_converter_retention_changes_only_trainable_target_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND, post.FULL_CONVERTER_TARGET
    )

    assert policy["slug"] == "exp154"
    assert policy["candidate_id"] == ("cv12-selective-retention-full-converter170")
    assert "42" not in policy["independent_variable"]


def test_full_converter_is_not_admitted_for_other_curricula() -> None:
    try:
        post.listening_policy(post.HARD_OUTPUT_KIND, post.FULL_CONVERTER_TARGET)
    except post.PostRehearsalError as error:
        assert "selective retention" in str(error)
    else:
        raise AssertionError("full converter unexpectedly admitted")


def test_real_reference_adversarial_keeps_selective_lora_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
    )

    assert policy["slug"] == "exp158"
    assert policy["candidate_id"] == ("cv12-selective-retention-real-adversarial170")
    assert "authorized original Amitaro" in policy["independent_variable"]


def test_real_reference_adversarial_rejects_full_converter() -> None:
    try:
        post.listening_policy(
            post.SELECTIVE_OUTPUT_KIND,
            post.FULL_CONVERTER_TARGET,
            post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        )
    except post.PostRehearsalError as error:
        assert "selective LoRA69" in str(error)
    else:
        raise AssertionError("adversarial full converter unexpectedly admitted")


def test_upstream_ema_policy_changes_reported_adapter_state() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp163"
    assert policy["candidate_id"] == "cv12-selective-real-adversarial-ema170"
    assert "EMA" in policy["independent_variable"]


def test_acoustic_encoder_policy_moves_learning_before_converter() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.ACOUSTIC_ENCODER_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp198"
    assert policy["candidate_id"] == (
        "cv12-selective-acoustic-encoder-real-adversarial-ema170"
    )
    assert "21,521,536" in policy["independent_variable"]


def test_unpaired_human_policy_factorizes_content_and_identity() -> None:
    policy = post.listening_policy(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.FACTORIZED_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp203"
    assert policy["candidate_id"] == "human170-factorized-unpaired-ema170"
    assert "unrelated-text Amitaro" in policy["independent_variable"]


def test_unpaired_output_cycle_policy_moves_content_loss_to_final_wav() -> None:
    policy = post.listening_policy(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp208"
    assert policy["candidate_id"] == "human170-unpaired-output-cycle-ema170"
    assert "final converted WAV" in policy["independent_variable"]


def test_cross_corpus_policy_changes_only_source_distribution() -> None:
    policy = post.listening_policy(
        post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp213"
    assert policy["candidate_id"] == ("cross-corpus170-unpaired-output-cycle-ema170")
    assert "Common Voice 48" in policy["independent_variable"]
    assert "exact 170 unrelated Amitaro" in policy["independent_variable"]


def test_cross_corpus_policy_rejects_internal_semantic_objective() -> None:
    try:
        post.listening_policy(
            post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
            post.LORA69_TARGET,
            post.FACTORIZED_UNPAIRED_OBJECTIVE,
            True,
        )
    except post.PostRehearsalError as error:
        assert "fixed output-cycle objective" in str(error)
    else:
        raise AssertionError("cross-corpus internal semantic objective admitted")


def test_content_voice_pcgrad_changes_only_gradient_composition() -> None:
    policy = post.listening_policy(
        post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
        post.PCGRAD_CONTENT_VOICE_OPTIMIZER,
    )

    assert policy["slug"] == "exp228"
    assert policy["candidate_id"] == ("cross-corpus170-content-voice-pcgrad-ema170")
    assert "one optimizer step per row" in policy["independent_variable"]
    assert "loss weights" in policy["independent_variable"]


def test_content_voice_pcgrad_task_split_preserves_total() -> None:
    import torch

    content = torch.tensor(0.25, requires_grad=True)
    speaker = torch.tensor(0.5, requires_grad=True)
    adversarial = torch.tensor(7.0, requires_grad=True)
    generator = {
        "output_cycle_content": content,
        "speaker": speaker,
        "loss": 1000.0 * content + 10.0 * speaker,
    }

    content_task, voice_task = post.content_voice_task_losses(
        generator, adversarial, torch=torch
    )

    assert content_task.item() == 250.0
    assert voice_task.item() == 12.0
    assert (content_task + voice_task).item() == (
        generator["loss"] + adversarial
    ).item()


def test_speaker7_voice_overlay_freezes_the_content_converter() -> None:
    policy = post.listening_policy(
        post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
        post.SPEAKER7_OVERLAY_TARGET,
        post.SPEAKER_PATH_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp233"
    assert policy["candidate_id"] == "control69-speaker7-real-voice-ema170"
    assert "seven speaker-conditioned" in policy["independent_variable"]
    assert "content-cycle loss" in policy["independent_variable"]


def test_pseudoparallel_policy_restores_complete_same_content_targets() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp238"
    assert policy["candidate_id"] == ("cross-corpus170-pseudoparallel-real-adv-ema170")
    assert "same source" in policy["independent_variable"]
    assert "real side" in policy["independent_variable"]


def test_robust_semantic_policy_is_exp297_and_exact_exp238_lane() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp297"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-robust-semantic-real-adv-ema170"
    )
    assert post.ROBUST_SEMANTIC_IMPLEMENTATION in policy["independent_variable"]
    assert "1000*(2.0*smooth_l1 - mse)" in policy["independent_variable"]
    assert "normal quantized" in policy["independent_variable"]
    assert "inference has no attachment" in policy["independent_variable"]
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE in choices


def test_robust_semantic_requires_exact_exp238_contract() -> None:
    for kwargs in (
        {
            "manifest_kind": post.SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND,
        },
        {"use_adapter_ema": False},
        {"optimizer_mode": post.PCGRAD_CONTENT_VOICE_OPTIMIZER},
        {"parameter_anchor": True},
        {"source_activity_envelope": True},
    ):
        try:
            arguments = {
                "manifest_kind": post.PSEUDOPARALLEL_OUTPUT_KIND,
                "trainable_target": post.LORA69_TARGET,
                "training_objective": (
                    post.PSEUDOPARALLEL_ROBUST_SEMANTIC_OBJECTIVE
                ),
                "use_adapter_ema": True,
            }
            arguments.update(kwargs)
            post.listening_policy(**arguments)
        except post.PostRehearsalError as error:
            assert "exact EXP-238" in str(error)
        else:
            raise AssertionError("robust semantic contract drifted")


def test_robust_semantic_receipt_binds_beta_weight_and_exp238() -> None:
    receipt = post.robust_semantic_receipt()

    assert receipt["implementation"] == (
        "scale-matched-smooth-l1-semantic-decoder-beta1/v1"
    )
    assert receipt["beta"] == 1.0
    assert receipt["scale_factor"] == 2.0
    assert receipt["weight"] == 1000.0
    assert receipt["reference"] == "exact-EXP-238-pseudoparallel-contract"
    assert receipt["exp238_adapter_sha256"] == post.EXP238_ADAPTER_SHA256
    assert receipt["inference_attachment"] is None


def test_robust_semantic_substitutes_only_scaled_smooth_l1_term() -> None:
    import torch

    class FakeModel:
        @staticmethod
        def generative_loss(_outputs):
            return {
                "loss": torch.tensor(100.0),
                "mse_loss": torch.tensor(0.25),
                "vq_loss": torch.tensor(3.0),
                "mel_loss": torch.tensor(4.0),
                "sim_mse_loss": torch.tensor(5.0),
            }

    prediction = torch.tensor([[0.0, 2.0, -3.0]], requires_grad=True)
    target = torch.zeros_like(prediction)
    losses = post.robust_semantic_generator_loss(
        FakeModel(),
        {"pred": prediction, "ssl_feat": target},
        torch=torch,
    )
    mse = torch.nn.functional.mse_loss(prediction, target)
    smooth = torch.nn.functional.smooth_l1_loss(prediction, target, beta=1.0)

    assert losses["semantic_mse"].item() == mse.item()
    assert losses["semantic_smooth_l1"].item() == smooth.item()
    assert losses["semantic_smooth_l1_scaled"].item() == (2.0 * smooth).item()
    assert losses["loss"].item() == (
        100.0 + 1000.0 * (2.0 * smooth - mse)
    ).item()
    assert losses["mse_loss"].item() == 0.25
    assert losses["vq_loss"].item() == 3.0
    assert losses["mel_loss"].item() == 4.0
    assert losses["sim_mse_loss"].item() == 5.0
    losses["loss"].backward()
    assert prediction.grad is not None
    assert bool(torch.isfinite(prediction.grad).all())
    assert torch.count_nonzero(prediction.grad).item() > 0


def test_pseudoparallel_fresh_lora_changes_only_initialization() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp273"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-fresh-lora-real-adv-ema170"
    )
    assert "zero-initialized" in policy["independent_variable"]
    assert "source-aligned control69 teacher targets" in policy[
        "independent_variable"
    ]
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_FRESH_LORA_OBJECTIVE in choices


def test_pseudoparallel_acoustic_code_dropout_changes_only_representation() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp279"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-acoustic-dropout-real-adv-ema170"
    )
    assert "85 alternating training rows" in policy["independent_variable"]
    assert "inference remain unmasked" in policy["independent_variable"]
    assert (
        post.PSEUDOPARALLEL_ACOUSTIC_CODE_DROPOUT_OBJECTIVE
        in post.parser()._option_string_actions["--training-objective"].choices
    )


def test_pseudoparallel_continuous_acoustic_policy_changes_only_source_latent() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp285"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-continuous-acoustic-real-adv-ema170"
    )
    assert "projected continuous pre-VQ" in policy["independent_variable"]
    assert "both training and inference" in policy["independent_variable"]
    assert (
        post.PSEUDOPARALLEL_CONTINUOUS_ACOUSTIC_OBJECTIVE
        in post.parser()._option_string_actions["--training-objective"].choices
    )


def test_pseudoparallel_acoustic_temporal_jitter_policy_is_exp291() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp291"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-acoustic-temporal-jitter-"
        "real-adv-ema170"
    )
    assert "odd-indexed 85" in policy["independent_variable"]
    assert "normal quantized zq_a" in policy["independent_variable"]
    assert (
        post.PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE
        in post.parser()._option_string_actions["--training-objective"].choices
    )


def test_acoustic_temporal_jitter_requires_exact_exp238_contract() -> None:
    for manifest_kind, use_ema in (
        (post.SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND, True),
        (post.PSEUDOPARALLEL_OUTPUT_KIND, False),
    ):
        try:
            post.listening_policy(
                manifest_kind,
                post.LORA69_TARGET,
                post.PSEUDOPARALLEL_ACOUSTIC_TEMPORAL_JITTER_OBJECTIVE,
                use_ema,
            )
        except post.PostRehearsalError as error:
            assert "exact EXP-238" in str(error)
        else:
            raise AssertionError("acoustic temporal jitter contract drifted")


def test_acoustic_code_dropout_schedule_is_exactly_balanced() -> None:
    schedule = post.acoustic_code_dropout_schedule(post.EXPECTED_ROWS)

    assert schedule[:4] == [False, True, False, True]
    assert schedule.count(False) == 85
    assert schedule.count(True) == 85


def test_acoustic_temporal_jitter_schedule_is_exactly_balanced() -> None:
    schedule = post.acoustic_temporal_jitter_schedule(post.EXPECTED_ROWS)

    assert schedule[:4] == [False, True, False, True]
    assert schedule.count(False) == 85
    assert schedule.count(True) == 85


def test_acoustic_temporal_jitter_receipt_binds_ordered_row_identities() -> None:
    items = [
        {
            "id": f"row-{index}",
            "teacher_id": f"teacher-{index}",
            "target_id": f"target-{index}",
            "source_sha256": f"source-{index}",
            "target_sha256": f"target-sha-{index}",
            "real_target_sha256": f"real-{index}",
        }
        for index in range(post.EXPECTED_ROWS)
    ]
    manifest = {
        "kind": post.PSEUDOPARALLEL_OUTPUT_KIND,
        "items": items,
    }

    receipt = post.training_row_identity_receipt(manifest)

    assert receipt["manifest_row_count"] == post.EXPECTED_ROWS
    assert receipt["selected_row_count"] == post.EXPECTED_ROWS
    assert receipt["selected_positions"] == list(range(post.EXPECTED_ROWS))
    assert receipt["row_ids"] == [f"row-{index}" for index in range(post.EXPECTED_ROWS)]
    assert receipt["unchanged"] is True


def test_acoustic_code_dropout_masks_only_quantized_acoustic_tensor() -> None:
    import torch

    class FakeQuantizer(torch.nn.Module):
        def forward(self, value):
            return value * 2, value.new_tensor([7]), value.new_tensor(3.0)

    class FakeXVC(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_quantizer = FakeQuantizer()

    model = FakeXVC()
    dropout = post.attach_acoustic_code_dropout(model, torch=torch)
    source = torch.tensor([[[1.0, -2.0]]])

    clean = model.acoustic_quantizer(source)
    dropout.set_enabled(True)
    masked = model.acoustic_quantizer(source)
    dropout.set_enabled(False)
    restored = model.acoustic_quantizer(source)

    assert torch.equal(clean[0], source * 2)
    assert torch.count_nonzero(masked[0]).item() == 0
    assert torch.equal(masked[1], clean[1])
    assert torch.equal(masked[2], clean[2])
    assert torch.equal(restored[0], clean[0])
    assert dropout.clean_calls == 2
    assert dropout.masked_calls == 1
    assert dropout.last_input_nonzero == 2
    assert dropout.last_output_nonzero == 2


def test_acoustic_temporal_jitter_shifts_only_zq_and_preserves_gradient() -> None:
    import torch

    class FakeQuantizer(torch.nn.Module):
        def forward(self, value):
            return value * 3.0, value.new_tensor([7]), value.new_tensor(3.0)

    class FakeXVC(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_quantizer = FakeQuantizer()

    model = FakeXVC()
    jitter = post.attach_acoustic_temporal_jitter(model, torch=torch)
    source = torch.tensor([[[1.0, -2.0, 4.0]]], requires_grad=True)

    jitter.set_training_active(True)
    jitter.set_enabled(False)
    normal = model.acoustic_quantizer(source)
    jitter.set_enabled(True)
    shifted = model.acoustic_quantizer(source)
    expected = torch.cat([normal[0][..., :1], normal[0][..., :-1]], dim=-1)
    assert torch.equal(shifted[0], expected)
    assert torch.equal(shifted[1], normal[1])
    assert torch.equal(shifted[2], normal[2])
    assert torch.count_nonzero(shifted[0]).item() > 0
    shifted[0].sum().backward()
    assert source.grad is not None
    assert bool(torch.isfinite(source.grad).all())
    assert torch.count_nonzero(source.grad).item() > 0

    jitter.set_enabled(False)
    jitter.set_training_active(False)
    inference = model.acoustic_quantizer(source.detach())
    diagnostics = jitter.diagnostics()
    assert torch.equal(inference[0], normal[0])
    assert diagnostics["training_normal_calls"] == 1
    assert diagnostics["training_shifted_calls"] == 1
    assert diagnostics["inference_normal_calls"] == 1
    assert diagnostics["shifted_calls"] == 1
    assert diagnostics["output_nonzero"] > 0


def test_continuous_acoustic_wrapper_replaces_zq_and_reports_gradient_diagnostics(
) -> None:
    import torch

    class FakeQuantizer(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.in_project = torch.nn.Conv1d(1, 2, 1, bias=False)
            self.out_project = torch.nn.Conv1d(2, 1, 1, bias=False)
            with torch.no_grad():
                self.in_project.weight.copy_(torch.tensor([[[2.0]], [[-1.0]]]))
                self.out_project.weight.copy_(torch.tensor([[[0.5], [0.25]]]))

        def forward(self, value):
            return value * 3.0, value.new_tensor([7]), value.new_tensor(3.0)

    class FakeXVC(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_quantizer = FakeQuantizer()

    model = FakeXVC()
    continuous = post.attach_continuous_acoustic_latent(model, torch=torch)
    source = torch.tensor([[[1.0, -2.0]]], requires_grad=True)

    outputs = model.acoustic_quantizer(source)
    expected = continuous.base_quantizer.out_project(
        continuous.base_quantizer.in_project(source)
    )
    assert torch.allclose(outputs[0], expected)
    assert torch.equal(outputs[1], source.new_tensor([7]))
    assert torch.equal(outputs[2], source.new_tensor(3.0))
    outputs[0].sum().backward()

    diagnostics = continuous.diagnostics()
    assert diagnostics["call_count"] == 1
    assert diagnostics["quantized_nonzero"] == 2
    assert diagnostics["continuous_nonzero"] == 2
    assert diagnostics["quantized_rms"] > 0.0
    assert diagnostics["continuous_rms"] > 0.0
    assert diagnostics["rms_ratio"] > 0.0
    assert source.grad is not None
    assert bool(torch.isfinite(source.grad).all())


def test_continuous_acoustic_wrapper_rejects_zero_continuous_latent() -> None:
    import torch

    class FakeQuantizer(torch.nn.Module):
        in_project = torch.nn.Identity()
        out_project = torch.nn.Identity()

        def forward(self, value):
            return torch.ones_like(value), value.new_tensor([7])

    class FakeXVC(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_quantizer = FakeQuantizer()

    model = FakeXVC()
    post.attach_continuous_acoustic_latent(model, torch=torch)
    try:
        model.acoustic_quantizer(torch.zeros(1, 1, 2))
    except post.PostRehearsalError as error:
        assert "continuous acoustic" in str(error)
    else:
        raise AssertionError("zero continuous acoustic latent unexpectedly accepted")


def test_src4vc_pseudoparallel_policy_changes_only_source_corpus_block() -> None:
    policy = post.listening_policy(
        post.SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp244"
    assert policy["candidate_id"] == "src4vc85-pseudoparallel-real-adv-ema170"
    assert "only the 85" in policy["independent_variable"]
    assert "LR" in policy["independent_variable"]


def test_pseudoparallel_output_speaker_policy_changes_only_final_wav_loss() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_OUTPUT_SPEAKER_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp252"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-output-speaker-ema170"
    )
    assert "final converted waveform" in policy["independent_variable"]
    assert "weight-10 cosine loss" in policy["independent_variable"]


def test_latent_speaker_margin_policy_changes_only_source_leakage_loss() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_LATENT_SPEAKER_MARGIN_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp266"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-latent-speaker-margin-ema170"
    )
    assert "target cosine" in policy["independent_variable"]
    assert "source-speaker ERes2Net cosine" in policy["independent_variable"]
    assert "margin 0.1" in policy["independent_variable"]


def test_real_speaker_condition_policy_separates_voice_and_audio_targets() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_SPEAKER_CONDITION_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp267"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-real-speaker-condition-ema170"
    )
    assert "global speaker condition" in policy["independent_variable"]
    assert "authorized real Amitaro" in policy["independent_variable"]
    assert "semantic and mel reconstruction target" in policy["independent_variable"]


def test_condition_calibrator_policy_freezes_exp238_and_moves_only_condition() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.SPEAKER_CONDITION_CALIBRATOR_TARGET,
        post.PSEUDOPARALLEL_CONDITION_CALIBRATOR_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp259"
    assert policy["candidate_id"] == (
        "exp238-speaker-condition-delta-output-speaker-ema170"
    )
    assert "192-value delta" in policy["independent_variable"]
    assert "freeze the exact EXP-238" in policy["independent_variable"]


def test_condition_calibrator_changes_only_converter_condition(tmp_path: Path) -> None:
    import torch

    class FakeConverter(torch.nn.Module):
        condition_dim = post.SPEAKER_CONDITION_DIMENSION

        def __init__(self) -> None:
            super().__init__()
            self.content = torch.nn.Parameter(torch.tensor(3.0))
            self.last_condition = None

        def forward(
            self, acoustic_latent, frame_condition, speaker_condition, mask=None
        ):
            del frame_condition, mask
            self.last_condition = speaker_condition
            return acoustic_latent + speaker_condition[:, :1].unsqueeze(-1)

    class FakeXVC(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_converter = FakeConverter()
            self.unrelated = torch.nn.Parameter(torch.tensor(5.0))

    model = FakeXVC()
    wrapped = post.attach_speaker_condition_calibrator(model, torch=torch)
    trainable = post._set_speaker_condition_calibrator_training_only(model)
    with torch.no_grad():
        wrapped.speaker_condition_delta[0] = 0.25
    output = model.acoustic_converter(
        torch.zeros(1, 1, 1),
        torch.zeros(1, 1, 1),
        torch.ones(1, post.SPEAKER_CONDITION_DIMENSION),
    )

    assert trainable == [wrapped.speaker_condition_delta]
    assert trainable[0].numel() == post.SPEAKER_CONDITION_DIMENSION
    assert model.unrelated.requires_grad is False
    assert wrapped.base_converter.content.requires_grad is False
    assert output.item() == 1.25
    assert wrapped.base_converter.last_condition[0, 0].item() == 1.25

    metadata = post.save_speaker_condition_calibrator(
        model, tmp_path / "saved", torch=torch
    )
    reloaded = FakeXVC()
    post.load_speaker_condition_calibrator(
        reloaded, tmp_path / "saved", torch=torch, device=torch.device("cpu")
    )
    assert metadata["parameter_count"] == post.SPEAKER_CONDITION_DIMENSION
    assert post._speaker_condition_calibrator(
        reloaded
    ).speaker_condition_delta[0].item() == 0.25


def test_output_speaker_identity_reaches_final_waveform_gradient() -> None:
    from types import SimpleNamespace

    import torch

    class FakeSpeakerModel(torch.nn.Module):
        def forward(self, features):
            embedding = features.mean(dim=1)
            return embedding, features

    speaker_encoder = SimpleNamespace(
        feat_extractor=lambda waveform: torch.stack(
            (waveform, torch.ones_like(waveform)), dim=-1
        ),
        model=FakeSpeakerModel().eval(),
    )
    reconstruction = torch.tensor([[[1.0, 0.0, -1.0, 0.0]]], requires_grad=True)
    target = torch.tensor([[[2.0, 2.0, 2.0, 2.0]]])

    loss, metrics = post.output_speaker_identity_regularizer(
        reconstruction,
        target,
        speaker_encoder=speaker_encoder,
        torch=torch,
    )
    loss.backward()

    assert metrics["output_speaker_identity_similarity"] < 1.0
    assert metrics["output_speaker_identity_loss"] > 0.0
    assert reconstruction.grad is not None
    assert torch.count_nonzero(reconstruction.grad).item() > 0


def test_latent_source_speaker_margin_rejects_source_leakage(monkeypatch) -> None:
    import torch

    class FakeModel:
        speaker_encoder = object()

        @staticmethod
        def generative_loss(outputs):
            return {"loss": outputs["pred_sim_feat"].sum() * 0.0 + 2.0}

    predicted = torch.tensor([[1.0, 0.0]], requires_grad=True)
    outputs = {
        "pred_sim_feat": predicted,
        "sim_feat": torch.tensor([[0.0, 1.0]]),
    }
    batch = {"source_wav": torch.zeros(1, 1, 8)}
    monkeypatch.setattr(
        post,
        "differentiable_xvc_speaker_embedding",
        lambda speaker_encoder, waveform, *, torch: torch.tensor([[1.0, 0.0]]),
    )

    losses = post.latent_source_speaker_margin_generator_loss(
        FakeModel(), outputs, batch, torch=torch
    )
    losses["loss"].backward()

    assert losses["latent_source_speaker_target_similarity"].item() == 0.0
    assert losses["latent_source_speaker_source_similarity"].item() == 1.0
    assert losses["latent_source_speaker_advantage"].item() == -1.0
    assert losses["latent_source_speaker_active_fraction"].item() == 1.0
    assert abs(losses["latent_source_speaker_margin_loss"].item() - 11.0) < 1e-6
    assert abs(losses["loss"].item() - 13.0) < 1e-6
    assert predicted.grad is not None
    assert torch.count_nonzero(predicted.grad).item() > 0


def test_latent_source_speaker_margin_is_zero_when_satisfied(monkeypatch) -> None:
    import torch

    class FakeModel:
        speaker_encoder = object()

        @staticmethod
        def generative_loss(outputs):
            return {"loss": outputs["pred_sim_feat"].sum() * 0.0 + 2.0}

    outputs = {
        "pred_sim_feat": torch.tensor([[1.0, 0.0]], requires_grad=True),
        "sim_feat": torch.tensor([[1.0, 0.0]]),
    }
    batch = {"source_wav": torch.zeros(1, 1, 8)}
    monkeypatch.setattr(
        post,
        "differentiable_xvc_speaker_embedding",
        lambda speaker_encoder, waveform, *, torch: torch.tensor([[0.0, 1.0]]),
    )

    losses = post.latent_source_speaker_margin_generator_loss(
        FakeModel(), outputs, batch, torch=torch
    )

    assert losses["latent_source_speaker_advantage"].item() == 1.0
    assert losses["latent_source_speaker_active_fraction"].item() == 0.0
    assert losses["latent_source_speaker_margin_loss"].item() == 0.0
    assert losses["loss"].item() == 2.0


def test_exp325_exp326_share_manifest_and_bind_only_grl_as_treatment() -> None:
    control = post.listening_policy(
        post.SRC4VC_TWO_UTTERANCE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_REAL_ADVERSARIAL_OBJECTIVE,
        True,
    )
    treatment = post.listening_policy(
        post.SRC4VC_TWO_UTTERANCE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
        True,
    )

    assert control["slug"] == "exp325"
    assert treatment["slug"] == "exp326"
    assert control["source_speaker_grl"] is False
    assert treatment["source_speaker_grl"] is True
    assert "same ordered 170" in treatment["independent_variable"]
    objective_choices = post.parser()._option_string_actions[
        "--training-objective"
    ].choices
    assert post.PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE in objective_choices


def test_exp325_exp326_manifest_has_deterministic_85_x2_labels() -> None:
    items = []
    for speaker_index in range(post.SOURCE_SPEAKER_CLASS_COUNT):
        for utterance_index in (0, 1):
            items.append(
                {
                    "source_speaker_id": f"SRC4VC{speaker_index:03d}",
                    "source_sha256": f"{len(items) + 1:064x}",
                    "source_utterance_index": utterance_index,
                }
            )
    manifest = {
        "kind": post.SRC4VC_TWO_UTTERANCE_OUTPUT_KIND,
        "composition": post.SRC4VC_TWO_UTTERANCE_COMPOSITION,
        "items": items,
    }
    receipt = post.validate_source_speaker_manifest(manifest)

    assert receipt is not None
    assert receipt["source_speaker_class_count"] == 85
    assert receipt["rows_per_source_speaker"] == 2
    labels = post.source_speaker_label_map(manifest)
    assert labels["SRC4VC000"] == 0
    assert labels["SRC4VC084"] == 84
    assert receipt["same_manifest_for_control_and_treatment"] is True


def test_exp326_realism_target_uses_row_real_target(
    tmp_path: Path,
) -> None:
    real_target = tmp_path / "real-target.wav"
    real_target.write_bytes(b"row-real-target")
    item = {
        "target_id": "RECITATION324_113",
        "real_target_file": real_target.name,
        "real_target_sha256": hashlib.sha256(real_target.read_bytes()).hexdigest(),
    }

    pair = post._realism_target_pair(
        post.PSEUDOPARALLEL_SOURCE_SPEAKER_GRL_OBJECTIVE,
        item,
        source_work=tmp_path,
        target_by_id={},
    )

    assert pair.pair_id == "RECITATION324_113"
    assert pair.source_path == real_target
    assert pair.target_path == real_target
    assert pair.source_sha256 == item["real_target_sha256"]
    assert pair.target_sha256 == item["real_target_sha256"]


def test_exp326_grl_forward_contract_keeps_teacher_speaker_target_and_real_audio(
    monkeypatch,
) -> None:
    import torch

    calls: list[object] = []
    discriminator_audios: list[torch.Tensor] = []

    def model_inputs(batch, speaker_target_wav):
        calls.append(speaker_target_wav)
        assert speaker_target_wav is None
        return dict(batch)

    monkeypatch.setattr(post.breadth, "_generator_model_inputs", model_inputs)
    monkeypatch.setattr(post.base, "_set_adapter_training_only", lambda _model: None)

    class FakeModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lora = torch.nn.Parameter(torch.tensor(0.5))

        def forward(self, inputs):
            # The teacher target must remain the batch target; the real audio is
            # supplied separately to the discriminator path.
            assert inputs["target_wav"] is teacher
            return {"recons": self.lora.expand(1, 1, 2)}

        def generative_loss(self, outputs):
            return {"loss": outputs["recons"].square().mean()}

    class FakeDiscriminator(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.weight = torch.nn.Parameter(torch.tensor(0.25))

        def discriminative_loss(self, outputs):
            discriminator_audios.append(outputs["audios"].detach().clone())
            return {"loss": self.weight.square()}

        def adversarial_loss(self, outputs):
            discriminator_audios.append(outputs["audios"].detach().clone())
            return {
                "loss": outputs["recons"].square().mean(),
                "adv_gen_loss": 0.0,
                "adv_feat_loss": 0.0,
            }

    class FakeHook:
        def set_enabled(self, _enabled):
            return None

        def clear(self):
            return None

        def pooled(self):
            return fake_model.lora.expand(1, post.SOURCE_SPEAKER_FEATURE_DIMENSION)

    fake_model = FakeModel()
    discriminator = FakeDiscriminator()
    classifier = post.source_speaker_classifier(torch=torch)
    generator_optimizer = torch.optim.SGD([fake_model.lora], lr=0.01)
    discriminator_optimizer = torch.optim.SGD(discriminator.parameters(), lr=0.01)
    classifier_optimizer = torch.optim.SGD(classifier.parameters(), lr=0.01)
    teacher = torch.ones(1, 1, 2)
    real_audio = torch.full((1, 1, 2), 7.0)
    batch = {
        "source_wav": torch.zeros(1, 1, 2),
        "target_wav": teacher,
        "source_speaker_label": torch.tensor([0], dtype=torch.long),
    }

    post.source_speaker_grl_adversarial_update(
        fake_model,
        discriminator,
        generator_optimizer,
        discriminator_optimizer,
        classifier,
        classifier_optimizer,
        [fake_model.lora],
        batch,
        FakeHook(),
        real_audios=real_audio,
        torch=torch,
    )

    assert len(calls) == 3
    assert all(value is None for value in calls)
    assert len(discriminator_audios) == 2
    assert torch.equal(discriminator_audios[0], real_audio)
    assert torch.equal(discriminator_audios[1], real_audio)


def test_source_speaker_mean_std_pool_and_cross_utterance_probe() -> None:
    import torch

    latent = torch.arange(2 * 1024 * 3, dtype=torch.float32).reshape(2, 1024, 3)
    pooled = post.source_speaker_pooled_features(latent, torch=torch)
    assert pooled.shape == (2, post.SOURCE_SPEAKER_FEATURE_DIMENSION)
    assert torch.allclose(pooled[:, :1024], latent.mean(dim=-1))
    assert torch.allclose(
        pooled[:, 1024:], latent.std(dim=-1, unbiased=False)
    )

    basis = torch.eye(post.SOURCE_SPEAKER_FEATURE_DIMENSION)[:85]
    features = torch.stack(
        [
            basis[index] + (0.001 * torch.roll(basis[index], 1))
            for index in range(85)
            for _ in (0, 1)
        ]
    )
    labels = [f"speaker-{index:03d}" for index in range(85) for _ in (0, 1)]
    probe = post.source_speaker_signal_probe(features, labels, torch=torch)
    assert probe["top1_accuracy"] == 1.0
    assert probe["top5_accuracy"] == 1.0
    assert probe["materially_above_chance"] is True


def test_source_speaker_hook_is_training_only_and_pools_converter_output() -> None:
    import torch

    class FakeConverter(torch.nn.Module):
        def forward(self, value):
            return value

    class FakeModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.acoustic_converter = FakeConverter()

    model = FakeModel()
    hook = post.attach_source_speaker_adversary(model, torch=torch)
    value = torch.randn(1, 1024, 4, requires_grad=True)
    model.acoustic_converter(value)
    assert hook.inference_calls == 1
    hook.set_enabled(True)
    model.acoustic_converter(value)
    pooled = hook.pooled()
    assert pooled.shape == (1, 2048)
    assert hook.training_calls == 1
    hook.close()
    assert hook.diagnostics()["training_only"] is True


def test_speaker_path_loss_contains_only_the_weighted_voice_target() -> None:
    import torch

    predicted = torch.tensor([[1.0, 3.0]], requires_grad=True)
    target = torch.tensor([[0.0, 1.0]])

    losses = post.speaker_path_unpaired_generator_loss(
        {"pred_sim_feat": predicted, "sim_feat": target},
        {},
        torch=torch,
    )

    assert losses["speaker"].item() == 2.5
    assert losses["loss"].item() == 25.0
    assert set(losses) == {"loss", "speaker"}


def test_contrastive_output_cycle_policy_changes_only_content_comparison() -> None:
    policy = post.listening_policy(
        post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.CONTRASTIVE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp218"
    assert policy["candidate_id"] == ("cross-corpus170-contrastive-output-cycle-ema170")
    assert "two-way framewise cosine InfoNCE" in policy["independent_variable"]
    assert "temperature 0.1" in policy["independent_variable"]


def test_contrastive_output_cycle_prefers_source_over_negative(monkeypatch) -> None:
    import torch

    reconstruction = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]], requires_grad=True)
    outputs = {
        "recons": reconstruction,
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {
        "ssl_feat": torch.tensor([[[1.0, 0.0], [0.0, 1.0]]]),
        "negative_ssl_feat": torch.tensor([[[0.0, 1.0], [1.0, 0.0]]]),
    }
    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda semantic_encoder, waveform, *, torch: waveform,
    )

    losses = post.contrastive_output_cycle_unpaired_generator_loss(
        outputs,
        batch,
        semantic_encoder=object(),
        torch=torch,
    )
    losses["loss"].backward()

    assert losses["positive_cosine"].item() == 1.0
    assert losses["negative_cosine"].item() == 0.0
    assert losses["output_cycle_contrastive_content"].item() < 0.001
    assert reconstruction.grad is not None
    assert torch.count_nonzero(reconstruction.grad).item() > 0


def test_discrete_output_cycle_policy_uses_frozen_source_tokens() -> None:
    policy = post.listening_policy(
        post.CROSS_CORPUS_UNPAIRED_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.DISCRETE_OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp223"
    assert policy["candidate_id"] == ("cross-corpus170-discrete-output-cycle-ema170")
    assert "16,384-entry WhisperVQ codebook" in policy["independent_variable"]
    assert "source semantic-token IDs" in policy["independent_variable"]


def test_discrete_output_cycle_classifies_source_tokens_from_final_wav(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import torch

    codebook = torch.nn.Embedding(16_384, 2)
    with torch.no_grad():
        codebook.weight.fill_(10.0)
        codebook.weight[5] = torch.tensor([1.0, 0.0])
        codebook.weight[9] = torch.tensor([0.0, 1.0])
    semantic_encoder = SimpleNamespace(
        encoder=SimpleNamespace(
            pooling_layer=torch.nn.AvgPool1d(kernel_size=1),
            codebook=codebook,
        )
    )
    # The real WhisperVQ ``whisper_hidden_states_50hz`` boundary is B, D, T.
    reconstruction = torch.tensor(
        [[[1.0, 0.0, 1.0], [0.0, 1.0, 0.0]]], requires_grad=True
    )
    outputs = {
        "recons": reconstruction,
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {"semantic_tokens": torch.tensor([[5, 9, 5]], dtype=torch.long)}
    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda current_encoder, waveform, *, torch: waveform,
    )

    losses = post.discrete_output_cycle_unpaired_generator_loss(
        outputs,
        batch,
        semantic_encoder=semantic_encoder,
        torch=torch,
    )
    losses["loss"].backward()

    assert losses["output_cycle_token_accuracy"].item() == 1.0
    assert losses["output_cycle_discrete_content"].item() < 0.1
    assert reconstruction.grad is not None
    assert torch.count_nonzero(reconstruction.grad).item() > 0


def test_factorized_loss_uses_source_semantics_and_target_speaker() -> None:
    import torch

    outputs = {
        "pred": torch.tensor([[[1.0, 3.0]]]),
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {"ssl_feat": torch.tensor([[[0.0, 1.0]]])}

    losses = post.factorized_unpaired_generator_loss(outputs, batch, torch=torch)

    assert losses["semantic"].item() == 2.5
    assert losses["speaker"].item() == 5.0
    assert losses["loss"].item() == 2_550.0


def test_output_cycle_loss_backpropagates_from_final_wav(
    monkeypatch,
) -> None:
    import torch

    reconstruction = torch.tensor([[[1.0, 3.0]]], requires_grad=True)
    outputs = {
        "recons": reconstruction,
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {"ssl_feat": torch.tensor([[[0.0, 1.0]]])}
    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda semantic_encoder, waveform, *, torch: waveform,
    )

    losses = post.output_cycle_unpaired_generator_loss(
        outputs,
        batch,
        semantic_encoder=object(),
        torch=torch,
    )
    losses["loss"].backward()

    assert losses["output_cycle_content"].item() == 2.5
    assert losses["speaker"].item() == 5.0
    assert losses["loss"].item() == 2_550.0
    assert reconstruction.grad is not None
    assert torch.count_nonzero(reconstruction.grad).item() == 2


def test_differentiable_whisper_frontend_keeps_waveform_gradient() -> None:
    from types import SimpleNamespace

    import numpy as np
    import torch

    class FakeEncoder:
        def __call__(self, *, input_features, attention_mask):
            assert attention_mask.shape == (
                input_features.shape[0],
                input_features.shape[-1],
            )
            return SimpleNamespace(whisper_hidden_states_50hz=input_features)

    semantic_encoder = SimpleNamespace(
        feature_extractor=SimpleNamespace(
            n_fft=4,
            hop_length=2,
            mel_filters=np.asarray(
                [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32
            ),
        ),
        encoder=FakeEncoder(),
    )
    waveform = torch.linspace(-0.5, 0.5, 16).reshape(1, 1, -1)
    waveform.requires_grad_(True)

    hidden = post.differentiable_whisper_hidden_states(
        semantic_encoder, waveform, torch=torch
    )
    hidden.square().mean().backward()

    assert hidden.shape[1] == 2
    assert waveform.grad is not None
    assert torch.count_nonzero(waveform.grad).item() > 0


def test_output_cycle_frontend_equivalence_rejects_drift(monkeypatch) -> None:
    import torch

    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda semantic_encoder, waveform, *, torch: waveform,
    )
    source = torch.tensor([[[1.0, 2.0]]])

    metrics = post.validate_output_cycle_frontend(
        object(), source, source + 1e-4, torch=torch
    )
    assert metrics["maximum_absolute_hidden_difference"] < 1e-3

    try:
        post.validate_output_cycle_frontend(object(), source, source + 0.1, torch=torch)
    except post.PostRehearsalError as error:
        assert "frontend mismatch" in str(error)
    else:
        raise AssertionError("drifted output-cycle frontend unexpectedly admitted")


def test_unpaired_human_manifest_does_not_require_predecessor_result(
    tmp_path: Path,
) -> None:
    curriculum = tmp_path / "curriculum.json"
    curriculum.write_text("{}", encoding="utf-8")

    identities = post.source_receipt_identities(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        tmp_path / "no-predecessor-result",
        curriculum,
    )

    assert identities["source_result_sha256"] is None
    assert identities["unpaired_human_curriculum_sha256"] == post.sha256_file(
        curriculum
    )


def test_acoustic_encoder_setter_freezes_every_other_module() -> None:
    class FakeModule:
        def train(self, value: bool) -> None:
            self.training = value

    class FakeParameter:
        def __init__(self, count: int) -> None:
            self.count = count
            self.requires_grad = True

        def requires_grad_(self, value: bool) -> None:
            self.requires_grad = value

        def numel(self) -> int:
            return self.count

    selected = FakeParameter(post.EXPECTED_ACOUSTIC_ENCODER_PARAMETERS)
    excluded = FakeParameter(99)

    class FakeModel:
        acoustic_encoder = FakeModule()

        def eval(self) -> None:
            self.training = False

        def named_parameters(self):
            yield "acoustic_encoder.weight", selected
            yield "acoustic_converter.weight", excluded

    trainable = post._set_acoustic_encoder_training_only(FakeModel())

    assert trainable == [selected]
    assert selected.requires_grad is True
    assert excluded.requires_grad is False


def test_jsut_retention_changes_only_easy_data_identity() -> None:
    policy = post.listening_policy(
        post.JSUT_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp171"
    assert policy["candidate_id"] == ("cv12-jsut-retention-real-adversarial-ema170")
    assert "easy85" in policy["independent_variable"]


def test_commonvoice_retention_changes_only_easy_data_identity() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp186"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-retention-real-adversarial-ema170"
    )
    assert "48 precommitted Common Voice" in policy["independent_variable"]


def test_source36_retention_changes_only_mutable_function_path() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.SOURCE36_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp194"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-source36-real-adversarial-ema170"
    )
    assert "36 source-side" in policy["independent_variable"]


def test_existing_adapter_scope_freezes_lora_outside_selected_path() -> None:
    class FakeModule:
        def train(self, value: bool) -> None:
            self.training = value

    class FakeParameter:
        def __init__(self, count: int) -> None:
            self.count = count
            self.requires_grad = True

        def requires_grad_(self, value: bool) -> None:
            self.requires_grad = value

        def numel(self) -> int:
            return self.count

    target = "acoustic_converter.transformer_blocks.0.attn.to_q"
    selected_a = FakeParameter(10)
    selected_b = FakeParameter(14)
    excluded = FakeParameter(99)

    class FakeModel:
        def eval(self) -> None:
            self.training = False

        def named_modules(self):
            yield f"base_model.model.{target}.lora_A.default", FakeModule()
            yield (
                "base_model.model.acoustic_converter.proj_out.lora_A.default",
                FakeModule(),
            )

        def named_parameters(self):
            yield f"base_model.model.{target}.lora_A.default.weight", selected_a
            yield f"base_model.model.{target}.lora_B.default.weight", selected_b
            yield (
                "base_model.model.acoustic_converter.proj_out.lora_A.default.weight",
                excluded,
            )

    trainable = post._set_existing_adapter_scope_training_only(
        FakeModel(),
        {"target_modules": [target], "trainable_parameter_count": 24},
    )

    assert trainable == [selected_a, selected_b]
    assert selected_a.requires_grad is True
    assert selected_b.requires_grad is True
    assert excluded.requires_grad is False


def test_conditioned_retention_changes_only_easy_condition_identity() -> None:
    policy = post.listening_policy(
        post.CONDITIONED_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp191"
    assert policy["candidate_id"] == (
        "cv12-conditioned-retention-real-adversarial-ema170"
    )
    assert "17 each clean" in policy["independent_variable"]


def test_paired_pcgrad_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.GENERATIVE_OBJECTIVE,
        False,
        post.PCGRAD_PAIRED_OPTIMIZER,
    )

    assert policy["slug"] == "exp176"
    assert policy["candidate_id"] == "cv12-selective-pcgrad85"
    assert "all 170 sources and targets" in policy["independent_variable"]


def test_parameter_anchor_changes_only_exp163_objective_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
        post.SEQUENTIAL_OPTIMIZER,
        True,
    )

    assert policy["slug"] == "exp181"
    assert policy["candidate_id"] == ("cv12-selective-real-adversarial-anchor-ema170")
    assert "L2-SP" in policy["independent_variable"]


def test_parameter_anchor_requires_exact_exp163_baseline() -> None:
    for manifest_kind, use_ema in (
        (post.SELECTIVE_OUTPUT_KIND, False),
        (post.JSUT_RETENTION_OUTPUT_KIND, True),
    ):
        try:
            post.listening_policy(
                manifest_kind,
                post.LORA69_TARGET,
                post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
                use_ema,
                post.SEQUENTIAL_OPTIMIZER,
                True,
            )
        except post.PostRehearsalError as error:
            assert "exact EXP-163 baseline" in str(error)
        else:
            raise AssertionError("unsupported parameter anchor policy admitted")


def test_source_activity_envelope_changes_only_exp186_objective_identity() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
        post.SEQUENTIAL_OPTIMIZER,
        False,
        True,
    )

    assert policy["slug"] == "exp196"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-source-envelope-real-adversarial-ema170"
    )
    assert "20 ms/10 ms" in policy["independent_variable"]


def test_paired_pcgrad_rejects_ema_or_other_curriculum() -> None:
    for manifest_kind, use_ema in (
        (post.SELECTIVE_OUTPUT_KIND, True),
        (post.JSUT_RETENTION_OUTPUT_KIND, False),
    ):
        try:
            post.listening_policy(
                manifest_kind,
                post.LORA69_TARGET,
                post.GENERATIVE_OBJECTIVE,
                use_ema,
                post.PCGRAD_PAIRED_OPTIMIZER,
            )
        except post.PostRehearsalError as error:
            assert "paired PCGrad" in str(error)
        else:
            raise AssertionError("unsupported paired PCGrad policy admitted")


def test_paired_rows_require_frozen_hard_easy_order() -> None:
    hard = {
        "curriculum_role": "hard",
        "learning_target": post.REPAIR_TARGET,
    }
    easy = {
        "curriculum_role": "easy",
        "learning_target": post.RETENTION_TARGET,
    }

    assert post.paired_hard_easy_rows([hard, easy]) == [(hard, easy)]
    try:
        post.paired_hard_easy_rows([easy, hard])
    except post.PostRehearsalError as error:
        assert "role order" in str(error)
    else:
        raise AssertionError("reversed PCGrad pair unexpectedly admitted")


def test_pcgrad_smoke_keeps_one_complete_hard_easy_pair() -> None:
    manifest = {
        "kind": post.SELECTIVE_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard"},
            {"curriculum_role": "easy"},
            {"curriculum_role": "hard"},
        ],
    }

    rows = post.smoke_rows(manifest, post.PCGRAD_PAIRED_OPTIMIZER)

    assert [row["curriculum_role"] for row in rows] == ["hard", "easy"]


def test_parameter_anchor_smoke_exercises_nonzero_distance_step() -> None:
    items = [{"id": "first"}, {"id": "second"}, {"id": "third"}]

    rows = post.smoke_rows(
        {"kind": post.SELECTIVE_OUTPUT_KIND, "items": items},
        parameter_anchor=True,
    )

    assert rows == items[:2]


def test_acoustic_encoder_smoke_exercises_hard_and_easy_roles() -> None:
    items = [
        {"id": "hard", "curriculum_role": "hard"},
        {"id": "easy", "curriculum_role": "easy"},
        {"id": "later", "curriculum_role": "hard"},
    ]

    rows = post.smoke_rows(
        {"kind": post.SELECTIVE_OUTPUT_KIND, "items": items},
        require_hard_easy=True,
    )

    assert rows == items[:2]


def test_pcgrad_projects_only_conflicting_task_components() -> None:
    import torch

    hard = [torch.tensor([1.0, 0.0])]
    easy = [torch.tensor([-1.0, 1.0])]

    merged, metrics = post.project_conflicting_pair(hard, easy, torch=torch)

    assert metrics["conflict"] is True
    assert torch.allclose(merged[0], torch.tensor([0.5, 1.5]))

    aligned, aligned_metrics = post.project_conflicting_pair(
        [torch.tensor([1.0, 0.0])],
        [torch.tensor([2.0, 0.0])],
        torch=torch,
    )
    assert aligned_metrics["conflict"] is False
    assert torch.equal(aligned[0], torch.tensor([3.0, 0.0]))


def test_parameter_anchor_regularizer_uses_control69_distance() -> None:
    import torch

    parameters = [torch.tensor([2.0, -1.0], requires_grad=True)]
    anchors = [torch.tensor([1.0, 1.0])]

    loss, metrics = post.parameter_anchor_regularizer(
        parameters, anchors, torch=torch, coefficient=2.0
    )
    loss.backward()

    assert float(loss.detach()) == 5.0
    assert metrics == {
        "parameter_anchor_loss": 5.0,
        "parameter_anchor_squared_distance": 5.0,
    }
    assert torch.equal(parameters[0].grad, torch.tensor([2.0, -4.0]))


def test_source_activity_envelope_ignores_gain_but_penalizes_timing() -> None:
    import torch

    source = torch.zeros(1, 1, 38400)
    source[..., 8000:24000] = 0.5
    same_timing = source * 0.2
    shifted = torch.zeros_like(source)
    shifted[..., 12000:28000] = 0.1

    same_loss, _ = post.source_activity_envelope_regularizer(
        same_timing, {"source_wav": source}, torch=torch
    )
    shifted_loss, shifted_metrics = post.source_activity_envelope_regularizer(
        shifted, {"source_wav": source}, torch=torch
    )

    assert float(same_loss) < 1e-5
    assert float(shifted_loss) > 1.0
    assert shifted_metrics["source_activity_envelope_distance"] > 0.1


def test_jsut_smoke_exercises_hard_and_diverse_easy_roots() -> None:
    manifest = {
        "kind": post.JSUT_RETENTION_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard", "source_root": "source-work"},
            {"curriculum_role": "easy", "source_root": "diverse-work"},
        ],
    }

    rows = post.smoke_rows(manifest)

    assert [row["source_root"] for row in rows] == [
        "source-work",
        "diverse-work",
    ]


def test_commonvoice_smoke_exercises_hard_and_diverse_easy_roots() -> None:
    manifest = {
        "kind": post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard", "source_root": "source-work"},
            {"curriculum_role": "easy", "source_root": "diverse-work"},
        ],
    }

    rows = post.smoke_rows(manifest)

    assert [row["source_root"] for row in rows] == [
        "source-work",
        "diverse-work",
    ]


def test_adapter_ema_matches_pinned_default_update_schedule() -> None:
    import torch

    model = torch.nn.Linear(1, 1, bias=False)
    model.weight.requires_grad_(True)
    tracker = post.AdapterEMA(model, torch)
    for update in range(1, 171):
        with torch.no_grad():
            model.weight.fill_(float(update))
        tracker.update()

    receipt = tracker.receipt()
    assert receipt["calls"] == 170
    assert receipt["copy_updates"] == 11
    assert receipt["moving_average_updates"] == 6
    assert receipt["last_decay"] == 1.0 - 61.0 ** (-2.0 / 3.0)
    assert float(tracker.shadow["weight"].item()) < 161.0
    tracker.copy_to()
    assert torch.equal(model.weight, tracker.shadow["weight"])


def test_exp334_feature_statistics_changes_only_nonlogit_feature_term() -> None:
    import torch

    fake_feature_3d = torch.randn(2, 3, 5, requires_grad=True)
    real_feature_3d = torch.randn(2, 3, 5, requires_grad=True)
    fake_feature_4d = torch.randn(2, 4, 3, 2, requires_grad=True)
    real_feature_4d = torch.randn(2, 4, 3, 2, requires_grad=True)
    fake_logit = torch.randn(2, 1, 4, requires_grad=True)
    real_logit = torch.randn(2, 1, 4, requires_grad=True)
    fake = [[fake_feature_3d, fake_feature_4d, fake_logit]]
    real = [[real_feature_3d, real_feature_4d, real_logit]]

    losses = post.feature_statistics_adversarial_loss_from_outputs(
        fake,
        real,
        loss_weights={"adv_gen_loss": 3.0, "adv_feat_loss": 2.0},
        torch=torch,
    )
    expected_gen = torch.mean((1 - fake_logit) ** 2)
    pointwise = torch.nn.functional.l1_loss(fake_feature_3d, real_feature_3d)
    pointwise = pointwise + torch.nn.functional.l1_loss(
        fake_feature_4d, real_feature_4d
    )

    assert torch.equal(losses["adv_gen_loss"], expected_gen)
    assert losses["feature_layer_count"] == 2
    assert not torch.equal(losses["adv_feat_loss"], pointwise)
    assert torch.equal(
        losses["loss"],
        3.0 * losses["adv_gen_loss"] + 2.0 * losses["adv_feat_loss"],
    )
    losses["loss"].backward()
    assert fake_feature_3d.grad is not None
    assert fake_feature_4d.grad is not None
    assert fake_logit.grad is not None
    assert real_feature_3d.grad is None
    assert real_feature_4d.grad is None
    assert real_logit.grad is None


def test_exp334_feature_statistics_reduces_all_post_channel_axes() -> None:
    import torch

    feature = torch.tensor([[[[1.0, 3.0], [5.0, 7.0]]]])
    statistics = post.feature_statistics(feature, torch=torch, epsilon=0.0)

    assert statistics.shape == (1, 2)
    assert torch.allclose(statistics, torch.tensor([[4.0, 2.2360679]]), atol=1e-6)


def test_exp334_feature_statistics_rejects_rank_and_layer_drift() -> None:
    import torch

    with pytest.raises(post.PostRehearsalError, match="rank"):
        post.feature_statistics(torch.zeros(1, 2), torch=torch)
    with pytest.raises(post.PostRehearsalError, match="layer count"):
        post.feature_statistics_adversarial_loss_from_outputs(
            [[torch.zeros(1, 2, 3), torch.zeros(1, 1, 3)]],
            [[torch.zeros(1, 2, 3)]],
            loss_weights={"adv_gen_loss": 1.0, "adv_feat_loss": 1.0},
            torch=torch,
        )


def test_exp334_policy_and_parser_bind_exact_exp238_contract() -> None:
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_FEATURE_STATISTICS_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp334"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-feature-statistics-real-adv-ema170"
    )
    assert "mean, sqrt(var+1e-6)" in policy["independent_variable"]
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_FEATURE_STATISTICS_OBJECTIVE in choices
    for kwargs in (
        {"manifest_kind": post.SRC4VC_PSEUDOPARALLEL_OUTPUT_KIND},
        {"use_adapter_ema": False},
        {"optimizer_mode": post.PCGRAD_CONTENT_VOICE_OPTIMIZER},
    ):
        arguments = {
            "manifest_kind": post.PSEUDOPARALLEL_OUTPUT_KIND,
            "trainable_target": post.LORA69_TARGET,
            "training_objective": post.PSEUDOPARALLEL_FEATURE_STATISTICS_OBJECTIVE,
            "use_adapter_ema": True,
        }
        arguments.update(kwargs)
        with pytest.raises(post.PostRehearsalError):
            post.listening_policy(**arguments)


def test_exp340_policy_and_scope_add_only_prenet_linear_pre() -> None:
    targets = [f"acoustic_converter.layer{index}.to_q" for index in range(69)]
    scope = post.composed_prenet_lora_scope(
        {
            "target_modules": targets,
            "trainable_parameter_count": post.CONTROL69_LORA_TRAINABLE_PARAMETERS,
        }
    )
    policy = post.listening_policy(
        post.PSEUDOPARALLEL_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.PSEUDOPARALLEL_PRENET_LORA_OBJECTIVE,
        True,
    )

    assert scope["target_modules"] == [*targets, "prenet.linear_pre"]
    assert scope["trainable_parameter_count"] == 858_112
    assert policy["slug"] == "exp340"
    assert policy["candidate_id"] == (
        "cross-corpus170-pseudoparallel-prenet-linear-pre-lora8-"
        "real-adv-ema170"
    )
    assert policy["result_kind"] == (
        "liveconv-exp340-xvc-prenet-linear-pre-lora8-real-adv-ema/v1"
    )
    choices = post.parser()._option_string_actions["--training-objective"].choices
    assert post.PSEUDOPARALLEL_PRENET_LORA_OBJECTIVE in choices


def test_exp340_state_receipt_requires_exact_control_and_zero_prenet_b() -> None:
    import torch

    control = {
        "base_model.model.acoustic_converter.x.lora_A.weight": torch.ones(2, 3),
        "base_model.model.acoustic_converter.x.lora_B.weight": torch.ones(3, 2),
    }
    candidate = {
        **{key: value.clone() for key, value in control.items()},
        "base_model.model.prenet.linear_pre.lora_A.weight": torch.ones(2, 4),
        "base_model.model.prenet.linear_pre.lora_B.weight": torch.zeros(4, 2),
    }

    receipt = post.composed_prenet_lora_state_receipt(
        control, candidate, torch=torch
    )

    assert receipt["control_values_exact"] is True
    assert receipt["added_lora_b_zero"] is True
    assert receipt["step0_output_equivalent_by_zero_delta"] is True
    candidate["base_model.model.prenet.linear_pre.lora_B.weight"][0, 0] = 1
    with pytest.raises(post.PostRehearsalError, match="not zero initialized"):
        post.composed_prenet_lora_state_receipt(control, candidate, torch=torch)


def test_exp340_smoke_gradient_diagnostics_cover_both_adapter_regions() -> None:
    import torch

    named = []
    for index in range(138):
        parameter = torch.nn.Parameter(torch.ones(1))
        parameter.grad = torch.ones_like(parameter)
        named.append(
            (
                "base_model.model.acoustic_converter."
                f"layer{index}.lora_A.default.weight",
                parameter,
            )
        )
    for side in ("A", "B"):
        parameter = torch.nn.Parameter(torch.ones(1))
        parameter.grad = torch.ones_like(parameter)
        named.append(
            (
                "base_model.model.prenet.linear_pre."
                f"lora_{side}.default.weight",
                parameter,
            )
        )

    class FakeModel:
        def named_parameters(self):
            yield from named

    diagnostics = post.composed_prenet_lora_gradient_diagnostics(
        FakeModel(), torch=torch
    )

    assert diagnostics["converter_lora69"]["tensor_count"] == 138
    assert diagnostics["prenet_linear_pre"]["tensor_count"] == 2
    assert diagnostics["converter_lora69"]["finite"] is True
    assert diagnostics["prenet_linear_pre"]["finite"] is True
