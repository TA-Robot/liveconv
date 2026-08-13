from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_phonetic_teacher.py"
SPEC = importlib.util.spec_from_file_location("xvc_phonetic_teacher", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREPARE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREPARE
SPEC.loader.exec_module(PREPARE)


def test_hadou_selection_is_quality_filtered_length_balanced_and_disjoint() -> None:
    rows = []
    audits = []
    kana = "アイウエオカキクケコサシスセソタチツテトナニヌネノ"
    for index in range(36):
        identifier = f"ROW_{index:02d}"
        rows.append(
            {
                "utterance_id": identifier,
                "split": "train",
                "reading_katakana": kana[: 4 + index % 25] + str(index),
            }
        )
        audits.append(
            {
                "utterance_id": identifier,
                "comparison": {
                    "best": {"character_error_rate": 0.2 if index == 1 else 0.1}
                },
            }
        )

    selected = PREPARE.select_hadou(
        rows, audits, excluded_ids={"ROW_00"}
    )

    assert len(selected) == 21
    assert "ROW_00" not in {row["utterance_id"] for row in selected}
    assert "ROW_01" not in {row["utterance_id"] for row in selected}
    assert Counter(row["_selection_bin"] for row in selected) == {
        "short": 7,
        "medium": 7,
        "long": 7,
    }
    assert max(row["_audit_cer"] for row in selected) <= 0.15


def test_kana_ngrams_keep_width_identity() -> None:
    assert PREPARE.ngrams("アイウ") == {
        "1:ア",
        "1:イ",
        "1:ウ",
        "2:アイ",
        "2:イウ",
        "3:アイウ",
    }
