from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_fresh_commonvoice.py"
SPEC = importlib.util.spec_from_file_location("prepare_fresh_commonvoice", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREPARE
SPEC.loader.exec_module(PREPARE)


def row(index: int, client: str, *, down_votes: int = 0) -> dict[str, object]:
    return {
        "file_name": f"common_voice_ja_{index:08d}.mp3",
        "text": f"これは十分な長さを持つ新しい評価文章その{index}です",
        "client_id": client,
        "up_votes": 2,
        "down_votes": down_votes,
        "age": "",
        "gender": "",
        "locale": "ja",
    }


def test_select_rows_excludes_existing_clients_and_keeps_unique_speakers() -> None:
    rows = [
        row(1, "existing"),
        row(2, "existing"),
        row(3, "rejected", down_votes=1),
        row(4, "fresh-a"),
        row(5, "fresh-a"),
        row(6, "fresh-b"),
    ]

    selected = PREPARE.select_rows(
        rows,
        existing_filenames={"common_voice_ja_00000001.mp3"},
        count=2,
    )

    assert [item["file_name"] for item in selected] == [
        "common_voice_ja_00000004.mp3",
        "common_voice_ja_00000006.mp3",
    ]


def test_select_rows_fails_when_fresh_count_is_short() -> None:
    with pytest.raises(PREPARE.FreshEvaluationError, match="not enough"):
        PREPARE.select_rows([row(1, "only")], existing_filenames=set(), count=2)
