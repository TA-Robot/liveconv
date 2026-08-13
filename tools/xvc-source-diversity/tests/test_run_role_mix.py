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
