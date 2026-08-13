from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_teacher_commonvoice.py"
SPEC = importlib.util.spec_from_file_location(
    "prepare_teacher_commonvoice", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
TEACHER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TEACHER
SPEC.loader.exec_module(TEACHER)


def test_excluded_clients_requires_frozen_fresh48(tmp_path: Path) -> None:
    path = tmp_path / "fresh.json"
    path.write_text(
        json.dumps(
            {
                "kind": TEACHER.FRESH_KIND,
                "items": [
                    {"client_id_sha256": f"{index + 1:064x}"}
                    for index in range(48)
                ],
            }
        ),
        encoding="utf-8",
    )

    assert len(TEACHER.excluded_clients(path)) == 48


def test_excluded_clients_rejects_short_manifest(tmp_path: Path) -> None:
    path = tmp_path / "fresh.json"
    path.write_text(
        json.dumps(
            {
                "kind": TEACHER.FRESH_KIND,
                "items": [{"client_id_sha256": "1" * 64}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TEACHER.common.FreshEvaluationError, match="drifted"):
        TEACHER.excluded_clients(path)
