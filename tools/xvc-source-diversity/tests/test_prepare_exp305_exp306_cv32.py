from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
import pytest

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import prepare_exp305_exp306_cv32 as cv32  # noqa: E402


def _digest(number: int) -> str:
    return f"{number:064x}"


def _wav(path: Path, *, frames: int = 38_400) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.full(frames, 1000, dtype="<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(values.tobytes())


def _base_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, domain in enumerate(
        ["commonvoice-unpaired"] * 48
        + ["jsut-unpaired"] * 85
        + ["jvs-unpaired"] * 3
        + ["hadou-unpaired"] * 34
    ):
        rows.append(
            {
                "id": f"base-{index:03d}",
                "teacher_id": f"teacher-{index:03d}",
                "domain": domain,
                "source_manifest_id": f"fixture:{index}",
                "source_root": "source-work",
                "source_file": f"sources/{index:03d}.wav",
                "source_sha256": _digest(index + 1),
                "source_text": f"ソース文{index}",
                "target_root": "diverse-work",
                "target_file": f"control-outputs/{index:03d}.wav",
                "target_sha256": _digest(index + 101),
                "target_id": f"target-{index:03d}",
                "target_text": f"ソース文{index}",
                "real_target_root": "source-work",
                "real_target_file": f"targets/{index:03d}.wav",
                "real_target_sha256": _digest(index + 201),
                "learning_target": (
                    "source-aligned-control69-plus-real-target-adversarial"
                ),
                "source_relative_distance": 0.0,
            }
        )
    return rows


def _base_manifest() -> dict[str, object]:
    return {
        "kind": cv32.EXP238_KIND,
        "composition": cv32.BASE_COMPOSITION,
        "items": _base_rows(),
    }


def _expanded() -> dict[str, object]:
    return {
        "kind": cv32.EXP055_KIND,
        "items": [
            {
                "id": f"cv-{index:02d}",
                "sha256": _digest(1000 + index),
                "filename": f"common_voice_ja_{index}.mp3",
                "text": f"未使用文{index}",
                "client_id_sha256": _digest(2000 + index),
            }
            for index in range(32)
        ]
        + [
            {
                "id": cv32.EXCLUDED_ID,
                "sha256": _digest(3000),
                "filename": "excluded.mp3",
                "text": "除外",
                "client_id_sha256": _digest(3001),
            }
        ],
    }


def _training() -> dict[str, object]:
    return {
        "kind": cv32.EXP186_KIND,
        "items": [
            {"id": f"train-{index:02d}", "client_id_sha256": _digest(4000 + index)}
            for index in range(48)
        ],
    }


def test_disjoint_validation_selects_exactly_32_and_checks_audio(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evaluation-sources"
    for index in range(32):
        _wav(root / f"cv-{index:02d}.wav")
    rows = cv32.validate_disjoint_commonvoice(
        _expanded(),
        evaluation_roots={
            "external7": {"items": [{"client_id_sha256": _digest(5000)}]},
            "fresh48": {"items": [{"client_id_sha256": _digest(5001)}]},
            "stress60": {"items": [{"client_id_sha256": _digest(5002)}]},
            "expanded144": {"items": [{"client_id_sha256": _digest(5003)}]},
        },
        training_windows=_training(),
        wav_root=root,
    )
    assert len(rows) == 32
    assert cv32.EXCLUDED_ID not in {row["id"] for row in rows}


def test_disjoint_validation_rejects_fixed_surface_client_overlap(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evaluation-sources"
    for index in range(32):
        _wav(root / f"cv-{index:02d}.wav")
    expanded = _expanded()
    expanded["items"][0]["client_id_sha256"] = _digest(5000)
    with pytest.raises(cv32.Cv32PreparationError, match="external7"):
        cv32.validate_disjoint_commonvoice(
            expanded,
            evaluation_roots={
                "external7": {"items": [{"client_id_sha256": _digest(5000)}]},
                "fresh48": {"items": []},
                "stress60": {"items": []},
                "expanded144": {"items": []},
            },
            training_windows=_training(),
            wav_root=root,
        )


def test_disjoint_validation_rejects_non_38400_wav(tmp_path: Path) -> None:
    root = tmp_path / "evaluation-sources"
    for index in range(32):
        _wav(root / f"cv-{index:02d}.wav", frames=38_399 if index == 0 else 38_400)
    with pytest.raises(cv32.Cv32PreparationError, match="format drifted"):
        cv32.validate_disjoint_commonvoice(
            _expanded(),
            evaluation_roots={
                name: {"items": []}
                for name in ("external7", "fresh48", "stress60", "expanded144")
            },
            training_windows=_training(),
            wav_root=root,
        )


def test_build_manifests_is_horizon_matched_and_target_aligned() -> None:
    expanded = [row for row in _expanded()["items"] if row["id"] != cv32.EXCLUDED_ID]
    repeat, pool, new_rows = cv32.build_manifests(
        _base_manifest(),
        expanded,
        source_wav_digests={
            str(row["id"]): _digest(9000 + index) for index, row in enumerate(expanded)
        },
    )
    assert len(repeat["items"]) == 202
    assert repeat["composition"] == cv32.EXPECTED_COMPOSITION
    assert len(pool["items"]) == 32
    assert [row["target_id"] for row in pool["items"]] == [
        row["target_id"] for row in repeat["items"][170:]
    ]
    assert [row["assignment_from"] for row in new_rows] == [
        row["repeat_of_id"] for row in repeat["items"][170:]
    ]


def test_build_manifests_rejects_wrong_new_source_digest() -> None:
    expanded = [row for row in _expanded()["items"] if row["id"] != cv32.EXCLUDED_ID]
    digests = {str(row["id"]): _digest(9000) for row in expanded[:-1]}
    with pytest.raises(cv32.Cv32PreparationError, match="source digest"):
        cv32.build_manifests(_base_manifest(), expanded, source_wav_digests=digests)
