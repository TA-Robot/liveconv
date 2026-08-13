from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "prepare_hadou_evaluation.py"
SPEC = importlib.util.spec_from_file_location("prepare_hadou_evaluation", MODULE_PATH)
assert SPEC and SPEC.loader
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def test_frozen_hadou_selection_rederives_exactly():
    selection = json.loads(
        Path(
            "experiments/EXP-060-xvc-filtered-pairs-hadou-evaluation/"
            "hadou-evaluation.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        Path("artifacts/xvc-human-paired/runrun-human-paired.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        Path(
            "artifacts/xvc-human-paired/audit/hadou-runrun/"
            "pronunciation-triage-2f35e75f.json"
        ).read_text(encoding="utf-8")
    )

    assert len(PREPARE.select_rows(selection, manifest, audit)) == 31


def test_hadou_selection_rejects_posthoc_id_change():
    selection = {"kind": PREPARE.SELECTION_KIND, "ids": ["wrong"] * 31}

    with pytest.raises(PREPARE.HadouPreparationError, match="digest"):
        PREPARE.select_rows(selection, {"rows": []}, {"rows": []})
