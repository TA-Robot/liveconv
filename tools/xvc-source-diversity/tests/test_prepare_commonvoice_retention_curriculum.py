from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_commonvoice_retention_curriculum as curriculum  # noqa: E402


def inputs() -> tuple[dict, dict, dict, dict]:
    selective_items = []
    sources = []
    targets = []
    screens = []
    for position in range(170):
        hard = position % 2 == 0
        target_id = f"target-{position % 74}"
        selective_items.append(
            {
                "id": f"old-{position}",
                "curriculum_role": "hard" if hard else "easy",
                "learning_target": (
                    curriculum.REPAIR_TARGET if hard else curriculum.RETENTION_TARGET
                ),
                "domain": "commonvoice" if position < 80 else "hadou",
                "source_manifest_id": f"old-source-{position}",
                "source_file": f"source-{position}.wav",
                "source_sha256": "a" * 64,
                "source_relative_distance": 0.1,
                "teacher_id": f"old-teacher-{position}",
                "target_id": target_id,
                "target_root": "source-work",
                "target_file": f"target-{position}.wav",
                "target_sha256": "b" * 64,
            }
        )
        if not hard:
            easy_index = position // 2
            source_index = easy_index if easy_index < 48 else easy_index - 48
            exposure = 1 if easy_index < 48 else 2
            source_id = f"cv{source_index:08d}f"
            teacher_id = f"{source_id}-e{exposure}"
            sources.append(
                {
                    "id": teacher_id,
                    "source_id": source_id,
                    "exposure": exposure,
                    "client_id_sha256": f"{source_index:064x}",
                    "curriculum_position": position,
                    "source_transcript": f"評価文{position}",
                }
            )
            targets.append(
                {
                    "teacher_id": teacher_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "curriculum_position": position,
                    "model_source_sha256": "c" * 64,
                    "output_sha256": "d" * 64,
                }
            )
            screens.append(
                {
                    "teacher_id": teacher_id,
                    "target_id": target_id,
                    "domain": "commonvoice",
                    "output_transcript": f"出力{position}",
                    "source_relative_distance": 0.6,
                    "repetition": {"gross_repetition": False},
                }
            )
    selective = {"kind": curriculum.SELECTIVE_KIND, "items": selective_items}
    sources_value = {"kind": curriculum.SOURCE_KIND, "items": sources}
    result = {"kind": curriculum.TARGET_KIND, "rows": targets}
    screen = {"kind": curriculum.SCREEN_KIND, "rows": screens}
    return selective, sources_value, result, screen


def test_build_changes_only_easy_rows_to_speaker_balanced_roots() -> None:
    manifest = curriculum.build_curriculum(*inputs())

    assert len(manifest["items"]) == 170
    assert manifest["composition"] == curriculum.EXPECTED_COMPOSITION
    assert manifest["learning_target_counts"] == curriculum.EXPECTED_TARGET_COUNTS
    assert manifest["curriculum"]["easy_unique_speakers"] == 48
    assert all(
        row.get("source_root") == "source-work"
        for row in manifest["items"]
        if row["curriculum_role"] == "hard"
    )
    easy = [
        row for row in manifest["items"] if row["curriculum_role"] == "easy"
    ]
    assert len({row["source_speaker_id_sha256"] for row in easy}) == 48
    assert all(
        row["source_root"] == row["target_root"] == "diverse-work" for row in easy
    )
