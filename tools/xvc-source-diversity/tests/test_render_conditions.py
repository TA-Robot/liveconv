from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_conditions.py"
SPEC = importlib.util.spec_from_file_location("xvc_render_conditions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RENDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RENDER
SPEC.loader.exec_module(RENDER)


def test_condition_index_is_unselected_and_compares_fixed_three_arms() -> None:
    source = RENDER.base.RenderSource(
        pair_id="heldout-1", display_text="heldout / noise", source_path=Path("x.wav")
    )

    index = RENDER.listening_index(
        source,
        target_reference_id="target-1",
        hashes={
            "base": "a" * 64,
            "jvs3-generated-pairs": "b" * 64,
            "cv12-generated-pairs": "c" * 64,
        },
    )

    assert index["status"] == "completed-listen-now-unselected"
    assert [row["variant_id"] for row in index["variants"]] == [
        "base",
        "jvs3-generated-pairs",
        "cv12-generated-pairs",
    ]
    assert "winner" not in str(index).lower()


def test_reconstruction_candidate_uses_exp042_condition_policy() -> None:
    policy = RENDER.candidate_policy("reconstruction20")

    assert policy["experiment_id"] == "EXP-042"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-reconstruction20"


def test_authentic_anchor_uses_exp048_condition_policy() -> None:
    policy = RENDER.candidate_policy("authentic-anchor")

    assert policy["experiment_id"] == "EXP-048"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv11-authentic1"


def test_semantic2x_uses_exp051_condition_policy() -> None:
    policy = RENDER.candidate_policy("semantic2x")

    assert policy["experiment_id"] == "EXP-051"
    assert policy["candidate"][0] == "cv12-semantic2x"


def test_source36_uses_exp054_condition_policy() -> None:
    policy = RENDER.candidate_policy("source36")

    assert policy["experiment_id"] == "EXP-054"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-source36"


def test_target275_uses_exp057_condition_policy() -> None:
    policy = RENDER.candidate_policy("target275")

    assert policy["experiment_id"] == "EXP-057"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-target275"


def test_content_filtered_uses_exp062_condition_policy() -> None:
    policy = RENDER.candidate_policy("content-filtered6x2")

    assert policy["experiment_id"] == "EXP-062"
    assert policy["candidate"][0] == "cv12-content-filtered6x2"


def test_wave_adversarial_uses_exp066_condition_policy() -> None:
    policy = RENDER.candidate_policy("wave-adversarial")

    assert policy["experiment_id"] == "EXP-066"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-wave-adversarial"
    choices = next(
        action.choices
        for action in RENDER._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "wave-adversarial" in choices


def test_output2_uses_exp070_condition_policy() -> None:
    policy = RENDER.candidate_policy("output2")

    assert policy["experiment_id"] == "EXP-070"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-output2"
    choices = next(
        action.choices
        for action in RENDER._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "output2" in choices


def test_real_rehearsal_uses_exp074_condition_policy() -> None:
    policy = RENDER.candidate_policy("real-reconstruction20")

    assert policy["experiment_id"] == "EXP-074"
    assert policy["control"][0] == "cv12-control69"
    assert policy["candidate"][0] == "cv12-real-reconstruction20"
    choices = next(
        action.choices
        for action in RENDER._parser()._actions
        if action.dest == "candidate_kind"
    )
    assert "real-reconstruction20" in choices


def test_decoder_final_uses_exp079_condition_policy() -> None:
    policy = RENDER.candidate_policy("decoder-final")
    assert policy["experiment_id"] == "EXP-079"
    assert policy["candidate"][0] == "cv12-decoder-final"


def test_source_semantic_uses_exp083_condition_policy() -> None:
    policy = RENDER.candidate_policy("source-semantic")

    assert policy["experiment_id"] == "EXP-083"
    assert policy["candidate"][0] == "cv12-source-semantic"


def test_denoise_semantic_uses_exp089_condition_policy() -> None:
    policy = RENDER.candidate_policy("denoise-semantic")

    assert policy["experiment_id"] == "EXP-089"
    assert policy["candidate"][0] == "cv12-denoise-semantic"


def test_cross_target_condition_uses_exp096_policy() -> None:
    policy = RENDER.candidate_policy("cross-target-condition")

    assert policy["experiment_id"] == "EXP-096"
    assert policy["candidate"][0] == "cv12-cross-target-condition"
    assert policy["conditioned_inference"] is True


def test_semantic_token_hold_uses_exp102_policy() -> None:
    policy = RENDER.candidate_policy("semantic-token-hold")

    assert policy["experiment_id"] == "EXP-102"
    assert policy["candidate"][0] == "cv12-semantic-token-hold"


def test_real_teacher_semantic_uses_exp108_policy() -> None:
    policy = RENDER.candidate_policy("real-teacher-semantic20")

    assert policy["experiment_id"] == "EXP-108"
    assert policy["candidate"][0] == "cv12-real-teacher-semantic20"
