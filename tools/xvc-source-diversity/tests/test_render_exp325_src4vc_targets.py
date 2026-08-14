from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import render_exp325_src4vc_targets as render  # noqa: E402


def _digest(number: int) -> str:
    return f"{number:064x}"


def _base() -> dict[str, object]:
    domains = (
        ["commonvoice-unpaired"] * 48
        + ["jsut-unpaired"] * 85
        + ["jvs-unpaired"] * 3
        + ["hadou-unpaired"] * 34
    )
    rows: list[dict[str, object]] = []
    for index, domain in enumerate(domains):
        rows.append(
            {
                "id": f"base-{index:03d}",
                "teacher_id": f"teacher-{index:03d}",
                "domain": domain,
                "source_root": "source-work",
                "source_file": f"base-sources/{index:03d}.wav",
                "source_sha256": _digest(index + 1),
                "source_text": f"元文{index}",
                "target_root": "diverse-work",
                "target_file": f"base-teachers/{index:03d}.wav",
                "target_sha256": _digest(index + 101),
                "target_id": f"target-{index:03d}",
                "target_text": f"元文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"real-targets/{index:03d}.wav",
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
    base_rows = base["items"]
    assert isinstance(base_rows, list)
    rows: list[dict[str, object]] = []
    for position in range(render.EXPECTED_ROWS):
        reference = base_rows[position]
        assert isinstance(reference, dict)
        speaker_index = position // 2
        utterance_index = position % 2
        rows.append(
            {
                "position": position,
                "id": f"src4vc-{speaker_index:03d}-{utterance_index}",
                "teacher_id": f"src4vc-teacher-{speaker_index:03d}-{utterance_index}",
                "domain": "src4vc-smartphone-unpaired",
                "source_root": "source-work",
                "source_file": f"sources/{position:03d}.wav",
                "source_sha256": _digest(1000 + position),
                "source_text": f"SRC4VC文{position}",
                "source_speaker_id": f"SRC4VC{speaker_index:03d}",
                "source_utterance_index": utterance_index,
                "target_id": reference["target_id"],
                "target_text": f"SRC4VC文{position}",
                "real_target_root": reference["real_target_root"],
                "real_target_file": reference["real_target_file"],
                "real_target_sha256": reference["real_target_sha256"],
                "real_target_text": reference["real_target_text"],
                "learning_target": render.LEARNING_TARGET,
            }
        )
    return {
        "kind": render.POOL_KIND,
        "composition": {"src4vc-smartphone-unpaired": render.EXPECTED_ROWS},
        "items": rows,
    }


def _rendered(pool: dict[str, object]) -> list[dict[str, object]]:
    rows = pool["items"]
    assert isinstance(rows, list)
    return [
        {
            "position": index,
            "teacher_id": row["teacher_id"],
            "target_id": row["target_id"],
            "target_file": f"control-outputs/{index:03d}.wav",
            "output_sha256": _digest(5000 + index),
        }
        for index, row in enumerate(rows)
    ]


def test_build_curriculum_preserves_source_identity_and_target_order() -> None:
    base = _base()
    pool = render.source_pool(_pool(base))
    result = render._build_curriculum(base, pool, _rendered(pool))

    assert result["kind"] == render.OUTPUT_KIND
    assert result["composition"] == {"src4vc-smartphone-unpaired": 170}
    rows = result["items"]
    assert isinstance(rows, list)
    assert len(rows) == render.EXPECTED_ROWS
    assert [(row["source_speaker_id"], row["source_utterance_index"]) for row in rows] == [
        (f"SRC4VC{index // 2:03d}", index % 2) for index in range(170)
    ]
    assert all(row["target_text"] == row["source_text"] for row in rows)
    assert all(row["target_root"] == "diverse-work" for row in rows)
    assert all(row["source_relative_distance"] == 0.0 for row in rows)
    assert all("target_file" in row and "target_sha256" in row for row in rows)
    assert [row["target_id"] for row in rows] == [
        f"target-{index:03d}" for index in range(170)
    ]


def test_pool_is_preteacher_and_real_boundary_is_checked() -> None:
    base = _base()
    value = _pool(base)
    assert all(
        not any(key in row for key in ("target_root", "target_file", "target_sha256"))
        for row in value["items"]
    )
    pool = render.source_pool(value)
    assert "target_root" not in pool["items"][0]

    value["items"][0]["target_text"] = "別内容"
    with pytest.raises(render.Src4vcRenderError, match="contract"):
        render.source_pool(value)

    value = _pool(base)
    value["items"][0]["real_target_text"] = "別の実ターゲット"
    pool = render.source_pool(value)
    with pytest.raises(render.Src4vcRenderError, match="real target text"):
        render._build_curriculum(base, pool, _rendered(pool))


def test_pool_rejects_missing_second_utterance_or_duplicate_speaker() -> None:
    base = _base()
    value = _pool(base)
    value["items"][1]["source_utterance_index"] = 0
    with pytest.raises(render.Src4vcRenderError, match="utterance"):
        render.source_pool(value)

    value = _pool(base)
    value["items"][2]["source_speaker_id"] = value["items"][0]["source_speaker_id"]
    with pytest.raises(render.Src4vcRenderError, match="speaker"):
        render.source_pool(value)


def test_pool_rejects_order_or_unsafe_source_path() -> None:
    base = _base()
    value = _pool(base)
    value["items"][0]["position"] = 1
    with pytest.raises(render.Src4vcRenderError, match="order"):
        render.source_pool(value)

    value = _pool(base)
    value["items"][0]["source_file"] = "../escape.wav"
    with pytest.raises(render.Src4vcRenderError, match="escapes"):
        render.source_pool(value)


def test_validate_inputs_checks_source_and_real_target_hashes(tmp_path: Path) -> None:
    base = _base()
    pool_value = _pool(base)
    source_work = tmp_path / "source-work"
    source_work.mkdir()
    pool_rows = pool_value["items"]
    assert isinstance(pool_rows, list)
    for index, row in enumerate(pool_rows):
        source = source_work / str(row["source_file"])
        target = source_work / str(row["real_target_file"])
        source.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"source-{index}".encode())
        target.write_bytes(f"target-{index}".encode())
        row["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        row["real_target_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        base_rows = base["items"]
        assert isinstance(base_rows, list)
        base_rows[index]["real_target_sha256"] = row["real_target_sha256"]
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(b"adapter")
    pool_path = tmp_path / "pool.json"
    base_path = tmp_path / "exp238.json"
    pool_path.write_text(json.dumps(pool_value), encoding="utf-8")
    base_path.write_text(json.dumps(base), encoding="utf-8")
    arguments = render.parser().parse_args(
        [
            "--check",
            "--pool",
            str(pool_path),
            "--source-work",
            str(source_work),
            "--exp238-curriculum",
            str(base_path),
            "--output-diverse-work",
            str(tmp_path / "output"),
            "--control-adapter",
            str(adapter),
            "--xvc-source-root",
            str(tmp_path / "xvc"),
            "--xvc-config",
            str(tmp_path / "config"),
            "--checkpoint",
            str(tmp_path / "checkpoint"),
        ]
    )
    pool, exp238 = render.validate_inputs(arguments)
    assert len(pool["items"]) == render.EXPECTED_ROWS
    assert len(exp238["items"]) == render.EXPECTED_ROWS

    pool_rows[0]["source_sha256"] = _digest(9999)
    pool_path.write_text(json.dumps(pool_value), encoding="utf-8")
    with pytest.raises(render.Src4vcRenderError, match="hash"):
        render.validate_inputs(arguments)


def test_create_output_root_refuses_existing_path(tmp_path: Path) -> None:
    output = tmp_path / "diverse-work"
    control = render._create_output_root(output)
    assert control == output / "control-outputs"
    assert control.is_dir()
    with pytest.raises(render.Src4vcRenderError, match="already exists"):
        render._create_output_root(output)


def test_existing_output_rows_requires_exact_unfinalized_inventory(tmp_path: Path) -> None:
    base = _base()
    pool = render.source_pool(_pool(base))
    output = tmp_path / "diverse-work"
    control = output / "control-outputs"
    control.mkdir(parents=True)
    for position, item in enumerate(pool["items"]):
        path = render._output_path(output, position, item)
        path.write_bytes(f"teacher-{position}".encode())

    rows = render._existing_output_rows(output, pool)
    assert len(rows) == render.EXPECTED_ROWS
    assert rows[0]["teacher_id"] == pool["items"][0]["teacher_id"]
    assert rows[-1]["target_file"].startswith("control-outputs/")
    assert all(render._is_sha256(row["output_sha256"]) for row in rows)

    (control / "unexpected.wav").write_bytes(b"unexpected")
    with pytest.raises(render.Src4vcRenderError, match="inventory"):
        render._existing_output_rows(output, pool)
