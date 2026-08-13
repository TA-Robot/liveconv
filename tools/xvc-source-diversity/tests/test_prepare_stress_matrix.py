from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_stress_matrix.py"
SPEC = importlib.util.spec_from_file_location("xvc_prepare_stress_matrix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MATRIX = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MATRIX
SPEC.loader.exec_module(MATRIX)


def test_planned_rows_cross_twelve_sources_with_five_conditions() -> None:
    source = {
        "items": [
            {
                "id": f"row{index:02d}",
                "filename": f"row{index:02d}.mp3",
                "client_id_sha256": f"{index:064x}",
                "sha256": f"{index + 20:064x}",
                "text": f"text {index}",
                "duration_seconds": 3.0,
            }
            for index in range(12)
        ]
    }

    rows = MATRIX.planned_rows(source)

    assert len(rows) == 60
    assert len({row["id"] for row in rows}) == 60
    assert Counter(row["group"] for row in rows) == {
        "stress-clean": 12,
        "stress-noise20": 12,
        "stress-silence300": 12,
        "stress-tempo120": 12,
        "stress-pitchp3": 12,
    }
    assert [row["base_id"] for row in rows[:5]] == ["row00"] * 5
    assert rows[1]["stress_condition"] == {"kind": "noise", "snr_db": 20.0}
