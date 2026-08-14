from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import run_post_rehearsal as post  # noqa: E402
import run_role_mix as role_mix  # noqa: E402


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
