from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_exp317_cv32_replacement as exp317  # noqa: E402


def digest(number: int) -> str:
    return f"{number:064x}"


def base_rows() -> list[dict[str, object]]:
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
                "source_manifest_id": f"EXP238:{index}",
                "source_root": "source-work",
                "source_file": f"sources/{index:03d}.wav",
                "source_sha256": digest(index + 1),
                "source_text": f"元文{index}",
                "target_root": "diverse-work",
                "target_file": f"control-outputs/{index:03d}.wav",
                "target_sha256": digest(index + 101),
                "target_id": f"target-{index:03d}",
                "target_text": f"元文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:03d}.wav",
                "real_target_sha256": digest(index + 201),
                "real_target_text": f"Amitaro文{index}",
                "learning_target": (
                    "source-aligned-control69-plus-real-target-adversarial"
                ),
            }
        )
    return rows


def manifests() -> tuple[dict[str, object], dict[str, object]]:
    old = {
        "kind": exp317.EXP238_KIND,
        "composition": exp317.BASE_COMPOSITION,
        "items": base_rows(),
    }
    new = [dict(row) for row in old["items"]]
    cv_positions = [
        index
        for index, row in enumerate(new)
        if row["domain"] == "commonvoice-unpaired"
    ][:32]
    for index, position in enumerate(cv_positions):
        row = dict(new[position])
        row.update(
            {
                "id": f"cv32-{index:02d}",
                "teacher_id": f"cv32-teacher-{index:02d}",
                "source_manifest_id": f"EXP306:cv32-{index:02d}",
                "source_file": f"new-sources/{index:02d}.wav",
                "source_sha256": digest(5000 + index),
                "source_client_id_sha256": digest(6000 + index),
                "target_file": f"control-outputs/cv32-{index:02d}.wav",
                "target_sha256": digest(7000 + index),
                "real_target_text": f"EXP306誤メタデータ{index}",
                "output_position": index,
            }
        )
        new.append(row)
    return old, {
        "kind": exp317.EXP306_KIND,
        "composition": exp317.EXP306_COMPOSITION,
        "items": new,
    }


def test_build_replaces_first_32_commonvoice_positions_only() -> None:
    old, breadth = manifests()
    result, positions = exp317.build_curriculum(old, breadth)

    assert result["kind"] == exp317.OUTPUT_KIND
    assert len(result["items"]) == 170
    assert positions == list(range(32))
    assert result["composition"] == exp317.BASE_COMPOSITION
    for index, row in enumerate(result["items"]):
        if index < 32:
            assert row["id"] == f"cv32-{index:02d}"
            assert row["target_id"] == old["items"][index]["target_id"]
            assert row["real_target_file"] == old["items"][index]["real_target_file"]
            assert (
                row["real_target_sha256"] == old["items"][index]["real_target_sha256"]
            )
            assert row["real_target_text"] == old["items"][index]["real_target_text"]
        else:
            assert row == old["items"][index]


def test_build_rejects_exp306_base_identity_drift() -> None:
    old, breadth = manifests()
    breadth["items"][50]["source_text"] = "壊れた"
    with pytest.raises(exp317.Exp317Error, match="first 170"):
        exp317.build_curriculum(old, breadth)


def test_build_rejects_wrong_position_specific_target() -> None:
    old, breadth = manifests()
    breadth["items"][170]["target_id"] = "wrong-target"
    with pytest.raises(exp317.Exp317Error, match="real target"):
        exp317.build_curriculum(old, breadth)


def test_build_rejects_duplicate_or_old_new_source_identity() -> None:
    old, breadth = manifests()
    breadth["items"][171]["source_sha256"] = breadth["items"][170]["source_sha256"]
    with pytest.raises(exp317.Exp317Error, match="source hashes"):
        exp317.build_curriculum(old, breadth)

    old, breadth = manifests()
    breadth["items"][172]["source_file"] = old["items"][0]["source_file"]
    with pytest.raises(exp317.Exp317Error, match="source files"):
        exp317.build_curriculum(old, breadth)


def test_validate_audio_rejects_hash_drift_and_unsafe_path(tmp_path: Path) -> None:
    old, breadth = manifests()
    result, _ = exp317.build_curriculum(old, breadth)
    source_root = tmp_path / "source-work"
    diverse_root = tmp_path / "diverse-work"
    source_root.mkdir()
    diverse_root.mkdir()
    for row in result["items"]:
        for root, key, digest_key in (
            (source_root, "source_file", "source_sha256"),
            (diverse_root, "target_file", "target_sha256"),
            (source_root, "real_target_file", "real_target_sha256"),
        ):
            path = root / str(row[key])
            path.parent.mkdir(parents=True, exist_ok=True)
            value = bytes.fromhex(str(row[digest_key]))[:16]
            path.write_bytes(value)
    with pytest.raises(exp317.Exp317Error, match="audio identity"):
        exp317.validate_audio(result["items"], source_root, diverse_root)
