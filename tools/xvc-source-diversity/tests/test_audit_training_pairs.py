from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "audit_training_pairs.py"
SPEC = importlib.util.spec_from_file_location("audit_training_pairs", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _row(pair_id: str, donor_id: str, distance: float, *, empty=False, gross=False):
    return {
        "pair_id": pair_id,
        "donor_id": donor_id,
        "target_normalized_characters": 10,
        "output_normalized_characters": 0 if empty else 10,
        "target_relative_distance": distance,
        "repetition": {"gross_repetition": gross},
    }


def test_rank_rows_selects_best_non_corrupt_half_and_two_passes(monkeypatch):
    monkeypatch.setattr(AUDIT, "TOTAL_UPDATES", 8)
    rows = [
        _row(pair_id, donor_id, distance)
        for pair_id in ("a", "b")
        for donor_id, distance in (
            ("d1", 0.4),
            ("d2", 0.1),
            ("d3", 0.2),
            ("d4", 0.3),
        )
    ]
    ranked, schedule = AUDIT.rank_rows(
        rows, keep_per_target=2, expected_targets=2
    )

    assert [(row["pair_id"], row["donor_id"]) for row in ranked if row["selected"]] == [
        ("a", "d2"),
        ("a", "d3"),
        ("b", "d2"),
        ("b", "d3"),
    ]
    assert schedule == [
        ("a", "d2"),
        ("a", "d3"),
        ("b", "d2"),
        ("b", "d3"),
    ] * 2


def test_rank_rows_rejects_target_with_too_few_eligible(monkeypatch):
    monkeypatch.setattr(AUDIT, "TOTAL_UPDATES", 4)
    rows = [
        _row("a", "d1", 0.0),
        _row("a", "d2", 0.1, empty=True),
        _row("a", "d3", 0.2, gross=True),
    ]

    with pytest.raises(AUDIT.TrainingPairAuditError, match="fewer than 2"):
        AUDIT.rank_rows(rows, keep_per_target=2, expected_targets=1)


def test_load_donor_ids_preserves_manifest_order(tmp_path):
    manifest = tmp_path / "donors.json"
    manifest.write_text(
        '{"items":[{"id":"z"},{"id":"a"}]}\n', encoding="utf-8"
    )

    assert AUDIT.load_donor_ids(manifest, expected_count=2) == ["z", "a"]
