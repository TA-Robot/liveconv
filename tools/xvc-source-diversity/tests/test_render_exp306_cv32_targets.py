from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_exp305_exp306_cv32 as prep  # noqa: E402
import render_exp306_cv32_targets as render  # noqa: E402


def _digest(number: int) -> str:
    return f"{number:064x}"


def test_render_creates_control_output_directory(tmp_path: Path) -> None:
    output_root = tmp_path / "render"
    assert render._create_output_root(output_root) == output_root / "control-outputs"
    assert (output_root / "control-outputs").is_dir()


def _pool() -> dict[str, object]:
    rows = []
    for index in range(32):
        rows.append(
            {
                "position": index,
                "id": f"cv32-{index:02d}-cv-{index:02d}--target-{index}",
                "teacher_id": f"commonvoice-cv32-{index:02d}",
                "domain": "commonvoice-unpaired",
                "source_root": "source-work",
                "source_file": f"new-sources/{index:02d}.wav",
                "source_sha256": _digest(index + 1),
                "source_text": f"新文{index}",
                "target_id": f"target-{index}",
                "target_text": f"旧文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:02d}.wav",
                "real_target_sha256": _digest(index + 100),
                "learning_target": render.LEARNING_TARGET,
            }
        )
    return {
        "kind": render.BREADTH_POOL_KIND,
        "composition": {"commonvoice-unpaired": 32},
        "items": rows,
    }


def _base() -> dict[str, object]:
    rows = []
    domains = (
        ["commonvoice-unpaired"] * 48
        + ["jsut-unpaired"] * 85
        + ["jvs-unpaired"] * 3
        + ["hadou-unpaired"] * 34
    )
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
                "target_text": f"元文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:03d}.wav",
                "real_target_sha256": _digest(index + 201),
                "learning_target": render.LEARNING_TARGET,
            }
        )
    return {
        "kind": render.EXP238_KIND,
        "composition": render.BASE_COMPOSITION,
        "items": rows,
    }


def _rendered() -> list[dict[str, object]]:
    return [
        {
            "position": index,
            "teacher_id": f"commonvoice-cv32-{index:02d}",
            "target_id": f"target-{index}",
            "target_file": f"control-outputs/cv32-{index:02d}.wav",
            "output_sha256": _digest(index + 500),
        }
        for index in range(32)
    ]


def test_pool_accepts_exact_order_and_curriculum_keeps_base_rows() -> None:
    pool = render.source_pool(_pool())
    result = render._build_curriculum(_base(), pool, _rendered())
    assert result["kind"] == render.BREADTH_OUTPUT_KIND
    assert len(result["items"]) == 202
    assert result["composition"] == prep.EXPECTED_COMPOSITION
    assert result["items"][170]["target_text"] == result["items"][170]["source_text"]
    assert result["items"][170]["real_target_text"] == "旧文0"
    assert result["items"][0]["target_file"] == "control-outputs/000.wav"


def test_pool_rejects_position_or_target_drift() -> None:
    value = _pool()
    value["items"][0]["position"] = 1
    with pytest.raises(render.Cv32RenderError, match="order"):
        render.source_pool(value)
    value = _pool()
    rendered = _rendered()
    rendered[0]["target_id"] = "wrong"
    with pytest.raises(render.Cv32RenderError, match="identity"):
        render._build_curriculum(_base(), render.source_pool(value), rendered)


def test_pool_rejects_unsafe_paths_and_wrong_kind() -> None:
    value = _pool()
    value["kind"] = prep.REPEAT_OUTPUT_KIND
    with pytest.raises(render.Cv32RenderError, match="identity"):
        render.source_pool(value)
    value = _pool()
    value["items"][0]["source_file"] = "../escape.wav"
    with pytest.raises(render.Cv32RenderError, match="escapes"):
        render.source_pool(value)
