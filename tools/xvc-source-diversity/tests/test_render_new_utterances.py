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
