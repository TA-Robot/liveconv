from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_exp319_cv26_targets as render  # noqa: E402


def _digest(number: int) -> str:
    return f"{number:064x}"


def _base() -> dict[str, object]:
    cv_positions = set(render.REPLACEMENT_POSITIONS) | {14, 31, 52, 78, 80, 91}
    cv_positions.update(range(104, 120))
    domains: list[str] = []
    jsut_seen = jvs_seen = hadou_seen = 0
    for index in range(render.EXPECTED_ROWS):
        if index in cv_positions:
            domains.append("commonvoice-unpaired")
        elif jsut_seen < 85:
            domains.append("jsut-unpaired")
            jsut_seen += 1
        elif jvs_seen < 3:
            domains.append("jvs-unpaired")
            jvs_seen += 1
        else:
            domains.append("hadou-unpaired")
            hadou_seen += 1
    rows: list[dict[str, object]] = []
    for index, domain in enumerate(domains):
        rows.append(
            {
                "id": f"base-{index:03d}",
                "teacher_id": f"teacher-{index:03d}",
                "domain": domain,
                "source_root": "source-work",
                "source_file": f"sources/{index:03d}.wav",
                "source_sha256": _digest(index + 1),
                "source_text": f"元文{index}",
                "target_root": "diverse-work",
                "target_file": f"control-outputs/{index:03d}.wav",
                "target_sha256": _digest(index + 101),
                "target_id": f"target-{index:03d}",
                "target_text": f"元文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:03d}.wav",
                "real_target_sha256": _digest(index + 201),
                "real_target_text": f"Amitaro文{index}",
                "learning_target": render.LEARNING_TARGET,
            }
        )
    return {
        "kind": render.EXP238_KIND,
        "composition": render.BASE_COMPOSITION,
        "items": rows,
    }


def _pool(base: dict[str, object]) -> dict[str, object]:
    base_items = base["items"]
    assert isinstance(base_items, list)
    rows: list[dict[str, object]] = []
    for index, position in enumerate(render.REPLACEMENT_POSITIONS):
        old = base_items[position]
        assert isinstance(old, dict)
        row = dict(old)
        row.update(
            {
                "id": f"active-{index:02d}",
                "teacher_id": f"active-teacher-{index:02d}",
                "source_manifest_id": f"EXP055:cv-active-{index:02d}",
                "source_file": f"active-sources/{index:02d}-active.wav",
                "source_sha256": _digest(5000 + index),
                "source_text": f"アクティブ文{index}",
                "source_client_id_sha256": _digest(6000 + index),
                "source_original_sha256": _digest(7000 + index),
                "curriculum_position": position,
                "target_text": f"アクティブ文{index}",
            }
        )
        rows.append(row)
    return {
        "kind": render.POOL_KIND,
        "composition": {"commonvoice-unpaired": render.EXPECTED_NEW_ROWS},
        "items": rows,
    }


def _rendered(pool: dict[str, object]) -> list[dict[str, object]]:
    rows = pool["items"]
    assert isinstance(rows, list)
    return [
        {
            "position": row["curriculum_position"],
            "teacher_id": row["teacher_id"],
            "target_id": row["target_id"],
            "target_file": (
                f"control-outputs/cv26-{row['curriculum_position']:03d}-fresh.wav"
            ),
            "output_sha256": _digest(8000 + index),
        }
        for index, row in enumerate(rows)
    ]


def test_build_replaces_absolute_positions_and_keeps_other_rows_exactly() -> None:
    base = _base()
    pool = render.source_pool(_pool(base))
    result = render._build_curriculum(base, pool, _rendered(pool))

    assert result["kind"] == render.OUTPUT_KIND
    assert len(result["items"]) == render.EXPECTED_ROWS
    assert result["composition"] == render.BASE_COMPOSITION
    base_items = base["items"]
    output_items = result["items"]
    assert isinstance(base_items, list)
    assert isinstance(output_items, list)
    replaced = set(render.REPLACEMENT_POSITIONS)
    for position, (before, after) in enumerate(zip(base_items, output_items, strict=True)):
        if position not in replaced:
            assert after == before
        else:
            assert after["id"] == f"active-{render.REPLACEMENT_POSITIONS.index(position):02d}"
            assert after["target_id"] == before["target_id"]
            assert after["real_target_file"] == before["real_target_file"]
            assert after["real_target_sha256"] == before["real_target_sha256"]
            assert after["real_target_text"] == before["real_target_text"]
            assert after["target_text"].startswith("アクティブ文")


def test_pool_rejects_position_or_position_specific_target_drift() -> None:
    base = _base()
    value = _pool(base)
    value["items"][0]["curriculum_position"] = 0
    with pytest.raises(render.Cv26RenderError, match="position"):
        render.source_pool(value)

    value = _pool(base)
    value["items"][0]["target_id"] = "wrong-target"
    pool = render.source_pool(value)
    with pytest.raises(render.Cv26RenderError, match="target"):
        render._build_curriculum(base, pool, _rendered(pool))


def test_pool_rejects_wrong_kind_and_unsafe_source_path() -> None:
    base = _base()
    value = _pool(base)
    value["kind"] = "wrong"
    with pytest.raises(render.Cv26RenderError, match="identity"):
        render.source_pool(value)

    value = _pool(base)
    value["items"][0]["source_file"] = "../escape.wav"
    with pytest.raises(render.Cv26RenderError, match="escapes"):
        render.source_pool(value)


def test_create_output_root_is_bounded(tmp_path: Path) -> None:
    output = tmp_path / "diverse-work"
    control = render._create_output_root(output)
    assert control == output / "control-outputs"
    assert control.is_dir()
