from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_expanded_stress_matrix.py"
SPEC = importlib.util.spec_from_file_location(
    "xvc_prepare_expanded_stress_matrix", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MATRIX = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MATRIX
SPEC.loader.exec_module(MATRIX)


def _fresh48() -> dict[str, object]:
    lengths = (
        list(range(10, 15)) * 2
        + [10, 11]
        + list(range(15, 22))
        + [15, 16, 17, 18, 19]
        + list(range(22, 31))
        + [22, 23, 24]
        + list(range(40, 52))
    )
    assert len(lengths) == 48
    return {
        "kind": MATRIX.render_new.FRESH48_KIND,
        "items": [
            {
                "id": f"row{index:02d}",
                "filename": f"row{index:02d}.mp3",
                "client_id_sha256": f"{index + 1:064x}",
                "sha256": f"{index + 101:064x}",
                "text": f"text {index}",
                "source_normalized_characters": length,
                "duration_seconds": 3.0,
            }
            for index, length in enumerate(lengths)
        ],
    }


def test_selection_balances_four_text_lengths_and_unique_speakers() -> None:
    selected = MATRIX.selected_sources(_fresh48())

    assert len(selected) == 16
    assert len({row["id"] for row in selected}) == 16
    assert len({row["client_id_sha256"] for row in selected}) == 16
    assert Counter(row["length_bin"] for row in selected) == {
        "short10to14": 4,
        "medium15to21": 4,
        "long22to30": 4,
        "verylong40plus": 4,
    }


def test_plan_crosses_sixteen_sources_with_nine_symmetric_conditions() -> None:
    rows = MATRIX.planned_rows(_fresh48())

    assert len(rows) == 144
    assert len({row["id"] for row in rows}) == 144
    assert set(Counter(row["group"] for row in rows).values()) == {4}
    assert len({row["group"] for row in rows}) == 36
    assert set(Counter(row["base_id"] for row in rows).values()) == {9}
    transforms = {name: value for name, value in MATRIX.CONDITIONS}
    assert transforms["noise30"] == {"kind": "noise", "snr_db": 30.0}
    assert transforms["noise10"] == {"kind": "noise", "snr_db": 10.0}
    assert transforms["tempo080"]["factor"] == 0.8
    assert transforms["tempo120"]["factor"] == 1.2
    assert transforms["pitchn3"]["factor"] < 1.0
    assert transforms["pitchp3"]["factor"] > 1.0


def test_selection_rejects_a_length_bin_with_fewer_than_four_sources() -> None:
    source = _fresh48()
    source["items"] = [
        row
        for row in source["items"]
        if not (
            row["source_normalized_characters"] >= 40
            and row["id"] not in {"row36", "row37", "row38"}
        )
    ]

    with pytest.raises(MATRIX.ExpandedStressError, match="too few"):
        MATRIX.selected_sources(source)
