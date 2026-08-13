from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_context.py"
SPEC = importlib.util.spec_from_file_location("xvc_render_context", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
CONTEXT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTEXT
SPEC.loader.exec_module(CONTEXT)


def test_target_condition_uses_separate_context_then_zero_current_window() -> None:
    class TorchStub:
        zeros_like = staticmethod(np.zeros_like)

        @staticmethod
        def cat(values, *, dim):
            return np.concatenate(values, axis=dim)

    reference = {"target_wav": np.ones((1, 1, 4), dtype=np.float32)}
    context = {"target_wav": np.full((1, 1, 4), 2.0, dtype=np.float32)}

    result = CONTEXT.target_condition(reference, context, TorchStub)

    assert result.shape == (1, 1, 8)
    np.testing.assert_array_equal(result[..., :4], context["target_wav"])
    np.testing.assert_array_equal(result[..., 4:], np.zeros((1, 1, 4)))


def test_listener_index_is_unselected_and_exposes_only_condition_change() -> None:
    item = {
        "age": "twenties",
        "gender": "female_feminine",
        "text": "短い文",
    }

    index = CONTEXT.listening_index(
        item,
        hashes={
            "cv12-zero-condition": "a" * 64,
            "cv12-context-condition": "b" * 64,
        },
    )

    assert index["status"] == "completed-listen-now-unselected"
    assert [row["variant_id"] for row in index["variants"]] == [
        "cv12-zero-condition",
        "cv12-context-condition",
    ]
    assert len(index["reference_audio"]) == 3
