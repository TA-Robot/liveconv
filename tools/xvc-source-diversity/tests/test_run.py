from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run.py"
SPEC = importlib.util.spec_from_file_location("xvc_source_diversity_run", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUN
SPEC.loader.exec_module(RUN)


def _evaluation() -> dict[str, object]:
    groups = [
        "clean-cross-speaker",
        "clean-cross-speaker",
        "clean-cross-speaker",
        "clean-cross-speaker",
        "clean-cross-speaker",
        "clean-cross-speaker",
        "tempo",
        "pitch",
        "noise",
        "leading-silence",
    ]
    transforms = ["clean"] * 6 + ["tempo", "pitch", "noise", "leading-silence"]
    return {
        "kind": RUN.KIND,
        "items": [
            {
                "id": f"row-{index}",
                "group": group,
                "source_set": "jvs",
                "filename": "jvs001.wav",
                "sha256": "a" * 64,
                "corpus": "JVS",
                "label": f"row {index}",
                "transform": {"kind": transform},
            }
            for index, (group, transform) in enumerate(
                zip(groups, transforms, strict=True)
            )
        ],
    }


def test_evaluation_set_requires_all_fixed_groups(tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(_evaluation()), encoding="utf-8")

    loaded = RUN.load_evaluation_set(path)

    assert len(loaded["items"]) == 10


def test_evaluation_set_rejects_collapsing_to_clean_only(tmp_path: Path) -> None:
    value = _evaluation()
    value["items"][-1]["group"] = "clean-cross-speaker"
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(RUN.SourceDiversityError, match="coverage"):
        RUN.load_evaluation_set(path)


def test_training_schedule_matches_old_target_exposure_and_updates() -> None:
    pair_ids = [f"pair-{index:02d}" for index in range(87)]

    schedule = RUN.training_schedule(pair_ids, ["jvs001", "jvs002", "jvs003"])

    assert len(schedule) == 1044
    for pair_id in pair_ids:
        assert sum(item[0] == pair_id for item in schedule) == 12
    assert schedule[:3] == [
        ("pair-00", "jvs001"),
        ("pair-00", "jvs002"),
        ("pair-00", "jvs003"),
    ]


def test_listening_index_never_claims_a_winner() -> None:
    source = RUN.base.RenderSource(Path("x").name, "JVS / noise / 20 dB", Path("x.wav"))

    index = RUN.listening_index(
        source,
        target_reference_id="EMOTION100_003",
        hashes={
            "base": "a" * 64,
            "human87-control69-e12": "b" * 64,
            "jvs3-generated-pairs": "c" * 64,
        },
    )

    assert index["status"] == "completed-listen-now-unselected"
    assert [item["variant_id"] for item in index["variants"]] == [
        "base",
        "human87-control69-e12",
        "jvs3-generated-pairs",
    ]
