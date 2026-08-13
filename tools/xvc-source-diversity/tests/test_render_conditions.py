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
