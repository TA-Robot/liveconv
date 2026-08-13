from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "prepare_clean_post_rehearsal.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_clean_post_rehearsal", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _row(index: int, *, distance: float = 0.1, gross: bool = False) -> dict:
    if index < 35:
        domain = "commonvoice"
    elif index < 167:
        domain = "hadou"
    else:
        domain = "jvs"
    return {
        "teacher_id": f"teacher-{index:03d}",
        "target_id": f"target-{index:03d}",
        "domain": domain,
        "source_relative_distance": distance,
        "repetition": {"gross_repetition": gross},
    }


def test_admission_keeps_unique_clean_rows_below_fixed_half_distance() -> None:
    rows = [_row(index) for index in range(170)]
    rows.extend(
        [
            {**_row(0), "target_id": "duplicate-target"},
            _row(170, distance=0.5),
            _row(171, gross=True),
        ]
    )
    while len(rows) < 209:
        rows.append(_row(len(rows), distance=1.0))
    screen = {
        "kind": MODULE.SCREEN_KIND,
        "teacher_manifest_sha256": MODULE.TEACHER_MANIFEST_SHA256,
        "rows": rows,
    }

    admitted = MODULE.admitted_rows(screen)

    assert len(admitted) == 170
    assert len({row["teacher_id"] for row in admitted}) == 170
    assert all(row["source_relative_distance"] < 0.5 for row in admitted)
