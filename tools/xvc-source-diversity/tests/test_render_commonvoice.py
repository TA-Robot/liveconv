from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_commonvoice.py"
SPEC = importlib.util.spec_from_file_location("xvc_render_commonvoice", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RENDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RENDER
SPEC.loader.exec_module(RENDER)


def _inputs() -> dict[str, object]:
    return {
        "kind": RENDER.KIND,
        "source": {"license": "CC0-1.0"},
        "items": [
            {
                "id": f"speaker-{index}",
                "group": "commonvoice-unseen-speaker",
                "filename": f"speaker-{index}.mp3",
                "sha256": f"{index + 1:064x}",
                "client_id_sha256": f"{index + 11:064x}",
                "text": f"known text {index}",
                "down_votes": 0,
            }
            for index in range(6)
        ],
    }


def test_inputs_require_six_distinct_speakers(tmp_path: Path) -> None:
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(_inputs()), encoding="utf-8")

    loaded = RENDER.load_inputs(path)

    assert len(loaded["items"]) == 6
    assert len({item["client_id_sha256"] for item in loaded["items"]}) == 6


def test_inputs_reject_reused_speaker(tmp_path: Path) -> None:
    value = _inputs()
    value["items"][1]["client_id_sha256"] = value["items"][0]["client_id_sha256"]
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(RENDER.ExternalEvaluationError, match="schema"):
        RENDER.load_inputs(path)


def test_listener_index_is_unselected_and_has_three_arms() -> None:
    item = {
        "age": "twenties",
        "gender": "female_feminine",
        "text": "短い文",
    }

    index = RENDER.listening_index(
        item,
        hashes={
            "base": "a" * 64,
            "human87-control69-e12": "b" * 64,
            "jvs3-generated-pairs": "c" * 64,
        },
    )

    assert index["status"] == "completed-listen-now-unselected"
    assert len(index["variants"]) == 3
