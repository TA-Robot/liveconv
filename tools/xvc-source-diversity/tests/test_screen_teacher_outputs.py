from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "screen_teacher_outputs.py"
SPEC = importlib.util.spec_from_file_location("xvc_teacher_screen", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TEACHER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TEACHER
SPEC.loader.exec_module(TEACHER)


def test_discover_outputs_requires_balanced_complete_pool(tmp_path: Path) -> None:
    root = tmp_path / "outputs"
    for target, teacher in (("t1", "a"), ("t2", "b"), ("t3", "a"), ("t4", "b")):
        path = root / target / f"teacher-output-{teacher}-16k.wav"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"wav")

    rows = TEACHER.discover_outputs(root, {"a": {}, "b": {}})

    assert [(target, teacher) for target, teacher, _ in rows] == [
        ("t1", "a"),
        ("t2", "b"),
        ("t3", "a"),
        ("t4", "b"),
    ]


def test_aggregate_keeps_domain_and_macro_failure_counts() -> None:
    rows = [
        {
            "domain": "cv",
            "source_relative_distance": 0.2,
            "repetition": {"gross_repetition": False},
        },
        {
            "domain": "cv",
            "source_relative_distance": 0.8,
            "repetition": {"gross_repetition": True},
        },
        {
            "domain": "hadou",
            "source_relative_distance": 0.4,
            "repetition": {"gross_repetition": False},
        },
    ]

    value = TEACHER.aggregate(rows)

    assert value["cv"]["mean_source_relative_distance"] == 0.5
    assert value["cv"]["distance_at_least_half_rows"] == 1
    assert value["macro"]["gross_repetition_rows"] == 1
