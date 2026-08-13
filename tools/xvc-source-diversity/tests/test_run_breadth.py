from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_breadth.py"
SPEC = importlib.util.spec_from_file_location("xvc_run_breadth", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BREADTH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BREADTH
SPEC.loader.exec_module(BREADTH)


def _manifest(kind: str, count: int) -> dict[str, object]:
    return {
        "kind": kind,
        "source": {"license": "CC0-1.0"},
        "items": [
            {
                "id": f"speaker-{index}",
                "filename": f"speaker-{index}.mp3",
                "sha256": f"{index + 1:064x}",
                "client_id_sha256": f"{index + 101:064x}",
                "text": f"known text {index}",
                "source_transcript": f"known text {index}",
                "known_text_distance": 0.0,
            }
            for index in range(count)
        ],
    }


def test_breadth_schedule_has_one_exposure_per_distinct_donor() -> None:
    targets = [f"target-{index}" for index in range(BREADTH.method.PAIR_COUNT)]
    donors = [f"donor-{index}" for index in range(BREADTH.DONOR_COUNT)]

    schedule = BREADTH.training_schedule(targets, donors)

    assert len(schedule) == 1_044
    assert schedule[:12] == [("target-0", donor) for donor in donors]
    assert len(set(schedule)) == 1_044


def test_manifest_rejects_source_above_admission_distance(tmp_path: Path) -> None:
    value = _manifest(BREADTH.DONOR_KIND, BREADTH.DONOR_COUNT)
    value["items"][0]["known_text_distance"] = 0.376
    path = tmp_path / "donors.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BREADTH.BreadthError, match="identity"):
        BREADTH._load_manifest(
            path, kind=BREADTH.DONOR_KIND, count=BREADTH.DONOR_COUNT
        )
